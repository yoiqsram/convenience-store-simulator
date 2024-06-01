from __future__ import annotations

import numpy as np
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

from .core import RandomDatetimeEnvironment
from .core.utils import cast
from .context import GlobalContext  # , DAYS_IN_YEAR
from .database import SubdistrictModel
from .logging import simulator_logger, store_logger, simulator_log_format
from .population import Family, Place
from .store import Customer, Store


class Simulator(
        RandomDatetimeEnvironment,
        repr_attrs=('n_stores', 'current_datetime')
        ):
    def __init__(
            self,
            initial_datetime: datetime = None,
            interval: Tuple[float, Tuple[float, float]] = None,
            speed: float = None,
            max_datetime: datetime = None,
            initial_stores: int = None,
            initial_store_population: int = None,
            store_growth_rate: float = None,
            restore_dir: Path = None,
            seed: int = None
            ) -> None:
        if store_growth_rate is None:
            store_growth_rate = GlobalContext.STORE_GROWTH_RATE
        self.store_growth_rate = store_growth_rate

        if initial_datetime is None:
            initial_datetime = datetime(
                GlobalContext.INITIAL_DATE.year,
                GlobalContext.INITIAL_DATE.month,
                GlobalContext.INITIAL_DATE.day
            )

        if interval is None:
            if GlobalContext.SIMULATOR_INTERVAL_MIN is None:
                interval = GlobalContext.SIMULATOR_INTERVAL
            else:
                interval = (
                    GlobalContext.SIMULATOR_INTERVAL_MIN,
                    GlobalContext.SIMULATOR_INTERVAL_MAX
                )

        if speed is None:
            speed = GlobalContext.SIMULATOR_SPEED

        super().__init__(
            initial_datetime,
            interval=interval,
            speed=speed,
            max_datetime=max_datetime,
            skip_step=True,
            seed=seed
        )

        # Prepare restore file
        if restore_dir is None:
            restore_dir = GlobalContext.RESTORE_DIR

        self.restore_file = restore_dir / 'simulator.json'

        # Generate stores
        if initial_stores is None:
            initial_stores = GlobalContext.INITIAL_STORES

        if initial_stores > 0:
            if initial_store_population is None:
                initial_store_population = \
                    GlobalContext.STORE_MARKET_POPULATION

            _time_stores = datetime.now()
            simulator_logger.info('Generating stores...')
            self._populate_stores(
                initial_stores,
                initial_store_population,
                build_range_days=GlobalContext.INITIAL_STORES_RANGE_DAYS
            )
            simulator_logger.info(
                f'Simulator has been created with '
                f'the initial of {self.n_stores} stores. '
                f'{(datetime.now() - _time_stores).total_seconds():.1f}s.'
            )

        self.push_restore(tmp=True)

    @property
    def n_stores(self) -> int:
        return super().n_agents

    def stores(self) -> Iterable[Store]:
        return super().agents()

    def total_market_population(self) -> int:
        return sum([
            store.total_market_population()
            for store in self.stores()
        ])

    def step(self):
        past_datetime = self.current_datetime
        current_step, next_step = super().step()
        current_datetime = cast(current_step, datetime)

        n_stores = self.n_stores
        n_active_stores = len([
            store
            for store in self.stores()
            if store.initial_step <= current_step
        ])

        # # @ 1 day - Daily update possibility of store growth
        # if current_datetime.day != past_datetime.day:
        #     for random in self._rng.random(n_stores):
        #         if random > self.store_growth_rate / DAYS_IN_YEAR:
        #             continue

        #         try:
        #             ...
        #             self.add_agent(new_store)
        #             simulator_logger.info(simulator_log_format(
        #                 f"New store #{self.n_stores}",
        #                 f"'{new_store.place_name}'",
        #                 'has been built with market population size',
        #                 f"{new_store.total_market_population()}.",
        #                 dt=current_datetime
        #             ))

        #         # Possible error when a store
        #         # has been exists in the same place
        #         except Exception:
        #             simulator_logger.error(
        #                 'Failed to build new store.',
        #                 exc_info=True
        #             )

        # @ 15 mins - Log synchronization between simulation
        # and the real/projected datetime
        if current_datetime.minute % 15 == 0 \
                and current_datetime.minute != past_datetime.minute:
            real_current_datetime = datetime.now()
            speed_adjusted_real_current_datetime = real_current_datetime
            if self.speed != 1.0:
                speed_adjusted_real_current_datetime = (
                    self._real_initial_datetime
                    + self.speed * (
                        real_current_datetime - self._real_initial_datetime
                    )
                )
            behind_seconds = (
                speed_adjusted_real_current_datetime
                - current_datetime
            ).total_seconds()

            dt_str = (
                speed_adjusted_real_current_datetime
                .isoformat(sep=' ', timespec='seconds')
            )
            if behind_seconds >= self._interval:
                simulator_logger.info(simulator_log_format(
                    'Simulation is behind the',
                    'real datetime' if self.speed == 1.0
                    else f"projected datetime ({dt_str})",
                    f'by {behind_seconds:.1f}s.',
                    dt=current_datetime
                ))

        # @ 1 hour - Log today orders hourly
        if current_datetime.hour != past_datetime.hour:
            simulator_logger.info(simulator_log_format(
                f'Total active stores: {n_active_stores}/{n_stores}.',
                'Today cumulative orders:',
                sum([
                    store.total_orders
                    for store in self.stores()
                ]),
                dt=current_datetime
            ))
            simulator_logger.debug(simulator_log_format(
                'Total canceled orders:',
                sum([
                    store.total_canceled_orders
                    for store in self.stores()
                ]),
                '. Total customer steps:',
                sum([
                    store.customer_steps
                    for store in self.stores()
                ]),
                '. Total employee steps:',
                sum([
                    store.employee_steps
                    for store in self.stores()
                ]),
                dt=current_datetime
            ))

            for i, store in enumerate(self.stores(), 1):
                if store.initial_step > current_step:
                    continue

                store_logger.debug(simulator_log_format(
                    f"Store #{str(i).rjust(len(str(n_stores)), '0')}",
                    store.place_name,
                    '-', 'OPEN' if store.is_open() else 'CLOSE',
                    f'({store.n_cashiers}/{store.n_employees})',
                    f'| Today cumulative orders: {store.total_orders}.',
                    dt=current_datetime
                ))

        return current_step, next_step

    def _populate_stores(
            self,
            n: int,
            market_population: int = None,
            market_fertility_rate: float = None,
            market_life_expectancy: float = None,
            market_marry_age: float = None,
            build_range_days: int = 0
            ) -> None:
        initial_datetime = self.current_datetime
        initial_date = initial_datetime.date()

        total_subdistricts = SubdistrictModel.select().count()
        subdistrict_ids = \
            self._rng.choice(total_subdistricts, n, replace=False)

        market_populations, fertility_rates, \
            life_expectancies, marry_ages = \
            self._calculate_market_params(
                n,
                market_population,
                market_fertility_rate,
                market_life_expectancy,
                market_marry_age
            )

        delay_days = self._rng.choice(build_range_days + 1, n)

        for i, subdistrict_id, market_population_, \
                fertility_rate_, life_expectancy_, marry_age_, \
                delay_days_ in zip(
                    range(1, n + 1),
                    subdistrict_ids,
                    market_populations,
                    fertility_rates,
                    life_expectancies,
                    marry_ages,
                    delay_days
                ):
            _time_store = datetime.now()

            subdistrict: SubdistrictModel = (
                SubdistrictModel.select()
                .limit(1)
                .offset(int(subdistrict_id))
                .execute()
                .iterate()
            )

            store_dir = (
                self.restore_file.parent
                / 'Store'
                / subdistrict.code
            )
            store_dir.mkdir(parents=True, exist_ok=True)

            # Create a place
            place = Place(
                code=subdistrict.code,
                name=subdistrict.name,
                initial_date=initial_date,
                initial_population=market_population_,
                fertility_rate=fertility_rate_,
                life_expectancy=life_expectancy_,
                marry_age=marry_age_,
                rng=np.random.RandomState(self.random_seed())
            )
            place.push_restore(store_dir / 'place.json', tmp=True)

            # Add store on the place
            store_initial_datetime = (
                datetime(
                    initial_datetime.year,
                    initial_datetime.month,
                    initial_datetime.day
                )
                + timedelta(days=int(delay_days_))
            )
            store = Store(
                place,
                store_initial_datetime,
                self.interval,
                rng=place._rng
            )
            store.created_datetime = initial_datetime
            self.add_agent(store)

            # Populate place with families and customer data
            for family in Family.bulk_generate(
                    int(place.initial_population / 3.0),
                    initial_date,
                    rng=place._rng
                    ):
                family_dir = (
                    store_dir
                    / 'Customer'
                    / family.id
                )
                family_dir.mkdir(parents=True, exist_ok=True)
                family.push_restore(family_dir / 'family.json')

                customer = Customer(
                    store_initial_datetime,
                    self.interval,
                    rng=place._rng
                )
                customer.push_restore(family_dir / 'customer.json', tmp=True)

            store.push_restore(store_dir / 'store.json')
            simulator_logger.debug(
                f"New store ({i}/{n}) '{place.name}' is created and "
                f"the initial date is on '{store.initial_date}'. "
                f'{(datetime.now() - _time_store).total_seconds():.1f}s.'
            )

    def _calculate_market_params(
            self,
            n: int,
            population: int = None,
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

        return populations, fertility_rates, life_expectancies, marry_ages

    @property
    def restore_attrs(self) -> Dict[str, Any]:
        attrs = super().restore_attrs
        attrs['store_growth_rate'] = self.store_growth_rate
        return attrs

    def _push_restore(
            self,
            file: Path = None,
            tmp: bool = False,
            **kwargs
            ) -> None:
        if not tmp:
            _time = datetime.now()
            simulator_logger.info("Simulator is being backup...")

            for i, store in enumerate(self.stores(), 1):
                _time_store = datetime.now()
                store.update_market_population(self.current_datetime)
                simulator_logger.info(
                    f'Backup store ({i}/{self.n_stores}) {store.place_name}. '
                    f'{(datetime.now() - _time_store).total_seconds():.1f}s.'
                )

            super()._push_restore(file, tmp=tmp, **kwargs)
            simulator_logger.info(
                f'Succesfully backup the simulator. '
                f'{(datetime.now() - _time).total_seconds():.1f}s.'
            )

        else:
            super()._push_restore(file, tmp=tmp, **kwargs)

    @classmethod
    def _restore(
            cls,
            attrs: Dict[str, Any],
            file: Path,
            **kwargs
            ) -> Simulator:
        base_dir = file.parent

        initial_step, interval, max_step, \
            next_step, skip_step, speed = attrs['base_params']
        obj = cls(
            initial_step,
            interval,
            speed,
            max_step,
            0,
            0,
            attrs['store_growth_rate']
        )
        obj._next_step = next_step
        obj._real_initial_datetime = attrs['real_initial_datetime']
        obj.load_rng_state(attrs['rng_state'])

        store_ids = kwargs.get('store_ids')
        for store_restore_file in base_dir.rglob('Store/*/store.json'):
            if isinstance(store_ids, list) \
                    and store_restore_file.parent.name not in store_ids:
                continue

            store = Store.restore(base_dir / str(store_restore_file))
            if store.record_id is None:
                shutil.rmtree(store_restore_file.parent)
                continue

            obj.add_agent(store)

        return obj
