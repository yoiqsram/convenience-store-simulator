from __future__ import annotations

import numpy as np
from datetime import date, timedelta
from typing import Dict, List, Generator, Iterable, Tuple

from .base import ReprMixin
from .constants import DAYS_IN_YEAR
from .context import GlobalContext
from .database import ModelMixin, SubdistrictModel
from .population import Family, FamilyStatus, Person, Gender


def match_adults(adults: Iterable[Person]) -> Iterable[Tuple[Person, Person]]:
    males: List[Person] = []
    females: List[Person] = []
    for adult in adults:
        if adult.gender == Gender.MALE:
            males.append(adult)
        else:
            females.append(adult)

    total_matches = min(len(males), len(females))
    return zip(males[:total_matches], females[:total_matches])


class Place(ModelMixin, ReprMixin):
    __model__ = SubdistrictModel
    __repr_attrs__ = ( 'id', 'name', 'current_population' )

    def __init__(
            self,
            id: str,
            name: str,
            initial_date: date,
            initial_population: int,
            fertility_rate: float,
            life_expectancy: float,
            marry_age: float,
            seed: int = None
        ) -> None:
        self.id = id
        self.name = name
        self.initial_population = initial_population
        self.fertility_rate = fertility_rate
        self.life_expectancy = life_expectancy
        self.marry_age = marry_age

        self._rng = np.random.RandomState(seed)
        self._prefix_id_counts: Dict[str, int] = dict()
        self.last_updated_date: date = initial_date - timedelta(days=1)

        self.families: List[Family] = Family.bulk_generate(
            int(self.initial_population / 3.0),
            initial_date,
            self,
            rng=self._rng
        )

        super().init_model(
            unique_identifiers={ 'code': self.id }
        )

    def current_population(self) -> int:
        return int(
            np.sum([
                family.n_members
                for family in self.families
            ])
        )

    def update(self, last_date: date) -> None:
        days_to_go = (last_date - self.last_updated_date).days
        if days_to_go < 1:
            return

        for _ in range(days_to_go):
            self.last_updated_date = last_date

            n_families = len(self.families)

            would_births = self._rng.random(n_families) < self.fertility_rate / DAYS_IN_YEAR
            new_born_males = self._rng.random(n_families) > 0.5

            life_expectancies = self._rng.normal(
                self.life_expectancy,
                self.life_expectancy * 0.1,
                size=n_families
            )
            would_dies = self._rng.random(n_families) < self.fertility_rate * 0.1

            marry_ages = self._rng.normal(
                self.marry_age,
                self.marry_age * 0.1,
                size=n_families
            )
            would_marries = self._rng.random(n_families) < 0.005

            unmarried_adults: List[Person] = []
            for family, would_birth, new_born_male, life_expectancy, would_die, marry_age, would_marry in zip(
                    self.families,
                    would_births,
                    new_born_males,
                    life_expectancies,
                    would_dies,
                    marry_ages,
                    would_marries
                ):
                # Born new babies
                if family.n_parents == 2 \
                        and family.youngest_age(last_date) > 1:
                    max_members = Family.random_max_n_members(rng=self._rng)
                    if family.n_members < max_members \
                            and would_birth:
                        family.birth(
                            place=self,
                            a_date=last_date,
                            gender=Gender.MALE if new_born_male else Gender.FEMALE,
                            rng=self._rng
                        )

                for person in family.members:
                    age = person.age(last_date)
                    if age > life_expectancy \
                            and would_die:
                        family.die(person)

                    # Gather unmarried adults
                    if person.status in (FamilyStatus.SINGLE, FamilyStatus.CHILD) \
                            and age > marry_age \
                            and would_marry:
                        unmarried_adults.append(person)

            # Marry the unmarried adults
            if len(unmarried_adults) > 0:
                for male, female in match_adults(( adult for adult in unmarried_adults )):
                    new_family = Family.from_marriage(male, female)
                    self.families.append(new_family)

            # Filter non-empty family
            self.families = [
                family
                for family in self.families
                if family.n_members > 0
            ]

    def register_birth(self, person: Person) -> None:
        prefix_id = (
            self.id[:6]
            + (str(person.birth_date.day) if person.gender == Gender.MALE else str(person.birth_date.day + 40))
            + person.birth_date.strftime('%m%y')
        )

        if prefix_id not in self._prefix_id_counts:
            self._prefix_id_counts[prefix_id] = 1
        else:
            self._prefix_id_counts[prefix_id] += 1

        person.id = prefix_id + str(self._prefix_id_counts[prefix_id]).rjust(4, '0')

    @classmethod
    def generate(
            cls,
            n: int,
            initial_date: date = None,
            initial_population: int = None,
            fertility_rate: float = None,
            life_expectancy: float = None,
            seed: int = None,
            rng: np.random.RandomState = None
        ) -> Generator[Place]:
        from .database import SubdistrictModel

        if rng is None:
            rng = np.random.RandomState(seed)

        initial_date = initial_date if initial_date is not None else GlobalContext.INITIAL_DATE

        initial_population = initial_population if initial_population is not None else GlobalContext.STORE_POPULATION
        initial_populations = np.clip(
            rng.normal(
                initial_population,
                initial_population * 0.25,
                size=n
            ),
            50.0, np.Inf
        )

        fertility_rate = fertility_rate if fertility_rate is not None else GlobalContext.POPULATION_FERTILITY_RATE
        fertility_rates = np.clip(
            rng.normal(
                fertility_rate,
                fertility_rate * 0.1,
                size=n
            ),
            0.0, np.Inf
        )

        life_expectancy = life_expectancy if life_expectancy is not None else GlobalContext.POPULATION_LIFE_EXPECTANCY
        life_expectancies = np.clip(
            rng.normal(
                life_expectancy,
                life_expectancy * 0.05,
                size=n
            ),
            50.0, np.Inf
        )

        marry_age = life_expectancy if life_expectancy is not None else GlobalContext.POPULATION_LIFE_EXPECTANCY
        marry_ages = np.clip(
            rng.normal(
                marry_age,
                marry_age * 0.05,
                size=n
            ),
            50.0, np.Inf
        )

        if seed is None:
            seeds = [ int(num) for num in rng.random(n) * 1_000_000 ]
        else:
            seeds = [ None ] * n

        total_subdistricts = SubdistrictModel.select().count()
        subdistrict_ids = rng.choice(total_subdistricts, n, replace=False)
        for subdistrict_id, initial_population_, fertility_rate_, life_expectancy_, marry_age_, seed in zip(
                subdistrict_ids,
                initial_populations,
                fertility_rates,
                life_expectancies,
                marry_ages,
                seeds
            ):
            subdistrict: SubdistrictModel = (
                SubdistrictModel.select()
                .limit(1)
                .offset(int(subdistrict_id))
                .execute()
                .iterate()
            )
            yield cls(
                id=subdistrict.code,
                name=subdistrict.name,
                initial_date=initial_date,
                initial_population=initial_population_,
                fertility_rate=fertility_rate_,
                life_expectancy=life_expectancy_,
                marry_age=marry_age_,
                seed=seed
            )
