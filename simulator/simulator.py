from __future__ import annotations

import numpy as np
import orjson
from datetime import date, datetime
from pathlib import Path
from peewee import JOIN
from time import time
from typing import Generator

from core import DateTimeEnvironment
from core.utils import cast, load_memmap_to_array, dump_memmap_to_array

from .context import GlobalContext, DAYS_IN_YEAR, SECONDS_IN_DAY
from .database import SubdistrictModel, StoreModel
from .logging import simulator_logger, simulator_log_format
from .store.place import Place
from .store import Store


class Simulator(
        DateTimeEnvironment,
        repr_attrs=('n_stores', 'current_datetime')
        ):
    def __init__(
            self,
            initial_datetime: datetime = None,
            max_datetime: datetime = None,
            interval: float = 1.,
            speed: float = 1.,
            initial_stores: int = None,
            initial_store_population: int = None,
            store_growth_rate: float = None,
            seed: int = None,
            rng: np.random.RandomState = None
            ) -> None:
        if initial_datetime is None:
            initial_datetime = datetime(
                GlobalContext.INITIAL_DATE.year,
                GlobalContext.INITIAL_DATE.month,
                GlobalContext.INITIAL_DATE.day
            )

        if interval is None:
            interval = GlobalContext.SIMULATOR_INTERVAL

        if speed is None:
            speed = GlobalContext.SIMULATOR_SPEED

        super().__init__(
            initial_datetime=initial_datetime,
            max_datetime=max_datetime,
            interval=interval,
            speed=speed,
            skip_step=True,
            agents=None,
            seed=seed,
            rng=rng
        )

        if store_growth_rate is None:
            store_growth_rate = GlobalContext.STORE_GROWTH_RATE
        self.store_growth_rate = store_growth_rate

        # Generate stores
        if initial_stores is None:
            initial_stores = GlobalContext.INITIAL_STORES
        if initial_stores > 0:
            _time = time()
            if initial_store_population is None:
                initial_store_population = \
                    GlobalContext.STORE_MARKET_POPULATION

            stores = self.init_stores(
                initial_stores,
                self.initial_step,
                market_population=initial_store_population,
                build_range_days=GlobalContext.INITIAL_STORES_RANGE_DAYS
            )
            self.add_agents(stores)
            simulator_logger.info(
                f'Simulator has been created with '
                f'{self.n_stores} initial stores. '
                f'{time() - _time:.1f}s.'
            )

    @property
    def n_stores(self) -> int:
        return super().n_agents

    def stores(self) -> Generator[Store]:
        return super().agents()

    def total_market_population(self) -> int:
        return sum([
            store.total_market_population()
            for store in self.stores()
        ])

    def step(self, *args, **kwargs) -> list[np.uint32, np.uint32, bool]:
        previous_datetime = self.current_datetime
        current_step, next_step, done = super().step(*args, **kwargs)
        current_datetime = cast(current_step, datetime)

        n_stores = self.n_stores

        # @ 1 hour - Log today orders hourly
        if previous_datetime.hour != current_datetime.hour:
            adjusted_real_current_timestamp, behind_seconds = \
                self.calculate_behind_seconds(current_step)
            dt_str = (
                datetime.fromtimestamp(adjusted_real_current_timestamp)
                .isoformat(sep=' ', timespec='seconds')
            )
            # Log synchronization between simulation
            # and the real/projected datetime
            if kwargs.get('sync', False) \
                    and behind_seconds >= self.interval:
                simulator_logger.debug(simulator_log_format(
                    'Simulation is behind the',
                    'real datetime' if self.speed == 1.0
                    else f"projected datetime ({dt_str})",
                    f'by {behind_seconds:.1f}s.',
                    dt=current_step
                ))

        if previous_datetime.day != current_datetime.day:
            # Grow new stores
            n_new_stores = np.sum(
                self._rng.random(n_stores)
                < self.store_growth_rate / DAYS_IN_YEAR
            )
            stores = self.init_stores(n_new_stores, current_step)
            if len(stores) > 0:
                self.add_agents(stores)
                simulator_logger.info(
                    f"Add {n_new_stores} new store on "
                    f"{date.fromtimestamp(int(current_step))}. "
                    f"Total stores: {self.n_stores}."
                )

        return current_step, next_step, done

    def init_stores(
            self,
            n: int,
            current_step: float,
            market_population: int = None,
            market_spending_rate: float = None,
            market_fertility_rate: float = None,
            market_life_expectancy: float = None,
            market_marry_age: float = None,
            build_range_days: int = 0,
            ) -> None:
        n = int(n)
        available_subdistricts_query = (
            SubdistrictModel.select()
            .join(StoreModel, JOIN.LEFT_OUTER)
            .where(StoreModel.id.is_null())
        )
        random_offset = \
            int(self._rng.randint(available_subdistricts_query.count() - n))
        new_subdistricts: list[SubdistrictModel] = list(
            available_subdistricts_query
            .limit(n)
            .offset(random_offset)
        )
        market_populations, spending_rates, \
            fertility_rates, life_expectancies, marry_ages = \
            self.calculate_market_params(
                n,
                market_population,
                market_spending_rate,
                market_fertility_rate,
                market_life_expectancy,
                market_marry_age
            )
        delay_days = self._rng.randint(0, build_range_days + 1, n)

        initial_step = current_step - current_step % SECONDS_IN_DAY
        stores = []
        for (
                subdistrict, population, spending_rate,
                fertility_rate, life_expectancy,
                marry_age, delay_days,
                random_seed
                ) in zip(
                    new_subdistricts,
                    market_populations,
                    spending_rates,
                    fertility_rates,
                    life_expectancies,
                    marry_ages,
                    delay_days,
                    self.random_seed(n)
                ):
            place = Place(
                code=subdistrict.code,
                name=subdistrict.name,
                initial_datetime=initial_step + delay_days * SECONDS_IN_DAY,
                initial_population=population,
                spending_rate=spending_rate,
                fertility_rate=fertility_rate,
                life_expectancy=life_expectancy,
                marry_age=marry_age,
                rng=np.random.RandomState(random_seed)
            )
            store = Store(
                place,
                current_step - current_step % SECONDS_IN_DAY,
                interval=self.interval,
                seed=random_seed
            )
            stores.append(store)

        return stores

    def calculate_market_params(
            self,
            n: int,
            population: int = None,
            spending_rate: float = None,
            fertility_rate: float = None,
            life_expectancy: float = None,
            marry_age: float = None,
            ):
        if population is None:
            population = GlobalContext.STORE_MARKET_POPULATION
        populations = np.clip(
            self._rng.normal(
                population,
                population * 0.25,
                size=n
            ),
            50.0, np.Inf
        )

        if spending_rate is None:
            spending_rate = GlobalContext.POPULATION_SPENDING_RATE
        spending_rates = np.clip(
            self._rng.normal(
                spending_rate,
                spending_rate * 0.1,
                size=n
            ),
            0.1,
            0.8
        )

        if fertility_rate is None:
            fertility_rate = GlobalContext.POPULATION_FERTILITY_RATE
        fertility_rates = np.clip(
            self._rng.normal(
                fertility_rate,
                fertility_rate * 0.1,
                size=n
            ),
            0.0, np.Inf
        )

        if life_expectancy is None:
            life_expectancy = GlobalContext.POPULATION_LIFE_EXPECTANCY
        life_expectancies = np.clip(
            self._rng.normal(
                life_expectancy,
                life_expectancy * 0.05,
                size=n
            ),
            50.0, np.Inf
        )

        if marry_age is None:
            marry_age = GlobalContext.POPULATION_MARRY_AGE
        marry_ages = np.clip(
            self._rng.normal(
                marry_age,
                marry_age * 0.05,
                size=n
            ),
            18.0, np.Inf
        )

        return (
            populations,
            spending_rates,
            fertility_rates,
            life_expectancies,
            marry_ages
        )

    def calculate_behind_seconds(
            self,
            current_step: float
            ) -> tuple[float, float]:
        real_current_timestamp = time()
        adjusted_real_current_timestamp = (
            self._real_initial_timestamp
            + self.speed * (
                real_current_timestamp - self._real_initial_timestamp
            )
        )
        behind_seconds = \
            adjusted_real_current_timestamp - current_step
        return adjusted_real_current_timestamp, behind_seconds

    def save(self, save_dir: Path) -> None:
        save_dir = cast(save_dir, Path)
        save_dir.mkdir(parents=True, exist_ok=True)

        for store in self.stores():
            store.save(save_dir=save_dir / f'Store_{store.record_id:06d}')

        with open(save_dir / 'simulator.json', 'wb') as f:
            f.write(
                orjson.dumps({
                    'store_growth_rate': self.store_growth_rate,
                    'real_initial_timestamp': self._real_initial_timestamp,
                    'rng_state': self.dump_rng_state()
                })
            )

        dump_memmap_to_array(
            self._steps,
            save_dir / 'simulator_steps.dat',
            dtype=np.uint32
        )

    @classmethod
    def load(self, load_dir: Path, store_ids: list[int] = None) -> Place:
        load_dir = cast(load_dir, Path)
        with open(load_dir / 'simulator.json', 'rb') as f:
            meta = orjson.loads(f.read())

        simulator_steps = load_memmap_to_array(
            load_dir / 'simulator_steps.dat',
            dtype=np.uint32
        )

        obj = Simulator(
            initial_stores=0,
            store_growth_rate=meta['store_growth_rate']
        )
        obj._real_initial_timestamp = meta['real_initial_timestamp']
        obj.load_rng_state(meta['rng_state'])

        StoreModel.delete() \
            .where(
                StoreModel.created_datetime
                > cast(simulator_steps[3], datetime)
            ) \
            .execute()

        stores = []
        for store_record in (
                    StoreModel.select()
                    .order_by(StoreModel.id)
                ):
            if store_ids is not None \
                    and store_record.id not in store_ids:
                continue

            store = Store.load(load_dir / f'Store_{store_record.id:06d}')
            stores.append(store)

        obj._steps = simulator_steps[:]
        obj.add_agents(stores)
        return obj
