from datetime import date, datetime
from typing import Iterable, List, Tuple

from .base import DatetimeEnvironment
from .context import GlobalContext
from .place import Place
from .store import Store


class Simulator(DatetimeEnvironment):
    __repr_attrs__ = ( 'n_stores', 'last_datetime' )

    def __init__(
            self,
            initial_datetime: datetime = None,
            time_interval: float = None,
            time_speed: float = None,
            initial_stores: int = None,
            initial_store_population: int = None,
            store_growth_rate: float = None,
            seed: int = None
        ) -> None:
        super().__init__(
            initial_datetime,
            time_interval,
            time_speed,
            seed
        )

        stores = self.generate_stores(
            initial_stores if initial_stores is not None else GlobalContext.INITIAL_STORES,
            initial_store_population if initial_store_population is not None else GlobalContext.STORE_POPULATION,
            self.last_date()
        )
        self.add_agents(
            stores,
            self._clock._last_step,
            self._clock._next_step,
            self._clock._max_step
        )
        self.store_growth_rate = store_growth_rate if store_growth_rate is not None else GlobalContext.STORE_GROWTH_RATE

        self._time = datetime.now()

    @property
    def n_stores(self) -> int:
        return len(self._agents)

    def stores(self) -> Iterable[Store]:
        return self.agents()

    def generate_stores(
            self,
            n: int,
            store_population,
            a_date: date
        ) -> List[Store]:
        seeds = [ int(num) for num in (self._rng.random(n) * 1_000_000) ]
        stores = [
            Store(
                place=place,
                seed=seed
            )
            for place, seed in zip(
                Place.generate(
                    n,
                    a_date,
                    initial_population=store_population,
                    rng=self._rng
                ),
                seeds
            )
        ]
        return stores

    def step(self) -> Tuple[datetime, datetime]:
        last_datetime, next_datetime = super().step()

        # Update step for each store
        if last_datetime.second == 0 \
                and last_datetime.minute == 0:
            for i, store in enumerate(self.stores(), 1):
                print(
                    f'#{i}',
                    store.place.name,
                    '-', last_datetime.isoformat(timespec='minutes', sep=' '),
                    f"- ({', '.join([repr(worker) for worker in store.get_active_workers()])})",
                    '- Total checkout', store.total_checkout,
                    '-', f'{(datetime.now() - self._time).seconds}s'
                )
            print()

        return last_datetime, next_datetime
