from __future__ import annotations

import numpy as np
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Iterable, Tuple

from ..core import ReprMixin, RandomGeneratorMixin
from ..core.restore import RestorableMixin
from ..context import DAYS_IN_YEAR
from ..database import ModelMixin, SubdistrictModel
from .family import Family, FamilyStatus, Gender


class Place(
        RestorableMixin, ModelMixin, RandomGeneratorMixin, ReprMixin,
        model=SubdistrictModel,
        repr_attrs=('name',)
        ):
    def __init__(
            self,
            code: str,
            name: str,
            initial_date: date,
            initial_population: int,
            fertility_rate: float,
            life_expectancy: float,
            marry_age: float,
            seed: int = None,
            rng: np.random.RandomState = None
            ) -> None:
        self.code = code
        self.name = name
        self.initial_population = int(initial_population)
        self.fertility_rate = float(fertility_rate)
        self.life_expectancy = float(life_expectancy)
        self.marry_age = float(marry_age)

        self._prefix_id_counts: Dict[str, int] = {}
        self.last_updated_date: date = initial_date

        super().__init_rng__(seed, rng)
        super().__init_model__(
            unique_identifiers={'code': self.code}
        )

    @property
    def families(self) -> Iterable[Family]:
        base_dir = self.restore_file.parent
        for restore_file in base_dir.rglob('Customer/*/family.json'):
            yield Family.restore(base_dir / str(restore_file))

    @property
    def n_families(self) -> int:
        count = 0
        base_dir = self.restore_file.parent
        for restore_file in base_dir.rglob('Family_*/family.json'):
            count += 1
        return count

    def total_population(self) -> int:
        population = 0
        for family in self.families:
            population += int(family.n_members)
        return population

    def get_population_update(
            self,
            current_date: date
            ) -> Tuple[List[Family], List[Family]]:
        days_to_go = (current_date - self.last_updated_date).days
        if days_to_go < 1:
            return

        fertility_rate = self.fertility_rate / DAYS_IN_YEAR
        old_families = {family.id for family in self.families}
        new_families = old_families.copy()
        for _ in range(days_to_go):
            n_families = len(new_families)

            max_members = Family.random_max_n_members(
                size=n_families,
                rng=self._rng
            )

            _birth_probs = self._rng.random(n_families)
            would_births = _birth_probs < fertility_rate
            new_born_males = (_birth_probs / fertility_rate) < 0.5

            die_ages = self._rng.normal(
                self.life_expectancy,
                self.life_expectancy * 0.1,
                size=n_families
            )
            would_dies = self._rng.random(n_families) < fertility_rate

            marry_ages = self._rng.normal(
                self.marry_age,
                self.marry_age * 0.1,
                size=n_families
            )
            would_marries = (
                self._rng.random(n_families)
                < (fertility_rate * 2.0)
            )

            unmarried_adults: List[Family] = []
            for family, max_members_, would_birth, new_born_male, \
                    die_age, would_die, marry_age, would_marry in zip(
                        new_families,
                        max_members,
                        would_births,
                        new_born_males,
                        die_ages,
                        would_dies,
                        marry_ages,
                        would_marries
                    ):
                family: Family
                max_members_: int
                would_birth: bool
                new_born_male: bool
                die_age: float
                would_die: bool
                marry_age: float
                would_marry: bool

                # Born new babies
                if family.n_parents == 2 \
                        and family.youngest_age(current_date) > 1.0:
                    if family.n_members < max_members_ \
                            and would_birth:
                        if new_born_male:
                            gender = Gender.MALE
                        else:
                            gender = Gender.FEMALE

                        family.birth(
                            current_date=current_date,
                            gender=gender,
                            rng=self._rng
                        )

                for person in family.members:
                    age = person.age(current_date)
                    if age > die_age \
                            and would_die:
                        family.die(person)

                    # Gather unmarried adults
                    elif person.status in (
                                FamilyStatus.SINGLE, FamilyStatus.CHILD
                            ) \
                            and age > marry_age \
                            and would_marry:
                        unmarried_adults.append(person)

            # Marry the unmarried adults
            if len(unmarried_adults) > 0:
                for male, female in self.match_adults(
                        (adult for adult in unmarried_adults)
                        ):
                    new_family = Family.from_marriage(male, female)
                    new_families[new_family.id] = new_family

            new_families = {
                id_: family
                for id_, family in new_families.items()
                if family.n_members > 0
            }

        return old_families, new_families

    def register_birth(self, person: Family) -> None:
        prefix_id = (
            self.id[:6]
            + (str(person.birth_date.day)
                if person.gender == Gender.MALE
                else str(person.birth_date.day + 40))
            + person.birth_date.strftime('%m%y')
        )

        if prefix_id not in self._prefix_id_counts:
            self._prefix_id_counts[prefix_id] = 1
        else:
            self._prefix_id_counts[prefix_id] += 1

        person.id = (
            prefix_id
            + str(self._prefix_id_counts[prefix_id]).rjust(4, '0')
        )

    @property
    def restore_attrs(self) -> Dict[str, Any]:
        return {
            'code': self.code,
            'name': self.name,
            'initial_population': self.initial_population,
            'fertility_rate': self.fertility_rate,
            'life_expectancy': self.life_expectancy,
            'marry_age': self.marry_age,
            'prefix_id_counts': self._prefix_id_counts,
            'last_updated_date': self.last_updated_date
        }

    @classmethod
    def _restore(
            cls,
            attrs: Dict[str, Any],
            file: Path,
            tmp: bool,
            **kwargs
            ) -> Place:
        base_dir = file.parent

        families = [
            Family.restore(base_dir / str(family_restore_file))
            for family_restore_file in base_dir.rglob('Family_*/family.json')
        ]

        obj = cls(
            attrs['code'],
            attrs['name'],
            attrs['last_updated_date'],
            attrs['initial_population'],
            attrs['fertility_rate'],
            attrs['life_expectancy'],
            attrs['marry_age'],
            None,
            families
        )

        obj._prefix_id_counts = attrs['prefix_id_counts']
        return obj

    @staticmethod
    def match_adults(
            adults: Iterable[Family]
            ) -> Iterable[Tuple[Family, Family]]:
        males: List[Family] = []
        females: List[Family] = []
        for adult in adults:
            if adult.gender == Gender.MALE:
                males.append(adult)
            else:
                females.append(adult)

        total_matches = min(len(males), len(females))
        return zip(males[:total_matches], females[:total_matches])
