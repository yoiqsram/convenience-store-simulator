from __future__ import annotations

import abc
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Tuple, Union

from ._base import (
    RandomGeneratorMixin, ReprMixin, DatetimeStepMixin, RandomDatetimeStepMixin,
    _STEP_TYPE, _INTERVAL_TYPE, cast
)
from .agent import Agent, MultiAgentStepMixin


class BaseEnvironment(MultiAgentStepMixin, RandomGeneratorMixin, ReprMixin, metaclass=abc.ABCMeta):
    __repr_attrs__ = ( 'n_agents', 'current_step' )

    def __init__(
            self,
            initial_step: _STEP_TYPE,
            interval: _INTERVAL_TYPE,
            max_step: _STEP_TYPE = None,
            skip_step: bool = False,
            agents: Iterable[Agent] = None,
            seed: int = None
        ) -> None:
        super().__init_rng__(seed)
        super().__init_step__(initial_step, interval, max_step)
        super().__init_agents__(agents, skip_step)

    @abc.abstractmethod
    def run(self, interval: _INTERVAL_TYPE = None, *args, **kwargs) -> None: ...


class Environment(BaseEnvironment):
    def __init__(
            self,
            initial_step: Union[int, float] = 0,
            interval: Union[int, float] = 1,
            max_step: Union[int, float] = None,
            agents: Iterable[Agent] = None,
            seed: int = None
        ) -> None:
        if isinstance(initial_step, float) \
                or isinstance(interval, float):
            type_ = float
        else:
            type_ = int

        super().__init__(
            initial_step=cast(initial_step, type_),
            interval=cast(interval, type_),
            max_step=cast(max_step, type_),
            skip_step=False,
            agents=agents,
            sed=seed
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
    __repr_attrs__ = ( 'n_agents', 'current_datetime' )

    def __init__(
            self,
            initial_datetime: datetime,
            interval: _INTERVAL_TYPE,
            speed: float = 1.0,
            max_datetime: datetime = None,
            skip_step: bool = False,
            agents: Iterable[Agent] = None,
            seed: int = None
        ) -> None:
        super().__init__(
            initial_step=initial_datetime,
            interval=interval,
            max_step=max_datetime,
            skip_step=skip_step,
            agents=agents,
            seed=seed
        )
        self.speed = speed

        self._real_initial_datetime: datetime = None

    @property
    def step_delay(self) -> float:
        next_step = self.next_step()
        if next_step is None:
            return

        interval = (next_step - self.current_step()) if self.skip_step else self._interval
        return interval.total_seconds() / self.speed

    def total_real_time_elapased(self) -> timedelta:
        if self._real_initial_datetime is None:
            raise ValueError(
                'Environment has not been run or through at least one step yet.'
            )

        return datetime.now() - self._real_initial_datetime

    def step(self, *args, **kwargs) -> Tuple[datetime, Union[datetime, None]]:
        if self._real_initial_datetime is None:
            self._real_initial_datetime = datetime.now()

        return super().step(*args, **kwargs)

    def step_await(
            self,
            sync: bool,
            *args,
            **kwargs
        ) -> Tuple[datetime, Union[datetime, None]]:
        real_start_datetime = datetime.now()
        current_datetime, next_datetime = self.step(*args, **kwargs)

        real_current_datetime = datetime.now()
        speed_adjusted_real_current_datetime = real_current_datetime
        if self.speed != 1.0:
            speed_adjusted_real_current_datetime = (
                self._real_initial_datetime
                + self.speed * (real_current_datetime - self._real_initial_datetime)
            )
        if sync and next_datetime is not None \
                and next_datetime > speed_adjusted_real_current_datetime:
            elapsed_seconds = (real_current_datetime - real_start_datetime).total_seconds()
            await_seconds = self.step_delay - elapsed_seconds
            if await_seconds > 0:
                time.sleep(await_seconds)

        return current_datetime, next_datetime

    def run(
            self,
            sync: bool = True,
            max_datetime: _STEP_TYPE = None,
            skip_step: bool = None,
            *args,
            **kwargs
        ) -> None:
        if skip_step is not None:
            _skip_step = self.skip_step
            self.skip_step = skip_step

        next_step = self.next_step()
        while next_step is not None \
                and (
                    max_datetime is None
                    or next_step > max_datetime
                ):
            _, next_step = self.step_await(sync=sync, *args, **kwargs)

        if skip_step is not None:
            self.skip_step = _skip_step


class RandomDatetimeEnvironment(DatetimeEnvironment, RandomDatetimeStepMixin):
    def __init__(
            self,
            initial_datetime: datetime,
            interval: Tuple[_INTERVAL_TYPE, Tuple[_INTERVAL_TYPE, _INTERVAL_TYPE]],
            speed: float = 1.0,
            max_datetime: datetime = None,
            skip_step: bool = False,
            agents: Iterable[Agent] = None,
            seed: int = None
        ) -> None:
        super().__init__(
            initial_datetime=initial_datetime,
            interval=interval,
            speed=speed,
            max_datetime=max_datetime,
            skip_step=skip_step,
            agents=agents,
            seed=seed
        )
