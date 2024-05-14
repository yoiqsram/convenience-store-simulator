from __future__ import annotations

import asyncio
import numpy as np
from datetime import datetime
from typing import Dict, Iterable, TYPE_CHECKING

from .clock import Clock, DatetimeClock, StepClock

if TYPE_CHECKING:
    from .agent import Agent


class Environment:
    def __init__(
            self,
            clock: Clock = None,
            seed: int = None
        ) -> None:
        self._agents: Dict[int, Agent] = dict()

        if clock is None:
            clock = StepClock()
        self._clock = clock

        self._rng = np.random.RandomState(seed)

    def current_step(self) -> datetime:
        return self._clock.current_step()

    @property
    def agents(self) -> Iterable[Agent]:
        return self._agents.values()

    def add_agent(self, agent: Agent):
        if agent.id in self._agents:
            print(self.agents)
            raise IndexError(f"Agent '{agent.id}' is already been in the environment.")

        self._agents[agent.id] = agent

    def add_agents(self, agents: Iterable[Agent]):
        for agent in agents:
            self.add_agent(agent)

    def remove_agent(self, agent: Agent):
        if agent.id not in self._agents:
            raise IndexError()

        del self._agents[agent.id]

    def remove_agents(self, agents: Iterable[Agent]):
        for agent in agents:
            self.remove_agent(agent)

    def step(self) -> None:
        self._clock.step()
        for agent in self._agents.values():
            agent.step(env=self)

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
