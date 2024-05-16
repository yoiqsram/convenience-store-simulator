from __future__ import annotations

import asyncio
from typing import Any

from .agent import MultiAgentMixin
from .clock import Clock, DatetimeClock, StepClock
from .random import RandomGeneratorMixin


class Environment(MultiAgentMixin, RandomGeneratorMixin):
    def __init__(
            self,
            clock: Clock = None,
            seed: int = None
        ) -> None:
        self.__init_agents__()

        if clock is None:
            clock = StepClock()
        self._clock = clock

        self.__init_rng__(seed)

    def step(self) -> Any:
        current_step = self._clock.step()
        for agent in self._agents.values():
            if agent.next_step() is not None \
                    and agent.next_step() > current_step:
                agent._next_step = agent.step(env=self)

        return self.calculate_next_step()

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
