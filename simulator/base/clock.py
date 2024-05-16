import abc
from datetime import datetime, timedelta
from typing import Any


class StepMixin(metaclass=abc.ABCMeta):
    def __init_step__(self) -> None:
        self._step_count = 0
        self._last_step = None
        self._next_step = None
        self._max_step = None

    def step_count(self) -> int:
        return self._step_count

    def max_step(self) -> Any:
        return self._max_step

    def last_step(self) -> Any:
        return self._last_step

    def next_step(self) -> Any:
        return self._next_step

    @abc.abstractmethod
    def step(self, *args, **kwargs) -> Any: ...

    @abc.abstractmethod
    def calculate_next_step(self, *args, **kwargs) -> Any: ...


class Clock(StepMixin):
    def __init__(self) -> None:
        self.__init_step__()

    def step(self) -> Any:
        self._step_count += 1

        if self._max_step is not None \
                and self._last_step >= self._max_step:
            raise StopIteration()

        self._last_step = self.calculate_next_step()
        return self._last_step


class StepClock(Clock):
    def __init__(self, max_step = None) -> None:
        super().__init__()

        self._last_step = self._step_count
        self._max_step = max_step

    def calculate_next_step(self) -> int:
        next_step = self._step_count + 1
        if self._max_step is not None \
                and next_step > self._max_step:
            return None

        return next_step


class DatetimeClock(Clock):
    def __init__(
            self,
            interval: float = 1.0,
            speed: float = None,
            initial_datetime: datetime = None,
            max_datetime: datetime = None
        ) -> None:
        super().__init__()

        if initial_datetime is None:
            initial_datetime = datetime.now()
        self._last_step = initial_datetime
        self._max_step = max_datetime

        self.interval = interval
        self.speed = speed if speed is not None else 1

    def calculate_next_step(self) -> datetime:
        next_step = self._last_step + timedelta(seconds=self.interval)
        if self._max_step is not None \
                and next_step > self._max_step:
            return None

        return next_step


class FPSClock(DatetimeClock):
    def __init__(
            self,
            fps: float = 30.0,
            max_frames: int = None
        ) -> None:
        interval = 1 / fps

        if initial_datetime is None:
            initial_datetime = datetime.now()

        max_datetime = None
        if max_frames is not None:
            max_datetime = initial_datetime + timedelta(seconds=max_frames * interval)

        super().__init__(
            interval=interval,
            initial_datetime=initial_datetime,
            max_datetime=max_datetime
        )
