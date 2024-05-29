from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from .core import RandomDatetimeEnvironment
from .context import GlobalContext, DAYS_IN_YEAR
from .database import Database, StoreModel, create_database
from .logging import simulator_logger, simulator_log_format
from .population import Place
from .store import Store


class Simulator(
        RandomDatetimeEnvironment,
        repr_attrs=('n_stores', 'total_market_population', 'current_datetime')
        ):
    def __init__(
            self,
            initial_datetime: datetime = None,
            interval: Tuple[float, Tuple[float, float]] = None,
            speed: float = None,
            max_datetime: datetime = None,
            skip_step: bool = False,
            initial_stores: int = None,
            initial_store_population: int = None,
            store_growth_rate: float = None,
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
            skip_step=skip_step,
            seed=seed
        )

        # Create simulator database if not available
        if StoreModel.table_exists():
            if StoreModel.select().count() > 1:
                raise FileExistsError('Database is already exists.')

        else:
            _time = datetime.now()
            database: Database = StoreModel._meta.database
            simulator_logger.info(
                f"Preparing {type(database).__name__.split('Database')[0]} "
                "database for the simulator..."
            )
            create_database(initial_datetime)
            simulator_logger.info(
                f'Simulator database is ready. '
                f'{(datetime.now() - _time).total_seconds():.1f}s'
            )

            import shutil
            shutil.copy(database.database, str(database.database) + '.backup')

        # Generate stores
        if initial_stores is None:
            initial_stores = GlobalContext.INITIAL_STORES

        if initial_stores == 0:
            return

        if initial_store_population is None:
            initial_store_population = \
                GlobalContext.STORE_MARKET_POPULATION

        _time = datetime.now()
        simulator_logger.info('Generating stores...')
        for store in self.generate_stores(
                initial_stores,
                initial_store_population,
                self.current_datetime(),
                GlobalContext.INITIAL_STORES_RANGE_DAYS
                ):
            store.update_market_population(self.current_datetime())
            self.add_agent(store)
            simulator_logger.debug(
                f"New store '{store.place_name}' with "
                f"market population size {store.total_market_population()} "
                f"has been added. It will be built on '{store.initial_date}'."
            )
        simulator_logger.info(
            f'Generated {self.n_stores} stores. '
            f'{(datetime.now() - _time).total_seconds():.1f}s'
        )
        simulator_logger.info(
            f'Simulator has been created. '
            f'Total market population: {self.total_market_population()}.'
        )

    @property
    def n_stores(self) -> int:
        return len(self._agents)

    def stores(self) -> Iterable[Store]:
        return super().agents()

    def total_market_population(self) -> int:
        return sum([
            store.total_market_population()
            for store in self.stores()
        ])

    def generate_stores(
            self,
            n: int,
            market_population_expected: int,
            initial_datetime: datetime,
            range_days: int = 0
            ) -> List[Store]:
        stores = []
        for place, delay_days in zip(
                Place.generate(
                    n,
                    initial_datetime.date(),
                    initial_population=market_population_expected,
                    rng=self._rng
                ),
                self._rng.choice(range_days + 1, n)
                ):
            initial_datetime_ = (
                datetime(
                    initial_datetime.year,
                    initial_datetime.month,
                    initial_datetime.day
                )
                + timedelta(days=int(delay_days))
            )
            store = Store(
                place,
                initial_datetime_,
                self.interval,
                rng=self._rng
            )
            stores.append(store)

        return stores

    def step(self):
        past_datetime = self.current_datetime()
        current_datetime, next_datetime = super().step()

        n_stores = self.n_stores
        n_active_stores = len([
            store
            for store in self.stores()
            if store.initial_datetime <= current_datetime
        ])

        # @ 1 day - Daily update possibility of store growth
        if current_datetime.day != past_datetime.day:
            for random in self._rng.random(n_stores):
                if random > self.store_growth_rate / DAYS_IN_YEAR:
                    continue

                try:
                    new_store = self.generate_stores(
                        1,
                        GlobalContext.STORE_MARKET_POPULATION,
                        current_datetime
                    )[0]
                    self.add_agent(new_store)
                    simulator_logger.info(simulator_log_format(
                        f"New store '{new_store.place_name}' has been built "
                        f"with market population size "
                        f"{new_store.total_market_population()}.",
                        dt=current_datetime
                    ))

                # Possible error when a store has been exists in the same place
                except Exception:
                    simulator_logger.error(
                        'Failed to build new store.',
                        exc_info=True
                    )

        # @ 1 month - Log market population size monthly
        if current_datetime.month != past_datetime.month:
            simulator_logger.info(simulator_log_format(
                f'Total active stores: {n_active_stores}/{n_stores}.',
                f'Total market population: {self.total_market_population()}.',
                dt=current_datetime
            ))
            for i, store in enumerate(self.stores(), 1):
                simulator_logger.info(simulator_log_format(
                    f"Store #{str(i).rjust(len(str(n_stores)), '0')}",
                    f"{store.place_name} |",
                    "Total market population:",
                    store.total_market_population(),
                    dt=current_datetime
                ))

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
            if behind_seconds >= self.interval.total_seconds():
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

            for i, store in enumerate(self.stores(), 1):
                if store.initial_datetime > current_datetime:
                    continue

                simulator_logger.info(simulator_log_format(
                    f"Store #{str(i).rjust(len(str(n_stores)), '0')}",
                    store.place_name,
                    '-', 'OPEN' if store.is_open() else 'CLOSE',
                    f'| Today cumulative orders: {store.total_orders}.',
                    dt=current_datetime
                ))

        self.push_restore()
        return current_datetime, next_datetime

    @property
    def restore_attrs(self) -> Dict[str, Any]:
        attrs = super().restore_attrs
        attrs['store_growth_rate'] = self.store_growth_rate
        return attrs

    def _push_restore(self, file: Path = None) -> None:
        _time = datetime.now()
        simulator_logger.info("Simulator is being backup...")

        for store in self.stores():
            if hasattr(store, 'restore_file'):
                store.push_restore()
            else:
                store_dir = file.parent / f'Store_{store.place.code}'
                store_dir.mkdir(exist_ok=True)
                store.push_restore(store_dir / 'store.json')

        super()._push_restore(file)

        simulator_logger.info(simulator_log_format(
            f"Succesfully backup the simulator in '{file}'.",
            f'{(datetime.now() - _time).total_seconds():.1f}s',
            dt=self.current_datetime()
        ))

    @classmethod
    def _restore(
            cls,
            attrs: Dict[str, Any],
            file: Path,
            store_restore_files: List[str],
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
            skip_step,
            0,
            0,
            attrs['store_growth_rate']
        )
        obj._next_step = next_step
        obj._real_initial_datetime = attrs['real_initial_datetime']

        for store_restore_file in base_dir.rglob('Store_*/store.json'):
            store = Store.restore(base_dir / str(store_restore_file))
            obj._agents.append(store)

        obj.load_rng_state(attrs['rng_state'])
        return obj
