from __future__ import annotations

import numpy as np
from datetime import date, datetime
from typing import Iterable, List, Tuple, Union, TYPE_CHECKING

from ..core import IdentityMixin, ReprMixin
from ..context import GlobalContext
from ..enums import AgeGroup, FamilyStatus, Gender
from .person import Person

if TYPE_CHECKING:
    from .place import Place


class Family(IdentityMixin, ReprMixin):
    __repr_attrs__ = ( 'n_members', )

    def __init__(
            self,
            members: Iterable[Person],
            spending_rate: float
        ) -> None:
        if len(members) == 0:
            raise ValueError()
        self.members: List[Person] = list(members)
        for member in self.members:
            member.family = self

        self.spending_rate = spending_rate

        super().__init_id__()

    @property
    def n_members(self) -> int:
        return len(self.members)

    @property
    def n_parents(self) -> int:
        return len([
            member for member in self.members
            if member.status == FamilyStatus.PARENT
        ])

    @property
    def n_children(self) -> int:
        return len([
            member for member in self.members
            if member.status == FamilyStatus.CHILD
        ])

    def youngest_age(self, current_date: Union[datetime, date]) -> float:
        return min([
            member.age(current_date)
            for member in self.members
        ])

    def oldest_age(self, current_date: Union[datetime, date]) -> float:
        return max([
            member.age(current_date)
            for member in self.members
        ])

    def total_purchasing_power(self, current_date: Union[datetime, date]) -> float:
        return np.sum([
            member.purchasing_power(current_date)
            for member in self.members
        ])

    def get(self, person_id: int) -> Person:
        for member in self.members:
            if member.id == person_id:
                return member

        raise IndexError()

    def add(self, person: Person) -> None:
        if person.family is not None:
            raise ValueError()

        self.members.append(person)
        person.family = self

    def remove(self, member: Person) -> None:
        self.members.remove(member)
        member.family = None

    def birth(
            self,
            place: Place,
            current_date: date,
            gender: Gender = None,
            anonymous: bool = True,
            seed: int = None,
            rng: np.random.RandomState = None
        ) -> None:
        if rng is None:
            rng = np.random.RandomState(seed)

        if gender is None:
            gender = Gender.MALE if rng.random() < 0.5 else Gender.FEMALE

        name = Person.generate_name(gender) if not anonymous else None
        baby = Person(
            name=name,
            gender=gender,
            status=FamilyStatus.CHILD,
            birth_date=current_date,
            birth_place=place
        )
        self.add(baby)

    def die(self, member: Person) -> None:
        self.remove(member)

    def split(self, members: List[Person]) -> Family:
        for member in members:
            if member not in self.members:
                raise IndexError()

        self.members.remove(member)
        new_family = self.__class__(
            members,
            self.spending_rate
        )
        return new_family

    @classmethod
    def random_max_n_members(
            cls,
            expected: float = None,
            size: int = 1,
            seed: int = None,
            rng: np.random.RandomState = None
        ) -> int:
        if rng is None:
            rng = np.random.RandomState(seed)

        shape = (expected if expected is not None else GlobalContext.POPULATION_FAMILY_SIZE) - 1
        max_n_members = np.round(rng.gamma(shape, 1.0, size=size) + 1)
        return max_n_members

    @classmethod
    def random_purchasing_power_range(
            cls,
            expected: float = None,
            seed: int = None,
            rng: np.random.RandomState = None
        ) -> Tuple[float, float]:
        if rng is None:
            rng = np.random.RandomState(seed)

        mean = expected if expected is not None else GlobalContext.POPULATION_PURCHASING_POWER
        max_purchasing_power = rng.lognormal(mean, 0.5)
        min_purchasing_power = rng.uniform(0.25, 0.50) * max_purchasing_power
        return min_purchasing_power, max_purchasing_power

    @classmethod
    def random_spending_rate(
            cls,
            expected: float = None,
            size: int = None,
            seed: int = None,
            rng: np.random.RandomState = None
        ) -> float:
        if rng is None:
            rng = np.random.RandomState(seed)

        expected = expected if expected is not None else GlobalContext.POPULATION_SPENDING_RATE
        spending_rate = np.clip(rng.normal(expected, expected * 0.25, size=size), 0.05, 0.80)
        return spending_rate

    @classmethod
    def from_marriage(
            cls,
            male: Person,
            female: Person
        ) -> Family:
        if male.gender != Gender.MALE:
            raise ValueError()
        if female.gender != Gender.FEMALE:
            raise ValueError()

        male_spending_rate = male.family.spending_rate
        male.family.remove(male)

        female_spending_rate = female.family.spending_rate
        female.family.remove(female)

        new_family = cls(
            members=[ male, female ],
            spending_rate=(male_spending_rate + female_spending_rate) / 2
        )
        male.status = FamilyStatus.PARENT
        female.status = FamilyStatus.PARENT
        return new_family

    @classmethod
    def generate(
            cls,
            current_date: date,
            place: Place,
            n_members: int = None,
            spending_rate: float = None,        
            n_members_expected: float = None,
            purchasing_power_expected: float = None,
            spending_rate_expected: float = None,
            seed: int = None,
            rng: np.random.RandomState = None
        ) -> Family:
        if rng is None:
            rng = np.random.RandomState(seed)

        if n_members is None:
            n_members = cls.random_max_n_members(n_members_expected, rng=rng)

        n_members = int(n_members)
        members: List[Person] = []
        # Single family
        if n_members == 1:
            gender = Gender.MALE if rng.random() < GlobalContext.POPULATION_FAMILY_SINGLE_AND_MALE_PROB else Gender.FEMALE
            age = 18.0 + rng.gamma(1.0, 5.0)

            single = Person.generate(
                gender=gender,
                age=age,
                status=FamilyStatus.SINGLE,
                current_date=current_date,
                birth_place=place,
                rng=rng
            )
            members.append(single)

        # Parent(s) with/without child(ren)
        elif n_members >= 2:
            # Family with married couple
            if rng.random() < GlobalContext.POPULATION_FAMILY_MARRIED_PROB:
                father_age_min = AgeGroup.TEENAGE.value + n_members * 2
                if rng.random() < GlobalContext.POPULATION_FAMILY_MARRIED_AND_ELDER_PROB:
                    father_age = AgeGroup.MIDDLE_ADULT.value + rng.gamma(3.0, 5.0)
                else:
                    father_age = father_age_min + rng.gamma(3.0, 5.0)

                father = Person.generate(
                    gender=Gender.MALE,
                    age=father_age,
                    status=FamilyStatus.PARENT,
                    current_date=current_date,
                    birth_place=place,
                    rng=rng
                )
                members.append(father)

                mother_age_min = father_age_min - 2.0
                mother_age = max(mother_age_min, rng.normal(father_age, 3.0))
                mother = Person.generate(
                    gender=Gender.FEMALE,
                    age=mother_age,
                    status=FamilyStatus.PARENT,
                    current_date=current_date,
                    birth_place=place,
                    rng=rng
                )
                members.append(mother)

                parent_age = min(father_age, mother_age)

            # Family with single parent
            else:
                parent_gender = Gender.MALE if rng.random() < GlobalContext.POPULATION_FAMILY_SINGLE_PARENT_AND_MALE_PROB else Gender.FEMALE
                parent_age = 18.0 + n_members + rng.gamma(4.0, 5.0)
                single_parent = Person.generate(
                    gender=parent_gender,
                    age=parent_age,
                    status=FamilyStatus.PARENT,
                    current_date=current_date,
                    birth_place=place,
                    rng=rng
                )
                members.append(single_parent)

            # Children
            n_children = n_members - len(members)
            for _ in range(n_children):
                child_gender = Gender.MALE if rng.random() < 0.5 else Gender.FEMALE
                child_age = np.clip(
                    parent_age - 18.0 - rng.gamma(1.0, 5.0),
                    0.0,
                    parent_age - 18.0
                )
                child = Person.generate(
                    gender=child_gender,
                    age=child_age,
                    status=FamilyStatus.CHILD,
                    current_date=current_date,
                    birth_place=place,
                    rng=rng
                )
                members.append(child)

        # Set purchasing power for each member
        for member in members:
            member.min_purchasing_power, member.max_purchasing_power = \
                cls.random_purchasing_power_range(purchasing_power_expected, rng=rng)

        if spending_rate_expected is None:
            spending_rate = cls.random_spending_rate(spending_rate_expected, rng=rng)

        return cls(members, spending_rate)

    @classmethod
    def bulk_generate(
            cls,
            n: int,
            current_date: date,
            place: Place,
            n_members_expected: float = None,
            purchasing_power_expected: float = None,
            spending_rate_expected: float = None,
            seed: int = None,
            rng: np.random.RandomState = None
        ) -> Family:
        if rng is None:
            rng = np.random.RandomState(seed)

        n_members = cls.random_max_n_members(n_members_expected, size=n, rng=rng)
        spending_rates = cls.random_spending_rate(spending_rate_expected, size=n, rng=rng)
        return [
            Family.generate(
                current_date,
                place,
                n_members[i],
                spending_rates[i],
                purchasing_power_expected=purchasing_power_expected,
                rng=rng
            )
            for i in range(n)
        ]
