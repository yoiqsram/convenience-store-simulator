from __future__ import annotations

import numpy as np
from collections import deque
from datetime import date, datetime, timedelta
from typing import Deque, Dict, Iterable, List, Tuple, Union, TYPE_CHECKING

from ..context import GlobalContext
from ..core import MultiAgent, DatetimeStepMixin
from ..database import Database, ModelMixin, StoreModel, SubdistrictModel, EmployeeShiftScheduleModel
from ..enums import EmployeeShift, EmployeeStatus
from ..logging import store_logger
from .customer import Customer
from .order import Order
from .employee import Employee

if TYPE_CHECKING:
    from ..population.place import Place


class Store(MultiAgent, DatetimeStepMixin, ModelMixin):
    __repr_attrs__ = ( 'place_name', 'n_employees', 'total_market_population', 'current_datetime' )
    __model__ = StoreModel

    def __init__(
            self,
            place: Place,
            initial_datetime: datetime,
            interval: float,
            skip_step: bool = False,
            max_cashiers: int = None,
            max_employees: int = None,
            max_queue: int = 15,
            seed: int = None
        ) -> None:
        super().__init__(
            initial_datetime,
            interval,
            skip_step=skip_step,
            seed=seed
        )

        # Add potential customers from the place
        self.place = place
        self.update_market_population(initial_datetime)

        # Add initial employees
        self._employees: List[Employee] = []
        self.max_employees = max_employees if max_employees is not None else GlobalContext.STORE_INITIAL_EMPLOYEES
        for _ in range(GlobalContext.STORE_INITIAL_EMPLOYEES):
            employee = Employee.generate(
                self.place,
                initial_datetime,
                interval,
                rng=self._rng
            )
            self.add_employee(employee)

        # Schedule initial shifts
        self.start_shift_hours = {
            EmployeeShift.FIRST: GlobalContext.STORE_OPEN_HOUR,
            EmployeeShift.SECOND: (GlobalContext.STORE_OPEN_HOUR + GlobalContext.STORE_CLOSE_HOUR) / 2
        }
        self.long_shift_hours = timedelta(hours=(GlobalContext.STORE_CLOSE_HOUR - GlobalContext.STORE_OPEN_HOUR) / 2)
        self.employee_shift_schedules: Dict[int, EmployeeShift] = {
            employee: EmployeeShift.NONE
            for employee in self._employees
        }
        self.schedule_shifts(shift_month=date(initial_datetime.year, initial_datetime.month, 1))

        self._cashiers: List[Employee] = []
        self.max_cashiers = max_cashiers if max_cashiers is not None else GlobalContext.STORE_MAX_CASHIERS        

        self._order_queue: Deque[Order] = deque(maxlen=max_queue)

        place_record: SubdistrictModel = self.place.record
        super().__init_model__(
            unique_identifiers={ 'subdistrict': place_record.id },
            subdistrict_id=place_record.id
        )
        self.created_datetime = initial_datetime

        self.total_orders = 0

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
        except:
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
        except:
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
        except:
            pass

    def step(self) -> Tuple[datetime, Union[datetime, None]]:
        previous_datetime = self.current_datetime()
        current_datetime, next_datetime = super().step()
        current_date = current_datetime.date()

        # Update population daily
        if self.place.last_updated_date < current_date:
            self.update_market_population(current_datetime)
            self.total_orders = 0

        # Update schedule working shifts midnight date 1st
        if current_datetime.month != previous_datetime.month:
            self.schedule_shifts(current_date)

        return current_datetime, next_datetime

    def update_market_population(self, current_datetime: datetime) -> None:
        self.place.update_population(current_datetime.date())

        old_market_population = {
            agent.family.id: agent
            for agent in self.agents()
            if isinstance(agent, Customer)
        }
        old_family_ids = set(old_market_population.keys())

        new_market_families = {
            family.id: family
            for family in self.place.families
        }
        new_family_ids = set(new_market_families.keys())

        family_ids_to_be_removed = old_family_ids - new_family_ids
        for family_id in family_ids_to_be_removed:
            self.remove_agent(old_market_population[family_id])

        family_ids_to_be_added = new_family_ids - old_family_ids
        for family_id, seed in zip(
                family_ids_to_be_added,
                self.random_seed(len(family_ids_to_be_added))
            ):
            customer = Customer(
                new_market_families[family_id],
                current_datetime,
                self.interval,
                seed=seed
            )
            self.add_agent(customer)

    def schedule_shifts(self, shift_month: date) -> None:
        shifts = (
            [ EmployeeShift.FIRST, EmployeeShift.SECOND ]
            * int(np.ceil(self.n_employees / 2))
        )[:self.n_employees]
        self._rng.shuffle(shifts)

        self.employee_shift_schedules = {
            employee.record_id: shift
            for employee, shift in zip(self._employees, shifts)
        }

        database: Database = EmployeeShiftScheduleModel._meta.database
        with database.atomic():
            created_datetime = datetime(shift_month.year, shift_month.month, shift_month.day)
            shift_datetime = created_datetime
            next_shift_datetime = shift_datetime + timedelta(days=1)
            while shift_datetime.month != shift_month.month:
                shift_start_datetime = (
                    shift_datetime
                    + timedelta(hours=self.start_shift_hours[shift])
                )
                shift_end_datetime = shift_start_datetime + self.long_shift_hours

                try:
                    for record in (
                            EmployeeShiftScheduleModel.select()
                            .where(EmployeeShiftScheduleModel.shift_start_datetime.between(shift_datetime, next_shift_datetime))
                            .execute()
                        ):
                        record: EmployeeShiftScheduleModel
                        shift = self.employee_shift_schedules[record.employee_id]
                        record.shift_start_datetime = shift_start_datetime
                        record.shift_end_datetime = shift_end_datetime
                        record.created_datetime = created_datetime
                        record.save()

                except:
                    for employee_id, shift in self.employee_shift_schedules.items():
                        EmployeeShiftScheduleModel.create(
                            employee=employee_id,
                            shift_start_datetime=shift_start_datetime,
                            shift_end_datetime=shift_end_datetime,
                            current_datetime=created_datetime
                        )

                shift_datetime = next_shift_datetime
                next_shift_datetime += timedelta(days=1)
