from __future__ import annotations

import uuid
from typing import Any, Dict, Iterable, TYPE_CHECKING

from .clock import StepMixin
from .random import RandomGeneratorMixin

if TYPE_CHECKING:
    from .environment import Environment


class Agent(StepMixin, RandomGeneratorMixin):
    def __init__(self, seed: int = None) -> None:
        self._id = uuid.uuid4().int
        self.community: Community = None

        self.__init_step__()
        self.__init_rng__(seed)

    @property
    def id(self) -> int:
        return self._id

    def other_agents(self, env: Environment) -> Iterable[Agent]:
        agents = env.agents.copy()
        if self._id not in agents:
            raise IndexError(f"Agent '{self._id}' is not added yet in the environment.")

        del agents[self._id]
        return agents.values()

    def step(self, env: Environment) -> Any:
        self._step_count += 1
        self._last_step = env.last_step()
        return self.calculate_next_step(env)

    def calculate_next_step(self, env: Environment) -> Any:
        return env.next_step()


class MultiAgentMixin(StepMixin):
    def __init_agents__(self, agents: Iterable[Agent]) -> None:
        self.__init_step__()

        self._agents: Dict[int, Agent] = dict()
        self.add_agents(agents)

    def agents(self) -> Iterable[Agent]:
        for agent in self._agents.values():
            yield agent

    def add_agent(self, agent: Agent) -> None:
        if agent.id in self._agents:
            print(self.agents)
            raise IndexError(f"Agent '{agent.id}' is already in the community.")

        self._agents[agent.id] = agent
        agent.community = self
        agent._next_step = self.last_step()

    def add_agents(self, agents: Iterable[Agent]) -> None:
        for agent in agents:
            self.add_agent(agent)

    def remove_agent(self, agent: Agent) -> None:
        if agent.id not in self._agents:
            raise IndexError()

        del self._agents[agent.id]

    def remove_agents(self, agents: Iterable[Agent]) -> None:
        for agent in agents:
            self.remove_agent(agent)


class Community(Agent, MultiAgentMixin):
    def __init__(
            self,
            agents: Iterable[Agent] = None,
            seed: int = None
        ) -> None:
        super().__init__(seed=seed)
        self.__init_agents__(agents)

    def step(self, env: Environment) -> Any:
        current_step = env.last_step()
        for agent in self._agents.values():
            next_step_ = agent.next_step()
            if next_step_ is not None \
                    and next_step_ >= current_step:
                agent._next_step = agent.step(env=env)

        return self.calculate_next_step(env)

    def calculate_next_step(self, env: Environment) -> Any:
        next_step = env.next_step()
        for agent in self._agents.values():
            next_step_ = agent.next_step()

            if next_step_ < next_step:
                next_step = next_step_

        return next_step
