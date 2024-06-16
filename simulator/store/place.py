from __future__ import annotations

import numpy as np
import orjson
from core import ReprMixin, RandomGeneratorMixin
from core.utils import cast
from datetime import datetime
from pathlib import Path

from ..context import GlobalContext, DAYS_IN_YEAR, SECONDS_IN_DAY
from ..database import ModelMixin, SubdistrictModel
from ..enums import AgeGroup

MAX_MEMBERS = 10


class Place(
        ModelMixin, RandomGeneratorMixin, ReprMixin,
        model=SubdistrictModel,
        repr_attrs=('code', 'name')
        ):
    def __init__(
            self,
            code: int,
            name: str,
            initial_datetime: datetime,
            initial_population: int,
            spending_rate: float,
            fertility_rate: float,
            life_expectancy: float,
            marry_age: float,
            family_config: tuple[np.ndarray, np.ndarray] = None,
            seed: int = None,
            rng: np.random.RandomState = None
            ) -> None:
        self.code = code
        self.name = name
        self.spending_rate = float(spending_rate)
        self.fertility_rate = float(fertility_rate)
        self.life_expectancy = float(life_expectancy)
        self.marry_age = float(marry_age)

        initial_timestamp = cast(initial_datetime, int)
        self.last_updated_timestamp: int = int(
            initial_timestamp + SECONDS_IN_DAY
            - initial_timestamp % SECONDS_IN_DAY
        )

        self.__init_rng__(seed, rng)

        if family_config is None:
            self._family_demographies, self._family_params = \
                self.generate_population(initial_population)
        else:
            self._family_demographies, self._family_params = \
                family_config

        super().__init_rng__(seed, rng)
        super().__init_model__(
            unique_identifiers={'code': self.code}
        )

    @property
    def n_families(self) -> int:
        return self._family_demographies.shape[0]

    @property
    def family_sizes(self) -> np.ndarray:
        return np.sum(self._family_demographies[:, :, 1] > 0, axis=1)

    def total_population(self) -> int:
        return int(np.sum(self.family_sizes))

    def generate_population(
            self,
            population: int
            ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        n_families = int(
            population
            / GlobalContext.POPULATION_FAMILY_SIZE
        )

        family_demographies = np.zeros(
            (n_families, MAX_MEMBERS, 2),
            dtype=np.uint16
        )
        family_params = self.generate_family_params(n_families)

        # Generate family demographies
        family_members = \
            np.round(
                self._rng.gamma(
                GlobalContext.POPULATION_FAMILY_SIZE - 1,
                1,
                n_families
            )).astype(np.uint8) + 1

        single_mask = family_members == 1
        n_singles = np.sum(single_mask)
        family_demographies[single_mask] = \
            self.generate_single_demographies(n_singles)

        family_mask = ~single_mask
        family_demographies[family_mask] = \
            self.generate_family_demographies(
                n_families - n_singles,
                family_params[family_mask],
                family_members[family_mask]
            )

        # Update fertility rate for family have both father & mother
        n_parents = np.sum(family_demographies[:, :2, 1] > 0, axis=1)
        mother_ages = family_demographies[:, 1, 1]
        n_children = np.sum(family_demographies[:, 2:, 1], axis=1)
        fertile_mask = (
            family_mask
            & (n_parents == 2)
            & (mother_ages < 40 * DAYS_IN_YEAR)
        )
        family_params[fertile_mask, 1] *= \
            n_children[fertile_mask] / (n_children[fertile_mask] + 1)
        family_params[~fertile_mask, 1] = 0

        return family_demographies, family_params

    def generate_family_params(self, n: int) -> np.ndarray:
        family_params = np.zeros((n, 4), dtype=np.float16)

        # Spending rate
        family_params[:, 0] = self._rng.normal(
            self.spending_rate,
            self.spending_rate * 0.1,
            n
        )

        # Fertility rate
        family_params[:, 1] = np.abs(
            self._rng.normal(
                self.fertility_rate,
                0.025,
                n
            )
        )

        # Marry age
        family_params[:, 2] = self._rng.normal(
            self.marry_age,
            self.marry_age * 0.1,
            n
        )

        # Life expectancy
        family_params[:, 3] = self._rng.normal(
            self.life_expectancy,
            self.life_expectancy * 0.05,
            n
        )

        return family_params

    def generate_single_demographies(self, n: int) -> np.ndarray:
        single_demographies = np.zeros((n, MAX_MEMBERS, 2), dtype=np.uint16)

        # Randomize genders
        single_demographies[:, 0, 0] = (
            self._rng.random(n)
            > GlobalContext.POPULATION_FAMILY_SINGLE_AND_MALE_PROB
        )

        # Randomize ages
        single_demographies[:, 0, 1] = (
            (AgeGroup.TEENAGE.value + self._rng.gamma(1., 5., n))
            * DAYS_IN_YEAR
        )

        return single_demographies

    def generate_family_demographies(
            self,
            n: int,
            params: np.ndarray,
            members: np.ndarray
            ) -> np.ndarray:
        family_demographies = np.zeros((n, MAX_MEMBERS, 2), dtype=np.uint16)
        n_parents = (
            1
            + (
                self._rng.random(n)
                < GlobalContext.POPULATION_FAMILY_MARRIED_PROB
            ).astype(np.int8)
        )

        # ELDER
        elder_mask = (
            self._rng.random(n)
            < GlobalContext.POPULATION_FAMILY_PARENT_ELDER_PROB
        )
        n_elder = np.sum(elder_mask)
        family_demographies[elder_mask, 0, 1] = (
            (
                self._rng.normal(
                    AgeGroup.MIDDLE_ADULT.value,
                    5,
                    n_elder
                ) * DAYS_IN_YEAR
            ).astype(np.uint16)
        )

        # Father/Main parent ages
        marry_ages = params[:, 2]
        family_demographies[:, 0, 1] = (
            (marry_ages + members * 3)
            * DAYS_IN_YEAR
        )

        # MARRIED
        complete_mask = n_parents == 2
        n_completes = np.sum(complete_mask)
        # Mother genders & ages
        family_demographies[complete_mask, 1, 0] = 1
        father_ages = family_demographies[complete_mask, 0, 1]
        family_demographies[complete_mask, 1, 1] = (
            father_ages
            + self._rng.normal(-2, 3, n_completes) * DAYS_IN_YEAR
        )

        # SINGLE PARENT
        # Randomize genders
        family_demographies[~complete_mask, 0, 0] = (
            self._rng.random(n - n_completes)
            > GlobalContext.POPULATION_FAMILY_SINGLE_PARENT_AND_MALE_PROB
        )

        # Adjust ages
        young_single_parents = ~complete_mask & ~elder_mask
        n_young_single_parents = np.sum(young_single_parents)
        family_demographies[young_single_parents, 0, 1] += (
            (
                self._rng.normal(10, 5, n_young_single_parents)
                * DAYS_IN_YEAR
            ).astype(np.uint16)
        )

        # CHILDREN
        n_children = members - n_parents
        max_children = family_demographies.shape[1] - 2
        for i in range(max_children):
            mask = (i + 1) <= n_children
            n_ = np.sum(mask)

            # Randomize genders
            family_demographies[mask, i + 2, 0] = \
                self._rng.randint(2, size=n_)

            # Randomize ages
            father_ages = family_demographies[mask, 0, 1]
            marry_ages = (
                (params[mask, 2] * DAYS_IN_YEAR)
                .astype(np.uint16)
            )
            max_children_age = father_ages - marry_ages + 1
            family_demographies[mask, i + 2, 1] = \
                self._rng.randint(1, max_children_age, size=n_)

        return family_demographies

    def update_population(
            self,
            current_timestamp: int,
            clean_empty: bool = True
            ) -> None:
        current_timestamp += \
            SECONDS_IN_DAY - current_timestamp % SECONDS_IN_DAY
        days = int(
            (current_timestamp - self.last_updated_timestamp)
            // SECONDS_IN_DAY
        )
        if days <= 0:
            return

        family_demographies = self._family_demographies.copy()
        family_params = self._family_params.copy()
        for _ in range(days):
            family_ages = family_demographies[:, :, 1]
            family_demographies[:, :, 1][family_ages > 0] += 1

            family_demographies = \
                self.update_population_by_death(
                    family_demographies,
                    family_params
                )

            family_demographies, family_params = \
                self.update_population_by_birth(
                    family_demographies,
                    family_params
                )

            family_demographies, family_params = \
                self.update_population_by_marriage(
                    family_demographies,
                    family_params
                )

            # Set family with neither father/mother,
            # or mother older than YOUNG ADULT to be infertile
            family_ages = family_demographies[:, :, 1]
            n_parents = np.sum(family_ages[:, :2] > 0, axis=1)
            infertile_mask = (
                (n_parents < 2)
                | (
                    family_ages[:, 1]
                    > AgeGroup.YOUNG_ADULT.value * DAYS_IN_YEAR
                )
            )
            family_params[infertile_mask][:, 1] = 0

        self._family_demographies = family_demographies
        self._family_params = family_params
        self.last_updated_timestamp = current_timestamp

        if clean_empty:
            self.clean_empty_families()

    def update_population_by_death(
            self,
            demographies: np.ndarray,
            params: np.ndarray
        ) -> np.ndarray:
        demographies = demographies.copy()
        params = params.copy()

        ages = demographies[:, :, 1]
        life_expectancies = params[:, 3:4] * DAYS_IN_YEAR
        death_mask = ages > life_expectancies
        death_mask &= (
            self._rng.random(ages.shape)
            < (self.fertility_rate * 0.1)
        )
        death_mask |= (
            self._rng.random(ages.shape)
            < (self.fertility_rate * 0.0001)
        )
        demographies[death_mask, 0] = 0
        demographies[death_mask, 1] = 0
        return demographies

    def update_population_by_birth(
            self,
            demographies: np.ndarray,
            params: np.ndarray
            ) -> tuple[np.ndarray, np.ndarray]:
        demographies = demographies.copy()
        params = params.copy()
        members = np.sum(demographies[:, :, 1] > 0, axis=1)

        fertile_mask = params[:, 1] > 0
        birth_mask = (
            fertile_mask
            & (members < demographies.shape[1])
        )
        birth_mask[birth_mask] = (
            self._rng.random(np.sum(birth_mask))
            < params[birth_mask, 1] * 0.005
        )
        n_births = np.sum(birth_mask)
        if n_births == 0:
            return demographies, params

        birth_index = np.argwhere(birth_mask).reshape(-1)
        genders = self._rng.randint(2, size=n_births)
        for i, gender in zip(birth_index, genders):
            members_ = members[i]
            demographies[i, members_, 0] = gender
            demographies[i, members_, 1] = 1
            params[i, 1] *= members_ / (members_ + 1)

        return demographies, params

    def update_population_by_marriage(
            self,
            demographies: np.ndarray,
            params: np.ndarray
            ) -> tuple[np.ndarray, np.ndarray]:
        demographies = demographies.copy()
        params = params.copy()

        n_parents = np.sum(demographies[:, :2, 1] > 0, axis=1)
        marriable_mask = n_parents < 2
        marry_ages = params[marriable_mask, 2:3] * DAYS_IN_YEAR

        unmarried_index = np.argwhere(
            demographies[marriable_mask, :, 1] > marry_ages
        )
        unmarried_male_index = []
        unmarried_female_index = []
        for i, j in unmarried_index:
            if demographies[i, j, 0] == 0:
                unmarried_male_index.append((i, j))
            else:
                unmarried_female_index.append((i, j))

        matches = min(
            len(unmarried_male_index),
            len(unmarried_female_index)
        )
        if matches == 0:
            return demographies, params

        marry_mask = (
            self._rng.random(matches)
            < self.fertility_rate * 0.005
        )
        n_marries = np.sum(marry_mask)
        if n_marries == 0:
            return demographies, params

        unmarried_index = np.array([
            [male_index, female_index]
            for male_index, female_index in zip(
                    unmarried_male_index[:matches],
                    unmarried_female_index[:matches]
                )
        ])
        unmarried_index = unmarried_index[marry_mask]
        fertility_rates = np.abs(
            self._rng.normal(
                self.fertility_rate,
                0.025,
                n_marries
            )
        )

        new_demographies = []
        new_params = []
        for (male_index, female_index), fertility_rate in zip(
                    unmarried_index,
                    fertility_rates
                ):
            new_demographies_ = (
                [
                    [0, demographies[male_index[0], male_index[1], 1]],
                    [1, demographies[female_index[0], female_index[1], 1]]
                ]
                + [[0, 0]] * (demographies.shape[1] - 2)
            )

            new_params_ =np.mean(
                params[[male_index[0], female_index[0]]],
                axis=0
            )
            new_params_[1] = fertility_rate

            demographies[male_index[0], male_index[1], :] = 0
            demographies[female_index[0], female_index[1], :] = 0

            new_demographies.append(new_demographies_)
            new_params.append(new_params_.tolist())

        new_demographies = np.array(new_demographies, dtype=np.uint16)
        demographies = np.concatenate(
            (demographies, new_demographies),
            axis=0,
            dtype=np.uint16
        )
        new_params = np.array(new_params, dtype=np.float16)
        params = np.concatenate(
            (params, new_params),
            axis=0,
            dtype=np.float16
        )

        return demographies, params

    def clean_empty_families(self) -> None:
        non_empty_mask = self.family_sizes > 0
        self._family_demographies = self._family_demographies[non_empty_mask]
        self._family_params = self._family_params[non_empty_mask]

    def save(self, save_dir: Path) -> None:
        with open(save_dir / 'place.json', 'wb') as f:
            f.write(
                orjson.dumps({
                    'code': self.code,
                    'name': self.name,
                    'spending_rate': self.spending_rate,
                    'fertility_rate': self.fertility_rate,
                    'life_expectancy': self.life_expectancy,
                    'marry_age': self.marry_age,
                    'last_updated_date': self.last_updated_timestamp,
                    'total_population': self.total_population(),
                    'rng_state': self.dump_rng_state()
                })
            )

        demographies = np.memmap(
            save_dir / 'place_demographies.dat',
            mode='w+',
            shape=self._family_demographies.shape,
            dtype=np.uint16
        )
        demographies[:] = self._family_demographies[:]
        demographies.flush()

        params = np.memmap(
            save_dir / 'place_params.dat',
            mode='w+',
            shape=self._family_params.shape,
            dtype=np.float16
        )
        params[:] = self._family_params[:]
        params.flush()

    @classmethod
    def load(
            self,
            load_dir: Path,
            max_members: int = None
            ) -> Place:
        max_members = MAX_MEMBERS if max_members is None else max_members

        demographies = (
            np.memmap(
                load_dir / 'place_demographies.dat',
                mode='r',
                dtype=np.uint16
            )
            .reshape((-1, max_members, 2))
        )
        params = (
            np.memmap(
                load_dir / 'place_params.dat',
                mode='r',
                dtype=np.float16
            )
            .reshape((-1, 4))
        )

        with open(load_dir / 'place.json', 'rb') as f:
            meta = orjson.loads(f.read())
        obj = Place(
            meta['code'],
            meta['name'],
            meta['last_updated_date'],
            meta['total_population'],
            meta['spending_rate'],
            meta['fertility_rate'],
            meta['life_expectancy'],
            meta['marry_age'],
            family_config=(demographies, params)
        )
        obj.load_rng_state(meta['rng_state'])

        return obj
