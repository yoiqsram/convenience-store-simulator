import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Tuple, Union

_STEP_TYPE = Union[int, datetime]
_INTERVAL_TYPE = Union[int, float, timedelta]


class IdentityMixin:
    def __init_id__(self) -> None:
        self._id = int(uuid.uuid4())

    @property
    def id(self) -> int:
        return self._id


class RandomGeneratorMixin:
    def __init_rng__(self, seed: int = None):
        from numpy.random import RandomState

        self._rng = RandomState(seed)

    def random_seed(
            self,
            size: int,
            maxlen: int = 6
        ) -> List[int]:
        return [ int(num) for num in self._rng.random(size) * int('1' + '0' * maxlen) ]


class ReprMixin:
    __repr_attrs__: Tuple[str]

    def __repr__(self) -> str:
        kwargs: Dict[str, str] = dict()
        for identifier in self.__class__.__repr_attrs__:
            attr = getattr(self, identifier)
            if callable(attr):
                attr = attr()

            kwargs[identifier] = attr

        return f"{self.__class__.__name__}({', '.join([f'{k}={v}' for k, v in kwargs.items()])})"


def cast_interval(value: Any, interval_type: type) -> _INTERVAL_TYPE:
    if interval_type == type(value):
        return value

    elif interval_type is timedelta \
            and (isinstance(value, int) or isinstance(value, float)):
        return timedelta(seconds=value)

    raise TypeError(f"Failed to cast value '{value}' to interval type '{interval_type.__name__}'.")


class StepMixin:
    def __init_step__(
            self,
            initial_step: _STEP_TYPE,
            interval: _INTERVAL_TYPE,
            max_step: _STEP_TYPE = None
        ) -> None:
        self._initial_step = initial_step
        self._max_step = max_step
        self._interval = interval

        self._current_step = self._initial_step
        self._next_step = self._initial_step + self._interval

    def _calculate_interval(
            self,
            a_step: _STEP_TYPE,
            b_step: _STEP_TYPE
        ) -> _INTERVAL_TYPE:
        if isinstance(self._current_step, int) \
                or isinstance(self._current_step, float):
            return b_step - a_step

        elif isinstance(self._current_step, datetime) \
                and isinstance(self._interval, timedelta) \
                and isinstance(a_step, datetime) \
                and isinstance(b_step, datetime):
            return (b_step - a_step).total_seconds()

        else:
            raise ValueError(f"Faild to calculate interval between {repr(a_step)} and {repr(b_step)}.")

    def _count_steps(
            self,
            a_step: _STEP_TYPE,
            b_step: _STEP_TYPE
        ) -> int:
        interval = self._calculate_interval(a_step, b_step)
        return int(interval)

    @property
    def interval(self) -> Any:
        return self._interval

    @interval.setter
    def interval(self, value: Any) -> None:
        self._interval = cast_interval(value, type(self._interval))

    @property
    def initial_step(self) -> _STEP_TYPE:
        return self._initial_step

    @property
    def max_step(self) -> Union[_STEP_TYPE, None]:
        return self._max_step

    @property
    def max_steps(self) -> Union[int, None]:
        if self._max_step is not None:
            return self._count_steps(self._initial_step, self._max_step)

    @property
    def steps(self) -> int:
        return self._count_steps(self._initial_step, self._current_step)

    def current_step(self) -> _STEP_TYPE:
        return self._current_step

    def next_step(self) -> _STEP_TYPE:
        return self._next_step

    def step(self, *args, **kwargs) -> Tuple[_STEP_TYPE, Union[_STEP_TYPE, None]]:
        self._current_step = self._next_step
        if self._current_step is None:
            raise StopIteration()

        self._next_step = self.get_next_step(*args, **kwargs)
        return self._current_step, self._next_step

    def get_next_step(self, *args, **kwargs) -> Union[_STEP_TYPE, None]:
        next_step = self._current_step + self._interval
        if self._max_step is not None \
                and next_step > self._max_step:
            return

        return next_step

class IntegerStepMixin(StepMixin):
    def __init_step__(
            self,
            initial_step: int,
            interval: int,
            max_step: int = None,
        ) -> None:
        super().__init_step__(
            initial_step,
            cast_interval(interval, int),
            max_step
        )

    @property
    def initial_step(self) -> Union[int, None]:
        return super().initial_step

    @property
    def max_step(self) -> Union[int, None]:
        return super().max_step

    def current_step(self) -> int:
        return super().current_step()

    def next_step(self) -> int:
        return super().next_step()

    def step(self, *args, **kwargs) -> Tuple[int, Union[int, None]]:
        return super().step(*args, **kwargs)

    def get_next_step(self, *args, **kwargs) -> Union[int, None]:
        return super().get_next_step(*args, **kwargs)


class FloatStepMixin(StepMixin):
    def __init_step__(
            self,
            initial_step: float,
            interval: float,
            max_step: float = None,
        ) -> None:
        super().__init_step__(
            initial_step,
            cast_interval(interval, float),
            max_step
        )

    @property
    def initial_step(self) -> Union[float, None]:
        return super().initial_step

    @property
    def max_step(self) -> Union[float, None]:
        return super().max_step

    def current_step(self) -> float:
        return super().current_step()

    def next_step(self) -> float:
        return super().next_step()

    def step(self, *args, **kwargs) -> Tuple[float, Union[float, None]]:
        return super().step(*args, **kwargs)

    def get_next_step(self, *args, **kwargs) -> Union[float, None]:
        return super().get_next_step(*args, **kwargs)


class DatetimeStepMixin(StepMixin):
    def __init_step__(
            self,
            initial_step: datetime,
            interval: timedelta,
            max_step: datetime = None,
        ) -> None:
        super().__init_step__(
            initial_step,
            cast_interval(interval, timedelta),
            max_step
        )

    @property
    def initial_step(self) -> Union[datetime, None]:
        return super().initial_step

    @property
    def max_step(self) -> Union[datetime, None]:
        return super().max_step

    @property
    def max_datetime(self) -> Union[datetime, None]:
        return super().max_step

    @property
    def max_date(self) -> Union[date, None]:
        max_steps = super().max_step
        if isinstance(max_steps, datetime):
            return max_steps.date()

    def current_step(self) -> datetime:
        return super().current_step()

    def current_datetime(self) -> datetime:
        return super().current_step()

    def current_date(self) -> date:
        return super().current_step().date()

    def next_step(self) -> Union[datetime, None]:
        return super().next_step()

    def next_datetime(self) -> Union[datetime, None]:
        return super().next_step()

    def next_date(self) -> Union[date, None]:
        next_step = super().next_step()
        if isinstance(next_step, datetime):
            return next_step.date()

    def step(self, *args, **kwargs) -> Tuple[datetime, Union[datetime, None]]:
        return super().step(*args, **kwargs)

    def get_next_step(self, *args, **kwargs) -> Union[datetime, None]:
        return super().get_next_step(*args, **kwargs)
