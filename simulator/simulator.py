from datetime import datetime
from typing import Iterable, List

from .core import DatetimeEnvironment
from .context import GlobalContext
from .database import create_database
from .logging import simulator_logger, store_logger
from .population import Place
from .store import Store


class Simulator(DatetimeEnvironment):
    __repr_attrs__ = ( 'n_stores', 'total_market_population', 'current_datetime' )

    def __init__(
            self,
            initial_datetime: datetime = None,
            interval: float = None,
            speed: float = None,
            max_datetime: datetime = None,
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

        super().__init__(
            initial_datetime,
            interval=interval if interval is not None else GlobalContext.CLOCK_INTERVAL,
            speed=speed if speed is not None else GlobalContext.CLOCK_SPEED,
            max_datetime=max_datetime,
            seed=seed
        )

        # ONLY FOR TESTING!!!
        if not GlobalContext.SQLITE_DB_PATH.exists():
            create_database(initial_datetime)
            raise SystemExit

        for store in self.generate_stores(
                initial_stores if initial_stores is not None else GlobalContext.INITIAL_STORES,
                initial_store_population if initial_store_population is not None else GlobalContext.STORE_POPULATION,
                self.current_datetime()
            ):
            self.add_agent(store)

        simulator_logger.info(repr(self))
        for i, store in enumerate(self.stores(), 1):
            store_logger.info(f'  #{i} {store.place_name}. Total market population: {store.total_market_population()}.')

        self.store_growth_rate = store_growth_rate if store_growth_rate is not None else GlobalContext.STORE_GROWTH_RATE

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
            store_population,
            current_datetime: datetime
        ) -> List[Store]:
        seeds = [ int(num) for num in (self._rng.random(n) * 1_000_000) ]
        stores = [
            Store(
                place,
                current_datetime,
                self.interval,
                seed=seed
            )
            for place, seed in zip(
                Place.generate(
                    n,
                    current_datetime.date(),
                    initial_population=store_population,
                    rng=self._rng
                ),
                seeds
            )
        ]
        return stores

    def step(self):
        current_datetime, next_datetime = super().step()

        if current_datetime.hour == 0 \
                and current_datetime.minute == 0 \
                and current_datetime.second == 0:
            simulator_logger.info(repr(self))
            for i, store in enumerate(self.stores(), 1):
                store_logger.info(
                    f'  #{i} {store}'
                    f'. Active employees: {", ".join([f"{employee.name}[{employee.record_id}][{employee.shift.name}]" for employee in store.get_active_employees()])}'
                    f'. Total orders: {store.total_orders}'
                    f'. Time elapsed: {self.total_real_time_elapsed().total_seconds():.2f}s.'
                )

        if current_datetime.hour != 0 \
                and current_datetime.second == 0 \
                and current_datetime.minute == 0:
            simulator_logger.debug(repr(self))
            for i, store in enumerate(self.stores(), 1):
                store_logger.debug(
                    f'  #{i} {store}'
                    f'. Active employees: {", ".join([f"{employee.name}[{employee.record_id}][{employee.shift.name}]" for employee in store.get_active_employees()])}'
                    f'. Total orders: {store.total_orders}'
                    f'. Time elapsed: {self.total_real_time_elapsed().total_seconds():.2f}s.'
                )

        return current_datetime, next_datetime
