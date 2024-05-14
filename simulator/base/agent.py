from __future__ import annotations

import numpy as np
from typing import Iterable, TYPE_CHECKING

from .context import BaseContext

if TYPE_CHECKING:
    from .environment import Environment


class Agent:
    def __init__(self, seed: int = None) -> None:
        BaseContext.__agent_counter__ += 1
        self._id = BaseContext.__agent_counter__

        self.next_step = None
        self._rng = np.random.RandomState(seed)

    @property
    def id(self) -> int:
        return self._id

    def other_agents(self, env: Environment) -> Iterable[Agent]:
        agents = env.agents.copy()
        if self._id not in agents:
            raise IndexError(f"Agent '{self._id}' is not added yet in the environment.")

        del agents[self._id]
        return agents.values()

    def step(self, env: Environment) -> None:
        if self.next_step is not None \
                and self.next_step < env.current_step():
            return

    async def step_async(self, env: Environment) -> None:
        self.step(env=env)
