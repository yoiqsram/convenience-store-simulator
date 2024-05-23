import numpy as np
from datetime import datetime, timedelta
from typing import Iterable, List, Tuple

from .core import RandomDatetimeEnvironment
from .context import GlobalContext, DAYS_IN_YEAR
from .database import Database, BaseModel, create_database
from .logging import simulator_logger, simulator_log_format
from .population import Place
from .store import Store


class Simulator(RandomDatetimeEnvironment):
    __repr_attrs__ = ( 'n_stores', 'total_market_population', 'current_datetime' )

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

        super().__init__(
            initial_datetime,
            interval=interval,
            speed=speed if speed is not None else GlobalContext.SIMULATOR_SPEED,
            max_datetime=max_datetime,
            skip_step=skip_step,
            seed=seed
        )

        self.store_growth_rate = store_growth_rate if store_growth_rate is not None else GlobalContext.STORE_GROWTH_RATE

        # Create simulator database if not available
        database: Database = BaseModel._meta.database
        if database.table_exists('version'):
            simulator_logger.info('Database is already exists.')
        else:
            _time = datetime.now()
            simulator_logger.info(f"Preparing {database.__class__.__name__.split('Database')[0]} database for the simulator...")
            create_database(initial_datetime)
            simulator_logger.info(f'Simulator database is ready. {(datetime.now() - _time).total_seconds():.1f}s')

        # Generate stores
        _time = datetime.now()
        simulator_logger.info('Generating stores...')
        for store in self.generate_stores(
                initial_stores if initial_stores is not None else GlobalContext.INITIAL_STORES,
                initial_store_population if initial_store_population is not None else GlobalContext.STORE_MARKET_POPULATION,
                self.current_datetime(),
                GlobalContext.INITIAL_STORES_RANGE_DAYS
            ):
            self.add_agent(store)
            simulator_logger.debug(f"New store '{store.place_name}' with market population size {store.total_market_population()} has been added. It will be built on '{store.initial_date}'.")
        simulator_logger.info(f'Generated {self.n_stores} stores. {(datetime.now() - _time).total_seconds():.1f}s')

        simulator_logger.info(f'Simulator has been created. Total market population: {self.total_market_population()}.')

    @property
    def n_stores(self) -> int:
        return len(self._agents)

    def stores(self) -> Iterable[Store]:
        return super().agents()

    def total_market_population(self) -> int:
        return sum([ store.total_market_population() for store in self.stores() ])

    def generate_stores(
            self,
            n: int,
            market_population_expected: int,
            initial_datetime: datetime,
            range_days: int = 0
        ) -> List[Store]:
        seeds = [ int(num) for num in (self._rng.random(n) * 1_000_000) ]
        stores = []
        for place, seed, delay_days in zip(
                Place.generate(
                    n,
                    initial_datetime.date(),
                    initial_population=market_population_expected,
                    rng=self._rng
                ),
                seeds,
                self._rng.choice(range_days + 1, n)
            ):
            initial_datetime_ = (
                datetime(initial_datetime.year, initial_datetime.month, initial_datetime.day)
                + timedelta(days=int(delay_days))
            )
            stores.append(Store(
                place,
                initial_datetime_,
                self.interval,
                seed=seed
            ))
        return stores

    def step(self):
        past_datetime = self.current_datetime()
        current_datetime, next_datetime = super().step()

        n_stores = self.n_stores
        n_active_stores = len([ store for store in self.stores() if store.initial_datetime <= current_datetime ])

        # Daily update possibility of store growth
        if current_datetime.day != past_datetime.day:
            for random in self._rng.random(n_stores):
                if random > (1 - np.power(1 + self.store_growth_rate, 1 / DAYS_IN_YEAR)):
                    continue

                try:
                    new_store = self.generate_stores(1, GlobalContext.STORE_MARKET_POPULATION, current_datetime)[0]
                    self.add_agent(new_store)
                    simulator_logger.info(simulator_log_format(
                        f"New store '{store.place_name}' has been built with market population size {new_store.total_market_population()}.",
                        dt=current_datetime
                    ))

                # Possible error when a store has been exists in the same place
                except:
                    simulator_logger.error(f'Failed to build new store.', exc_info=True)

        # Log market population size monthly
        if current_datetime.month != past_datetime.month:
            simulator_logger.info(simulator_log_format(
                f'Total active stores: {n_active_stores}/{n_stores}.',
                f'Total market population: {self.total_market_population()}.',
                dt=current_datetime
            ))
            for i, store in enumerate(self.stores(), 1):
                simulator_logger.info(simulator_log_format(
                    f"Store #{str(i).rjust(len(str(n_stores)), '0')} {store.place_name} | Total market population: {store.total_market_population()}",
                    dt=current_datetime
                ))

        # Log today orders hourly
        if current_datetime.hour != past_datetime.hour:
            simulator_logger.info(simulator_log_format(
                f'Total active stores: {n_active_stores}/{n_stores}.',
                f'Today cumulative orders: {sum([ store.total_orders for store in self.stores() ])}.',
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

        return current_datetime, next_datetime
