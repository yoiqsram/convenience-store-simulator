from __future__ import annotations

import numpy as np
import yaml
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Iterable, List, Tuple, Union, TYPE_CHECKING

from .constants import CONFIG_DIR, DAYS_IN_YEAR
from .utils import add_years

if TYPE_CHECKING:
    from .checkout import Checkout
    from .place import Place

DEFAULT_CONFIG_NAMES = None
DEFAULT_CONFIG_LOCATIONS = None


class Gender(Enum):
    MALE = 0
    FEMALE = 1


class AgeGroup(Enum):
    KID = 0
    '''below 12 years'''

    TEENAGE = 1
    '''12-18 years'''

    YOUNG_ADULT = 2
    '''19-44 years'''

    MIDDLE_ADULT = 3
    '''45-64 years'''

    OLDER_ADULT = 4
    '''65 years and older'''


class FamilyStatus(Enum):
    SINGLE = 0
    PARENT = 1
    CHILD = 2


class Person:
    __counter__ = 0

    def __init__(
            self,
            name: str,
            gender: Gender,
            status: FamilyStatus,
            birth_date: datetime,
            birth_place: Place = None
        ) -> None:
        self.__class__.__counter__ += 1
        self._id = self.__class__.__counter__

        self.name = name
        self.gender = gender
        self.status = status
        self.birth_date = birth_date
        self.birth_place = birth_place

        self.min_purchasing_power = 0.0
        self.max_purchasing_power = 0.0

        self.family: Union[Family, None] = None

    def __repr__(self) -> str:
        return f"Person(name={repr(self.name)}, gender={self.gender.name}, status={self.status.name}, birth_date={self.birth_date.isoformat()})"

    @property
    def id(self) -> int:
        return self._id

    def age(self, a_date: Union[datetime, date]) -> float:
        age = (a_date - self.birth_date).days / DAYS_IN_YEAR
        return age

    def current_purchasing_power(self, a_date: Union[datetime, date]) -> float:
        if self.max_purchasing_power == 0.0:
            return 0.0

        career_progress = (
            self.min_purchasing_power
            / self.max_purchasing_power
            / (1.0 + 10.0 * np.exp(-0.25 * (self.age(a_date) - 18.0) / 20.0))
        )
        return career_progress * self.max_purchasing_power

    @staticmethod
    def generate_name(
            gender: Gender,
            config_path: Path = None,
            seed: int = None
        ) -> str:
        rng = np.random.RandomState(seed)

        config = None
        if config_path is None:
            config_path = CONFIG_DIR / 'names.yaml'
            config = DEFAULT_CONFIG_NAMES

        if config is None:
            with open(config_path) as f:
                config = yaml.safe_load(f)

        first_name_choices = config[gender.name]['first']
        return rng.choice(first_name_choices)

    @classmethod
    def generate(
            self,
            gender: Gender,
            age: float,
            status: FamilyStatus,
            a_date: date,
            birth_place: Place = None,
            seed: int = None
        ) -> Person:
        return Person(
            name=Person.generate_name(gender, seed=seed),
            gender=gender,
            status=status,
            birth_date=add_years(a_date, -age),
            birth_place=birth_place
        )


class Family:
    __default_params__ = {
        'member_shape': 1.5,
        'member_scale': 1.0,
        'purchasing_power_mean': 3400,
        'purchasing_power_sigma': 0.5,
        'spending_rate_min': 0.05,
        'spending_rate_max': 0.25,
        'family_single_male_prob': 0.7,
        'family_married_prob': 0.75,
        'family_single_parent_and_male_prob': 0.4
    }
    def __init__(
            self,
            members: Iterable[Person],
            spending_rate: float
        ) -> None:
        super().__init__()

        if len(members) == 0:
            raise ValueError()
        self.members: List[Person] = list(members)
        for member in self.members:
            member.family = self

        self.spending_rate = spending_rate

        self._checkout: Checkout = None
        self._last_checkout_datetime: datetime = None
        self._next_checkout_datetime: datetime = None

    def __repr__(self) -> str:
        return f'Family(n_members={self.n_members})'

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

    def youngest_age(self, a_date: Union[datetime, date]) -> float:
        return min([
            member.age(a_date)
            for member in self.members
        ])

    def total_purchasing_power(self, a_date: Union[datetime, date]) -> float:
        return np.sum([
            member.current_purchasing_power(a_date)
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
            a_date: date,
            seed: int = None
        ) -> None:
        rng = np.random.RandomState(seed)

        baby_gender = Gender.MALE if rng.random() < 0.5 else Gender.FEMALE
        baby = Person(
            name=Person.generate_name(baby_gender),
            gender=baby_gender,
            status=FamilyStatus.CHILD,
            birth_date=a_date,
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
            shape: float = None,
            scale: float = None,
            seed: int = None
        ) -> int:
        if shape is None:
            shape = cls.__default_params__['member_shape']
        if scale is None:
            scale = cls.__default_params__['member_scale']

        rng = np.random.RandomState(seed)
        return int(np.round(rng.gamma(shape, scale))) + 1

    @classmethod
    def random_purchasing_power_range(
            cls,
            mean: float = None,
            sigma: float = None,
            seed: int = None
        ) -> Tuple[float, float]:
        if mean is None:
            mean = cls.__default_params__['purchasing_power_mean']
        if sigma is None:
            sigma = cls.__default_params__['purchasing_power_sigma']

        rng = np.random.RandomState(seed)
        max_purchasing_power = rng.lognormal(mean, sigma)
        return rng.uniform(0.25, 0.50) * max_purchasing_power, max_purchasing_power

    @classmethod
    def random_spending_rate(
            cls,
            min: float = None,
            max: float = None,
            seed: int = None
        ) -> float:
        if min is None:
            min = cls.__default_params__['spending_rate_min']
        if max is None:
            max = cls.__default_params__['spending_rate_max']

        rng = np.random.RandomState(seed)
        mean = (min + max) / 2
        spread = max - min
        spending_rate = np.clip(
            spread * rng.normal(mean, 2 * spread),
            min,
            max
        )
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
            a_date: date,
            member_shape: float = None,
            member_scale: float = None,
            purchasing_power_mean: float = None,
            purchasing_power_sigma: float = None,
            spending_rate_min: float = None,
            spending_rate_max: float = None,
            seed: int = None
        ) -> Family:
        rng = np.random.RandomState(seed)
        n_members = cls.random_max_n_members(
            member_shape,
            member_scale,
            seed=seed
        )

        members: List[Person] = []
        # Single family
        if n_members == 1:
            FAMILY_SINGLE_MALE_PROB = cls.__default_params__['family_single_male_prob']
            gender = Gender.MALE if rng.random() < FAMILY_SINGLE_MALE_PROB else Gender.FEMALE
            age = 18.0 + rng.gamma(1.0, 2.5)

            single = Person.generate(
                gender=gender,
                age=age,
                status=FamilyStatus.SINGLE,
                a_date=a_date,
                seed=rng.get_state()[1][0]
            )
            members.append(single)

        # Parent(s) with/without child(ren)
        elif n_members >= 2:
            # Family with married couple
            FAMILY_MARRIED_PROB = cls.__default_params__['family_married_prob']
            if rng.random() < FAMILY_MARRIED_PROB:
                father_age = 18.0 + n_members + rng.gamma(2.5, 5.0)
                father = Person.generate(
                    gender=Gender.MALE,
                    age=father_age,
                    status=FamilyStatus.PARENT,
                    a_date=a_date,
                    seed=rng.get_state()[1][0]
                )
                members.append(father)

                mother_age = max(16.0, rng.normal(father_age, 3.0))
                mother = Person.generate(
                    gender=Gender.FEMALE,
                    age=mother_age,
                    status=FamilyStatus.PARENT,
                    a_date=a_date,
                    seed=rng.get_state()[1][0]
                )
                members.append(mother)

                parent_age = min(father_age, mother_age)

            # Family with single parent
            else:
                FAMILY_SINGLE_PARENT_AND_MALE_PROB = cls.__default_params__['family_single_parent_and_male_prob']
                parent_gender = Gender.MALE if rng.random() < FAMILY_SINGLE_PARENT_AND_MALE_PROB else Gender.FEMALE
                parent_age = 18.0 + n_members + rng.gamma(2.5, 5.0)
                single_parent = Person.generate(
                    gender=parent_gender,
                    age=parent_age,
                    status=FamilyStatus.PARENT,
                    a_date=a_date,
                    seed=rng.get_state()[1][0]
                )
                members.append(single_parent)

            # Children
            n_children = n_members - len(members)
            for _ in range(n_children):
                child_gender = Gender.MALE if rng.random() < 0.5 else Gender.FEMALE
                child_age = np.clip(
                    parent_age - 18.0 - rng.gamma(1.0, 3.0),
                    0.0,
                    parent_age
                )
                child = Person.generate(
                    gender=child_gender,
                    age=child_age,
                    status=FamilyStatus.CHILD,
                    a_date=a_date,
                    seed=rng.get_state()[1][0]
                )
                members.append(child)

        # Set purchasing power for each member
        for member in members:
            member.min_purchasing_power, member.max_purchasing_power = \
                cls.random_purchasing_power_range(
                    purchasing_power_mean,
                    purchasing_power_sigma,
                    seed=seed
                )

        spending_rate = cls.random_spending_rate(
            spending_rate_min,
            spending_rate_max,
            seed=seed
        )
        return cls(members, spending_rate)
