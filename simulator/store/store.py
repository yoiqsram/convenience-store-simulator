from __future__ import annotations

import numpy as np
import orjson
from collections import deque
from datetime import datetime
from pathlib import Path
from time import time
from typing import Generator

from core import MultiAgent, DateTimeStepMixin
from core.utils import cast, load_memmap_to_array, dump_memmap_to_array

from ..context import GlobalContext, DAYS_IN_YEAR, SECONDS_IN_DAY
from ..database import (
    ModelMixin, EmployeeModel,
    StoreModel, OrderModel
)
from ..database.config import (
    ProductConfigModel,
    ProductBuyerModifierConfigModel,
    ProductAssociationConfigModel
)
from ..enums import (
    AgeGroup, Gender,
    EmployeeStatus, PaymentMethod
)
from ..logging import store_logger, simulator_log_format
from .customer import Customer
from .order import Order
from .employee import Employee
from .manager import Manager
from .place import Place


class Store(
        MultiAgent,
        DateTimeStepMixin, ModelMixin,
        model=StoreModel,
        repr_attrs=(
            'place_name',
            'total_market_population',
            'current_datetime'
        )):
    def __init__(
            self,
            place: Place,
            initial_datetime: datetime = None,
            interval: float = 1.,
            max_employees: int = None,
            max_cashiers: int = None,
            max_queue: int = 15,
            product_config: tuple[np.ndarray, np.ndarray, np.ndarray] = None,
            customer_config: tuple[np.ndarray, np.ndarray, np.ndarray] = None,
            employee_params: np.ndarray = None,
            seed: int = None,
            rng: np.random.RandomState = None
            ) -> None:
        self.place = place
        self.total_orders = 0
        self.total_steps = 0
        self.total_employee_steps = 0
        self.total_customer_steps = 0
        self._order_queue: deque[Order] = deque(maxlen=max_queue)

        super().__init__(
            cast(initial_datetime or time(), int),
            interval=interval,
            skip_step=True,
            seed=seed,
            rng=rng
        )

        super().__init_model__(
            unique_identifiers={'subdistrict': self.place.record.id}
        )
        if self.record_id is None:
            self.created_datetime = self.current_datetime

        # Setup product config
        (
            self._products,
            self._product_need_days_left,
            self._product_modifiers,
            self._product_associations
            ) = self.init_product_config(product_config)

        # Setup potential customers
        (
            self._customers,
            self._customer_steps,
            self._customer_product_need_days_left,
            self._customer_payment_methods
            ) = self.init_customer_config(self.place.n_families, customer_config)
        for i, customer in enumerate(self._customers):
            customer._index = i

        # Setup employees
        self.start_shift_hours, self.long_shift_hours = \
            self.get_shift_hours()
        self.max_employees = max_employees or GlobalContext.STORE_MAX_EMPLOYEES
        self.max_cashiers = max_cashiers or GlobalContext.STORE_MAX_CASHIERS
        (
            manager,
            employees,
            self._employee_params
            ) = self.init_employees(employee_params)
        self.add_agent(manager)

        self._employees = []
        for employee in employees:
            self.add_employee(employee)

        self.last_updated_timestamp = None

    def init_product_config(
            self,
            product_config: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray] = None
            ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        if product_config is not None:
            (
                products,
                product_need_days_left,
                product_modifiers,
                product_associations
                ) = product_config

        else:
            age_groups = {
                enum.name: i
                for i, enum in enumerate(AgeGroup)
            }
            records = [
                record
                for record in (
                    ProductConfigModel.select()
                    .order_by(ProductConfigModel.id)
                    )
            ]
            record_indexes = {
                record.id: i
                for i, record in enumerate(records)
            }

            products = np.array([
                record.name
                for record in records
            ])
            product_need_days_left = np.array([
                record.interval_days_need
                for record in records
                ],
                dtype=np.uint16
            )

            product_modifiers = (
                np.repeat(
                    np.array([
                        record.modifier
                        for record in records
                    ], dtype=np.float16),
                    len(AgeGroup) * len(Gender)
                )
                .reshape((
                    product_need_days_left.shape[0],
                    len(AgeGroup),
                    len(Gender)
                ))
            )
            product_associations = np.zeros(
                (len(products), len(products)), dtype=np.float16
            )
            for buyer_modifier in ProductBuyerModifierConfigModel.select():
                index = record_indexes[buyer_modifier.product_id]
                product_modifiers[
                    index,
                    age_groups[buyer_modifier.age_group],
                    getattr(Gender, buyer_modifier.gender).value
                    ] *= buyer_modifier.modifier

                for association in (
                        ProductAssociationConfigModel.select()
                        .where(
                            ProductAssociationConfigModel.product_id
                            == buyer_modifier.product_id
                        )):
                    associated_index = record_indexes[association.associated_product_id]
                    product_associations[
                        index,
                        associated_index
                        ] = association.strength

        return (
            products,
            product_need_days_left,
            product_modifiers,
            product_associations
        )

    def init_customer_config(
            self,
            n: int,
            customer_config: tuple[np.ndarray, np.ndarray, np.ndarray] = None
            ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        if customer_config is not None:
            (
                customer_steps,
                customer_product_need_days_left,
                customer_payment_methods
                ) = customer_config

        else:
            customer_steps = self.generate_customer_steps(n)
            customer_product_need_days_left = self._rng.uniform(
                    0,
                    self._product_need_days_left,
                    (n, self._product_need_days_left.shape[0])
                ).astype(np.uint16)

            # PAYMENT METHOD
            customer_payment_methods = np.zeros(
                (n, len(PaymentMethod), 2),
                dtype=np.float16
                )

            # Payment method prob
            customer_payment_methods[:, :, 0] = np.concatenate((
                self._rng.normal(.80, .40, (n, 1)),  # CASH
                self._rng.normal(.10, .05, (n, 1)),  # DIGITAL_CASH
                self._rng.normal(.07, .03, (n, 1)),  # DEBIT_CARD
                self._rng.normal(.03, .01, (n, 1))   # CREDIT_CARD
                ), axis=1
                )
            customer_payment_methods[:, :, 0] = np.abs(
                customer_payment_methods[:, :, 0]
                )
            customer_payment_methods[:, :, 0] = (
                customer_payment_methods[:, :, 0]
                / np.sum(customer_payment_methods[:, :, 0], axis=1).reshape((-1, 1))
                )

            # Payment method time
            customer_payment_methods[:, :, 1] = np.concatenate((
                np.clip(self._rng.normal(5., 1., (n, 1)), 2., 15.),    # CASH
                np.clip(self._rng.normal(10., 2., (n, 1)), 5., 30.),   # DIGITAL_CASH
                np.clip(self._rng.normal(20., 3., (n, 1)), 10., 45.),  # DEBIT_CARD
                np.clip(self._rng.normal(15., 3., (n, 1)), 10., 45.),  # CREDIT_CARD
                ), axis=1
                )

        # Customer agents
        customers = []
        for i in range(customer_steps.shape[0]):
            customer = Customer(self, i, rng=self._rng)
            customer._steps = customer_steps[i]
            customers.append(customer)

        return (
            customers,
            customer_steps,
            customer_product_need_days_left,
            customer_payment_methods
            )

    def get_shift_hours(self) -> tuple[float, float]:
        start_shift_hours = [
            GlobalContext.STORE_OPEN_HOUR,
            (
                GlobalContext.STORE_OPEN_HOUR
                + GlobalContext.STORE_CLOSE_HOUR
            ) / 2
            ]
        long_shift_hours = (
            GlobalContext.STORE_CLOSE_HOUR
            - GlobalContext.STORE_OPEN_HOUR
            ) / len(start_shift_hours)
        return start_shift_hours, long_shift_hours

    def init_employees(
            self,
            employee_params: np.ndarray = None
            ) -> tuple[Manager, list[Employee], np.ndarray]:
        manager = Manager(rng=self._rng)
        manager._steps = self._steps.copy()

        employees = []
        if employee_params is not None:
            for record in (
                    EmployeeModel.select()
                    .where(EmployeeModel.store_id == self.record_id)
                    ):
                employee = Employee(rng=self._rng, record_id=record.id)
                employee._steps = self._steps.copy()
                employees.append(employee)

        return manager, employees, employee_params

    @property
    def place_name(self) -> str:
        return self.place.name

    def total_market_population(self) -> int:
        return self.place.total_population()

    @property
    def n_order_queue(self) -> int:
        return len(self._order_queue)

    @property
    def n_employees(self) -> int:
        return len(self._employees)

    def employees(self) -> Generator[Employee]:
        for employee in self._employees:
            yield employee

    def cashiers(self) -> Generator[Employee]:
        for employee in self._employees:
            if employee.status in (
                    EmployeeStatus.IDLE,
                    EmployeeStatus.PROCESSING_ORDER):
                yield employee

    @property
    def n_cashiers(self) -> int:
        return len(list(self.cashiers()))

    def is_open(self) -> bool:
        for employee in self.employees():
            if employee.status not in (
                    EmployeeStatus.OFF,
                    EmployeeStatus.OUT_OF_OFFICE
                    ):
                return True
        return False

    def is_full_queue(self) -> bool:
        return self.n_order_queue == self._order_queue.maxlen

    def total_active_shift_employees(self) -> int:
        return len([
            employee
            for employee in self._employees
            if employee.today_shift_start_timestamp is not None
        ])

    def add_employee(self, employee: Employee) -> None:
        if employee in self._employees:
            raise IndexError('Employee is already registered in the store.')

        employee_param = (
            self._rng.normal(
                [4.0, 4.5, 4.5, 4.5],
                [0.5, 0.05, 0.25, 0.25],
            )
            .reshape((1, -1))
            .astype(np.float16)
        )
        if self._employee_params is None:
            self._employee_params = employee_param
        else:
            self._employee_params = np.concatenate(
                (self._employee_params, employee_param),
                axis=0
            )

        employee._steps = self._steps.copy()
        self.add_agent(employee)
        self._employees.append(employee)
        employee._record.store_id = self.record_id

    def add_order_queue(self, order: Order) -> None:
        if order in self._order_queue:
            return

        self._order_queue.append(order)

        for employee in self.cashiers():
            if employee.current_order is None:
                self.assign_order_queue(employee)
                return

    def remove_order_queue(self, order: Order) -> None:
        if order in self._order_queue:
            self._order_queue.remove(order)

    def assign_order_queue(self, employee: Employee) -> None:
        if len(self._order_queue) == 0:
            raise IndexError("There's no queue in the moment.")

        employee.current_order = self._order_queue.popleft()
        employee.status = EmployeeStatus.PROCESSING_ORDER

        self.next_step = self.get_next_step(self.current_step)
        employee.next_step = self.next_step

    def step(self, *args, **kwargs) -> tuple[np.uint32, np.uint32, bool]:
        if self.last_updated_timestamp is None:
            self.last_updated_timestamp = self.current_step

        current_step, next_step, done = super().step(*args, **kwargs)

        if self.last_updated_timestamp // SECONDS_IN_DAY \
                != current_step // SECONDS_IN_DAY \
                or self.steps == 1:
            if self.steps > 1:
                store_logger.info(simulator_log_format(
                    'STORE', self.place_name, '-',
                    f'Daily cumulative order: {self.total_orders}.',
                    f'Daily steps: {self.total_steps}',
                    dt=cast(current_step, datetime)
                ))

            self.last_updated_timestamp = current_step            
            # self.update_market_population(current_step)

            # Check for customers' today need
            tomorrow_timestamp = (
                current_step + SECONDS_IN_DAY
                - current_step % SECONDS_IN_DAY
            )
            today_customer_mask = self._customer_steps[:, 4] <= \
                tomorrow_timestamp
            customer_need_mask, product_need_mask = \
                self.get_customer_need_mask(
                    today_customer_mask,
                    current_step
                )

            # Prepare customers' today order
            customer_order_mask, product_order_mask, buyer_demographies = \
                self.get_product_order_mask(
                    customer_need_mask,
                    product_need_mask
                )
            for (
                    customer_index, product_mask,
                    (buyer_gender, buyer_age)
                    ) \
                    in zip(
                        np.argwhere(customer_order_mask).reshape(-1),
                        product_order_mask[customer_order_mask],
                        buyer_demographies
                    ):
                order_products = self._products[product_mask]
                payment_method = self._rng.choice(
                    list(PaymentMethod),
                    p=self._customer_payment_methods[customer_index, :, 0]
                )
                self._customers[customer_index].create_order(
                    Gender(int(buyer_gender)),
                    buyer_age,
                    order_products,
                    payment_method
                    )

            # Skip non converted customer
            customer_non_converted = today_customer_mask.copy()
            customer_non_converted[customer_order_mask] = False
            self._customer_steps[customer_non_converted, 4] = \
                Customer.calculate_next_need_timestamp(
                    np.repeat(
                        tomorrow_timestamp,
                        np.sum(customer_non_converted)
                    ),
                    rng=self._rng
                )
            if np.sum(customer_non_converted) > 0 \
                    and self._customer_steps[customer_non_converted, 4].min() \
                    <= current_step:
                raise

            # Update customers' product needs
            product_need_mask = self._customer_product_need_days_left < 0
            product_need_indexes = np.argwhere(product_need_mask)[:, 1]
            self._customer_product_need_days_left[product_need_mask] = \
                self._rng.poisson(
                    self._product_need_days_left[product_need_indexes]
                )

            # Reset telemetrics
            self.total_orders = 0
            self.total_steps = 0
            self.total_customer_steps = 0
            self.total_employee_steps = 0

        min_customer_next_step = self.customer_steps(*args, **kwargs)
        if min_customer_next_step < next_step:
            self.next_step = min_customer_next_step

        self.total_steps += 1
        return current_step, self.next_step, done

    def customer_steps(self, *args, **kwargs) -> bool:
        current_step = self.current_step
        mask = self._customer_steps[:, 4] <= current_step
        self._customer_steps[mask, 3] = current_step

        for i in np.argwhere(mask).reshape(-1):
            self._customers[int(i)].step()

        return self._customer_steps[:, 4].min()

    def update_market_population(self, current_step: float) -> None:
        self.place.update_population(current_step, clean_empty=False)

        if self.place.n_families > len(self._customers):
            self.update_customer_changes()

        self.remove_empty_customers()

    def update_customer_changes(self) -> None:
        n_new_families = self.place.n_families - len(self._customers)
        (
            new_customers,
            new_customer_steps,
            new_customer_product_need_days_left,
            new_customer_payment_methods
            ) = self.init_customer_config(n_new_families)
        self._customers.extend(new_customers)
        self._customer_steps = np.concatenate(
            (self._customer_steps, new_customer_steps),
            axis=0
            )
        self._customer_product_need_days_left = np.concatenate(
            (
                self._customer_product_need_days_left,
                new_customer_product_need_days_left
            ),
            axis=0
            )
        self._customer_payment_methods = np.concatenate(
            (
                self._customer_payment_methods,
                new_customer_payment_methods
            ),
            axis=0
            )
        
        for i, customer in enumerate(new_customers):
            i = self._customer_steps.shape[0] - n_new_families + i
            customer._index = int(i)
            customer._steps = self._customer_steps[i]

    def generate_customer_steps(
            self,
            n_families: int
            ) -> np.ndarray:
        customer_steps = np.repeat(
            self._steps.reshape((1, -1)),
            n_families,
            axis=0
            )
        customer_steps[:, 0] = \
            Customer.calculate_next_need_timestamp(
                customer_steps[:, 3],
                method='uniform',
                rng=self._rng
            )
        customer_steps[:, 3] = customer_steps[:, 0]
        customer_steps[:, 4] = customer_steps[:, 3] + self.interval
        return customer_steps

    def remove_empty_customers(self) -> None:
        non_empty_mask = self.place.family_sizes > 0
        customer_steps = self._customer_steps[non_empty_mask]
        customers = []
        for i, j in enumerate(np.argwhere(non_empty_mask)):
            customer = self._customers[int(j)]
            customer._steps = customer_steps[i]
            customers.append(customer)

        self._customers = customers
        self._customer_steps = customer_steps
        self._customer_product_need_days_left = \
            self._customer_product_need_days_left[non_empty_mask]
        self._customer_payment_methods = \
            self._customer_payment_methods[non_empty_mask]

        self.place.clean_empty_families()

    def get_customer_need_mask(
            self,
            customer_mask: np.ndarray,
            current_step: float
            ) -> tuple[np.ndarray, np.ndarray]:
        current_datetime = cast(current_step, datetime)
        weekday = current_datetime.weekday()
        spending_rate = self.place._family_params[:, 0].copy()
        if weekday == 0:
            spending_rate *= 1.1
        elif weekday == 5:
            spending_rate *= 1.25
        elif weekday == 6:
            spending_rate *= 1.5

        product_need_mask = self._customer_product_need_days_left <= 0
        product_need_mask[~customer_mask, :] = False
        customer_need_mask = np.sum(product_need_mask, axis=1) > 0
        customer_need_mask[customer_need_mask] = (
            customer_need_mask[customer_need_mask]
            * (
                self._rng.random(np.sum(customer_need_mask))
                < spending_rate[customer_need_mask]
            )
        )
        product_need_mask[~customer_need_mask] = False
        return customer_need_mask, product_need_mask

    def get_product_order_mask(
            self,
            customer_need_mask: np.ndarray,
            product_need_mask: np.ndarray
            ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        family_demographies = \
            self.place._family_demographies[customer_need_mask]

        weights = np.cumsum(
            np.array(
                [[4, 5] + [1] * (family_demographies.shape[1] - 2)]
            )
            * (
                self.place._family_demographies[customer_need_mask, :, 1]
                > AgeGroup.KID.value * DAYS_IN_YEAR
            ),
            axis=1
        )
        weights = weights / weights[:, -1:]
        buyer_indexes = np.sum(
            weights < self._rng.random(weights.shape[0]).reshape((-1, 1)),
            axis=1
        )

        buyer_demographies = np.take_along_axis(
            family_demographies,
            buyer_indexes.reshape((buyer_indexes.shape[0], 1, 1)),
            axis=1
        )[:, 0, :]
        age_groups = np.sum(
            np.repeat(
                np.array([[enum.value for enum in AgeGroup]]),
                buyer_demographies.shape[0],
                axis=0
            ) * DAYS_IN_YEAR
            > buyer_demographies[:, -1:],
            axis=1
        )

        # Basic order
        product_order_mask_ = [
            (
                random
                < (
                    self._product_modifiers[:, age_group, gender]
                    * product_mask
                    * 1.5
                )
            )
            .reshape((1, -1))
            for gender, age_group, product_mask, random in zip(
                buyer_demographies[:, 0],
                age_groups,
                product_need_mask[customer_need_mask],
                self._rng.random(buyer_demographies.shape[0])
            )
        ]
        product_order_mask = \
            np.zeros(product_need_mask.shape, dtype=bool)
        if len(product_order_mask_) > 0:
            product_order_mask[customer_need_mask] = \
                np.concatenate(product_order_mask_, axis=0)

        customer_order_mask = np.sum(product_order_mask, axis=1) > 0
        buyer_demographies = buyer_demographies[
            customer_need_mask[customer_need_mask]
        ]

        # Add associated products in the order
        for i in np.argwhere(customer_order_mask):
            product_indexes = (
                np.argwhere(product_order_mask[i].reshape(-1))
                .reshape(-1)
            )
            product_association_mask = \
                np.max(self._product_associations[product_indexes], axis=0)
            associated_mask = product_association_mask > 0
            n_associated = np.sum(associated_mask)
            if n_associated > 0:
                product_association_mask[associated_mask] = (
                    self._rng.random(n_associated)
                    < product_association_mask[associated_mask]
                )
                product_order_mask[i] |= product_association_mask.astype(bool)

        return (
            customer_order_mask,
            product_order_mask,
            buyer_demographies
        )

    @classmethod
    def clean_records(cls, place: Place, max_timestamp: float) -> None:
        max_datetime = cast(max_timestamp, datetime)
        store_record = StoreModel.get(
            StoreModel.subdistrict_id == place.record_id
        )
        OrderModel.delete() \
            .where(
                (OrderModel.store_id == store_record.id)
                & (OrderModel.created_datetime >= max_datetime)
            ) \
            .execute()

        EmployeeModel.delete() \
            .where(
                (EmployeeModel.store_id == store_record.id)
                & (EmployeeModel.created_datetime >= max_datetime)
            ) \
            .execute()

    def save(self, save_dir: Path) -> None:
        save_dir = cast(save_dir, Path)
        save_dir.mkdir(parents=True, exist_ok=True)
        self.place.save(save_dir)

        with open(save_dir / 'store.json', 'wb') as f:
            f.write(
                orjson.dumps({
                    'max_employees': self.max_employees,
                    'max_cashiers': self.max_cashiers,
                    'max_queue': self._order_queue.maxlen,
                    'products': self._products.tolist(),
                    'rng_state': self.dump_rng_state()
                })
            )

        # Steps
        dump_memmap_to_array(
            self._steps,
            save_dir / 'store_steps.dat',
            dtype=np.uint32
        )

        dump_memmap_to_array(
            self._agent_steps,
            save_dir / 'store_agent_steps.dat',
            dtype=np.uint32
        )

        # Product Config
        dump_memmap_to_array(
            self._product_need_days_left,
            save_dir / 'product_need_days_left.dat',
            dtype=np.int16
        )

        dump_memmap_to_array(
            self._product_modifiers,
            save_dir / 'product_modifiers.dat',
            dtype=np.float16
        )

        dump_memmap_to_array(
            self._product_associations,
            save_dir / 'product_associations.dat',
            dtype=np.float16
        )

        # Customer config
        dump_memmap_to_array(
            self._customer_steps,
            save_dir / 'customer_steps.dat',
            dtype=np.uint32
        )

        dump_memmap_to_array(
            self._customer_product_need_days_left,
            save_dir / 'customer_product_need_days_left.dat',
            dtype=np.uint16
        )

        dump_memmap_to_array(
            self._customer_payment_methods,
            save_dir / 'customer_payment_methods.dat',
            dtype=np.float16
        )

        # Employees
        if self._employee_params is not None:
            dump_memmap_to_array(
                self._employee_params,
                save_dir / 'employee_params.dat',
                dtype=np.float16
            )

    @classmethod
    def load(
            cls,
            load_dir: Path,
            max_members: int = None
            ) -> Place:
        load_dir = cast(load_dir, Path)
        with open(load_dir / 'store.json', 'rb') as f:
            meta = orjson.loads(f.read())

        place = Place.load(load_dir, max_members)

        # Steps
        store_steps = load_memmap_to_array(
            load_dir / 'store_steps.dat',
            dtype=np.uint32
        )
        agent_steps = load_memmap_to_array(
            load_dir / 'store_agent_steps.dat',
            shape=(-1, 6),
            dtype=np.uint32
        )

        # Product config
        product_need_days_left = load_memmap_to_array(
            load_dir / 'product_need_days_left.dat',
            dtype=np.uint16
        )
        product_modifiers = load_memmap_to_array(
            load_dir / 'product_modifiers.dat',
            shape=(-1, len(AgeGroup), len(Gender)),
            dtype=np.float16
        )
        product_associations = load_memmap_to_array(
            load_dir / 'product_associations.dat',
            shape=(product_need_days_left.shape[0], -1),
            dtype=np.float16
        )

        # Customer config
        customer_steps = load_memmap_to_array(
            load_dir / 'customer_steps.dat',
            shape=(-1, 6),
            dtype=np.uint32
        )
        customer_product_need_days_left = load_memmap_to_array(
            load_dir / 'customer_product_need_days_left.dat',
            shape=(-1, product_need_days_left.shape[0]),
            dtype=np.uint16
        )
        customer_payment_methods = load_memmap_to_array(
            load_dir / 'customer_payment_methods.dat',
            shape=(customer_steps.shape[0], -1, 2),
            dtype=np.float16
        )

        # Employee params
        employee_params_file = load_dir / 'employee_params.dat'
        employee_params = None
        if employee_params_file.exists():
            employee_params = load_memmap_to_array(
                employee_params_file,
                shape=(-1, 4),
                dtype=np.float16
            )

        cls.clean_records(place, store_steps[4])

        obj = Store(
            place,
            max_employees=meta['max_employees'],
            max_cashiers=meta['max_cashiers'],
            max_queue=meta['max_queue'],
            product_config=(
                np.array(meta['products']),
                product_need_days_left,
                product_modifiers,
                product_associations
            ),
            customer_config=(
                customer_steps,
                customer_product_need_days_left,
                customer_payment_methods
            ),
            employee_params=employee_params
        )
        obj._steps = store_steps
        obj._agent_steps = agent_steps
        for i, agent in enumerate(obj.agents()):
            agent._steps = obj._agent_steps[i]
        obj.last_updated_timestamp = store_steps[3]
        obj.load_rng_state(meta['rng_state'])
        return obj
