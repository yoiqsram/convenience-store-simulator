from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from core import ReprMixin, IdentityMixin
from core.utils import cast
from ..database import OrderModel, OrderSKUModel, SKUModel
from ..enums import Gender, PaymentMethod, OrderStatus

if TYPE_CHECKING:
    from .store import Store
    from .employee import Employee


class Order(
        ReprMixin, IdentityMixin,
        repr_attrs=('n_order_skus', 'status')
        ):
    def __init__(
            self,
            store: Store,
            buyer_gender: Gender,
            buyer_age: float,
            order_skus: list[tuple[SKUModel, int]],
            payment_method: PaymentMethod,
            _id: str = None
            ) -> None:
        self.store = store
        self.buyer_gender = buyer_gender
        self.buyer_age = buyer_age
        self.payment_method = payment_method
        self.order_skus = order_skus

        self.begin_timestamp: float = None
        self.queue_timestamp: float = None
        self.checkout_start_timestamp: float = None
        self.checkout_end_timestamp: float = None
        self.paid_timestamp: float = None
        self.complete_timestamp: float = None
        self._status = OrderStatus.PLANNING

        super().__init_id__(_id)

    @property
    def status(self) -> OrderStatus:
        return self._status

    @property
    def n_order_skus(self) -> int:
        return len(self.order_skus)

    def cancel_order(self) -> None:
        self.store.remove_order_queue(self)

    def collect(self, current_timestamp: float) -> None:
        self._status = OrderStatus.COLLECTING
        self.begin_timestamp = current_timestamp

    def queue(self, current_timestamp: float) -> None:
        self._status = OrderStatus.QUEUING
        self.queue_timestamp = current_timestamp
        self.store.add_order_queue(self)

    def begin_checkout(
            self,
            current_timestamp: float,
            checkout_time: float
            ) -> None:
        self._status = OrderStatus.PROCESSING
        self.checkout_start_timestamp = current_timestamp
        self.checkout_end_timestamp = current_timestamp + checkout_time

    def complete_checkout(self, current_step: float = None) -> None:
        self._status = OrderStatus.WAITING_PAYMENT
        if current_step is not None:
            self.checkout_end_timestamp = current_step

    def begin_payment(
            self,
            current_timestamp: float,
            payment_time: float
            ) -> None:
        self._status = OrderStatus.DOING_PAYMENT
        self.paid_timestamp = current_timestamp + payment_time

    def complete_payment(self, current_timestamp: float = None) -> None:
        self._status = OrderStatus.PAID
        if current_timestamp is not None:
            self.paid_timestamp = current_timestamp

    def submit(self, employee: Employee, current_timestamp: float) -> None:
        self.store.total_orders += 1
        self._status = OrderStatus.DONE
        self.complete_timestamp = current_timestamp

        with OrderModel._meta.database.atomic():
            buyer_age_group = \
                employee.estimate_customer_age_group(self.buyer_age)

            order = OrderModel.create(
                store_id=self.store.record.id,
                cashier_employee=employee.record.id,
                buyer_gender=self.buyer_gender.name,
                buyer_age_group=buyer_age_group.name,
                created_datetime=cast(self.checkout_start_timestamp, datetime),
                complete_datetime=cast(self.complete_timestamp, datetime)
            )

            for sku, quantity in self.order_skus:
                OrderSKUModel.create(
                    order=order.id,
                    sku=sku.id,
                    price=sku.price,
                    quantity=quantity,
                    created_datetime=cast(current_timestamp, datetime)
                )
