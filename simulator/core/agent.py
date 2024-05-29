from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple, Union, TYPE_CHECKING

from ._base import (
    RandomGeneratorMixin, ReprMixin, SuperclassMixin, StepMixin,
    _STEP_TYPE, _INTERVAL_TYPE
)
from .restore import RestorableMixin

if TYPE_CHECKING:
    from .environment import BaseEnvironment


class Agent(
        RestorableMixin, SuperclassMixin,
        StepMixin, RandomGeneratorMixin, ReprMixin,
        repr_attrs=( 'current_step', )
    ):
    def __init__(
            self,
            initial_step: _STEP_TYPE = 0,
            interval: _INTERVAL_TYPE = 1,
            max_step: _STEP_TYPE = None,
            seed: int = None
        ) -> None:
        self.parent: Union[MultiAgent, BaseEnvironment, None] = None

        super().__init_step__(initial_step, interval, max_step)
        super().__init_rng__(seed)

    def other_agents(self) -> Iterable[Agent]:
        if self.parent is None:
            raise IndexError()

        for agent in self.parent.agents():
            if agent != self:
                yield agent

    def get_next_step(self, current_step: _STEP_TYPE) -> Union[_STEP_TYPE, None]:
        next_step = super().get_next_step(current_step)

        if next_step is not None \
                and self.parent is not None:
            parent_next_step = self.parent.next_step()
            if next_step < parent_next_step:
                return parent_next_step

        return next_step

    def step(self, *args, **kwargs) -> Tuple[_STEP_TYPE, Union[_STEP_TYPE, None]]:
        current_step, next_step = super().step(*args, **kwargs)

        if self.parent is not None:
            current_step = self.parent.current_step()
            self._current_step = current_step

        return current_step, next_step

    @property
    def restore_attrs(self) -> Dict[str, Any]:
        return {
            'initial_step': self._initial_step,
            'interval': self._interval,
            'max_step': self._max_step,
            'next_step': self._next_step,
            'rng_state': self.dump_rng_state()
        }

    def _pull_restore(self, attrs: Dict[str, Any]) -> None:
        self._initial_step = attrs['initial_step']
        self.interval = attrs['interval']
        self._max_step = attrs['max_step']
        self._next_step = attrs['next_step']
        self.load_rng_state(attrs['rng_state'])


class MultiAgentStepMixin(StepMixin):
    def __init_agents__(
            self,
            agents: Iterable[Agent] = None,
            skip_step: bool = False
        ) -> None:
        self._agents: List[Agent] = agents if agents is not None else []
        self._skip_step = skip_step

        self._rc = False
        '''Whether step is in racing condition, where agent step is increase while this multi agent hasn't.'''

    @property
    def skip_step(self) -> bool:
        return self._skip_step

    @skip_step.setter
    def skip_step(self, value: bool) -> bool:
        self._skip_step = value
        for agent in self.agents():
            if isinstance(agent, MultiAgentStepMixin):
                agent.skip_step = self._skip_step

    @property
    def n_agents(self) -> int:
        return len(self._agents)

    def agents(self) -> Iterable[Agent]:
        for agent in self._agents:
            yield agent

    def add_agent(self, agent: Agent) -> None:
        self._agents.append(agent)
        agent.parent = self
        if isinstance(agent, MultiAgentStepMixin):
            agent.skip_step = self.skip_step

    def add_agents(self, agents: Iterable[Agent]) -> None:
        for agent in agents:
            self.add_agent(agent)

    def remove_agent(self, agent: Agent) -> None:
        self._agents.remove(agent)

    def remove_agents(self, agents: Iterable[Agent]) -> None:
        for agent in agents:
            self.remove_agent(agent)

    def current_step(self) -> _STEP_TYPE:
        return super().current_step() if not self._rc else super().next_step()

    def next_step(self) -> Union[_STEP_TYPE, None]:
        next_step = super().next_step()
        if not self._rc:
            return next_step

        return super().get_next_step(next_step)

    def get_next_step(self, current_step: _STEP_TYPE) -> Union[_STEP_TYPE, None]:
        next_step = super().get_next_step(current_step)
        if not self._skip_step \
                or next_step is None:
            return next_step

        min_agent_next_step = None
        for agent in self.agents():
            agent_next_step = agent.next_step()
            if min_agent_next_step is None \
                or agent_next_step < min_agent_next_step:
                min_agent_next_step = agent_next_step

        if min_agent_next_step is None \
                or min_agent_next_step > next_step:
            return min_agent_next_step

        return next_step

    def step(self, *args, **kwargs) -> Tuple[_STEP_TYPE, Union[_STEP_TYPE, None]]:
        self._rc = True

        _, next_step = super().step(*args, **kwargs)
        if next_step is not None:
            for agent in self.agents():
                agent_next_step = agent.next_step()
                if agent_next_step is not None \
                        and agent_next_step <= next_step:
                    agent.step()

        self._rc = False
        return super().step(*args, **kwargs)


class MultiAgent(
        Agent,
        MultiAgentStepMixin,
        repr_attrs=( 'n_agents', 'current_step' )
    ):
    def __init__(
            self,
            initial_step: _STEP_TYPE = 0,
            interval: _INTERVAL_TYPE = 1,
            max_step: _STEP_TYPE = None,
            skip_step: bool = False,
            agents: Iterable[Agent] = None,
            seed: int = None
        ) -> None:
        super().__init__(initial_step, interval, max_step, seed)
        super().__init_agents__(agents, skip_step)

    def add_agent(self, agent: Agent) -> None:
        super().add_agent(agent)

    def remove_agent(self, agent: Agent) -> None:
        super().remove_agent(agent)

    @property
    def restore_attrs(self) -> Dict[str, Any]:
        attrs = super().restore_attrs
        attrs['agent_restore_files'] = [
            {
                'type': type(agent).__name__,
                'restore_file': agent.restore_file
            }
            for agent in self.agents()
        ]
        attrs['skip_step'] = self._skip_step
        return attrs

    def _pull_restore(self, attrs: Dict[str, Any]) -> None:
        super()._pull_restore(attrs)

        self._skip_step = attrs['skip_step']
        self._agents: List[Agent] = [
            Agent.__subclasses__[agent_restore_data['type']]
                .restore(agent_restore_data['restore_file'])
            for agent_restore_data in attrs['agent_restore_files']
        ]
