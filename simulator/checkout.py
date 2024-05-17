from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Tuple, TYPE_CHECKING

from .base import ReprMixin
from .database import ModelMixin

if TYPE_CHECKING:
    from .item import SKU
    from .population import AgeGroup, Gender, Person


class CheckoutStatus(Enum):
    COLLECTING = 0
    QUEUING = 1
    PROCESSING = 2
    WAITING_PAYMENT = 3
    DOING_PAYMENT = 4
    PAID = 5
    DONE = 6


class PaymentMethod(Enum):
    CASH = 0
    DIGITAL_CASH = 1
    DEBIT_CARD = 2
    CREDIT_CARD = 3


class Checkout(ModelMixin, ReprMixin):
    __repr_attrs__ = ( 'items', 'payment_method' )

    def __init__(
            self,
            items: List[Tuple[SKU, int]],
            buyer: Person,
            payment_method: PaymentMethod,
            begin_datetime: datetime
        ) -> None:
        self.items = items
        self.buyer = buyer
        self.payment_method = payment_method

        self._status = CheckoutStatus.COLLECTING
        self.begin_datetime = begin_datetime
        self.queue_datetime: datetime = None
        self.counting_start_datetime: datetime = None
        self.counting_end_datetime: datetime = None
        self.complete_datetime: datetime = None

    @property
    def status(self) -> CheckoutStatus:
        return self._status

    def set_status(
            self,
            value: CheckoutStatus,
            last_datetime: datetime
        ) -> None:
        if value == CheckoutStatus.QUEUING:
            self.queue_datetime = last_datetime

        elif value == CheckoutStatus.PROCESSING:
            self.counting_start_datetime = last_datetime

        elif value == CheckoutStatus.WAITING_PAYMENT:
            self.counting_end_datetime = last_datetime

        elif value == CheckoutStatus.PAID:
            self.complete_datetime = last_datetime

        self._status = value

    def total_price(self) -> float:
        return sum([
            sku.price * quantity
            for sku, quantity in self.items
        ])

    def submit(
            self,
            store_id: int,
            worker_id: int,
            buyer_gender: Gender,
            buyer_age_group: AgeGroup
        ) -> None:
        return
        # print(self.complete_datetime, '- Complete', [ ( sku.name, q )for sku, q in self.items ], 'from', f'({self.buyer.id}, {buyer_gender}, {buyer_age_group})', 'by', worker_id, 'in', store_id)
