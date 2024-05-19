from __future__ import annotations

import abc
from typing import Any, List, Iterable, Tuple, Union, TYPE_CHECKING

from ._base import IdentityMixin, RandomGeneratorMixin, ReprMixin, StepMixin, _STEP_TYPE, _INTERVAL_TYPE

if TYPE_CHECKING:
    from .environment import BaseEnvironment


class Agent(IdentityMixin, StepMixin, RandomGeneratorMixin, ReprMixin, metaclass=abc.ABCMeta):
    __repr_attrs__ = ( 'id', )

    def __init__(
            self,
            initial_step: _STEP_TYPE,
            interval: _INTERVAL_TYPE,
            max_step: _STEP_TYPE = None,
            seed: int = None) -> None:
        self.parent: Union[MultiAgent, BaseEnvironment, None] = None

        super().__init_id__()
        super().__init_step__(initial_step, interval, max_step)
        super().__init_rng__(seed)

    def other_agents(self) -> Iterable[Agent]:
        if self.parent is None:
            raise IndexError()

        for agent in self.parent.agents():
            if agent != self:
                yield agent

    def get_next_step(self) -> Union[_STEP_TYPE, None]:
        if self.parent is None:
            next_step = self.next_step()
        else:
            next_step = self.parent.next_step()

        if self._max_step is not None \
                and next_step > self._max_step:
            return

        return next_step


class MultiAgentMixin:
    def __init_agents__(self, agents: Iterable[Agent] = None) -> None:
        self._agents: List[Agent] = agents if agents is not None else []

    @property
    def n_agents(self) -> int:
        return len(self._agents)

    def agents(self) -> Iterable[Agent]:
        for agent in self._agents:
            yield agent

    def add_agent(self, agent: Agent) -> None:
        if agent in self._agents:
            raise IndexError(f"Agent is already in the index.")

        self._agents.append(agent)
        agent.parent = self

    def add_agents(self, agents: Iterable[Agent]) -> None:
        for agent in agents:
            self.add_agent(agent)

    def remove_agent(self, agent: Agent) -> None:
        self._agents.remove(agent)

    def remove_agents(self, agents: Iterable[Agent]) -> None:
        for agent in agents:
            self.remove_agent(agent)


class MultiAgent(Agent, MultiAgentMixin):
    def __init__(
            self,
            initial_step: _STEP_TYPE,
            interval: _INTERVAL_TYPE,
            max_step: _STEP_TYPE = None,
            agents: Iterable[Agent] = None,
            seed: int = None
        ) -> None:
        super().__init__(initial_step, interval, max_step, seed)
        super().__init_agents__(agents)

    def step(self):
        if self.parent is None:
            self._current_step = self._next_step
        else:
            self._current_step = self.parent.current_step()

        for agent in self._agents:
            next_step = agent._next_step
            if next_step is not None \
                    and next_step <= self._current_step:
                agent.step()

        self._next_step = self.get_next_step()
        return self._current_step, self._next_step
