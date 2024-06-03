from __future__ import annotations

from datetime import datetime
from typing import Iterable, List, Tuple, TYPE_CHECKING

from ..core import ReprMixin, IdentityMixin
from ..core.restore import RestorableMixin, RestoreTypes
from ..database import Database, OrderModel, OrderSKUModel
from ..enums import AgeGroup, Gender, PaymentMethod, OrderStatus
from .sku import SKU

if TYPE_CHECKING:
    from ..population import Person
    from .store import Store
    from .employee import Employee


class Order(
        RestorableMixin, ReprMixin, IdentityMixin,
        repr_attrs=('n_order_skus', 'status')
        ):
    __additional_types__ = RestoreTypes(PaymentMethod, OrderStatus)

    def __init__(
            self,
            order_skus: List[Tuple[SKU, int]],
            begin_datetime: datetime,
            _id: str = None
            ) -> None:
        self._order_skus = order_skus
        self.buyer: Person = None
        self.store: Store = None
        self.payment_method: PaymentMethod = None

        self._status = OrderStatus.COLLECTING
        self.begin_datetime = begin_datetime
        self.queue_datetime: datetime = None
        self.checkout_start_datetime: datetime = None
        self.checkout_end_datetime: datetime = None
        self.complete_datetime: datetime = None

        self._order_record: OrderModel = None

        super().__init_id__(_id)

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
        self._status = OrderStatus.QUEUING
        self.queue_datetime = current_datetime
        self.store = store
        self.store.add_order_queue(self)

    def cancel_order(self) -> None:
        self.store.remove_order_queue(self)

    def begin_checkout(
            self,
            employee: Employee,
            current_datetime: datetime,
            buyer_gender: Gender = None,
            buyer_age_group: AgeGroup = None
            ) -> None:
        database: Database = OrderModel._meta.database
        with database.atomic():
            if buyer_gender is not None:
                buyer_gender = buyer_gender.name

            if buyer_age_group is not None:
                buyer_age_group = buyer_age_group.name

            self._order_record = OrderModel(
                store_id=self.store.record.id,
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
            self._order_record.payment_method = self.payment_method.value
            self._order_record.complete_datetime = self.complete_datetime
            self._order_record.save()

            for sku, quantity in self._order_skus:
                OrderSKUModel.create(
                    order=self._order_record.id,
                    sku=sku.record.id,
                    price=sku.price,
                    quantity=quantity,
                    created_datetime=current_datetime
                )
