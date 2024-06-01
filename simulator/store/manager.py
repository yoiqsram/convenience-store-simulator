from __future__ import annotations

import numpy as np
from datetime import date, datetime, timedelta
from typing import Tuple, Union, TYPE_CHECKING

from ..core import Agent, DatetimeStepMixin
from ..core.agent import _STEP_TYPE, _INTERVAL_TYPE
from ..core.utils import cast
from .employee import Employee

if TYPE_CHECKING:
    from .store import Store


class Manager(Agent, DatetimeStepMixin):
    def __init__(
            self,
            initial_step: _STEP_TYPE,
            interval: _INTERVAL_TYPE,
            seed: int = None,
            rng: np.random.RandomState = None
            ) -> None:
        super().__init__(
            cast(initial_step, float),
            cast(interval, float),
            seed=seed,
            rng=rng
        )

        self.parent: Store

    def get_next_step(
            self,
            current_step: _STEP_TYPE
            ) -> Union[_STEP_TYPE, None]:
        current_date = cast(current_step, date)
        next_date = datetime(
            current_date.year,
            current_date.month,
            current_date.day
        ) + timedelta(days=1)
        return next_date.timestamp()

    def step(
            self,
            *args,
            **kwargs
            ) -> Tuple[_STEP_TYPE, Union[_STEP_TYPE, None]]:
        current_step, next_step = super().step(*args, **kwargs)
        current_datetime = cast(current_step, datetime)

        if self.parent.n_employees < self.parent.max_employees:
            new_employees = []
            for _ in range(
                    self.parent.max_employees
                    - self.parent.n_employees
                    ):
                employee = Employee.generate(
                    datetime(
                        current_datetime.year,
                        current_datetime.month,
                        current_datetime.day
                    ) + timedelta(days=1, hours=6),
                    self.parent.interval,
                    rng=self._rng
                )
                employee.created_datetime = current_datetime

                employee_dir = (
                    self.parent.restore_file.parent
                    / 'Employee'
                    / employee.person.id
                )
                employee_dir.mkdir(parents=True, exist_ok=True)
                employee.person.push_restore(employee_dir / 'person.json')
                employee.push_restore(
                    employee_dir / 'employee.json',
                    tmp=True
                )

                self.parent.add_employee(employee)
                new_employees.append(employee)

            self.parent.schedule_shifts(
                date(
                    current_datetime.year,
                    current_datetime.month,
                    current_datetime.day
                ),
                new_employees
            )
