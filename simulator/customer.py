from __future__ import annotations

import numpy as np
from datetime import date, datetime, timedelta
from typing import Dict, Tuple, Union, TYPE_CHECKING

from .base import Agent
from .checkout import Checkout, PaymentMethod
from .item import Product, SKU
from .population import Family, FamilyStatus

if TYPE_CHECKING:
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


def random_checkout_hour(
        min_hour: int,
        max_hour: int,
        rng: np.random.RandomState
    ) -> None:
    peak_hours = [12.5, 19.0]
    peak_hour = rng.choice(peak_hours)
    return np.clip(
        rng.normal(peak_hour, peak_hour * 0.25),
        min_hour,
        max_hour
    )


class Customer(Agent):
    def __init__(
            self,
            family: Family,
            seed: int = None
        ) -> None:
        super().__init__(seed=seed)

        self.family = family

        if len(Product.all()) == 0:
            Product.load()

        self.products_days_left: Dict[str, int] = {
            product.name: self._rng.random_integers(0, product.interval_days_need)
            for product in Product.all()
        }

        self.payment_method_prob, self.payment_method_time = random_payment_method_config(self._rng)
        self._last_update_date: date = None

    def __repr__(self) -> str:
        return f'Customer(n_members={self.family.n_members})'

    def step(self, env: Store) -> None:
        self.update_product_days_left(env.current_step().date())

        if self.next_step is None:
            self.next_step, self._next_days_left = self.calculate_next_checkout(
                env.current_step(),
                min_hour=env.open_hour,
                max_hour=env.close_hour
            )

        super().step(env)

        if self.next_step < env.current_step():
            self.checkout(env)
            self.next_step, self._next_days_left = None, None

    def update_product_days_left(self, a_date: date) -> None:
        self._last_update_date = a_date
        for product_name, days_left in self.products_days_left.copy().items():
            if self._last_update_date is not None \
                    and a_date <= self._last_update_date \
                    and days_left is not None \
                    and days_left > 0:
                self.products_days_left[product_name] -= 1

            product = Product.get(product_name)
            if self.products_days_left[product_name] is None:
                self.products_days_left[product_name] = self._rng.poisson(
                    product.interval_days_need
                )

    def calculate_next_checkout(
            self,
            a_datetime: datetime,
            min_hour: int,
            max_hour: int
        ) -> Tuple[Union[datetime, None], int]:
        n = 1 + int(self._rng.poisson(2))

        try:
            nearest_products_days_left = sorted(self.products_days_left.values())[:n]
        except:
            print(self.products_days_left)
            raise
        days_to_go = int(max(nearest_products_days_left))
        next_datetime = a_datetime + timedelta(days=days_to_go)

        checkout_hour = random_checkout_hour(
            min_hour=min_hour,
            max_hour=max_hour,
            rng=self._rng
        )
        checkout_minutes = (checkout_hour % 1) * 60
        checkout_seconds = (checkout_minutes % 1) * 60

        next_datetime = datetime(
            next_datetime.year,
            next_datetime.month,
            next_datetime.day,
            int(checkout_hour),
            int(checkout_minutes),
            int(checkout_seconds)
        )
        return next_datetime, days_to_go

    def calculate_payment(self) -> Tuple[PaymentMethod, float]:
        payment_method = self._rng.choice(
            list(self.payment_method_prob.keys()),
            p=list(self.payment_method_prob.values())
        )
        payment_time = self.payment_method_time[payment_method]
        return payment_method, payment_time

    def checkout(self, env: Store) -> None:
        a_date = env.current_step().date()
        member_to_buyer_weight: Dict[int, int] = dict()
        for member in self.family.members:
            if member.status == FamilyStatus.SINGLE:
                member_to_buyer_weight[member.id] = 1
            elif member.status == FamilyStatus.PARENT:
                member_to_buyer_weight[member.id] = self._rng.random_integers(5, 10)
            elif member.status == FamilyStatus.CHILD and member.age(a_date) > 12:
                member_to_buyer_weight[member.id] = self._rng.random_integers(0, 3)

        total_weight = np.sum(list(member_to_buyer_weight.values()))
        buyer_member_id = self._rng.choice(
            list(member_to_buyer_weight.keys()),
            p=[
                weight / total_weight
                for weight in member_to_buyer_weight.values()
            ]
        )
        buyer = self.family.get(buyer_member_id)

        quantities = []
        potential_products = {
            product_name: (
                Product.get(product_name).modifier * 0.25,
                self._rng.random()
            )
            for product_name, days_left in self.products_days_left.items()
            if days_left <= self._next_days_left
        }

        associated_potential_products = dict()
        for product_name in potential_products.copy():
            product = Product.get(product_name)
            for associated_product_name, value in product.associations.items():
                if associated_product_name not in associated_potential_products:
                    associated_potential_products[associated_product_name] = value
                elif value > associated_potential_products[associated_product_name]:
                    associated_potential_products[associated_product_name] = value

                if associated_product_name not in potential_products:
                    potential_products[associated_product_name] = self._rng.random()

        for product_name, prob in potential_products.items():
            product = Product.get(product_name)
            checkout_prob = prob[0]
            if product_name in associated_potential_products:
                for associated_product_name in product.associations.keys():
                    if potential_products[associated_product_name][0] >= potential_products[associated_product_name][1] \
                            and associated_potential_products[product_name] > checkout_prob:
                        checkout_prob = associated_potential_products[product_name]
                        break

            self.products_days_left[product_name] = None
            if prob[1] > checkout_prob:
                continue

            sku: SKU = self._rng.choice(product.skus)
            quantity = min(1, self._rng.poisson(int(np.round(self.family.n_members / sku.pax))))
            quantities.append((sku, quantity))

        if len(quantities) == 0 \
                or env.is_full_queue():
            return

        checkout = Checkout(
            self,
            buyer,
            quantities,
            queue_datetime=env.current_step()
        )
        env.add_checkout_queue(checkout)

        self.next_step = None
