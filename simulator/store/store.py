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
    EmployeeModel, EmployeeShiftScheduleModel,
    SubdistrictModel, OrderModel
)
from ..enums import EmployeeShift, EmployeeStatus
from ..logging import store_logger, simulator_log_format
from ..population import Place
from .customer import Customer
from .order import Order
from .employee import Employee
from .manager import Manager
from .sku import Product


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
            max_employees: int = None,
            max_cashiers: int = None,
            max_queue: int = 15,
            seed: int = None,
            rng: np.random.RandomState = None
            ) -> None:
        super().__init__(
            cast(initial_datetime, float),
            cast(interval, float),
            skip_step=True,
            seed=seed,
            rng=rng
        )

        self.place = place

        self.manager = Manager(
            self.initial_step,
            self.interval
        )
        self.add_agent(self.manager)

        # Add initial employees
        self._employees: List[Employee] = []

        if max_employees is None:
            max_employees = GlobalContext.STORE_MAX_EMPLOYEES
        self.max_employees = max_employees

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

        self._cashiers: List[Employee] = []
        if max_cashiers is None:
            max_cashiers = GlobalContext.STORE_MAX_CASHIERS
        self.max_cashiers = max_cashiers

        self._customers: List[Customer] = []
        self._order_queue: Deque[Order] = deque(maxlen=max_queue)

        place_record: SubdistrictModel = self.place.record
        super().__init_model__(
            unique_identifiers={'subdistrict': place_record.id},
            subdistrict_id=place_record.id
        )

        self.total_orders = 0
        self.total_canceled_orders = 0
        self.employee_steps = 0
        self.customer_steps = 0

    @property
    def place_name(self) -> str:
        return self.place.name

    def total_market_population(self) -> int:
        return self.place.total_population()

    @property
    def products(self) -> Dict[str, Product]:
        return self.parent.products

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
            employee.status = EmployeeStatus.OFF
        except Exception:
            pass

    def potential_customers(self) -> Iterable[Customer]:
        customer_dir = self.restore_file.parent / 'Customer'
        for file in customer_dir.rglob('customer.json'):
            customer = Customer.restore(
                customer_dir / str(file),
                tmp=True,
                products=self.products,
                rng=self._rng
            )
            yield customer

    @property
    def n_customers(self) -> int:
        return len(self._customers)

    def customers(self) -> Iterable[Customer]:
        for customer in self._customers:
            yield customer

    def add_customer(self, customer: Customer) -> None:
        self._customers.append(customer)
        self.add_agent(customer)

    def clear_customers(self) -> None:
        self.remove_agents(self._customers)
        self._customers = []

    def assign_order_queue(self, employee: Employee) -> None:
        if len(self._order_queue) == 0:
            raise IndexError("There's no queue in the moment.")

        employee.current_order = self._order_queue.popleft()
        employee.status = EmployeeStatus.PROCESSING_ORDER
        employee._next_step = self.next_step

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
        if order in self._order_queue:
            return

        self._order_queue.append(order)

        self._rng.shuffle(self._cashiers)
        for employee in self.cashiers():
            if employee.current_order is None:
                self.assign_order_queue(employee)
                return

    def remove_order_queue(self, order: Order) -> None:
        self._order_queue.remove(order)

    def step(self) -> Tuple[datetime, Union[datetime, None]]:
        previous_datetime = self.current_datetime
        current_step, next_step = super().step()
        current_datetime = cast(current_step, datetime)
        current_date = current_datetime.date()

        # Daily update
        if previous_datetime.day != current_datetime.day:
            self.total_orders = 0
            self.total_canceled_orders = 0
            self.customer_steps = 0
            self.employee_steps = 0
            self.clear_customers()

        if self.n_customers == 0:
            _time = datetime.now()

            for customer in self.potential_customers():
                if customer.next_date <= current_date:
                    self.add_customer(customer)

            store_logger.info(simulator_log_format(
                f'Store {self.place_name} -',
                f'{self.n_customers} customer(s) is cached.',
                f'{(datetime.now() - _time).total_seconds():.1f}s.',
                dt=current_datetime
            ))

        # Update schedule working shifts midnight date 1st
        if current_datetime.month != previous_datetime.month:
            self.schedule_shifts(current_date, self._employees)

        return current_step, self._next_step

    def update_market_population(self, current_datetime: datetime) -> None:
        customer_initial_datetime = self.initial_datetime
        if current_datetime > self.initial_datetime:
            customer_initial_datetime = current_datetime

        families = \
            self.place.get_population_update(current_datetime.date())

        for family in families:
            if family.n_members == 0:
                shutil.rmtree(family.restore_file.parent)
                continue

            family.push_restore()

            customer_restore_file = (
                family.restore_file.parent
                / 'customer.json'
            )
            if not customer_restore_file.exists():
                customer = Customer(
                    customer_initial_datetime,
                    self.interval,
                    rng=self._rng
                )
                customer.restore_file = customer_restore_file
            else:
                customer = Customer.restore(
                    customer_restore_file,
                    tmp=True,
                    products=self.products
                )

            customer.push_restore(products=self.products)

        self.place.push_restore()

    def schedule_shifts(
            self,
            shift_month: date,
            employees: List[Employee]
            ) -> None:
        shifts = (
            [EmployeeShift.FIRST, EmployeeShift.SECOND]
            * int(np.ceil(self.n_employees / 2))
        )[:len(employees)]
        self._rng.shuffle(shifts)

        self.employee_shift_schedules.update({
            employee.record_id: shift
            for employee, shift in zip(employees, shifts)
        })

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

        return attrs

    def _push_restore(
            self,
            file: Path = None,
            tmp: bool = False,
            **kwargs
            ) -> None:
        if not tmp:
            self.update_market_population(self.current_datetime)

            for employee in self.employees():
                employee.push_restore()

        super()._push_restore(file, tmp=tmp, **kwargs)

    @classmethod
    def _restore(cls, attrs: Dict[str, Any], file: Path, **kwargs) -> Store:
        base_dir = file.parent

        initial_step, interval, max_step, \
            current_step, next_step, skip_step = attrs['base_params']
        max_employees, max_cashiers, max_queue = attrs['max_params']
        place = Place.restore(base_dir / 'place.json')
        obj = cls(
            place,
            initial_datetime=initial_step,
            interval=interval,
            max_employees=max_employees,
            max_cashiers=max_cashiers,
            max_queue=max_queue,
            rng=place._rng
        )
        obj._max_step = max_step
        obj._current_step = current_step
        obj._next_step = next_step

        # Delete temporary employee records
        EmployeeModel.delete() \
            .where(EmployeeModel.store_id == obj.record_id) \
            .where(EmployeeModel.created_datetime > obj.current_datetime) \
            .execute()

        # Delete temporary orders
        OrderModel.delete() \
            .where(OrderModel.store_id == obj.record_id) \
            .where(OrderModel.created_datetime > obj.current_datetime) \
            .execute()

        # Restore employees
        employee_dir = base_dir / 'Employee'
        for employee_restore_file in (
                employee_dir.glob('*/employee.json')
                ):
            employee = Employee.restore(
                employee_dir / str(employee_restore_file)
            )

            if employee.record_id is None:
                shutil.rmtree(employee_restore_file.parent)
                continue

            obj.add_employee(employee)
            shift, is_cashier = attrs['employee_info'][employee.person.id]
            obj.employee_shift_schedules[employee.record_id] = \
                getattr(EmployeeShift, shift)
            if is_cashier:
                obj._cashiers.append(employee)

        return obj
