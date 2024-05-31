from __future__ import annotations

import numpy as np
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Tuple, Union, TYPE_CHECKING

from ..core import Agent, DatetimeStepMixin
from ..core.restore import RestoreTypes
from ..core.utils import cast
from ..database import EmployeeModel, EmployeeAttendanceModel, ModelMixin
from ..enums import (
    AgeGroup, Gender, FamilyStatus, OrderStatus,
    EmployeeAttendanceStatus, EmployeeShift, EmployeeStatus
)
from ..logging import store_logger, simulator_log_format
from ..population import Person
from .order import Order

if TYPE_CHECKING:
    from .store import Store


class Employee(
        Agent,
        DatetimeStepMixin, ModelMixin,
        model=EmployeeModel,
        repr_attrs=('name', 'status', 'shift')
        ):
    __additional_types__ = RestoreTypes(EmployeeStatus, EmployeeShift)

    def __init__(
            self,
            person: Person,
            name: str,
            initial_datetime: datetime,
            interval: float,
            age_recognition_rate: float = None,
            counting_skill_rate: float = None,
            content_rate: float = None,
            discipline_rate: float = None,
            seed: int = None,
            rng: np.random.RandomState = None
            ) -> None:
        super().__init__(
            cast(initial_datetime, float),
            cast(interval, float),
            seed=seed,
            rng=rng
        )

        self.parent: Store
        self.person = person
        self.name = name
        self.age_recognition_rate = float(age_recognition_rate)
        self.counting_skill_rate = float(counting_skill_rate)
        self.content_rate = float(content_rate)
        self.discipline_rate = float(discipline_rate)
        self.status = EmployeeStatus.OFF

        self.shift: EmployeeShift = EmployeeShift.NONE
        self.schedule_shift_start_datetime: datetime = None
        self.schedule_shift_end_datetime: datetime = None
        self.today_shift_start_datetime: datetime = None
        self.today_shift_end_datetime: datetime = None

        self.current_order: Union[Order, None] = None

        super().__init_model__(
            unique_identifiers={'person_id': self.person.id},
            name=self.name,
            gender=person.gender.name,
            birth_date=person.birth_date
        )

    def step(self) -> Tuple[datetime, Union[datetime, None]]:
        self.parent.employee_steps += 1
        current_step, next_step = super().step()
        current_datetime = cast(current_step, datetime)

        if current_step >= next_step:
            raise

        # Schedule next day shift on the midnight
        if self.schedule_shift_start_datetime is None:
            self.schedule_shift_attendance(
                self.parent.employee_shift_schedules[self.record_id],
                current_datetime.date()
            )
            self._next_step = cast(
                self.schedule_shift_start_datetime,
                float
            )
            return current_step, self._next_step

        # Begin shift
        elif self.status == EmployeeStatus.OFF \
                and self.today_shift_start_datetime is None \
                and self.schedule_shift_start_datetime <= current_datetime:
            self.begin_shift(current_datetime)
            return current_step, next_step

        # Assign to be cashier, if there's an idle cashier machine
        elif self.status == EmployeeStatus.STARTING_SHIFT \
                and self.parent.n_cashiers < self.parent.max_cashiers:
            self.parent.assign_cashier(self)
            return current_step, next_step

        # Complete shift, if not busy
        # and there'll be enough cashiers in the store
        elif self.status in (
                    EmployeeStatus.IDLE,
                    EmployeeStatus.STARTING_SHIFT
                ) \
                and self.today_shift_end_datetime is None \
                and self.schedule_shift_end_datetime <= current_datetime \
                and (
                    self.shift == EmployeeShift.SECOND or
                    (
                        self.parent.n_cashiers
                        + self.parent.total_active_shift_employees()
                        - 1
                    ) > 0
                ):
            self.complete_shift(current_datetime)

            self._next_step = cast(
                datetime(
                    current_datetime.year,
                    current_datetime.month,
                    current_datetime.day
                )
                + timedelta(days=1, hours=6),  # Wake up time
                float
            )
            return current_step, self._next_step

        # Wait for order from queue and assign it
        if self.current_order is None:
            if self.status == EmployeeStatus.IDLE \
                    and self.parent.n_order_queue > 0:
                self.parent.assign_order_queue(self)

                buyer_gender, buyer_age_group = None, None
                if self._rng.random() > 0.05:
                    buyer_gender = self.current_order.buyer.gender
                    buyer_age_group = self.estimate_age_group(
                        self.current_order.buyer,
                        current_datetime.date()
                    )

                self.status = EmployeeStatus.PROCESSING_ORDER
                self.parent.remove_order_queue(self.current_order)
                self.current_order.begin_checkout(
                    store=self.parent,
                    employee=self,
                    buyer_gender=buyer_gender,
                    buyer_age_group=buyer_age_group,
                    current_datetime=current_datetime
                )

                processing_time = \
                    self.calculate_checkout_time(self.current_order)
                self._next_step = cast(
                    current_datetime
                    + timedelta(seconds=processing_time),
                    float
                )
                return current_step, self._next_step

        # Wait for order payment
        elif self.current_order.status == OrderStatus.PROCESSING:
            self.current_order.complete_checkout(current_datetime)

        # Complete order
        elif self.current_order.status == OrderStatus.PAID:
            self.current_order.submit(current_datetime)
            self.current_order = None

            self.status = EmployeeStatus.IDLE
            self.parent.total_orders += 1

        return current_step, next_step

    def schedule_shift_attendance(
            self,
            shift: EmployeeShift,
            shift_date: date
            ) -> None:
        if shift == EmployeeShift.NONE:
            return

        self.shift = shift
        self.today_shift_start_datetime = None
        self.today_shift_end_datetime = None

        shift_start_datetime = (
            datetime(shift_date.year, shift_date.month, shift_date.day)
            + timedelta(hours=self.parent.start_shift_hours[self.shift])
        )
        self.schedule_shift_start_datetime = (
            shift_start_datetime
            + timedelta(seconds=int(self._rng.normal(
                -self.discipline_rate * 60,
                150
            )))
        )
        self.schedule_shift_end_datetime = (
            shift_start_datetime
            + self.parent.long_shift_hours
        )

        store_logger.debug(simulator_log_format(
            f'STORE {self.parent.place_name} -',
            f'[{self.record_id}]:',
            f"Schedule today's {self.shift.name} shift at",
            self.schedule_shift_start_datetime,
            dt=self.current_datetime
        ))

    def begin_shift(self, current_datetime: datetime) -> None:
        EmployeeAttendanceModel.create(
            employee=self.record.id,
            status=EmployeeAttendanceStatus.BEGIN_SHIFT.name,
            created_datetime=current_datetime
        )
        self.status = EmployeeStatus.STARTING_SHIFT
        self.today_shift_start_datetime = current_datetime

        store_logger.debug(simulator_log_format(
            f'STORE {self.parent.place_name} -',
            f'[{self.record_id}]:',
            f"Begin today's {self.shift.name} shift until",
            self.schedule_shift_end_datetime,
            dt=self.current_datetime
        ))

    def complete_shift(self, current_datetime: datetime) -> None:
        store_logger.debug(simulator_log_format(
            f'STORE {self.parent.place_name} -',
            f'[{self.record_id}]:',
            f"Completed today's {self.shift.name} shift.",
            dt=current_datetime
        ))

        EmployeeAttendanceModel.create(
            employee=self.record.id,
            status=EmployeeAttendanceStatus.COMPLETE_SHIFT.name,
            created_datetime=current_datetime
        )
        self.parent.dismiss_cashier(self)
        self.today_shift_end_datetime = current_datetime
        self.schedule_shift_start_datetime = None
        self.schedule_shift_end_datetime = None

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
                            for _, quantity in order.order_skus()
                        ])),
                    0.0,
                    5.0
                )
            )
        )
        return checkout_time

    def estimate_age_group(
            self,
            person: Person,
            current_date: date
            ) -> AgeGroup:
        age = (
            person.age(current_date)
            + self._rng.normal(0, (6.0 - self.age_recognition_rate) * 2)
        )

        if age < AgeGroup.KID.value:
            return AgeGroup.KID

        elif age < AgeGroup.TEENAGE.value:
            return AgeGroup.TEENAGE

        elif age < AgeGroup.YOUNG_ADULT.value:
            return AgeGroup.YOUNG_ADULT

        elif age < AgeGroup.MIDDLE_ADULT.value:
            return AgeGroup.MIDDLE_ADULT

        return AgeGroup.OLDER_ADULT

    @property
    def restore_attrs(self) -> Dict[str, Any]:
        attrs = super().restore_attrs
        attrs['name'] = self.name
        attrs['skill_params'] = [
            self.age_recognition_rate,
            self.counting_skill_rate,
            self.content_rate,
            self.discipline_rate
        ]
        attrs['status'] = self.status
        attrs['shift'] = self.shift
        attrs['shift_datetimes'] = [
            self.schedule_shift_start_datetime,
            self.schedule_shift_end_datetime,
            self.today_shift_start_datetime,
            self.today_shift_end_datetime
        ]

        attrs['order_restore_file'] = None
        if self.current_order is not None:
            attrs['order_restore_file'] = self.current_order.restore_file.name

        return attrs

    @classmethod
    def _restore(cls, attrs: Dict[str, Any], file: Path, **kwargs) -> Employee:
        initial_step, interval, max_step, next_step = attrs['base_params']
        age_recognition_rate, counting_skill_rate, \
            content_rate, discipline_rate = \
            attrs['skill_params']

        for person_restore_file in file.parent.rglob('person.json'):
            person_restore_file = str(person_restore_file)
            person = Person.restore(file.parent / person_restore_file)

        obj = cls(
            person,
            attrs['name'],
            initial_step,
            interval,
            age_recognition_rate,
            counting_skill_rate,
            content_rate,
            discipline_rate,
        )
        obj._max_step = max_step
        obj._next_step = next_step

        obj.status = attrs['status']
        obj.shift = attrs['shift']

        (
            obj.schedule_shift_start_datetime,
            obj.schedule_shift_end_datetime,
            obj.today_shift_start_datetime,
            obj.today_shift_end_datetime
        ) = attrs['shift_datetimes']

        if attrs['order_restore_file'] is not None:
            obj.current_order = Order.restore(
                file.parents[2]
                / 'Order'
                / attrs['order_rerstore_file']
            )
        return obj

    @classmethod
    def generate(
            cls,
            current_datetime: datetime,
            interval: float,
            age_recognition_loc: float = 4.0,
            age_recognition_scale: float = 0.5,
            counting_skill_loc: float = 4.5,
            counting_skill_scale: float = 0.050,
            content_rate_loc: float = 4.5,
            content_rate_scale: float = 0.5,
            discipline_rate_loc: float = 4.5,
            discipline_rate_scale: float = 0.5,
            seed: int = None,
            rng: np.random.RandomState = None
            ) -> Employee:
        if rng is None:
            rng = np.random.RandomState(seed)

        age_recognition_rate = np.clip(
            rng.normal(
                age_recognition_loc,
                age_recognition_scale
            ),
            1.0,
            5.0
        )
        counting_skill_rate = np.clip(
            rng.normal(
                counting_skill_loc,
                counting_skill_scale
            ),
            1.0,
            5.0
        )
        content_rate = np.clip(
            rng.normal(
                content_rate_loc,
                content_rate_scale
            ),
            1.0,
            5.0
        )
        discipline_rate = np.clip(
            rng.normal(
                discipline_rate_loc,
                discipline_rate_scale
            ),
            1.0,
            5.0
        )

        gender = Gender.MALE if rng.random() < 0.5 else Gender.FEMALE
        age = np.clip(
            rng.normal(24.0, 2.0),
            18.0,
            30.0
        )

        person = Person.generate(
            gender=gender,
            age=age,
            status=FamilyStatus.SINGLE,
            current_date=current_datetime.date(),
            seed=seed,
            rng=rng
        )
        return cls(
            person,
            'Unnamed',
            current_datetime,
            interval,
            age_recognition_rate=age_recognition_rate,
            counting_skill_rate=counting_skill_rate,
            content_rate=content_rate,
            discipline_rate=discipline_rate,
            seed=seed,
            rng=rng
        )

    @classmethod
    def bulk_generate(
            cls,
            n: int,
            current_date: date,
            age_recognition_loc: float = 4.0,
            age_recognition_scale: float = 0.5,
            counting_skill_loc: float = 4.5,
            counting_skill_scale: float = 0.050,
            content_rate_loc: float = 4.5,
            content_rate_scale: float = 0.5,
            discipline_rate_loc: float = 4.5,
            discipline_rate_scale: float = 0.5,
            seed: int = None,
            rng: np.random.RandomState = None,
            ) -> Employee:
        return [
            cls.generate(
                current_date,
                age_recognition_loc,
                age_recognition_scale,
                counting_skill_loc,
                counting_skill_scale,
                content_rate_loc,
                content_rate_scale,
                discipline_rate_loc,
                discipline_rate_scale,
                seed=seed,
                rng=rng
            )
            for _ in range(n)
        ]
