from __future__ import annotations

import numpy as np
from typing import Generator

from ._base import (
    RandomGeneratorMixin, ReprMixin,
    StepMixin, _STEP_TYPE
)


class Agent(
        StepMixin,
        RandomGeneratorMixin, ReprMixin,
        repr_attrs=('current_step',)
        ):
    def __init__(
            self,
            initial_step: _STEP_TYPE = 0,
            max_step: _STEP_TYPE = 0,
            interval: _STEP_TYPE = 1,
            seed: int = None,
            rng: np.random.RandomState = None
            ) -> None:
        self._index = None
        self.parent: MultiAgent | None = None

        super().__init_step__(initial_step, max_step, interval)
        super().__init_rng__(seed, rng)

    @property
    def index(self) -> int | None:
        return self._index

    def get_next_step(
            self,
            current_step: _STEP_TYPE
            ) -> _STEP_TYPE:
        next_step = super().get_next_step(current_step)
        if self.parent is not None \
                and next_step < self.parent.next_step:
            next_step = self.parent.next_step
        return next_step


class MultiAgent(
        Agent,
        repr_attrs=('n_agents', 'current_step')
        ):
    def __init__(
            self,
            initial_step: _STEP_TYPE = 0,
            max_step: _STEP_TYPE = 0,
            interval: _STEP_TYPE = 1,
            skip_step: bool = False,
            agents: list[Agent] = None,
            seed: int = None,
            rng: np.random.RandomState = None
            ) -> None:
        super().__init__(
            initial_step,
            max_step,
            interval,
            seed,
            rng
        )

        self._agent_steps = None
        self._skip_step = skip_step

        self._agents: list[Agent] = []
        if agents is not None:
            self.add_agents(agents)

    @property
    def skip_step(self) -> bool:
        return self._skip_step

    @property
    def n_agents(self) -> int:
        return len(self._agents)

    def agents(self) -> Generator[Agent]:
        for agent in self._agents:
            yield agent

    def add_agent(self, agent: Agent) -> None:
        agent.parent = self
        if isinstance(agent, MultiAgent):
            agent._skip_step = self.skip_step
        agent_steps = agent._steps.reshape(1, -1)
        agent_steps[0, 3] = np.max([
            agent_steps[0, 3], self._steps[3]
        ])

        self._agents.append(agent)
        if self._agent_steps is None:
            self._agent_steps = agent_steps.reshape((1, -1))
        else:
            self._agent_steps = np.concatenate(
                (self._agent_steps, agent_steps),
                axis=0
            )
            for i, agent_ in enumerate(self._agents):
                agent_._steps = self._agent_steps[i, :]

        agent._index = int(self._agent_steps.shape[0]) - 1

    def add_agents(self, agents: list[Agent]) -> None:
        for agent in agents:
            self.add_agent(agent)

    def remove_agent(self, agent: Agent) -> None:
        index = agent._index
        agent._index = None
        agent.parent = None

        self._steps = np.delete(self._steps, index, axis=0)
        self._agents.remove(agent)
        for agent in self._agents:
            if agent._index >= index:
                agent._index -= 1

    def remove_agents(self, agents: list[Agent]) -> None:
        for agent in agents:
            self.remove_agent(agent)

    def step(
            self,
            *args,
            **kwargs
            ) -> tuple[_STEP_TYPE, _STEP_TYPE, bool]:
        current_step, next_step, done = super().step(*args, **kwargs)

        mask = (
            # agents' next step
            (self._agent_steps[:, 4] <= current_step)
            & (
                # agents' max step
                (self._agent_steps[:, 1] == 0)
                | (self._agent_steps[:, 4] <= self._agent_steps[:, 4])
            )
        )
        n_mask = np.sum(mask)
        if n_mask > 0:
            self._agent_steps[mask, 3] = current_step
            self._agent_steps[mask, 4] = np.max(
                np.concatenate(
                    (
                        self._agent_steps[mask, 4],
                        np.repeat(next_step, n_mask)
                    ),
                    axis=0
                ),
                axis=0
            )
            for i in np.argwhere(mask).reshape(-1):
                self._agents[int(i)].step(*args, **kwargs)

        if self._skip_step:
            min_agent_next_step = self._agent_steps[:, 4].min()
            if min_agent_next_step > next_step:
                self.next_step = min_agent_next_step

        return current_step, self.next_step, done
