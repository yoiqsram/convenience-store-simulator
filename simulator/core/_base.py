import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Tuple, Union

from ..utils import cast

_STEP_TYPE = Union[int, datetime]
_INTERVAL_TYPE = Union[int, float, timedelta]


class IdentityMixin:
    def __init_id__(self) -> None:
        self._id = int(uuid.uuid4())

    @property
    def id(self) -> int:
        return self._id


class RandomGeneratorMixin:
    def __init_rng__(self, seed: int = None) -> None:
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

        elif isinstance(self._current_step, datetime) \
                and isinstance(self._interval, timedelta) \
                and isinstance(a_step, datetime) \
                and isinstance(b_step, datetime):
            return (b_step - a_step).total_seconds()

        else:
            raise ValueError(f"Faild to calculate interval between {repr(a_step)} and {repr(b_step)}.")

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

    def current_step(self) -> _STEP_TYPE:
        return self._current_step

    def next_step(self) -> _STEP_TYPE:
        return self._next_step

    def step(self, *args, **kwargs) -> Tuple[_STEP_TYPE, Union[_STEP_TYPE, None]]:
        self._step_count += 1
        current_step = self.next_step()
        if current_step is None:
            raise StopIteration()

        next_step = self.get_next_step(current_step)
        if next_step is not None \
                and next_step <= current_step:
            raise ValueError(
                'Next step should be higher than current step. '
                f"Please check the 'get_next_step' method in {repr(self.__class__.__name__)} class. "
                f"Next step is {repr(next_step)} and current step is {repr(current_step)}."
            )

        self._current_step = current_step
        self._next_step = next_step
        return self._current_step, next_step

    def get_next_step(self, current_step: _STEP_TYPE) -> Union[_STEP_TYPE, None]:
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
            cast(max_step, int) if max_step is not None else max_step
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

    def current_step(self) -> int:
        return super().current_step()

    def next_step(self) -> int:
        return super().next_step()

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
            cast(max_step, float) if max_step is not None else max_step
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

    def current_step(self) -> float:
        return super().current_step()

    def next_step(self) -> float:
        return super().next_step()

    def step(self, *args, **kwargs) -> Tuple[float, Union[float, None]]:
        return super().step(*args, **kwargs)

    def get_next_step(self, current_step: float) -> Union[float, None]:
        return super().get_next_step(current_step)


class DatetimeStepMixin(StepMixin):
    def __init_step__(
            self,
            initial_step: datetime,
            interval: _STEP_TYPE,
            max_step: datetime = None,
        ) -> None:
        super().__init_step__(
            cast(initial_step, datetime),
            cast(interval, timedelta),
            cast(max_step, datetime) if max_step is not None else max_step
        )

    @property
    def initial_step(self) -> Union[datetime, None]:
        return super().initial_step

    @property
    def initial_datetime(self) -> Union[datetime, None]:
        return super().initial_step

    @property
    def initial_date(self) -> Union[date, None]:
        return super().initial_step.date()

    @property
    def max_step(self) -> Union[datetime, None]:
        return super().max_step

    @max_step.setter
    def max_step(self, value: Union[str, date, datetime, None]) -> None:
        super().max_step = value

    @property
    def max_datetime(self) -> Union[datetime, None]:
        return self.max_step

    @max_datetime.setter
    def max_datetime(self, value: Union[datetime, None]) -> None:
        super().max_step = value

    @property
    def max_date(self) -> Union[date, None]:
        max_step = super().max_step
        if isinstance(max_step, datetime):
            return max_step.date()

    @max_date.setter
    def max_date(self, value: Union[date, None]) -> None:
        super().max_step = value

    def current_step(self) -> datetime:
        return super().current_step()

    def current_datetime(self) -> datetime:
        return self.current_step()

    def current_date(self) -> date:
        return super().current_step().date()

    def next_step(self) -> Union[datetime, None]:
        return super().next_step()

    def next_datetime(self) -> Union[datetime, None]:
        return self.next_step()

    def next_date(self) -> Union[date, None]:
        next_step = self.next_step()
        if isinstance(next_step, datetime):
            return next_step.date()

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
            interval: Tuple[_INTERVAL_TYPE, Tuple[_INTERVAL_TYPE, _INTERVAL_TYPE]],
            max_step: datetime = None,
        ) -> None:
        self._interval_min, self._interval_max = self._normalize_interval_range(interval)

        super().__init_step__(
            initial_step,
            self._interval_min,
            max_step
        )

    @staticmethod
    def _normalize_interval_range(
            value: Tuple[_INTERVAL_TYPE, Tuple[_INTERVAL_TYPE, _INTERVAL_TYPE]]
        ) -> Tuple[_INTERVAL_TYPE, _INTERVAL_TYPE]:
        if isinstance(value, float) \
                or isinstance(value, int) \
                or isinstance(value, timedelta):
            min_interval = cast(value, timedelta)
            max_interval = min_interval

        elif isinstance(value, tuple) \
                or isinstance(value, list):
            min_interval, max_interval = value
            min_interval: timedelta = cast(min_interval, timedelta)
            max_interval: timedelta = cast(max_interval, timedelta)

            if min_interval > max_interval:
                raise ValueError(
                    f'Minimum interval should be less than or equal to the maximum interval, '
                    f'{min_interval.total_seconds()} is greater then {max_interval.total_seconds}.'
                )

        else:
            raise ValueError(
                f"Value is '{value.__class__.__name__}' while it should be either 'int', 'float', 'timedelta' "
                'or a tuple contains a couple values of minimum and maximum.'
            )

        return min_interval, max_interval

    @property
    def interval(self) -> timedelta:
        if self._interval_min == self._interval_max:
            return self._interval_min
        return self.random_interval()

    @interval.setter
    def interval(
            self,
            value: Tuple[_INTERVAL_TYPE, Tuple[_INTERVAL_TYPE, _INTERVAL_TYPE]]
        ) -> None:
        self._interval_min, self._interval_max = self._normalize_interval_range(value)

    @property
    def interval_min(self) -> timedelta:
        return self._interval_min

    @property
    def interval_max(self) -> timedelta:
        return self._interval_max

    def random_interval(self) -> timedelta:
        interval = self._rng.uniform(
            self._interval_min.total_seconds(),
            self._interval_max.total_seconds()
        )
        return timedelta(seconds=interval)
