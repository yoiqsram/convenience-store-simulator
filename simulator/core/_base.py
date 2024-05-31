from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Tuple, Union

from .utils import cast

_STEP_TYPE = Union[int, datetime]
_INTERVAL_TYPE = Union[int, float, timedelta]
_OPTIONAL_INTERVAL_TYPE = Union[
    _INTERVAL_TYPE,
    Tuple[_INTERVAL_TYPE, _INTERVAL_TYPE]
]


class IdentityMixin:
    def __init_id__(self, _id: str = None) -> None:
        self._id = str(uuid.uuid4()) if _id is None else _id

    @property
    def id(self) -> str:
        return self._id


class RandomGeneratorMixin:
    def __init_rng__(self, seed: int = None, rng=None) -> None:
        from numpy.random import RandomState

        self._rng = RandomState(seed) if rng is None else rng

    def dump_rng_state(self) -> Tuple[str, List[int], int, int, float]:
        state = self._rng.get_state()
        return state[:1] + (state[1].tolist(),) + state[2:]

    def load_rng_state(
            self,
            state: Tuple[str, List[int], int, int, float]
            ) -> None:
        self._rng.set_state(state)

    def random_seed(
            self,
            size: int = 1,
            maxlen: int = 6
            ) -> List[int]:
        return [
            int(num)
            for num in self._rng.random(size) * int('1' + '0' * maxlen)
        ]


class ReprMixin:
    __repr_attrs__: Tuple[str, ...]

    def __init_subclass__(cls, repr_attrs=Tuple[str, ...], **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        cls.__repr_attrs__ = repr_attrs

    def __repr__(self) -> str:
        kwargs: Dict[str, str] = {}
        for identifier in self.__class__.__repr_attrs__:
            attr = getattr(self, identifier)
            if callable(attr):
                attr = attr()

            kwargs[identifier] = attr

        return (
            f"{self.__class__.__name__}"
            f"({', '.join([f'{k}={v}' for k, v in kwargs.items()])})"
        )


class SuperclassMixin:
    __subclasses__: Dict[str, SuperclassMixin] = {}

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        for superclass in cls.__mro__[1:-1]:
            if not isinstance(superclass, SuperclassMixin):
                continue

            superclass.__subclasses__[superclass.__name__] = superclass

        cls.__subclasses__ = {}


class StepMixin:
    def __init_step__(
            self,
            initial_step: _STEP_TYPE,
            interval: _INTERVAL_TYPE,
            max_step: _STEP_TYPE = None
            ) -> None:
        self._step_count = 0
        self._initial_step = initial_step
        self._max_step = max_step
        self._interval = interval

        self._current_step = self._initial_step
        self._next_step: _STEP_TYPE = self._initial_step + self._interval

    def _calculate_interval(
            self,
            a_step: _STEP_TYPE,
            b_step: _STEP_TYPE
            ) -> _INTERVAL_TYPE:
        if isinstance(self._current_step, int) \
                or isinstance(self._current_step, float):
            return b_step - a_step

        else:
            raise ValueError(
                f"Faild to calculate interval between "
                f"{repr(a_step)} and {repr(b_step)}."
            )

    @property
    def interval(self) -> _INTERVAL_TYPE:
        return self._interval

    @interval.setter
    def interval(self, value: Any) -> None:
        self._interval = cast(value, type(self._interval))

    @property
    def initial_step(self) -> _STEP_TYPE:
        return self._initial_step

    @property
    def max_step(self) -> Union[_STEP_TYPE, None]:
        return self._max_step

    @max_step.setter
    def max_step(self, value: Union[_STEP_TYPE, None]) -> None:
        self._max_step = cast(value, type(self._initial_step))

    @property
    def steps(self) -> int:
        return self._step_count

    @property
    def current_step(self) -> _STEP_TYPE:
        return self._current_step

    @property
    def next_step(self) -> _STEP_TYPE:
        return self._next_step

    def step(
            self,
            *args,
            **kwargs
            ) -> Tuple[_STEP_TYPE, Union[_STEP_TYPE, None]]:
        self._step_count += 1
        current_step = self.next_step
        if current_step is None:
            raise StopIteration()

        next_step = self.get_next_step(current_step)
        if next_step is not None \
                and next_step <= current_step:
            raise ValueError(
                'Next step should be higher than current step. '
                f"Please check the 'get_next_step' method in "
                f"{repr(self.__class__.__name__)} class. "
                f"Next step is {repr(next_step)} "
                f"and current step is {repr(current_step)}."
            )

        self._current_step = current_step
        self._next_step = next_step
        return self._current_step, self._next_step

    def get_next_step(
            self,
            current_step: _STEP_TYPE
            ) -> Union[_STEP_TYPE, None]:
        next_step = current_step + self.interval

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
            cast(initial_step, int),
            cast(interval, int),
            cast(max_step, int) if max_step is not None else None
        )

    @property
    def initial_step(self) -> Union[int, None]:
        return super().initial_step

    @property
    def max_step(self) -> Union[int, None]:
        return super().max_step

    @max_step.setter
    def max_step(self, value: Union[int, None]) -> None:
        super().max_step = value

    @property
    def current_step(self) -> int:
        return super().current_step

    @property
    def next_step(self) -> int:
        return super().next_step

    def step(self, *args, **kwargs) -> Tuple[int, Union[int, None]]:
        return super().step(*args, **kwargs)

    def get_next_step(self, current_step: int) -> Union[int, None]:
        return super().get_next_step(current_step)


class FloatStepMixin(StepMixin):
    def __init_step__(
            self,
            initial_step: float,
            interval: float,
            max_step: float = None,
            ) -> None:
        super().__init_step__(
            cast(initial_step, float),
            cast(interval, float),
            cast(max_step, float) if max_step is not None else None
        )

    @property
    def initial_step(self) -> Union[float, None]:
        return super().initial_step

    @property
    def max_step(self) -> Union[float, None]:
        return super().max_step

    @max_step.setter
    def max_step(self, value: Union[float, None]) -> None:
        super().max_step = value

    @property
    def current_step(self) -> float:
        return super().current_step

    @property
    def next_step(self) -> float:
        return super().next_step

    def step(self, *args, **kwargs) -> Tuple[float, Union[float, None]]:
        return super().step(*args, **kwargs)

    def get_next_step(self, current_step: float) -> Union[float, None]:
        return super().get_next_step(current_step)


class DatetimeStepMixin(StepMixin):
    def __init_step__(
            self,
            initial_step: _STEP_TYPE,
            interval: _INTERVAL_TYPE,
            max_step: _STEP_TYPE = None,
            ) -> None:
        initial_step = cast(initial_step, datetime).timestamp()
        interval = cast(interval, timedelta).total_seconds()
        if max_step is not None:
            max_step = cast(max_step, datetime).timestamp()

        super().__init_step__(
            initial_step,
            interval,
            max_step
        )

    @property
    def initial_step(self) -> Union[datetime, None]:
        return super().initial_step

    @property
    def initial_datetime(self) -> Union[datetime, None]:
        return datetime.fromtimestamp(super().initial_step)

    @property
    def initial_date(self) -> Union[date, None]:
        return date.fromtimestamp(super().initial_step)

    @property
    def max_step(self) -> Union[datetime, None]:
        return super().max_step

    @max_step.setter
    def max_step(self, value: Union[_STEP_TYPE, None]) -> None:
        if value is None:
            self._max_step = None
        else:
            self._max_step = cast(value, datetime).timestamp()

    @property
    def max_datetime(self) -> Union[datetime, None]:
        return cast(self.max_step, datetime)

    @max_datetime.setter
    def max_datetime(self, value: Union[datetime, None]) -> None:
        self.max_step = value

    @property
    def max_date(self) -> Union[date, None]:
        max_step = super().max_step
        if isinstance(max_step, datetime):
            return max_step.date()

    @max_date.setter
    def max_date(self, value: Union[date, None]) -> None:
        self.max_step = value

    @property
    def current_step(self) -> datetime:
        return super().current_step

    @property
    def current_datetime(self) -> datetime:
        return datetime.fromtimestamp(super().current_step)

    @property
    def current_date(self) -> date:
        return date.fromtimestamp(super().current_step)

    @property
    def next_step(self) -> Union[datetime, None]:
        return super().next_step

    @property
    def next_datetime(self) -> Union[datetime, None]:
        return cast(super().next_step, datetime)

    @property
    def next_date(self) -> Union[date, None]:
        return cast(super().next_step, date)

    def total_time_elapsed(self) -> timedelta:
        return self._calculate_interval(self._initial_step, self._current_step)

    def step(self, *args, **kwargs) -> Tuple[datetime, Union[datetime, None]]:
        return super().step(*args, **kwargs)

    def get_next_step(self, current_step: datetime) -> Union[datetime, None]:
        return super().get_next_step(current_step)


class RandomDatetimeStepMixin(DatetimeStepMixin, RandomGeneratorMixin):
    def __init_step__(
            self,
            initial_step: datetime,
            interval: _OPTIONAL_INTERVAL_TYPE,
            max_step: datetime = None,
            ) -> None:
        self._interval_min, self._interval_max = \
            self._normalize_interval_range(interval)

        super().__init_step__(
            initial_step,
            self._interval_min,
            max_step
        )

    @staticmethod
    def _normalize_interval_range(
            value: _OPTIONAL_INTERVAL_TYPE
            ) -> Tuple[float, float]:
        if isinstance(value, float) \
                or isinstance(value, int) \
                or isinstance(value, timedelta):
            min_interval = cast(value, float)
            max_interval = min_interval

        elif isinstance(value, tuple) \
                or isinstance(value, list):
            min_interval, max_interval = value
            min_interval: timedelta = cast(min_interval, float)
            max_interval: timedelta = cast(max_interval, float)

            if min_interval > max_interval:
                raise ValueError(
                    f'Minimum interval should be less than '
                    f'or equal to the maximum interval, '
                    f'{min_interval} '
                    f'is greater then {max_interval}.'
                )

        else:
            raise ValueError(
                f"Value is '{value.__class__.__name__}' "
                f"while it should be either 'int', 'float', 'timedelta' "
                'or a tuple contains a couple values of minimum and maximum.'
            )

        return min_interval, max_interval

    @property
    def interval(self) -> float:
        if self._interval_min == self._interval_max:
            return self._interval_min
        return self._rng.uniform(
            self._interval_min,
            self._interval_max
        )

    @interval.setter
    def interval(
            self,
            value: _OPTIONAL_INTERVAL_TYPE
            ) -> None:
        self._interval_min, self._interval_max = \
            self._normalize_interval_range(value)

    @property
    def interval_min(self) -> float:
        return self._interval_min

    @property
    def interval_max(self) -> float:
        return self._interval_max
