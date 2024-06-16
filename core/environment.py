from __future__ import annotations

import numpy as np
from abc import abstractmethod
from datetime import datetime, timedelta
from time import time, sleep

from ._base import DateTimeStepMixin, _STEP_TYPE
from .agent import Agent, MultiAgent
from .utils import cast


class BaseEnvironment(
        MultiAgent,
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
            skip_step,
            agents,
            seed,
            rng
        )

    @abstractmethod
    def run(self, *args, **kwargs) -> None: ...


class Environment(BaseEnvironment):
    def __init__(
            self,
            initial_step: int | float = 0,
            interval: int | float = 1,
            max_step: int | float = 0,
            skip_step: bool = False,
            agents: list[Agent] = None,
            seed: int = None,
            rng: np.random.RandomState = None
            ) -> None:
        super().__init__(
            initial_step,
            max_step,
            interval,
            skip_step,
            agents,
            seed,
            rng
        )

    def run(self, *args, **kwargs) -> None:
        done = self.next_step >= self.max_step
        while not done:
            _, _, done = self.step(*args, **kwargs)


class DateTimeEnvironment(
        BaseEnvironment,
        DateTimeStepMixin,
        repr_attrs=('n_agents', 'current_datetime', 'interval', 'speed')
        ):
    def __init__(
            self,
            initial_datetime: datetime = None,
            max_datetime: datetime = None,
            interval: float = 1.,
            speed: float = 1.,
            skip_step: bool = False,
            agents: list[Agent] = None,
            seed: int = None,
            rng: np.random.RandomState = None
            ) -> None:
        super().__init__(
            cast(initial_datetime or time(), float),
            cast(max_datetime or 0, float),
            interval,
            skip_step,
            agents,
            seed,
            rng
        )

        self.speed = speed
        self._real_initial_timestamp: float | None = None

    @property
    def step_delay(self) -> float:
        next_step = self.next_step
        if self.skip_step:
            interval = self._interval
        else:
            interval = (next_step - self.current_step)
        return interval / self.speed

    def total_real_seconds(self) -> timedelta:
        if self._real_initial_timestamp is None:
            raise ValueError(
                'Environment has not been run '
                'or through at least one step yet.'
            )
        return time() - self._real_initial_timestamp

    def step(self, *args, **kwargs) -> tuple[np.uint32, np.uint32, bool]:
        if self._real_initial_timestamp is None:
            self._real_initial_timestamp = time()
        return super().step(*args, **kwargs)

    def step_await(
            self,
            sync: bool,
            *args,
            **kwargs
            ) -> tuple[np.uint32, np.uint32, bool]:
        real_current_timestamp = time()
        current_step, next_step, done = self.step(*args, sync=sync, **kwargs)

        adjusted_real_current_timestamp = (
            self._real_initial_timestamp
            + (real_current_timestamp - self._real_initial_timestamp)
            * self.speed
        )
        if sync and next_step > adjusted_real_current_timestamp:
            wait_seconds = (next_step - current_step) / self.speed
            wait_seconds -= time() - adjusted_real_current_timestamp
            if wait_seconds > 0:
                sleep(wait_seconds)

        return current_step, next_step, done

    def run(
            self,
            sync: bool = True,
            max_datetime: datetime = None,
            *args,
            **kwargs
            ) -> None:
        max_step = cast(max_datetime, float)
        done = self.next_step >= max_step
        while not done:
            _, next_step, done = self.step_await(sync=sync, *args, **kwargs)
            if max_step is not None:
                done |= next_step >= max_step
