from __future__ import annotations

import numpy as np
from datetime import datetime
from typing import TYPE_CHECKING

from core import Agent, DateTimeStepMixin

from ..context import SECONDS_IN_DAY
from ..enums import EmployeeShift, EmployeeStatus
from .employee import Employee

if TYPE_CHECKING:
    from .store import Store


class Manager(
        Agent,
        DateTimeStepMixin,
        repr_attrs=('current_datetime',)
        ):
    def __init__(
            self,
            seed: int = None,
            rng: np.random.RandomState = None
            ) -> None:
        super().__init__(seed=seed, rng=rng)
        self.parent: Store

    def get_next_step(
            self,
            current_step: np.uint32
            ) -> np.uint32:
        return (
            current_step + SECONDS_IN_DAY
            - current_step % SECONDS_IN_DAY
        )

    def step(
            self,
            *args,
            **kwargs
            ) -> tuple[np.uint32, np.uint32, bool]:
        previous_date = self.current_date
        current_step, next_step, done = super().step(*args, **kwargs)
        current_date = self.current_date

        # Hire new employees if needed
        if self.parent.n_employees < self.parent.max_employees:
            new_employees = self.hire_employees(
                self.parent.max_employees - self.parent.n_employees,
                current_step
            )
            self.schedule_shifts(new_employees)

        # Update schedule working shifts midnight date 1st
        if previous_date.month != current_date.month:
            for employee in self.parent.employees():
                employee.shift = EmployeeShift.NONE

        shift_employees = []
        for employee in self.parent.employees():
            if employee.shift == EmployeeShift.NONE \
                    and employee.status != EmployeeStatus.OUT_OF_OFFICE:
                shift_employees.append(employee)
        self.schedule_shifts(shift_employees)

        return current_step, next_step, done

    def hire_employees(
            self,
            n: int,
            current_timestamp: float
            ) -> list[Employee]:
        new_employees = []
        for _ in range(n):
            employee = Employee.generate(rng=self._rng)
            self.parent.add_employee(employee)
            employee.created_datetime = \
                datetime.fromtimestamp(float(current_timestamp))
            new_employees.append(employee)

        return new_employees

    def schedule_shifts(self, employees: list[Employee]) -> None:
        shifts = (
            [EmployeeShift.FIRST, EmployeeShift.SECOND]
            * int(np.ceil(self.parent.n_employees / 2))
        )
        shifts = shifts[:len(employees)]
        self._rng.shuffle(shifts)
        for employee, shift in zip(employees, shifts):
            employee.shift = shift
