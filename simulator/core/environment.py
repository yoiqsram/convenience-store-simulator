from __future__ import annotations

import abc
import asyncio
from datetime import datetime, timedelta
from typing import Iterable, Tuple, Union

from ._base import RandomGeneratorMixin, ReprMixin, StepMixin, DatetimeStepMixin, _STEP_TYPE, _INTERVAL_TYPE
from .agent import Agent, MultiAgentMixin


class BaseEnvironment(StepMixin, MultiAgentMixin, RandomGeneratorMixin, ReprMixin, metaclass=abc.ABCMeta):
    __repr_attrs__ = ( 'n_agents', 'current_step' )

    def __init__(
            self,
            initial_step: _STEP_TYPE,
            interval: _INTERVAL_TYPE,
            max_step: _STEP_TYPE = None,
            agents: Iterable[Agent] = None,
            seed: int = None
        ) -> None:
        super().__init_step__(initial_step, interval, max_step)
        super().__init_agents__(agents)
        super().__init_rng__(seed)

    def step(self) -> Tuple[_STEP_TYPE, Union[_STEP_TYPE, None]]:
        current_step, next_step = super().step()

        for agent in self._agents:
            agent_next_step = agent.next_step()
            if agent_next_step is not None \
                    and agent_next_step <= current_step:
                agent.step(env=self)

        return current_step, next_step

    @abc.abstractmethod
    def run(self, *args, **kwargs) -> None: ...


class Environment(BaseEnvironment):
    def __init__(
            self,
            initial_step: int = 0,
            interval: int = 1,
            max_step: int = None,
            agents: Iterable[Agent] = None,
            seed: int = None
        ) -> None:
        super().__init__(
            initial_step,
            interval,
            max_step,
            agents,
            seed
        )

    def step(self) -> Tuple[int, Union[int, None]]:
        return super().step()

    def run(self) -> None:
        next_step = self.next_step()
        while next_step is not None:
            _, next_step = self.step()


class DatetimeEnvironment(BaseEnvironment, DatetimeStepMixin, ReprMixin):
    __repr_attrs__ = ( 'n_agents', 'curent_datetime' )

    def __init__(
            self,
            initial_datetime: datetime,
            interval: float,
            speed: float,
            max_datetime: datetime = None,
            agents: Iterable[Agent] = None,
            seed: int = None
        ) -> None:
        super().__init__(
            initial_step=initial_datetime,
            interval=interval,
            max_step=max_datetime,
            agents=agents,
            seed=seed
        )
        self.speed = speed

        self._real_init_datetime = datetime.now()

    def total_time_elapsed(self) -> timedelta:
        return self._calculate_interval(self._initial_step, self._current_step)

    def total_real_time_elapsed(self) -> timedelta:
        return datetime.now() - self._real_init_datetime

    def step(self) -> Tuple[datetime, Union[datetime, None]]:
        return super().step()

    def run(self):
        current_datetime = self.current_datetime()
        next_datetime = self.next_datetime()
        while next_datetime is not None:
            interval = (next_datetime - current_datetime).total_seconds()
            delay = max(0.0, interval / self.speed)

            current_datetime, next_datetime = asyncio.run(self._step_await(delay))

    async def _step_await(self, delay: float) -> Tuple[datetime, Union[datetime, None]]:
        delay_task = asyncio.create_task(asyncio.sleep(delay))
        current_datetime, next_datetime = self.step()
        await delay_task
        return current_datetime, next_datetime
