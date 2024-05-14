from __future__ import annotations

import asyncio
import numpy as np
import yaml
from datetime import date
from pathlib import Path
from typing import Dict, List, Generator, Iterable, Tuple, Union

from .constants import CONFIG_DIR
from .population import Family, FamilyStatus, Person, Gender

DEFAULT_CONFIG_LOCATIONS = None


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


class Place:
    __default_params__ = {
        'initial_population_loc': 12_500,
        'initial_population_scale': 5_000,
        'fertility_rate_loc': 0.01,
        'fertility_rate_scale': 0.01,
        'life_expectancy_loc': 71.0,
        'life_expectancy_scale': 5.0,
        'marry_age_loc': 22.5,
        'marry_age_scale': 2.5
    }

    def __init__(
            self,
            id: str,
            name: str,
            initial_date: date,
            initial_population: int,
            fertility_rate: float,
            life_expectancy: float,
            seed: int = None
        ) -> None:
        self.id = id
        self.name = name
        self.initial_population = initial_population
        self.fertility_rate = fertility_rate
        self.life_expectancy = life_expectancy

        self._rng = np.random.RandomState(seed)
        self._last_update_date: date = initial_date

        self.families: List[Family] = self.generate_families(
            int(self.initial_population / 3.0),
            a_date=initial_date,
            seed=self._rng.get_state()[1][0]
        )

    def __repr__(self) -> str:
        return f"Place(name={repr(self.name)}, population={self.current_population()})"

    def last_update_date(self) -> Union[date, None]:
        return self._last_update_date

    def current_population(self) -> int:
        return int(
            np.sum([
                family.n_members
                for family in self.families
            ])
        )

    def update(self, a_date: date) -> None:
        for _ in range(max(0, (a_date - self._last_update_date).days)):
            self._last_update_date = a_date

            unmarried_adults: List[Person] = []
            for family in self.families:
                # Born new babies
                if family.n_parents == 2 \
                        and family.youngest_age(a_date) > 1:
                    seed = self._rng.get_state()[1][0]
                    max_members = Family.random_max_n_members(seed=seed)
                    if family.n_members < max_members \
                            and self._rng.random() < self.fertility_rate * 0.25:
                        family.birth(
                            place=self,
                            a_date=a_date,
                            seed=seed
                        )

                for person in family.members:
                    age = person.age(a_date)

                    # Remove died member
                    die_age = self._rng.normal(
                        self.life_expectancy,
                        self.life_expectancy * 0.1
                    )
                    if age > die_age \
                            and self._rng.random() < 0.1:
                        family.die(person)

                    # Gather unmarried adults
                    marry_age = self._rng.normal(
                        self.__default_params__['marry_age_loc'],
                        self.__default_params__['marry_age_scale']
                    )
                    if age > marry_age \
                            and person.status in (FamilyStatus.SINGLE, FamilyStatus.CHILD):
                        unmarried_adults.append(person)

            # Marry the unmarried adults
            if len(unmarried_adults) > 0:
                self._rng.shuffle(unmarried_adults)
                matched_adults = match_adults((
                    adult
                    for adult in unmarried_adults
                    if self._rng.random() < 0.005
                ))
                for male, female in matched_adults:
                    new_family = Family.from_marriage(male, female)
                    self.families.append(new_family)

            # Filter non-empty family
            self.families = list(filter(lambda family: family.n_members > 0, self.families))

    @staticmethod
    def generate_families(
            n: int,
            a_date: date,
            seed: int = None,
            **kwargs
        ) -> None:
        async def generate_family(new_seed: int = None):
            return Family.generate(
                a_date,
                seed=new_seed,
                **kwargs
            )

        async def generate_families():
            return await asyncio.gather(*[
                generate_family(
                    seed + i if seed is not None else seed
                )
                for i in range(n)
            ])

        return asyncio.run(generate_families())

    @classmethod
    def _generate_params(
            cls,
            initial_population_loc: int = None,
            initial_population_scale: int = None,
            fertility_rate_loc: float = None,
            fertility_rate_scale: float = None,
            life_expectancy_loc: float = None,
            life_expectancy_scale: float = None,
            seed: int = None
        ) -> Dict[str, Union[int, float]]:
        rng = np.random.RandomState(seed)

        if initial_population_loc is None:
            initial_population_loc = cls.__default_params__['initial_population_loc']
        if initial_population_scale is None:
            initial_population_scale = cls.__default_params__['initial_population_scale']
        initial_population = int(np.max([
            0.0,
            rng.normal(
                initial_population_loc,
                initial_population_scale
            )
        ]))

        if fertility_rate_loc is None:
            fertility_rate_loc = cls.__default_params__['fertility_rate_loc']
        if fertility_rate_scale is None:
            fertility_rate_scale = cls.__default_params__['fertility_rate_scale']
        fertility_rate = rng.normal(
            fertility_rate_loc,
            fertility_rate_scale
        )

        if life_expectancy_loc is None:
            life_expectancy_loc = cls.__default_params__['life_expectancy_loc']
        if life_expectancy_scale is None:
            life_expectancy_scale = cls.__default_params__['life_expectancy_scale']
        life_expectancy = rng.normal(
            life_expectancy_loc,
            life_expectancy_scale
        )

        return {
            'initial_population': initial_population,
            'fertility_rate': fertility_rate,
            'life_expectancy': life_expectancy
        }

    @classmethod
    def generate(
            cls,
            n: int,
            initial_date: date,
            initial_population_loc: int = None,
            initial_population_scale: int = None,
            fertility_rate_loc: float = None,
            fertility_rate_scale: float = None,
            life_expectancy_loc: float = None,
            life_expectancy_scale: float = None,
            config_path: Path = None,
            seed: int = None
        ) -> Generator[Place]:
        rng = np.random.RandomState(seed)

        config = None
        if config_path is None:
            config_path = CONFIG_DIR / 'locations.yaml'
            config = DEFAULT_CONFIG_LOCATIONS

        if config is None:
            with open(CONFIG_DIR / 'locations.yaml') as f:
                locations = yaml.safe_load(f)

        districts = [
            district
            for country in locations['countries']
            for province in country['provinces']
            for city in province['cities']
            for district in city['districts']
        ]
        for i, district in enumerate(rng.choice(districts, n, replace=False)):
            yield cls(
                    id=district['id'],
                    name=district['name'],
                    initial_date=initial_date,
                    **cls._generate_params(
                        initial_population_loc=initial_population_loc,
                        initial_population_scale=initial_population_scale,
                        fertility_rate_loc=fertility_rate_loc,
                        fertility_rate_scale=fertility_rate_scale,
                        life_expectancy_loc=life_expectancy_loc,
                        life_expectancy_scale=life_expectancy_scale,
                        seed=seed + i if seed is not None else seed
                    )
            )
