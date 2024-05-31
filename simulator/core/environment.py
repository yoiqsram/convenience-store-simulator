from __future__ import annotations

import time
from abc import abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, Tuple, Union

from ._base import (
    DatetimeStepMixin, RandomDatetimeStepMixin,
    _STEP_TYPE, _INTERVAL_TYPE, _OPTIONAL_INTERVAL_TYPE,
    cast
)
from .agent import Agent, MultiAgent


class BaseEnvironment(
        MultiAgent,
        repr_attrs=('n_agents', 'current_step')
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
        super().__init__(
            initial_step,
            interval,
            max_step,
            skip_step,
            agents,
            seed
        )

    @abstractmethod
    def run(self, workers: int = 0, *args, **kwargs) -> None: ...


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
        start_step = self.current_step
        next_step = self.next_step
        while next_step is not None \
                and (
                    interval is None
                    or next_step - start_step <= interval
                ):
            _, next_step = self.step(*args, **kwargs)


class DatetimeEnvironment(
        BaseEnvironment,
        DatetimeStepMixin,
        repr_attrs=('n_agents', 'current_datetime', 'interval', 'speed')
        ):
    def __init__(
            self,
            initial_datetime: datetime = None,
            interval: _INTERVAL_TYPE = 1,
            speed: float = 1.0,
            max_datetime: datetime = None,
            skip_step: bool = False,
            agents: Iterable[Agent] = None,
            seed: int = None
            ) -> None:
        if initial_datetime is None:
            initial_datetime = datetime.now()

        super().__init__(
            initial_step=cast(initial_datetime, float),
            interval=cast(interval, float),
            max_step=cast(max_datetime, float),
            skip_step=skip_step,
            agents=agents,
            seed=seed
        )
        self.speed = speed

        self._real_initial_datetime: datetime = None

    @property
    def step_delay(self) -> float:
        next_step = self.next_step
        if next_step is None:
            return

        if self.skip_step:
            interval = self._interval
        else:
            interval = (next_step - self.current_step)
        return interval / self.speed

    def total_real_time_elapased(self) -> timedelta:
        if self._real_initial_datetime is None:
            raise ValueError(
                'Environment has not been run '
                'or through at least one step yet.'
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
        current_step, next_step = self.step(*args, **kwargs)
        next_datetime = cast(next_step, datetime)

        real_current_datetime = datetime.now()
        speed_adjusted_real_current_datetime = real_current_datetime
        if self.speed != 1.0:
            speed_adjusted_real_current_datetime = (
                self._real_initial_datetime
                + self.speed * (
                    real_current_datetime - self._real_initial_datetime
                )
            )
        if sync and next_datetime is not None \
                and next_datetime > speed_adjusted_real_current_datetime:
            elapsed_seconds = (
                real_current_datetime - real_start_datetime
                ).total_seconds()
            await_seconds = self.step_delay - elapsed_seconds
            if await_seconds > 0:
                time.sleep(await_seconds)

        return current_step, next_step

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

        next_datetime = self.next_datetime
        while next_datetime is not None \
                and (
                    max_datetime is None
                    or max_datetime >= next_datetime
                ):
            _, next_step = self.step_await(sync=sync, *args, **kwargs)
            next_datetime = cast(next_step, datetime)

        if skip_step is not None:
            self.skip_step = _skip_step

    @property
    def restore_attrs(self) -> Dict[str, Any]:
        attrs = super().restore_attrs
        attrs['base_params'].append(self.speed)
        attrs['real_initial_datetime'] = self._real_initial_datetime
        attrs['rng_state'] = self.dump_rng_state()
        return attrs

    def _pull_restore(self, attrs: Dict[str, Any]) -> None:
        (
            self._initial_step,
            self.interval,
            self._max_step,
            self._next_step,
            self._skip_step,
            self.speed
        ) = attrs['base_params']
        self._real_initial_datetime = attrs['real_initial_datetime']
        self.load_rng_state(attrs['rng_state'])


class RandomDatetimeEnvironment(
        DatetimeEnvironment,
        RandomDatetimeStepMixin
        ):
    def __init__(
            self,
            initial_datetime: datetime = None,
            interval: _OPTIONAL_INTERVAL_TYPE = 1,
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
