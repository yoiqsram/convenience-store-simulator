import abc
from datetime import datetime, timedelta
from typing import Any


class Clock(metaclass=abc.ABCMeta):
    @property
    def max_step(self) -> Any:
        return self._max_step

    def current_step(self) -> datetime:
        return self._step

    @abc.abstractmethod
    def next_step(self) -> Any: ...

    def step(self) -> None:
        if self._max_step is not None \
                and self._step >= self._max_step:
            raise IndexError()

        self._step = self.next_step()


class StepClock(Clock):
    def __init__(self, max_step = None) -> None:
        self._step = 0
        self._max_step = max_step

    def next_step(self) -> int:
        next_step = self.step + 1
        if self._max_step is not None \
                and next_step >= self._max_step:
            return None

        return next_step


class DatetimeClock(Clock):
    def __init__(
            self,
            interval: float = 1,
            speed: float = None,
            initial_datetime: datetime = None,
            max_datetime: datetime = None
        ) -> None:
        self.interval = interval
        self.speed = speed if speed is not None else 1

        if initial_datetime is None:
            initial_datetime = datetime.now()
        self._step = initial_datetime
        self._max_step = max_datetime

    def next_step(self) -> datetime:
        next_step = self._step + timedelta(seconds=self.interval)
        if self._max_step is not None \
                and next_step >= self._max_step:
            return None

        return next_step
