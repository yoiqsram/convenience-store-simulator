from __future__ import annotations

import abc
import time
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
        self._current_step = self._next_step

        for agent in self._agents:
            next_step = agent._next_step
            if next_step is not None \
                    and next_step <= self._current_step:
                agent.step()

        self._next_step = self.get_next_step()
        return self._current_step, self._next_step

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

    @property
    def step_delay(self) -> int:
        return self._interval.total_seconds() / self.speed

    def total_time_elapsed(self) -> timedelta:
        return self._calculate_interval(self._initial_step, self._current_step)

    def total_real_time_elapsed(self) -> timedelta:
        return datetime.now() - self._real_init_datetime

    def step(self) -> Tuple[datetime, Union[datetime, None]]:
        return super().step()

    def run(self):
        next_datetime = self.next_datetime()
        while next_datetime is not None:
            _, next_datetime = self.step_await()

    def step_await(self) -> Tuple[datetime, Union[datetime, None]]:
        start_datetime = datetime.now()
        current_datetime, next_datetime = self.step()

        elapsed_seconds = (datetime.now() - start_datetime).total_seconds()
        await_seconds = self.step_delay - elapsed_seconds
        if await_seconds > 0:
            time.sleep(await_seconds)

        return current_datetime, next_datetime
