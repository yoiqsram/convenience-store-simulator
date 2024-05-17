import abc
from datetime import date, datetime, timedelta
from typing import Any, Tuple, Union

from ._base import ReprMixin


class StepMixin(metaclass=abc.ABCMeta):
    def __init_step__(
            self,
            initial_step,
            next_step,
            max_step = None
        ) -> None:
        self._step_count = 0
        self._last_step = initial_step
        self._next_step = next_step
        self._max_step = max_step

    def step_count(self) -> int:
        return self._step_count

    def max_step(self) -> Any:
        return self._max_step

    def last_step(self) -> Any:
        return self._last_step

    def next_step(self) -> Any:
        return self._next_step

    @abc.abstractmethod
    def step(self, **kwargs) -> Tuple[Any, Any]: ...

    @abc.abstractmethod
    def calculate_next_step(self, last_step: Any, max_step: Any, **kwargs) -> Any: ...


class DatetimeStepMixin(StepMixin):
    def max_datetime(self) -> Union[datetime, None]:
        return self._max_step

    def max_date(self) -> Union[date, None]:
        max_step = self.max_step()
        if isinstance(max_step, datetime):
            return max_step.date()

    def last_datetime(self) -> Union[datetime, None]:
        return self.last_step()

    def last_date(self) -> Union[date, None]:
        last_step = self.last_step()
        if isinstance(last_step, datetime):
            return last_step.date()

    def next_datetime(self) -> Union[datetime, None]:
        return self.next_step()

    def next_date(self) -> Union[date, None]:
        next_step = self.next_step()
        if isinstance(next_step, datetime):
            return self._next_step.date()


class Clock(StepMixin, ReprMixin):
    __repr_attrs__ = ( 'last_step', 'next_step', 'max_step' )

    def __init__(
            self,
            initial_step,
            max_step = None
        ) -> None:
        self.__init_step__(
            initial_step,
            self.calculate_next_step(initial_step, max_step),
            max_step
        )

    def step(self) -> Any:
        self._step_count += 1
        self._last_step = self._next_step

        if self._last_step is None:
            raise StopIteration()

        self._next_step = self.calculate_next_step(self._last_step, self._max_step)
        return self._last_step, self._next_step


class StepClock(Clock):
    def __init__(
            self,
            initial_step: int = None,
            max_step: int = None
        ) -> None:
        initial_step = initial_step if initial_step is not None else 0
        super().__init__(initial_step, max_step)

    def calculate_next_step(self, last_step: int, max_step: Union[int, None]) -> int:
        next_step = last_step + 1
        if max_step is not None \
                and next_step > max_step:
            return None

        return next_step


class DatetimeClock(Clock, DatetimeStepMixin):
    __repr_attrs__ = ( 'interval', 'speed', 'last_datetime', 'next_datetime', 'max_datetime' )

    def __init__(
            self,
            interval: float = 1.0,
            speed: float = None,
            initial_datetime: datetime = None,
            max_datetime: datetime = None
        ) -> None:
        self.interval = interval
        self.speed = speed if speed is not None else 1

        if initial_datetime is None:
            initial_datetime = datetime.now()
        super().__init__(initial_datetime, max_datetime)

    def calculate_next_step(self, last_step: datetime, max_step: Union[datetime, None]) -> datetime:
        next_step = last_step + timedelta(seconds=self.interval)
        if max_step is not None \
                and next_step > max_step:
            return None

        return next_step


class FPSClock(DatetimeClock):
    __repr_attrs__ = ( 'fps', 'last_step', 'next_step', 'max_frames' )

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
