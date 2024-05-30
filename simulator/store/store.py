from __future__ import annotations

import numpy as np
import shutil
from collections import deque
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import (
    Any, Deque, Dict, Iterable, List, Tuple, Union
)

from ..context import GlobalContext
from ..core import MultiAgent, DatetimeStepMixin
from ..core.utils import cast
from ..database import (
    Database, ModelMixin, StoreModel,
    SubdistrictModel, EmployeeShiftScheduleModel
)
from ..enums import EmployeeShift, EmployeeStatus
from ..population import Place
from .customer import Customer
from .order import Order
from .employee import Employee


class Store(
        MultiAgent,
        DatetimeStepMixin, ModelMixin,
        model=StoreModel,
        repr_attrs=(
            'place_name', 'n_employees', 'current_datetime'
        )):
    def __init__(
            self,
            place: Place,
            initial_datetime: datetime = None,
            interval: float = None,
            skip_step: bool = False,
            initial_employees: int = None,
            max_employees: int = None,
            max_cashiers: int = None,
            max_queue: int = 15,
            seed: int = None,
            rng: np.random.RandomState = None
            ) -> None:
        super().__init__(
            initial_datetime,
            interval,
            skip_step=skip_step,
            seed=seed,
            rng=rng
        )

        self.place = place

        # Add initial employees
        self._employees: List[Employee] = []

        if max_employees is None:
            max_employees = GlobalContext.STORE_INITIAL_EMPLOYEES
        self.max_employees = max_employees

        if initial_employees is None:
            initial_employees = GlobalContext.STORE_INITIAL_EMPLOYEES

        for _ in range(initial_employees):
            employee = Employee.generate(
                self.initial_datetime,
                self.interval,
                rng=self._rng
            )
            self.add_employee(employee)

        # Schedule initial shifts
        self.start_shift_hours = {
            EmployeeShift.FIRST: GlobalContext.STORE_OPEN_HOUR,
            EmployeeShift.SECOND: (
                GlobalContext.STORE_OPEN_HOUR
                + GlobalContext.STORE_CLOSE_HOUR
            ) / 2
        }
        self.long_shift_hours = timedelta(
            hours=(
                GlobalContext.STORE_CLOSE_HOUR
                - GlobalContext.STORE_OPEN_HOUR
            ) / 2
        )
        self.employee_shift_schedules: Dict[Employee, EmployeeShift] = {
            employee.record_id: EmployeeShift.NONE
            for employee in self._employees
        }
        self.schedule_shifts(
            shift_month=date(
                self.initial_datetime.year,
                self.initial_datetime.month,
                1
            )
        )

        self._cashiers: List[Employee] = []
        if max_cashiers is None:
            max_cashiers = GlobalContext.STORE_MAX_CASHIERS
        self.max_cashiers = max_cashiers

        self._order_queue: Deque[Order] = deque(maxlen=max_queue)

        place_record: SubdistrictModel = self.place.record
        super().__init_model__(
            unique_identifiers={'subdistrict': place_record.id},
            subdistrict_id=place_record.id
        )
        self.created_datetime = self.initial_datetime

        self.total_orders = 0
        self.potential_customers = 0

    @property
    def place_name(self) -> str:
        return self.place.name

    def total_market_population(self) -> int:
        return self.place.total_population()

    def employees(self) -> Iterable[Employee]:
        for employee in self._employees:
            yield employee

    @property
    def n_employees(self) -> int:
        return len(self._employees)

    def total_active_shift_employees(self) -> int:
        return len([
            employee
            for employee in self._employees
            if employee.today_shift_start_datetime is not None
        ])

    def get_active_employees(self) -> List[Employee]:
        return [
            employee
            for employee in self.employees()
            if employee.status not in (
                EmployeeStatus.OFF,
                EmployeeStatus.OUT_OF_OFFICE
            )
        ]

    def cashiers(self) -> Iterable[Employee]:
        for cashier in self._cashiers:
            yield cashier

    @property
    def n_cashiers(self) -> int:
        return len(self._cashiers)

    @property
    def n_order_queue(self) -> int:
        return len(self._order_queue)

    def add_employee(self, employee: Employee) -> None:
        if employee in self._employees:
            raise IndexError('Employee is already registered in the store.')

        employee.created_datetime = self.current_datetime()
        self._employees.append(employee)
        self.add_agent(employee)

    def remove_employee(self, employee: Employee) -> None:
        try:
            self._employees.remove(employee)
        except Exception:
            pass

        self.remove_agent(employee)

    def assign_cashier(self, employee: Employee) -> None:
        if len(self._cashiers) == self.max_cashiers:
            raise IndexError("There's no idle cashier machine.")

        self._cashiers.append(employee)
        employee.status = EmployeeStatus.IDLE

    def dismiss_cashier(self, employee: Employee) -> None:
        try:
            self._cashiers.remove(employee)
        except Exception:
            pass

    def assign_order_queue(self, employee: Employee) -> None:
        if len(self._order_queue) == 0:
            raise IndexError("There's no queue in the moment.")

        employee.current_order = self._order_queue.popleft()

    def is_open(self) -> bool:
        for employee in self.employees():
            if employee.status not in (
                    EmployeeStatus.OFF,
                    EmployeeStatus.OUT_OF_OFFICE
                    ):
                return True
        return False

    def is_full_queue(self) -> bool:
        return len(self._order_queue) == self._order_queue.maxlen

    def add_order_queue(self, order: Order) -> None:
        if order not in self._order_queue:
            self._order_queue.append(order)

    def remove_order_queue(self, order: Order) -> None:
        try:
            self._order_queue.remove(order)
        except Exception:
            pass

    def step(self) -> Tuple[datetime, Union[datetime, None]]:
        previous_datetime = self.current_datetime()
        current_datetime, next_datetime = super().step()
        current_date = current_datetime.date()

        # Update population daily
        if previous_datetime.day != current_datetime.day:
            self.total_orders = 0
            self.potential_customers = len([
                agent.next_date() <= current_date
                for agent in self.agents()
                if isinstance(agent, Customer)
            ])

        # Update schedule working shifts midnight date 1st
        if current_datetime.month != previous_datetime.month:
            self.schedule_shifts(current_date)

        return current_datetime, next_datetime

    def update_market_population(self, current_datetime: datetime) -> None:
        old_families, new_families = \
            self.place.get_population_update(current_datetime.date())

        old_customers = {
            agent.family.id: agent
            for agent in self.agents()
            if isinstance(agent, Customer)
        }

        olf_family_ids = set(old_families.keys())
        family_ids_to_be_removed = \
            olf_family_ids - set(new_families.keys())
        for family_id in family_ids_to_be_removed:
            self.remove_agent(old_customers[family_id])
            family = old_families[family_id]
            shutil.rmtree(family.restore_file.parent)

        for family_id, family in new_families:
            family_dir = (
                self.restore_file.parent
                / 'Family'
                / family_id
            )
            family_dir.mkdir(parents=True, exist_ok=True)
            family.push_restore(family_dir / 'family.json')

            customer_initial_datetime = self.initial_datetime
            if current_datetime > self.initial_datetime:
                customer_initial_datetime = current_datetime
            customer = Customer(
                customer_initial_datetime,
                self.interval,
                self._rng
            )
            customer.push_restore(family_dir / '')
            shutil.copy(
                customer.restore_file,
                customer.restore_file.parent
                / (customer.restore_file.name / '.tmp')
            )

            self.add_agent(customer)

        self.place.push_restore()
        self.push_restore()

    def schedule_shifts(self, shift_month: date) -> None:
        shifts = (
            [EmployeeShift.FIRST, EmployeeShift.SECOND]
            * int(np.ceil(self.n_employees / 2))
        )[:self.n_employees]
        self._rng.shuffle(shifts)

        self.employee_shift_schedules = {
            employee.record_id: shift
            for employee, shift in zip(self._employees, shifts)
        }

        database: Database = EmployeeShiftScheduleModel._meta.database
        with database.atomic():
            created_datetime = datetime(
                shift_month.year,
                shift_month.month,
                shift_month.day
            )
            shift_datetime = created_datetime
            next_shift_datetime = shift_datetime + timedelta(days=1)
            while shift_datetime.month != shift_month.month:
                try:
                    for record in (
                            EmployeeShiftScheduleModel.select()
                            .where(
                                EmployeeShiftScheduleModel.shift_start_datetime
                                .between(shift_datetime, next_shift_datetime)
                            )
                            .execute()
                            ):
                        record: EmployeeShiftScheduleModel
                        shift = \
                            self.employee_shift_schedules[record.employee_id]
                        shift_start_datetime = (
                            shift_datetime
                            + timedelta(hours=self.start_shift_hours[shift])
                        )
                        shift_end_datetime = (
                            shift_start_datetime
                            + self.long_shift_hours
                        )
                        record.shift_start_datetime = shift_start_datetime
                        record.shift_end_datetime = shift_end_datetime
                        record.created_datetime = created_datetime
                        record.save()

                except Exception:
                    for employee_id, shift in (
                            self.employee_shift_schedules.items()
                            ):
                        shift_start_datetime = (
                            shift_datetime
                            + timedelta(hours=self.start_shift_hours[shift])
                        )
                        shift_end_datetime = (
                            shift_start_datetime
                            + self.long_shift_hours
                        )
                        EmployeeShiftScheduleModel.create(
                            employee=employee_id,
                            shift_start_datetime=shift_start_datetime,
                            shift_end_datetime=shift_end_datetime,
                            current_datetime=created_datetime
                        )

                shift_datetime = next_shift_datetime
                next_shift_datetime += timedelta(days=1)

    @property
    def restore_attrs(self) -> Dict[str, Any]:
        attrs = super().restore_attrs
        attrs['max_params'] = [
            self.max_employees,
            self.max_cashiers,
            self._order_queue.maxlen
        ]

        attrs['employee_info'] = {
            employee.person.id: [
                self.employee_shift_schedules[employee.record_id].name,
                employee in self._cashiers
            ]
            for employee in self.employees()
        }

        attrs['created_datetime'] = self.created_datetime
        attrs['total_orders'] = self.total_orders
        return attrs

    def _push_restore(
            self,
            file: Path = None,
            tmp: bool = False,
            **kwargs
            ) -> None:
        if not tmp:
            for agent in self.agents():
                if hasattr(agent, 'current_order') \
                        and agent.current_order is not None:
                    agent.current_order.push_restore()
                agent.push_restore()

        super()._push_restore(file, tmp=tmp, **kwargs)

    @classmethod
    def _restore(cls, attrs: Dict[str, Any], file: Path, **kwargs) -> Store:
        base_dir = file.parent

        initial_step, interval, max_step, \
            next_step, skip_step = attrs['base_params']
        max_employees, max_cashiers, max_queue = attrs['max_params']
        place = Place.restore(base_dir / 'place.json')
        obj = cls(
            place,
            initial_datetime=initial_step,
            interval=interval,
            skip_step=skip_step,
            initial_employees=0,
            max_employees=max_employees,
            max_cashiers=max_cashiers,
            max_queue=max_queue
        )
        obj._max_step = cast(max_step, datetime)
        obj._next_step = cast(next_step, datetime)
        obj._skip_step = skip_step

        employee_dir = base_dir / 'Employee'
        for employee_restore_file in (
                employee_dir.glob('*/employee.json')
                ):
            employee_restore_file = str(employee_restore_file)
            employee = Employee.restore(employee_dir / employee_restore_file)
            obj._employees.append(employee)
            obj.add_agent(employee)

            shift, is_cashier = attrs['employee_info'][employee.person.id]
            obj.employee_shift_schedules[employee.record_id] = \
                getattr(EmployeeShift, shift)
            if is_cashier:
                obj._cashiers.append(employee)

        customer_dir = base_dir / 'Customer'
        for customer_restore_file in customer_dir.glob('*/customer.json'):
            customer_restore_file = str(customer_restore_file)
            customer = Customer.restore(customer_dir / customer_restore_file)
            obj.add_agent(customer)

        order_dir = base_dir / 'Order'
        for order_restore_file in order_dir.glob('*.json'):
            order_restore_file = str(order_restore_file)
            order = Order.restore(order_dir / order_restore_file)
            obj.add_order_queue(order)

        obj.created_datetime = attrs['created_datetime']
        obj.total_orders = attrs['total_orders']
        return obj
