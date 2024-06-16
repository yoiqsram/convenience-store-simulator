from __future__ import annotations

import numpy as np
from typing import TYPE_CHECKING

from core import Agent, DateTimeStepMixin
from ..context import GlobalContext, SECONDS_IN_DAY
from ..database import ProductModel, SKUModel
from ..enums import Gender, OrderStatus
from .order import Order

if TYPE_CHECKING:
    from .store import Store


class Customer(
        Agent, DateTimeStepMixin,
        repr_attrs=('current_order',)
        ):
    __slots__ = ['store', 'current_order']

    def __init__(
            self,
            store: Store,
            index: int,
            seed: int = None,
            rng: np.random.RandomState = None) -> None:
        self.store: Store = store
        self._index = index

        self.current_order: Order | None = None

        super().__init__(seed=seed, rng=rng)

    @property
    def n_members(self) -> int:
        return self.store.place.family_sizes[self._index]

    def step(self, *args, **kwargs) -> tuple[np.uint32, np.uint32, bool]:
        self.store.total_customer_steps += 1
        current_step, _, done = super().step(*args, **kwargs)

        # Plan next need
        if self.current_order is None:
            self.next_step = self.get_next_need_timestamp(current_step)

        # Cancel planned order when store is closed or full
        elif self.current_order.status == OrderStatus.PLANNING:
            if not self.store.is_open() \
                    or self.store.is_full_queue():
                self.current_order.cancel_order()
                self.current_order = None
                self.next_step = self.get_next_need_timestamp(current_step)
            else:
                self.current_order.collect(current_step)

        # Queuing order
        elif self.current_order.status == OrderStatus.COLLECTING:
            self.current_order.queue(current_step)
            # self.next_step = current_step + GlobalContext.STORE_QUEUE_MAX_WAIT_TIME

        # Cancel order if the queue takes longer than 30 minutes
        elif self.current_order.status == OrderStatus.QUEUING \
                and (
                    current_step - self.current_order.queue_timestamp
                    > GlobalContext.STORE_QUEUE_MAX_WAIT_TIME
                ):
            self.current_order.cancel_order()
            self.current_order = None
            self.next_step = self.get_next_need_timestamp(current_step)

        # Waiting for checkout process
        elif self.current_order.status == OrderStatus.PROCESSING:
            self.next_step = self.current_order.checkout_end_timestamp

        # Paying order
        elif self.current_order.status == OrderStatus.WAITING_PAYMENT:
            payment_time = self.store._customer_payment_methods[
                self._index,
                self.current_order.payment_method.value - 1,
                1
            ]
            self.current_order.begin_payment(current_step, payment_time)
            self.next_step = self.current_order.paid_timestamp

        # Complete the payment
        elif self.current_order.status == OrderStatus.DOING_PAYMENT:
            self.current_order.complete_payment(current_step)
            self.current_order = None
            self.next_step = self.get_next_need_timestamp(current_step)

        return current_step, self.next_step, done

    def create_order(
            self,
            buyer_gender: Gender,
            buyer_age: float,
            product_names: list[str],
            payment_method
            ) -> list[tuple[SKUModel, int]]:
        order_skus = []
        for product_name in product_names:
            product = ProductModel.get(ProductModel.name == product_name)
            sku: SKUModel = self._rng.choice(list(product.skus))
            quantity = \
                1 + int(self._rng.poisson(
                    max(0, self.n_members / sku.pax - 1)
                ))
            order_skus.append((sku, quantity))

        self.current_order = Order(
            self.store,
            buyer_gender,
            buyer_age,
            order_skus,
            payment_method
        )
        return self.current_order

    def get_next_need_timestamp(self, current_timestamp: float) -> float:
        return self.calculate_next_need_timestamp(
            current_timestamp,
            rng=self._rng
        )[0]

    @classmethod
    def calculate_next_need_timestamp(
            self,
            current_timestamp: np.ndarray,
            method: str = 'poisson',
            seed: int = None,
            rng: np.random.RandomState = None
            ) -> np.ndarray:
        if rng is None:
            rng = np.random.RandomState(seed)

        if not isinstance(current_timestamp, np.ndarray):
            current_timestamp = np.array((current_timestamp,))

        n = current_timestamp.shape[0]
        next_timestamp = \
            current_timestamp - current_timestamp % SECONDS_IN_DAY
        if method == 'uniform':
            next_timestamp += (
                (rng.randint(0, 7, n) * SECONDS_IN_DAY)
                .astype(np.uint32)
            )
        else:
            next_timestamp += (
                (rng.poisson(7, n) * SECONDS_IN_DAY)
                .astype(np.uint32)
            )

        random_mask = rng.random(n) < 0.2
        n_random = np.sum(random_mask)
        next_timestamp[random_mask] += (
            (
                rng.uniform(
                    GlobalContext.STORE_OPEN_HOUR,
                    GlobalContext.STORE_CLOSE_HOUR,
                    n_random
                ) * 3600
            )
            .astype(np.uint32)
        )
        next_timestamp[~random_mask] += (
            (
                np.clip(
                    rng.choice(
                        GlobalContext.STORE_PEAK_HOURS,
                        n - n_random
                        )
                    + rng.normal(0, 1, n - n_random),
                    GlobalContext.STORE_OPEN_HOUR - 1,
                    GlobalContext.STORE_CLOSE_HOUR - 1,
                ) * 3600
            )
            .astype(np.uint32)
        )
        return next_timestamp
