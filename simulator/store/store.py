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
    SubdistrictModel, EmployeeShiftScheduleModel,
    MODELS
)
from ..enums import EmployeeShift, EmployeeStatus
from ..population import Place
from .customer import Customer
from .order import Order, OrderStatus
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

    def assign_order_queue(self, employee: Employee) -> None:
        if len(self._order_queue) == 0:
            raise IndexError("There's no queue in the moment.")

        employee.current_order = self._order_queue.popleft()
        employee.status = EmployeeStatus.PROCESSING_ORDER

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
        previous_datetime = self.current_datetime
        current_step, next_step = super().step()
        current_datetime = cast(current_step, datetime)
        current_date = current_datetime.date()
        next_datetime = cast(next_step, datetime)

        if current_step >= next_step:
            raise

        if self.n_employees < self.max_employees:
            new_employees = []
            for _ in range(self.max_employees - self.n_employees):
                employee = Employee.generate(
                    datetime(
                        current_date.year,
                        current_date.month,
                        current_date.day
                    ) + timedelta(days=1, hours=6),
                    self.interval,
                    rng=self._rng
                )
                employee.created_datetime = current_datetime

                employee_dir = (
                    self.restore_file.parent
                    / 'Employee'
                    / employee.person.id
                )
                employee_dir.mkdir(parents=True, exist_ok=True)
                employee.person.push_restore(employee_dir / 'person.json')
                employee.push_restore(
                    employee_dir / 'employee.json',
                    tmp=True
                )

                self.add_employee(employee)
                new_employees.append(employee)

            self.schedule_shifts(
                date(
                    current_date.year,
                    current_date.month,
                    current_date.day
                ),
                new_employees
            )

        # Daily update
        if previous_datetime.day != current_datetime.day:
            self.total_orders = 0
            self.total_canceled_orders = 0
            self.customer_steps = 0
            self.employee_steps = 0

        # Update schedule working shifts midnight date 1st
        if current_datetime.month != previous_datetime.month:
            self.schedule_shifts(current_date, self._employees)

        return current_step, next_step

        for employee in self.employees():
            if employee.status in (
                    EmployeeStatus.STARTING_SHIFT,
                    EmployeeStatus.PROCESSING_ORDER
                    ):
                return current_step, next_step

        # Skip to the nearest customer step
        min_agent_step = None
        for agent in self.agents():
            if isinstance(agent, Customer):
                agent_next_step = agent.next_step

            elif agent.schedule_shift_start_datetime is not None \
                    and agent.schedule_shift_start_datetime > next_datetime \
                    and agent.today_shift_start_datetime is None:
                agent_next_step = \
                    agent.schedule_shift_start_datetime.timestamp()

            elif agent.schedule_shift_end_datetime is not None \
                    and agent.schedule_shift_end_datetime > next_datetime \
                    and agent.today_shift_end_datetime is None:
                agent_next_step = \
                    agent.schedule_shift_end_datetime.timestamp()

            else:
                continue

            if min_agent_step is None \
                    or agent_next_step < min_agent_step:
                min_agent_step = agent_next_step

        if min_agent_step is not None:
            self._next_step = min_agent_step

        return current_step, self._next_step

    def update_market_population(self, current_datetime: datetime) -> None:
        family_dir = self.restore_file.parent / 'Customer'

        old_family_ids, new_family_ids = \
            self.place.get_population_update(current_datetime.date())

        old_customers = {
            agent.family.id: agent
            for agent in self.agents()
            if isinstance(agent, Customer)
        }

        family_ids_to_be_removed = old_family_ids - new_family_ids
        for family_id in family_ids_to_be_removed:
            self.remove_agent(old_customers[family_id])
            shutil.rmtree(family_dir / family_id)

        for family_id in new_family_ids:
            customer_initial_datetime = self.initial_datetime
            if current_datetime > self.initial_datetime:
                customer_initial_datetime = current_datetime
            customer = Customer(
                customer_initial_datetime,
                self.interval,
                rng=self._rng
            )
            customer.push_restore(
                family_dir
                / family_id
                / 'customer.json'
            )
            self.add_agent(customer)

        self.place.push_restore()
        self.push_restore()

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
            max_employees=max_employees,
            max_cashiers=max_cashiers,
            max_queue=max_queue,
            rng=place._rng
        )
        obj._max_step = max_step
        obj._next_step = next_step

        for model in MODELS:
            model.delete()\
                .where(model.created_datetime > obj.current_datetime)\
                .execute()

        order_ids = set()
        order_dir = file.parent / 'Order'

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

            if employee.current_order is not None:
                order_ids.add(
                    employee.current_order.restore_file.name.split('.')[0]
                )

        customer_dir = base_dir / 'Customer'
        for customer_restore_file in customer_dir.glob('*/customer.json'):
            customer_restore_file = str(customer_restore_file)
            customer = Customer.restore(
                customer_dir / customer_restore_file,
                rng=obj._rng
            )
            obj.add_agent(customer)
            if customer.current_order is not None:
                order_ids.add(
                    customer.current_order.restore_file.name.split('.')[0]
                )
                if customer.current_order.status == OrderStatus.QUEUING:
                    obj._order_queue.append(customer.current_order)

        for order_restore_file in order_dir.rglob('*.json*'):
            if order_restore_file not in order_ids:
                order_restore_file.unlink()

        obj.total_orders = attrs['total_orders']
        return obj
