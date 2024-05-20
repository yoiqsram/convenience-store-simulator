from __future__ import annotations

import abc
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Tuple, Union

from ._base import (
    RandomGeneratorMixin, ReprMixin, DatetimeStepMixin,
    _STEP_TYPE, _INTERVAL_TYPE, cast_interval
)
from .agent import Agent, MultiAgentStepMixin


class BaseEnvironment(MultiAgentStepMixin, RandomGeneratorMixin, ReprMixin, metaclass=abc.ABCMeta):
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

    @abc.abstractmethod
    def run(self, interval: _INTERVAL_TYPE = None, *args, **kwargs) -> None: ...


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

    def run(self, interval: int = None, *args, **kwargs) -> None:
        start_step = self.current_step()
        next_step = self.next_step()
        while next_step is not None \
                and (
                    interval is None
                    or next_step - start_step <= interval
                ):
            _, next_step = self.step(*args, **kwargs)


class DatetimeEnvironment(BaseEnvironment, DatetimeStepMixin, ReprMixin):
    __repr_attrs__ = ( 'n_agents', 'curent_datetime' )

    def __init__(
            self,
            initial_datetime: datetime,
            speed: float,
            interval: float,
            max_datetime: datetime = None,
            skip_step: bool = False,
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
        self.skip_step = skip_step

        self._real_init_datetime = datetime.now()

    @property
    def step_delay(self) -> float:
        next_step = self.next_step()
        if next_step is None:
            return

        interval = (next_step - self.current_step()) if self.skip_step else self._interval
        return interval.total_seconds() / self.speed

    def total_time_elapsed(self) -> timedelta:
        return self._calculate_interval(self._initial_step, self._current_step)

    def total_real_time_elapsed(self) -> timedelta:
        return datetime.now() - self._real_init_datetime

    def step(self, *args, **kwargs) -> Tuple[datetime, Union[datetime, None]]:
        return super().step(*args, **kwargs)

    def run(
            self,
            interval: _STEP_TYPE = None,
            sync: bool = True,
            *args,
            **kwargs
        ) -> None:
        if interval is not None:
            interval = cast_interval(interval, timedelta)

        start_step = self.current_step()
        next_step = self.next_step()
        while next_step is not None \
                and (
                    interval is None
                    or next_step - start_step <= interval
                ):
            if sync:
                _, next_step = self.step_await(*args, **kwargs)
            else:
                _, next_step = self.step(*args, **kwargs)

    def step_await(self, *args, **kwargs) -> Tuple[datetime, Union[datetime, None]]:
        start_datetime = datetime.now()
        current_datetime, next_datetime = self.step(*args, **kwargs)

        if next_datetime is not None:
            elapsed_seconds = (datetime.now() - start_datetime).total_seconds()
            await_seconds = self.step_delay - elapsed_seconds
            if await_seconds > 0:
                time.sleep(await_seconds)

        return current_datetime, next_datetime

    @classmethod
    def load(cls, path: Path) -> DatetimeEnvironment:
        super().load(path)
