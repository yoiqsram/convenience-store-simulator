from __future__ import annotations

import numpy as np
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple, Union, TYPE_CHECKING

from ..context import GlobalContext, DAYS_IN_YEAR
from ..core import Agent, DatetimeStepMixin, IdentityMixin
from ..core.restore import RestoreTypes
from ..enums import AgeGroup, FamilyStatus, OrderStatus, PaymentMethod
from ..population import Family, Family
from .order import Order
from .sku import Product, SKU

if TYPE_CHECKING:
    from .store import Store


class Customer(
        Agent,
        DatetimeStepMixin, IdentityMixin,
        repr_attrs=( 'n_members', 'current_datetime', 'current_order' )
    ):
    __additional_types__ = RestoreTypes(PaymentMethod)

    def __init__(
            self,
            family: Family,
            initial_datetime: datetime,
            interval: float,
            seed: int = None,
            rng: np.random.RandomState = None
        ) -> None:
        super().__init__(
            initial_datetime,
            interval,
            seed=seed,
            rng=rng
        )

        self.parent: Store
        self.family = family

        self.product_need_days_left: Dict[Product, int] = {
            product: int(self._rng.randint(0, product.interval_days_need))
            for product in Product.all()
        }
        self.last_product_need_updated_date: date = initial_datetime.date()

        self.payment_method_prob, self.payment_method_time = self.random_payment_method_config()

        self.current_order: Union[Order, None] = None

        self.__init_id__()

    @property
    def n_members(self) -> int:
        return self.family.n_members

    def step(self) -> Tuple[datetime, Union[datetime, None]]:
        current_datetime, next_datetime = super().step()
        if next_datetime is None:
            return current_datetime, next_datetime

        current_date = current_datetime.date()
        if self.current_order is None:
            # Unfortunately some kids could be orphaned and only be able to order when they reach teenage
            oldest_age = self.family.oldest_age(current_date)
            if oldest_age < AgeGroup.KID.value:
                self._next_step = current_datetime + timedelta(days=(AgeGroup.KID.value - oldest_age) * DAYS_IN_YEAR)
                return current_datetime, self._next_step

            # Randomize buyer representative and get the family needs
            buyer = self.random_buyer()
            needed_products = self.get_needed_products()

            # Update product needs
            for product in self.product_need_days_left.keys():
                if product in needed_products:
                    self.product_need_days_left[product] = self._rng.poisson(
                        product.interval_days_need
                    )
                elif self.last_product_need_updated_date:
                    self.product_need_days_left[product] =- (current_date - self.last_product_need_updated_date).days
            self.last_product_need_updated_date = current_date

            # Calculate conversion from needs to purchase from the store, then order
            order_products = self.get_order_products(needed_products, buyer, current_date)

            # Skip order if have no product to purchase, wouldn't spend, store is close or store is open but full
            if len(order_products) == 0 \
                    or self._rng.random() > self.family.spending_rate \
                    or not self.parent.is_open() \
                    or self.parent.is_full_queue():
                self._next_step = self.calculate_next_order_datetime(current_date)
                
                return current_datetime, self._next_step

            # Collecting order products in the store
            order_skus = self.get_order_skus(order_products)
            self.current_order = Order(order_skus, current_datetime)
            self.current_order.buyer = buyer

            collection_time = self.calculate_collection_time(self.current_order)
            self._next_step = current_datetime + timedelta(seconds=collection_time)
            
            return current_datetime, self._next_step

        # Queuing order
        elif self.current_order.status == OrderStatus.COLLECTING:
            self.current_order.queue(self.parent, current_datetime)

        # Paying order
        elif self.current_order.status == OrderStatus.WAITING_PAYMENT:
            payment_method = self.random_payment_method()
            self.current_order.begin_payment(payment_method)

            payment_time = self.calculate_payment_time(self.current_order)
            self._next_step = current_datetime + timedelta(seconds=payment_time)
            
            return current_datetime, self._next_step

        # Complete the payment
        elif self.current_order.status == OrderStatus.DOING_PAYMENT:
            self.current_order.complete_payment(current_datetime)

        # Leave the store
        elif self.current_order.status == OrderStatus.DONE:
            self.current_order = None
            self._next_step = self.calculate_next_order_datetime(current_date)
            
            return current_datetime, self._next_step

        return current_datetime, next_datetime

    def random_payment_method_config(self) -> Tuple[Dict[PaymentMethod, float], Dict[PaymentMethod, float]]:
        payment_method_weight = {
            PaymentMethod.CASH: max(0, self._rng.normal(0.8, 0.05)),
            PaymentMethod.CREDIT_CARD: max(0, self._rng.normal(0.01, 0.01)),
            PaymentMethod.DEBIT_CARD: max(0, self._rng.normal(0.05, 0.025)),
            PaymentMethod.DIGITAL_CASH: max(0, self._rng.normal(0.05, 0.025))
        }
        total_payment_method_weight = np.sum(list(payment_method_weight.values()))
        payment_method_prob: Dict[PaymentMethod, float] = {
            payment_method: float(weight / total_payment_method_weight)
            for payment_method, weight in payment_method_weight.items()
        }
        payment_method_time: Dict[PaymentMethod, float] = {
            PaymentMethod.CASH: float(np.clip(self._rng.normal(5.0, 1.0), 2.0, 15.0)),
            PaymentMethod.CREDIT_CARD: float(np.clip(self._rng.normal(15.0, 3.0), 10.0, 45.0)),
            PaymentMethod.DEBIT_CARD: float(np.clip(self._rng.normal(20.0, 3.0), 10.0, 45.0)),
            PaymentMethod.DIGITAL_CASH: float(np.clip(self._rng.normal(10.0, 2.0), 5.0, 30.0))
        }
        return payment_method_prob, payment_method_time

    def calculate_next_order_datetime(self, current_date: date) -> datetime:
        order_datetime = (
            datetime(current_date.year, current_date.month, current_date.day)
            + timedelta(days=int(self._rng.poisson(7)))
        )
        if self._rng.random() < 0.2:
            order_datetime += timedelta(
                hours=self._rng.uniform(
                    GlobalContext.STORE_OPEN_HOUR,
                    GlobalContext.STORE_CLOSE_HOUR
                )
            )

        else:
            hour_loc = self._rng.choice(GlobalContext.STORE_PEAK_HOURS)
            hour_spread = min(
                hour_loc - GlobalContext.STORE_OPEN_HOUR,
                GlobalContext.STORE_CLOSE_HOUR - hour_loc
            )
            order_datetime += timedelta(
                hours=self._rng.normal(hour_loc, hour_spread / 2.0)
            )

        return order_datetime

    def random_buyer(self) -> Family:
        family_weight = {
            FamilyStatus.SINGLE: 1,
            FamilyStatus.PARENT: 8,
            FamilyStatus.CHILD: 1
        }

        potential_buyers = [ member for member in self.family.members ]
        potential_buyer_weights = [
            family_weight[member.status]
            for member in potential_buyers
        ]

        return self._rng.choice(
            potential_buyers,
            p=np.array(potential_buyer_weights) / np.sum(potential_buyer_weights)
        )

    def random_payment_method(self) -> PaymentMethod:
        return self._rng.choice(
            list(self.payment_method_prob.keys()),
            p=list(self.payment_method_prob.values())
        )

    def get_needed_products(self) -> List[Product]:
        return [
            product
            for product, days_left in self.product_need_days_left.items()
            if days_left <= 0
        ]

    def get_order_products(
            self,
            products: List[Product],
            buyer: Family,
            current_date: date
        ) -> List[Product]:
        order_products = [
            product
            for product, random in zip(
                products,
                self._rng.random(len(products))
            )
            if random <= product.adjusted_modifier(buyer, current_date)
        ]

        for product in order_products.copy():
            order_product_names = [
                product.name
                for product in order_products
            ]
            for ( product_name, association_strength ), random in zip(
                    product.associations.items(),
                    self._rng.random(len(product.associations))
                ):
                if product_name not in order_product_names \
                        and random <= association_strength:
                    associated_product = Product.get(product_name)
                    order_products.append(associated_product)

        return order_products

    def get_order_skus(self, products: List[Product]) -> List[Tuple[SKU, int]]:
        items = []
        for product in products:
            sku: SKU = self._rng.choice(product.skus)
            quantity = 1 + int(self._rng.poisson(max(0.0, self.n_members / sku.pax - 1)))
            items.append((sku, quantity))

        return items

    def calculate_collection_time(self, order: Order) -> float:
        collection_time = (
            15.0
            + np.sum(
                np.clip(
                    self._rng.normal(15.0, 5.0, size=order.n_order_skus),
                    1.0,
                    3.0
                )
            )
            + np.sum(
                np.clip(
                    self._rng.normal(2.5, size=sum([quantity - 1 for _, quantity in order.order_skus()])),
                    0.0,
                    5.0
                )
            )
        )
        return collection_time

    def calculate_payment_time(self, order: Order) -> float:
        payment_time = self.payment_method_time[order.payment_method]
        return payment_time

    @property
    def restore_attrs(self) -> Dict[str, Any]:
        attrs = super().restore_attrs
        attrs['product_need_days_left'] = {
            product.name: days_left
            for product, days_left in self.product_need_days_left.items()
        }
        attrs['last_product_need_updated_date'] = self.last_product_need_updated_date

        attrs['payment_method_params'] = {
            payment_method.name: (
                self.payment_method_prob[payment_method],
                self.payment_method_time[payment_method]
            )
            for payment_method in self.payment_method_prob.keys()
        }

        if self.current_order is not None:
            attrs['order_restore_file'] = self.current_order.restore_file.relative_to(GlobalContext.BASE_DIR)

        return attrs

    def _push_restore(self, file: Path = None) -> None:
        base_dir = file.parents[1]
        if self.current_order is not None:
            if hasattr(self.current_order, 'restore_file'):
                self.current_order.push_restore()
            else:
                order_dir = base_dir / 'Order'
                order_dir.mkdir(parents=True, exist_ok=True)
                self.current_order.push_restore(order_dir / f'{uuid.uuid4()}.json')

        super()._push_restore(file)

    @classmethod
    def _restore(cls, attrs: Dict[str, Any], file: Path, **kwargs) -> Customer:
        family = Family.restore(file.parent / 'family.json')

        initial_step, interval, max_step, next_step = attrs['base_params']
        obj = cls(
            family,
            initial_step,
            interval
        )
        obj._max_step = max_step
        obj._next_step = next_step

        obj.product_need_days_left = {
            Product.get(product_name): days_left
            for product_name, days_left in attrs['product_need_days_left'].items()
        }
        obj.last_product_need_updated_date = attrs['last_product_need_updated_date']

        obj.payment_method_prob = {}
        obj.payment_method_time = {}
        for payment_method_name, ( prob, time ) in attrs['payment_method_params'].items():
            obj.payment_method_prob[getattr(PaymentMethod, payment_method_name)] = prob
            obj.payment_method_time[getattr(PaymentMethod, payment_method_name)] = time

        if 'order_restore_file' in attrs:
            obj.current_order = Order.restore(file.parents[1] / 'Order' / attrs['order_restore_file'])
        return obj

    @classmethod
    def from_families(
            cls,
            families: Iterable[Family],
            seed: int = None,
            rng: np.random.RandomState = None
        ) -> Iterable[Customer]:
        for family in families:
            yield cls(
                family,
                seed=seed,
                rng=rng
            )
