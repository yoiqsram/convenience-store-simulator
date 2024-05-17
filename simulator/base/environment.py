from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Tuple

from ..context import GlobalContext
from ._base import ReprMixin
from .agent import MultiAgentMixin
from .clock import Clock, DatetimeClock, StepClock, DatetimeStepMixin
from .random import RandomGeneratorMixin


class Environment(MultiAgentMixin, RandomGeneratorMixin, ReprMixin):
    __repr_attrs__ = ( 'n_agents', 'last_step' )

    def __init__(
            self,
            clock: Clock = None,
            seed: int = None
        ) -> None:
        if clock is None:
            clock = StepClock()
        self._clock = clock

        self.__init_agents__(
            [],
            self._clock._last_step,
            self._clock._next_step,
            self._clock._max_step
        )
        self.__init_rng__(seed)

    def max_step(self) -> Any:
        return self._clock.max_step()

    def last_step(self) -> Any:
        return self._clock.last_step()

    def next_step(self) -> Any:
        return self._clock.next_step()

    def step(self) -> Tuple[Any, Any]:
        current_step, next_step = self._clock.step()
        for agent in self._agents.values():
            if agent.next_step() is not None \
                    and agent.next_step() <= current_step:
                agent.step(env=self)

        return current_step, next_step


    def calculate_next_step(self) -> Any:
        return self._clock.next_step()

    async def _run_await(self) -> None:
        self._clock: DatetimeClock
        waiting_time = self._clock.interval / self._clock.speed
        waiting_task = asyncio.create_task(asyncio.sleep(max(waiting_time, 0)))
        self.step()
        await waiting_task

    def run(self) -> None:
        while True:
            if isinstance(self._clock, DatetimeClock) \
                    and self._clock.next_step() is not None:
                asyncio.run(self._run_await())
            else:
                self.step()

            if self._clock.next_step() is None:
                break


class DatetimeEnvironment(Environment, DatetimeStepMixin, ReprMixin):
    __repr_attrs__ = ( 'last_datetime', 'n_agents' )

    def __init__(
            self,
            initial_datetime: datetime = None,
            time_interval: float = None,
            time_speed: float = None,
            seed: int = None
        ) -> None:
        if initial_datetime is None:
            initial_datetime = datetime(
                GlobalContext.INITIAL_DATE.year,
                GlobalContext.INITIAL_DATE.month,
                GlobalContext.INITIAL_DATE.day
            )
        clock = DatetimeClock(
            interval=time_interval if time_interval is not None else GlobalContext.CLOCK_INTERVAL,
            speed=time_speed if time_speed is not None else GlobalContext.CLOCK_SPEED,
            initial_datetime=initial_datetime
        )
        super().__init__(clock, seed)
