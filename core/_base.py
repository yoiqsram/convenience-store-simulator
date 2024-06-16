from __future__ import annotations

import uuid
import numpy as np
from datetime import date, datetime
from time import time


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

    def dump_rng_state(self) -> tuple[str, list[int], int, int, float]:
        state = self._rng.get_state()
        return state[:1] + (state[1].tolist(),) + state[2:]

    def load_rng_state(
            self,
            state: tuple[str, list[int], int, int, float]
            ) -> None:
        self._rng.set_state(state)

    def random_seed(
            self,
            size: int = 1,
            maxlen: int = 6
            ) -> list[int]:
        return [
            int(num)
            for num in self._rng.random(size) * int('1' + '0' * maxlen)
        ]


class ReprMixin:
    __repr_attrs__: tuple[str, ...]

    def __init_subclass__(cls, repr_attrs=tuple[str, ...], **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        cls.__repr_attrs__ = repr_attrs

    def __repr__(self) -> str:
        kwargs: dict[str, str] = {}
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
    __subclasses__: dict[str, SuperclassMixin] = {}

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        for superclass in cls.__mro__[1:-1]:
            if not isinstance(superclass, SuperclassMixin):
                continue

            superclass.__subclasses__[superclass.__name__] = superclass

        cls.__subclasses__ = {}


_STEP_TYPE = (
    np.uint8 | np.uint16 | np.uint32 | np.uint64 |
    np.float16 | np.float32 | np.float64
)


class StepMixin:
    def __init_step__(
            self,
            initial_step: _STEP_TYPE = 0,
            max_step: _STEP_TYPE = 0,
            interval: _STEP_TYPE = 1,
            dtype: type = np.uint16
            ) -> None:
        # Stores initial step, max step, interval, current step, next step, step_count
        self._steps = np.array(
            [
                initial_step,
                max_step,
                interval,
                initial_step,
                initial_step + interval,
                0
            ],
            dtype=dtype
        )

    @property
    def initial_step(self) -> _STEP_TYPE:
        return self._steps[0]

    @property
    def max_step(self) -> _STEP_TYPE:
        return self._steps[1]

    @max_step.setter
    def max_step(self, value: _STEP_TYPE) -> None:
        self._steps[1] = value

    @property
    def interval(self) -> _STEP_TYPE:
        return self._steps[2]

    @interval.setter
    def interval(self, value: _STEP_TYPE) -> None:
        self._steps[2] = value

    @property
    def current_step(self) -> _STEP_TYPE:
        return self._steps[3]

    @property
    def next_step(self) -> _STEP_TYPE:
        return self._steps[4]

    @next_step.setter
    def next_step(self, value: _STEP_TYPE) -> None:
        self._steps[4] = value

    @property
    def steps(self) -> int:
        return self._steps[5]

    def step(
            self,
            *args,
            **kwargs
            ) -> tuple[_STEP_TYPE, _STEP_TYPE, bool]:
        self._steps[3] = self._steps[4]
        self._steps[4] = self.get_next_step(self._steps[3])
        self._steps[5] += 1
        done = self._steps[1] > 0 and self._steps[4] >= self._steps[1]
        return self._steps[3], self._steps[4], done

    def get_next_step(self, current_step: _STEP_TYPE) -> _STEP_TYPE:
        return current_step + self.interval


class DateTimeStepMixin(StepMixin):
    def __init_step__(
            self,
            initial_step: _STEP_TYPE = None,
            max_step: _STEP_TYPE = 0,
            interval: _STEP_TYPE = 1
            ) -> None:
        super().__init_step__(
            initial_step or time(),
            max_step,
            interval,
            dtype=np.uint32
        )

    @property
    def initial_step(self) -> np.uint32:
        return super().initial_step

    @property
    def initial_datetime(self) -> datetime:
        return datetime.fromtimestamp(float(super().initial_step))

    @property
    def initial_date(self) -> date:
        return date.fromtimestamp(float(super().initial_step))

    @property
    def max_step(self) -> np.uint32:
        return super().max_step

    @max_step.setter
    def max_step(self, value: _STEP_TYPE) -> None:
        super().max_step = value

    @property
    def max_datetime(self) -> datetime:
        return datetime.fromtimestamp(float(self.max_step))

    @max_datetime.setter
    def max_datetime(self, value: datetime) -> None:
        super().max_step = value.timestamp()

    @property
    def max_date(self) -> date:
        return date.fromtimestamp(float(self.max_step))

    @max_date.setter
    def max_date(self, value: date) -> None:
        self.max_datetime = datetime(value.year, value.month, value.day)

    @property
    def current_step(self) -> np.uint32:
        return super().current_step

    @property
    def current_datetime(self) -> datetime:
        return datetime.fromtimestamp(float(self.current_step))

    @property
    def current_date(self) -> date:
        return date.fromtimestamp(float(self.current_step))

    @property
    def next_datetime(self) -> datetime:
        return datetime.fromtimestamp(float(self.next_step))

    @property
    def next_date(self) -> date:
        return date.fromtimestamp(float(self.next_step))

    def total_seconds(self) -> np.uint32:
        return self.current_step - self.initial_step

    def step(self, *args, **kwargs) -> tuple[np.uint32, np.uint32, bool]:
        return super().step(*args, **kwargs)

    def get_next_step(self, current_step: np.uint32) -> np.uint32:
        return super().get_next_step(current_step)
