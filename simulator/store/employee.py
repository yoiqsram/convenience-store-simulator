from __future__ import annotations

import numpy as np
from datetime import date, datetime
from typing import TYPE_CHECKING

from core import Agent, DateTimeStepMixin
from core.utils import cast
from ..context import DAYS_IN_YEAR, SECONDS_IN_DAY
from ..database import EmployeeModel, EmployeeAttendanceModel, ModelMixin
from ..enums import (
    AgeGroup, Gender, OrderStatus,
    EmployeeAttendanceStatus, EmployeeShift, EmployeeStatus
)
from ..logging import store_logger, simulator_log_format
from .order import Order

if TYPE_CHECKING:
    from .store import Store


class Employee(
        Agent,
        DateTimeStepMixin, ModelMixin,
        model=EmployeeModel,
        repr_attrs=('status', 'shift')
        ):
    def __init__(
            self,
            name: str = None,
            gender: Gender = None,
            age: float = None,
            seed: int = None,
            rng: np.random.RandomState = None,
            record_id: int = None
            ) -> None:
        super().__init__(seed=seed, rng=rng)
        self.parent: Store

        self.status = EmployeeStatus.OFF
        self.shift: EmployeeShift = EmployeeShift.NONE
        self.schedule_shift_start_timestamp = None
        self.schedule_shift_end_timestamp = None
        self.today_shift_start_timestamp = None
        self.today_shift_end_timestamp = None

        self.current_order: Order | None = None

        attrs = {}
        if record_id is None:
            attrs['name'] = name
            attrs['gender'] = gender.name
            attrs['birth_date'] = date.fromtimestamp(int(self.initial_step - age))
        super().__init_model__(
            unique_identifiers={'id': record_id},
            **attrs
        )

    @property
    def age_recognition_rate(self) -> float:
        return self.parent._employee_params[self._index - 1, 0]

    @property
    def counting_skill_rate(self) -> float:
        return self.parent._employee_params[self._index - 1, 1]

    @property
    def content_rate(self) -> float:
        return self.parent._employee_params[self._index - 1, 2]

    @property
    def discipline_rate(self) -> float:
        return self.parent._employee_params[self._index - 1, 3]

    def step(self, *args, **kwargs) -> tuple[np.uint32, np.uint32, bool]:
        self.parent.total_employee_steps += 1
        current_step, next_step, done = super().step(*args, **kwargs)

        # Schedule next day shift on the midnight
        if self.schedule_shift_start_timestamp is None \
                or (
                    self.schedule_shift_start_timestamp // SECONDS_IN_DAY
                    < current_step // SECONDS_IN_DAY
                ):
            self.schedule_shift_attendance(current_step)
            self.next_step = self.schedule_shift_start_timestamp
            return current_step, self.next_step, done

        # Begin shift
        elif self.status == EmployeeStatus.OFF \
                and self.today_shift_start_timestamp is None \
                and self.schedule_shift_start_timestamp <= current_step:
            self.begin_shift(current_step)

        # Assign to be cashier, if there's an idle cashier machine
        if self.status == EmployeeStatus.STARTING_SHIFT:
            if self.parent.n_cashiers >= self.parent.max_cashiers:
                return current_step, next_step, done

            self.status = EmployeeStatus.IDLE
            if self.parent.n_order_queue > 0:
                self.parent.assign_order_queue(self)

        # Complete shift, if not busy
        # and there'll be enough cashiers in the store
        elif self.status in (
                    EmployeeStatus.IDLE,
                    EmployeeStatus.STARTING_SHIFT
                ) \
                and self.today_shift_end_timestamp is None \
                and self.schedule_shift_end_timestamp <= current_step \
                and (
                    self.parent.n_order_queue == 0 or
                    (self.parent.total_active_shift_employees() - 1 > 0)
                ):
            self.complete_shift(current_step)
            # Set next wake up at 6 a.m.
            self.next_step = (
                current_step - current_step % SECONDS_IN_DAY
                + SECONDS_IN_DAY
                + 6 * 3600
            )
            return current_step, self.next_step, done

        # Set idle until the end of shift
        if self.current_order is None:
            if self.status == EmployeeStatus.IDLE:
                self.next_step = self.schedule_shift_end_timestamp

        # Process the assigned order
        elif self.current_order.status == OrderStatus.QUEUING:
            self.status = EmployeeStatus.PROCESSING_ORDER
            checkout_time = \
                self.calculate_checkout_time(self.current_order)
            self.current_order.begin_checkout(
                current_step,
                checkout_time
            )
            self.next_step = self.current_order.checkout_end_timestamp

        # Complete checkout
        elif self.current_order.status == OrderStatus.PROCESSING:
            self.current_order.complete_checkout(current_step)

        # Waiting for payment
        elif self.current_order.status == OrderStatus.DOING_PAYMENT:
            self.next_step = self.current_order.paid_timestamp

        # Complete order
        elif self.current_order.status == OrderStatus.PAID:
            self.current_order.submit(self, current_step)
            self.current_order = None
            self.status = EmployeeStatus.IDLE

            # Check for another order in queue
            if self.parent.n_order_queue > 0:
                self.parent.assign_order_queue(self)
            else:
                self.next_step = self.schedule_shift_end_timestamp

        return current_step, self.next_step, done

    def schedule_shift_attendance(self, current_step: float) -> None:
        if self.shift == EmployeeShift.NONE:
            return

        self.today_shift_start_timestamp = None
        self.today_shift_end_timestamp = None

        shift_start_timestamp = int(
            current_step - current_step % SECONDS_IN_DAY
            + self.parent.start_shift_hours[self.shift.value - 1] * 3600
        )
        self.schedule_shift_start_timestamp = int(
            shift_start_timestamp
            + self._rng.normal(-self.discipline_rate * 60, 150)
        )
        self.schedule_shift_end_timestamp = int(
            shift_start_timestamp
            + self.parent.long_shift_hours * 3600
        )

        store_logger.debug(simulator_log_format(
            f'STORE {self.parent.place_name} -',
            f'[{self.record_id}]:',
            f"Schedule today's {self.shift.name} shift at",
            cast(self.schedule_shift_start_timestamp, datetime),
            dt=self.current_datetime
        ))

    def begin_shift(self, current_step: int) -> None:
        EmployeeAttendanceModel.create(
            employee=self.record.id,
            status=EmployeeAttendanceStatus.BEGIN_SHIFT.name,
            created_datetime=cast(current_step, datetime)
        )
        self.status = EmployeeStatus.STARTING_SHIFT
        self.today_shift_start_timestamp = current_step

        store_logger.debug(simulator_log_format(
            f'STORE {self.parent.place_name} -',
            f'[{self.record_id}]:',
            f"Begin today's {self.shift.name} shift until",
            cast(self.schedule_shift_end_timestamp, datetime),
            dt=self.current_datetime
        ))

    def complete_shift(self, current_step: float) -> None:
        EmployeeAttendanceModel.create(
            employee=self.record.id,
            status=EmployeeAttendanceStatus.COMPLETE_SHIFT.name,
            created_datetime=cast(current_step, datetime)
        )
        self.status = EmployeeStatus.OFF
        self.today_shift_end_timestamp = current_step

        store_logger.debug(simulator_log_format(
            f'STORE {self.parent.place_name} -',
            f'[{self.record_id}]:',
            f"Completed today's {self.shift.name} shift.",
            dt=current_step
        ))

    def calculate_checkout_time(self, order: Order) -> float:
        checkout_time = (
            2.5
            + np.sum(
                np.clip(
                    self._rng.normal(
                        6.0 - self.counting_skill_rate,
                        (5.1 - self.counting_skill_rate),
                        size=order.n_order_skus
                    ),
                    1.0,
                    3.0
                )
            )
            + np.sum(
                np.clip(
                    self._rng.normal(
                        1.0,
                        0.25,
                        size=sum([
                            quantity - 1
                            for _, quantity in order.order_skus
                        ])),
                    0.0,
                    5.0
                )
            )
        )
        return checkout_time

    def estimate_customer_age_group(
            self,
            buyer_age: float
            ) -> tuple[AgeGroup]:
        age = (
            buyer_age / DAYS_IN_YEAR
            + self._rng.normal(0, (6.0 - self.age_recognition_rate) * 2)
        )

        for age_group in AgeGroup:
            if age < age_group.value:
                break

        return age_group

    @classmethod
    def generate(
            cls,
            seed: int = None,
            rng: np.random.RandomState = None
            ) -> Employee:
        if rng is None:
            rng = np.random.RandomState(seed)

        gender = Gender(int(rng.randint(2)))
        age = int(
            np.clip(
                rng.normal(24.0, 2.0),
                18.0,
                30.0
            )
            * DAYS_IN_YEAR
        )

        return cls(
            'Unnamed',
            gender,
            age,
            seed=seed,
            rng=rng
        )
