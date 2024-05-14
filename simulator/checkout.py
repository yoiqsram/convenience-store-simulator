from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import List, Tuple, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from .customer import Customer
    from .item import SKU
    from .population import Person
    from .store import Store, Worker


class CheckoutStatus(Enum):
    QUEUEING = 0
    PROCESSING = 1
    WAITING_PAYMENT = 2
    DONE = 3


class PaymentMethod(Enum):
    CASH = 0
    DIGITAL_CASH = 1
    DEBIT_CARD = 2
    CREDIT_CARD = 3


class Checkout:
    def __init__(
            self,
            customer: Customer,
            buyer: Person,
            quantities: List[Tuple[SKU, int]],
            queue_datetime: datetime
        ) -> None:
        self.customer = customer
        self.buyer = buyer
        self.quantities = quantities
        self.payment_method = None

        self.queue_datetime = queue_datetime
        self.chekout_datetime: datetime = None
        self.processed_datetime: datetime = None
        self.paid_datetime: datetime = None

        self.worker = None
        self.env = None
        self.status = CheckoutStatus.QUEUEING

    def __repr__(self) -> str:
        return f"Checkout(customer_id={self.customer.id}, buyer='{self.buyer.name}', quantities={[sku.name for sku, _ in self.quantities]})"

    def total_price(self):
        return sum([
            sku.price * quantity
            for sku, quantity in self.quantities
        ])

    def process(
            self,
            worker: Worker,
            env: Store
        ) -> None:
        self.worker = worker
        self.env = env
        self.checkout_datetime = self.env.current_step()
        self.status = CheckoutStatus.PROCESSING

        processing_time = worker.calculate_checkout(self)
        self.processed_datetime = self.checkout_datetime + timedelta(seconds=processing_time)

    def pay(self) -> None:
        self.status = CheckoutStatus.WAITING_PAYMENT

        self.payment_method, payment_time = self.customer.calculate_payment()
        self.paid_datetime = self.processed_datetime + timedelta(seconds=payment_time)

    def complete(self) -> Union[int, None]:
        self.status = CheckoutStatus.DONE
