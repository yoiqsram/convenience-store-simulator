from __future__ import annotations

import numpy as np
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Tuple, Union, TYPE_CHECKING

from .base import Agent
from .checkout import Checkout, CheckoutStatus, PaymentMethod
from .context import GlobalContext
from .item import Product, SKU
from .population import Family, FamilyStatus, Person

if TYPE_CHECKING:
    from .simulation import Simulator
    from .store import Store


def random_payment_method_config(
        rng: np.random.RandomState
    ) -> Tuple[Dict[PaymentMethod, float], Dict[PaymentMethod, float]]:
    payment_method_weight = {
        PaymentMethod.CASH: max(0, rng.normal(0.8, 0.05)),
        PaymentMethod.CREDIT_CARD: max(0, rng.normal(0.01, 0.01)),
        PaymentMethod.DEBIT_CARD: max(0, rng.normal(0.05, 0.025)),
        PaymentMethod.DIGITAL_CASH: max(0, rng.normal(0.05, 0.025))
    }
    total_payment_method_weight = np.sum(list(payment_method_weight.values()))
    payment_method_prob: Dict[PaymentMethod, float] = {
        payment_method: weight / total_payment_method_weight
        for payment_method, weight in payment_method_weight.items()
    }
    payment_method_time: Dict[PaymentMethod, float] = {
        PaymentMethod.CASH: np.clip(rng.normal(5.0, 1.0), 2.0, 15.0),
        PaymentMethod.CREDIT_CARD: np.clip(rng.normal(15.0, 3.0), 10.0, 45.0),
        PaymentMethod.DEBIT_CARD: np.clip(rng.normal(20.0, 3.0), 10.0, 45.0),
        PaymentMethod.DIGITAL_CASH: np.clip(rng.normal(10.0, 2.0), 5.0, 30.0),
    }
    return payment_method_prob, payment_method_time


class Customer(Agent):
    __repr_attrs__ = ( 'id', 'last_step', 'current_checkout' )

    def __init__(
            self,
            family: Family,
            seed: int = None
        ) -> None:
        super().__init__(seed=seed)

        self.community: Store
        self.family = family

        self.product_need_days_left: Dict[str, int] = {
            product.name: self._rng.randint(0, product.interval_days_need)
            for product in Product.all()
        }
        self.payment_method_prob, self.payment_method_time = random_payment_method_config(self._rng)

        self.current_checkout: Union[Checkout, None] = None

        self._last_updated_date: date = None

    @property
    def n_members(self) -> int:
        return self.family.n_members

    def update(self, last_date: date) -> None:
        if self._last_updated_date is not None:
            days_to_go = (last_date - self._last_updated_date).days
            if days_to_go < 1:
                return

            for product_name, days_left in self.product_need_days_left.copy().items():
                self.product_need_days_left[product_name] = max(0, days_left - days_to_go)

            self._last_updated_date = last_date

        if self._next_step is None:
            self._next_step = self.calculate_next_order_datetime(last_date)

    def step(self, env: Simulator) -> Tuple[datetime, Union[datetime, None]]:
        last_datetime, next_datetime = super().step(env)
        if next_datetime is None:
            return last_datetime, next_datetime

        last_date = last_datetime.date()

        if self.current_checkout is None:
            # Randomize buyer representative and get the family needs
            buyer = self.random_buyer(last_date)
            payment_method = self.random_payment_method()
            needed_products = self.get_needed_products()
            for product in needed_products:
                self.product_need_days_left[product.name] = self._rng.poisson(
                    product.interval_days_need
                )

            # Calculate conversion from needs to purchase from the store, then checkout
            checkout_products = self.get_checkout_products(needed_products, buyer, last_date)

            # Skip checkout if have no product to purchase, wouldn't spend, store is close or store is open but full
            if len(checkout_products) == 0 \
                    or self._rng.random() > self.family.spending_rate \
                    or not self.community.is_open() \
                    or self.community.is_full_queue():
                self._next_step = self.calculate_next_order_datetime(last_date)
                return last_datetime, self._next_step

            # Collecting checkout products in the store
            checkout_items = self.get_checkout_items(checkout_products)
            self.current_checkout = Checkout(
                checkout_items,
                buyer,
                payment_method,
                last_datetime
            )
            collection_time = self.calculate_collection_time(self.current_checkout)
            self._next_step = last_datetime + timedelta(seconds=collection_time)
            return last_datetime, self._next_step

        # Queuing checkout
        elif self.current_checkout.status == CheckoutStatus.COLLECTING:
            self.community.add_checkout_queue(self.current_checkout)
            self.current_checkout.set_status(
                CheckoutStatus.QUEUING,
                last_datetime
            )

        # Paying checkout
        elif self.current_checkout.status == CheckoutStatus.WAITING_PAYMENT:
            self.current_checkout.set_status(
                CheckoutStatus.DOING_PAYMENT,
                last_datetime
            )
            payment_time = self.calculate_payment_time(self.current_checkout)
            self._next_step = last_datetime + timedelta(seconds=payment_time)
            return last_datetime, self._next_step

        # Complete the payment
        elif self.current_checkout.status == CheckoutStatus.DOING_PAYMENT:
            self.current_checkout.set_status(
                CheckoutStatus.PAID,
                last_datetime
            )

        # Leave the store
        elif self.current_checkout.status == CheckoutStatus.DONE:
            self.current_checkout = None
            self._next_step = self.calculate_next_order_datetime(last_date)
            return last_datetime, self._next_step

        return last_datetime, next_datetime

    def calculate_next_order_datetime(self, last_date: date) -> datetime:
        n = 1 + int(self._rng.poisson(7))
        most_needed_products = sorted(self.product_need_days_left.values())[:n]
        max_need_days_left = int(max(most_needed_products))

        order_datetime = (
            datetime(last_date.year, last_date.month, last_date.day)
            + timedelta(days=max_need_days_left)
            + timedelta(hours=self._rng.normal(self._rng.choice(GlobalContext.STORE_PEAK_HOURS), 1.0))
        )
        return order_datetime

    def random_buyer(self, last_date: date) -> Person:
        family_weight = {
            FamilyStatus.SINGLE: 1,
            FamilyStatus.PARENT: 8,
            FamilyStatus.CHILD: 1
        }

        potential_buyers = [
            member
            for member in self.family.members
            if member.age(last_date) > 12
        ]
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
        days_to_go = self._rng.poisson(7)
        return [
            Product.get(product_name)
            for product_name, days_left in self.product_need_days_left.items()
            if days_left <= days_to_go
        ]

    def get_checkout_products(
            self,
            products: List[Product],
            buyer: Person,
            last_date: date
        ) -> List[Product]:
        checkout_products = [
            product
            for product, random in zip(
                products,
                self._rng.random(len(products))
            )
            if random <= product.adjusted_modifier(buyer, last_date)
        ]

        for product in checkout_products.copy():
            checkout_product_names = [
                product.name
                for product in checkout_products
            ]
            for ( product_name, association_strength ), random in zip(
                    product.associations.items(),
                    self._rng.random(len(product.associations))
                ):
                if product_name not in checkout_product_names \
                        and random <= association_strength:
                    associated_product = Product.get(product_name)
                    checkout_products.append(associated_product)

        return checkout_products

    def get_checkout_items(self, products: List[Product]) -> List[Tuple[SKU, int]]:
        items = []
        for product in products:
            sku: SKU = self._rng.choice(product.skus)
            quantity = 1 + int(self._rng.poisson(max(0.0, self.n_members / sku.pax - 1)))
            items.append((sku, quantity))

        return items

    def calculate_collection_time(self, checkout: Checkout) -> float:
        collection_time = (
            15.0
            + np.sum(
                np.clip(
                    self._rng.normal(15.0, 5.0, size=len(checkout.items)),
                    1.0,
                    3.0
                )
            )
            + np.sum(
                np.clip(
                    self._rng.normal(2.5, size=sum([quantity - 1 for _, quantity in checkout.items])),
                    0.0,
                    5.0
                )
            )
        )
        return collection_time

    def calculate_payment_time(self, checkout: Checkout) -> float:
        payment_time = self.payment_method_time[checkout.payment_method]
        return payment_time

    @classmethod
    def from_families(
            cls,
            families: Iterable[Family],
            seed: int = None,
            rng: np.random.RandomState = None
        ) -> Iterable[Customer]:
        if rng is None:
            rng = np.random.RandomState(seed)

        for family in families:
            yield cls(
                family,
                seed=int(rng.random() * 1_000_000)
            )
