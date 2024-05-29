from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Tuple, TYPE_CHECKING

from ..core import ReprMixin
from ..core.restore import RestorableMixin, RestoreTypes
from ..database import Database, OrderModel, OrderSKUModel
from ..enums import AgeGroup, Gender, PaymentMethod, OrderStatus

if TYPE_CHECKING:
    from ..population import Person
    from .sku import SKU
    from .store import Store
    from .employee import Employee


class Order(
        RestorableMixin, ReprMixin,
        repr_attrs=('n_order_skus', 'status')
        ):
    __additional_types__ = RestoreTypes(PaymentMethod, OrderStatus)

    def __init__(
            self,
            order_skus: List[Tuple[SKU, int]],
            begin_datetime: datetime
            ) -> None:
        self._order_skus = order_skus
        self.buyer: Person = None
        self.payment_method: PaymentMethod = None

        self._status = OrderStatus.COLLECTING
        self.begin_datetime = begin_datetime
        self.queue_datetime: datetime = None
        self.checkout_start_datetime: datetime = None
        self.checkout_end_datetime: datetime = None
        self.complete_datetime: datetime = None

        self._order_record: OrderModel = None

    @property
    def status(self) -> OrderStatus:
        return self._status

    @property
    def n_order_skus(self) -> int:
        return len(self._order_skus)

    def order_skus(self) -> Iterable[Tuple[SKU, int]]:
        for sku, quantity in self._order_skus:
            yield sku, quantity

    def queue(
            self,
            store: Store,
            current_datetime: datetime
            ) -> None:
        store.add_order_queue(self)
        self._status = OrderStatus.QUEUING
        self.queue_datetime = current_datetime

    def begin_checkout(
            self,
            store: Store,
            employee: Employee,
            current_datetime: datetime,
            buyer_gender: Gender = None,
            buyer_age_group: AgeGroup = None
            ) -> None:
        database: Database = OrderModel._meta.database
        with database.atomic():
            for sku, _ in self._order_skus:
                sku: SKU
                sku.update(current_datetime)

            if buyer_gender is not None:
                buyer_gender = buyer_gender.name

            if buyer_age_group is not None:
                buyer_age_group = buyer_age_group.name

            self._order_record = OrderModel.create(
                store=store.record.id,
                cashier_employee=employee.record.id,
                buyer_gender=buyer_gender,
                buyer_age_group=buyer_age_group,
                created_datetime=current_datetime
            )

        self._status = OrderStatus.PROCESSING
        self.checkout_start_datetime = current_datetime

    def complete_checkout(self, current_datetime: datetime) -> None:
        self._status = OrderStatus.WAITING_PAYMENT
        self.checkout_end_datetime = current_datetime

    def begin_payment(self, payment_method: PaymentMethod) -> None:
        self.payment_method = payment_method
        self._status = OrderStatus.DOING_PAYMENT

    def complete_payment(self, current_datetime: datetime) -> None:
        self._status = OrderStatus.PAID
        self.complete_datetime = current_datetime

    def submit(self, current_datetime: datetime) -> None:
        self._status = OrderStatus.DONE
        self.complete_datetime = current_datetime

        database: Database = OrderModel._meta.database
        with database.atomic():
            for sku, quantity in self._order_skus:
                OrderSKUModel.create(
                    order=self._order_record,
                    sku=sku.record.id,
                    price=sku.price,
                    quantity=quantity,
                    created_datetime=current_datetime
                )

            self._order_record.payment_method = self.payment_method.value
            self._order_record.complete_datetime = self.complete_datetime
            self._order_record.save()

    @property
    def restore_attrs(self) -> Dict[str, Any]:
        return {
            'order_skus': {
                sku.name: quantity
                for sku, quantity in self.order_skus
            },
            'status': self.status,
            'payment_method': self.payment_method,
            'timeline': [
                self.begin_datetime,
                self.queue_datetime,
                self.checkout_start_datetime,
                self.checkout_end_datetime,
                self.complete_datetime
            ],
            'order_record_id': self._order_record.id
        }

    @classmethod
    def _restore(cls, attrs: Dict[str, Any], **kwargs) -> Order:
        order_skus = [
            (SKU.get(name), quantity)
            for name, quantity in attrs['order_skus']
        ]

        obj = cls(
            order_skus,
            attrs['timeline'][0]
        )

        obj._status = attrs['status']
        obj.payment_method = attrs['payment_method']
        (
            _,
            obj.queue_datetime,
            obj.checkout_start_datetime,
            obj.checkout_end_datetime,
            obj.complete_datetime
        ) = attrs['timeline']

        obj._order_record = OrderModel.get(
            OrderModel.id == attrs['order_record_id']
        )
        return obj
