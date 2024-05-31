from __future__ import annotations

import numpy as np
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union, TYPE_CHECKING

from ..context import GlobalContext, DAYS_IN_YEAR
from ..core import Agent, DatetimeStepMixin, IdentityMixin
from ..core.restore import RestorableMixin
from ..core.utils import cast
from ..enums import AgeGroup, FamilyStatus, OrderStatus, PaymentMethod
from ..population import Family, Person
from .order import Order
from .sku import Product, SKU

if TYPE_CHECKING:
    from .store import Store


class CustomerData(RestorableMixin):
    def __init__(
            self,
            initial_date: date,
            seed: int = None,
            rng: np.random.RandomState = None,
            product_need_days_left: Dict[Product, int] = None,
            payment_method_prob: Dict[PaymentMethod, float] = None,
            payment_method_time: Dict[PaymentMethod, float] = None
            ) -> None:
        if rng is None:
            rng = np.random.RandomState(seed)

        if product_need_days_left is None:
            product_need_days_left = {
                product: int(rng.randint(0, product.interval_days_need))
                for product in Product.all()
            }
        self.product_need_days_left = product_need_days_left
        self.last_product_need_updated_date = initial_date

        if payment_method_prob is None \
                or payment_method_time is None:
            payment_method_prob_, payment_method_time_ = \
                self.random_payment_method_config(seed, rng)

        if payment_method_prob is None:
            self.payment_method_prob = payment_method_prob_
        else:
            self.payment_method_prob = payment_method_prob

        if payment_method_time is None:
            self.payment_method_time = payment_method_time_
        else:
            self.payment_method_time = payment_method_time

    @property
    def restore_attrs(self) -> Dict[str, Any]:
        attrs = {
            'product_need_days_left': {
                product.name: days_left
                for product, days_left in self.product_need_days_left.items()
            },
            'last_product_need_updated_date':
                self.last_product_need_updated_date,
            'payment_method_params': {
                payment_method.name: (
                    self.payment_method_prob[payment_method],
                    self.payment_method_time[payment_method]
                )
                for payment_method in self.payment_method_prob.keys()
            }
        }
        return attrs

    @staticmethod
    def random_payment_method_config(
            seed: int = None,
            rng: np.random.RandomState = None
            ) -> Tuple[Dict[PaymentMethod, float], Dict[PaymentMethod, float]]:
        if rng is None:
            rng = np.random.RandomState(seed)

        payment_method_weight = {
            PaymentMethod.CASH: max(0, rng.normal(0.8, 0.05)),
            PaymentMethod.CREDIT_CARD: max(0, rng.normal(0.01, 0.01)),
            PaymentMethod.DEBIT_CARD: max(0, rng.normal(0.05, 0.025)),
            PaymentMethod.DIGITAL_CASH: max(0, rng.normal(0.05, 0.025))
        }
        total_payment_method_weight = \
            np.sum(list(payment_method_weight.values()))
        payment_method_prob: Dict[PaymentMethod, float] = {
            payment_method: float(weight / total_payment_method_weight)
            for payment_method, weight in payment_method_weight.items()
        }
        payment_method_time: Dict[PaymentMethod, float] = {
            PaymentMethod.CASH: float(np.clip(
                rng.normal(5.0, 1.0), 2.0, 15.0
            )),
            PaymentMethod.CREDIT_CARD: float(np.clip(
                rng.normal(15.0, 3.0), 10.0, 45.0
            )),
            PaymentMethod.DEBIT_CARD: float(np.clip(
                rng.normal(20.0, 3.0), 10.0, 45.0
            )),
            PaymentMethod.DIGITAL_CASH: float(np.clip(
                rng.normal(10.0, 2.0), 5.0, 30.0
            ))
        }
        return payment_method_prob, payment_method_time

    @classmethod
    def _restore(cls, attrs: Dict[str, Any], file: Path, **kwargs) -> Customer:
        payment_method_prob = {}
        payment_method_time = {}
        for payment_method_name, (prob, time) in (
                attrs['payment_method_params'].items()
                ):
            payment_method = getattr(PaymentMethod, payment_method_name)
            payment_method_prob[payment_method] = prob
            payment_method_time[payment_method] = time

        obj = cls(
            attrs['last_product_need_updated_date'],
            product_need_days_left={
                Product.get(product_name): days_left
                for product_name, days_left in (
                    attrs['product_need_days_left'].items()
                )
            },
            payment_method_prob=payment_method_prob,
            payment_method_time=payment_method_time
        )

        return obj


class Customer(
        Agent,
        DatetimeStepMixin, IdentityMixin,
        repr_attrs=('current_datetime', 'current_order')
        ):
    def __init__(
            self,
            initial_datetime: datetime,
            interval: float,
            seed: int = None,
            rng: np.random.RandomState = None
            ) -> None:
        super().__init__(
            cast(initial_datetime, float),
            cast(interval, float),
            seed=seed,
            rng=rng
        )

        self._next_step = cast(
            self.calculate_next_order_datetime(self.current_date),
            float
        )

        self.parent: Store
        self.current_order: Union[Order, None] = None

        self.__init_id__()

    @property
    def family(self) -> Family:
        return Family.restore(
            self.restore_file.parent / 'family.json',
            tmp=True
        )

    @property
    def n_members(self) -> int:
        return self.family.n_members

    @property
    def data(self) -> CustomerData:
        return CustomerData.restore(
            self.restore_file.parent / 'customer_data.json',
            tmp=True
        )

    def step(self) -> Tuple[datetime, Union[datetime, None]]:
        self.parent.customer_steps += 1
        current_step, next_step = super().step()
        current_datetime = cast(current_step, datetime)
        current_date = current_datetime.date()
        next_datetime = cast(next_step, datetime)

        if self.current_order is None:
            family = self.family

            # Unfortunately some kids could be orphaned
            # and only be able to order when they reach teenage
            oldest_age = family.oldest_age(current_date)
            if oldest_age < AgeGroup.KID.value:
                self._next_step = cast(
                    current_datetime
                    + timedelta(
                        days=int(
                            (AgeGroup.KID.value - oldest_age) * DAYS_IN_YEAR
                        ) + 1
                    ),
                    float
                )
                return current_step, self._next_step

            data = self.data

            # Randomize buyer representative and get the family needs
            buyer = self.random_buyer(family)
            needed_products = self.get_needed_products(
                data.product_need_days_left
            )

            # Update product needs
            for product in data.product_need_days_left.keys():
                if product in needed_products:
                    data.product_need_days_left[product] = self._rng.poisson(
                        product.interval_days_need
                    )
                elif data.last_product_need_updated_date < current_date:
                    data.product_need_days_left[product] -= (
                        current_date - data.last_product_need_updated_date
                    ).days
            data.last_product_need_updated_date = current_date
            data.push_restore(tmp=True)

            # Calculate conversion from needs to purchase
            # from the store, then order
            order_products = self.get_order_products(
                needed_products,
                buyer,
                current_date
            )

            # Skip order if have no product to purchase,
            # wouldn't spend, store is close or store is open but full
            #     Adjust spending rate to conversion rate based on weekday
            conversion_rate = family.spending_rate
            weekday = current_datetime.weekday()
            if weekday == 0:
                conversion_rate *= 1.1
            elif weekday == 5:
                conversion_rate *= 1.25
            elif weekday == 6:
                conversion_rate *= 1.5

            if len(order_products) == 0 \
                    or self._rng.random() > conversion_rate \
                    or not self.parent.is_open() \
                    or self.parent.is_full_queue():
                self.parent.total_canceled_orders += 1
                self._next_step = cast(
                    self.calculate_next_order_datetime(current_date),
                    float
                )
                return current_step, self._next_step

            # Collecting order products in the store
            order_skus = self.get_order_skus(order_products)
            self.current_order = Order(order_skus, current_datetime)
            self.current_order.buyer = buyer

            order_dir = (
                self.parent.restore_file.parent
                / 'Order'
            )
            order_dir.mkdir(exist_ok=True)
            self.current_order.push_restore(
                order_dir / f'{self.current_order.id}.json',
                tmp=True
            )

            collection_time = \
                self.calculate_collection_time(self.current_order)
            self._next_step = cast(
                current_datetime
                + timedelta(seconds=collection_time),
                float
            )
            return current_step, self._next_step

        # Queuing order
        elif self.current_order.status == OrderStatus.COLLECTING:
            self.current_order.queue(self.parent, current_datetime)

        # Paying order
        elif self.current_order.status == OrderStatus.WAITING_PAYMENT:
            data = self.data

            payment_method = \
                self.random_payment_method(data.payment_method_prob)
            self.current_order.begin_payment(payment_method)

            payment_time = self.calculate_payment_time(
                self.current_order,
                data.payment_method_time
            )
            self._next_step = cast(
                current_datetime
                + timedelta(seconds=payment_time),
                float
            )

            return current_step, self._next_step

        # Complete the payment
        elif self.current_order.status == OrderStatus.DOING_PAYMENT:
            self.current_order.complete_payment(current_datetime)

        # Leave the store
        elif self.current_order.status == OrderStatus.DONE:
            self.current_order = None
            self._next_step = cast(
                self.calculate_next_order_datetime(current_date),
                float
            )
            return current_step, self._next_step

        return current_step, next_datetime

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
            hours = np.clip(
                self._rng.normal(hour_loc, hour_spread / 2.0),
                GlobalContext.STORE_OPEN_HOUR - 0.5,
                GlobalContext.STORE_CLOSE_HOUR + 0.5
            )
            order_datetime += timedelta(hours=hours)

        return order_datetime

    def random_buyer(self, family: Family) -> Person:
        family_weight = {
            FamilyStatus.SINGLE: 1,
            FamilyStatus.PARENT: 8,
            FamilyStatus.CHILD: 1
        }

        potential_buyers = [member for member in family.members]
        potential_buyer_weights = [
            family_weight[member.status]
            for member in potential_buyers
        ]

        return self._rng.choice(
            potential_buyers,
            p=(
                np.array(potential_buyer_weights)
                / np.sum(potential_buyer_weights)
            )
        )

    def random_payment_method(
            self,
            payment_method_prob: Dict[PaymentMethod, float]
            ) -> PaymentMethod:
        return self._rng.choice(
            list(payment_method_prob.keys()),
            p=list(payment_method_prob.values())
        )

    def get_needed_products(
            self,
            product_need_days_left: Dict[Product, int]
            ) -> List[Product]:
        return [
            product
            for product, days_left in product_need_days_left.items()
            if days_left <= 0
        ]

    def get_order_products(
            self,
            products: List[Product],
            buyer: Person,
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
            for (product_name, association_strength), random in zip(
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
            quantity = \
                1 + int(self._rng.poisson(
                    max(0.0, self.n_members / sku.pax - 1)
                ))
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
                    self._rng.normal(
                        2.5,
                        size=sum([
                            quantity - 1
                            for _, quantity in order.order_skus()
                        ])
                    ),
                    0.0,
                    5.0
                )
            )
        )
        return collection_time

    def calculate_payment_time(
            self,
            order: Order,
            payment_method_time: Dict[PaymentMethod, float]
            ) -> float:
        payment_time = payment_method_time[order.payment_method]
        return payment_time

    @property
    def restore_attrs(self) -> Dict[str, Any]:
        attrs = super().restore_attrs

        if self.current_order is not None:
            attrs['order_restore_file'] = \
                self.current_order.restore_file\
                    .relative_to(GlobalContext.BASE_DIR)

        return attrs

    def _push_restore(
            self,
            file: Path = None,
            tmp: bool = False,
            **kwargs
            ) -> None:
        data_restore_file = file.parent / 'customer_data.json'
        if not data_restore_file.exists():
            data = CustomerData(
                self.current_date,
                rng=self._rng
            )
            data.push_restore(data_restore_file, tmp=tmp)

        super()._push_restore(file, tmp=tmp, **kwargs)

    @classmethod
    def _restore(cls, attrs: Dict[str, Any], file: Path, **kwargs) -> Customer:
        initial_step, interval, max_step, next_step = attrs['base_params']
        obj = cls(
            initial_step,
            interval
        )
        obj._max_step = max_step
        obj._next_step = next_step

        if 'order_restore_file' in attrs:
            obj.current_order = Order.restore(
                file.parents[1]
                / 'Order'
                / attrs['order_restore_file']
            )
        return obj
