from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime
from typing import Deque, Dict, Iterable, List, Tuple, TYPE_CHECKING

from .base import DatetimeClock, Environment
from .checkout import Checkout, CheckoutStatus
from .customer import Customer
from .worker import Worker, WorkerStatus

if TYPE_CHECKING:
    from .place import Place


class Store(Environment):
    def __init__(
            self,
            place: Place,
            max_queue: int = 15,
            clock: DatetimeClock = None,
            seed: int = None
        ) -> None:
        super().__init__(
            clock=clock if clock is not None else DatetimeClock(),
            seed=seed
        )

        self.place = place
        self._potential_customers = []
        for i, family in enumerate(self.place.families):
            customer = Customer(family, seed=seed + i)
            self.add_agent(customer)
            self._potential_customers.append(customer)

        self.open_hour = 7
        self.close_hour = 22

        self._workers: Dict[int, Worker] = dict()
        for _ in range(2):
            worker = Worker.generate(env=self)
            self.add_worker(worker)

        self._checkout_queue: Deque[Checkout] = deque(maxlen=max_queue)
        self._checkout_queue_lock = asyncio.Lock()

        self.total_checkouts = 0

    @property
    def potential_customers(self) -> Iterable[Customer]:
        for customer in self._potential_customers:
            yield customer

    @property
    def workers(self) -> Iterable[Worker]:
        return self._workers.values()

    @property
    def n_workers(self) -> int:
        return len(self._workers)

    def is_full_queue(self) -> bool:
        return len(self._checkout_queue) == self._checkout_queue.maxlen

    def get_active_workers(self) -> List[Worker]:
        return [
            worker
            for worker in self.workers
            if worker.status in (
                WorkerStatus.IDLE,
                WorkerStatus.PROCESSING_CHECKOUT,
                WorkerStatus.COMPLETING_SHIFT
            )
        ]

    def add_worker(self, cashier: Worker) -> None:
        self.add_agent(cashier)

        if cashier.id in self._workers:
            raise IndexError()

        self._workers[cashier.id] = cashier

    def remove_worker(self, cashier) -> None:
        self.remove_agent(cashier)

        if cashier.id not in self._workers:
            raise IndexError()

        del self._workers[cashier.id]

    async def add_checkout_queue_async(self, checkout: Checkout) -> None:
        async with self._checkout_queue_lock:
            self._checkout_queue.append(checkout)

    def add_checkout_queue(self, checkout: Checkout) -> None:
        self._checkout_queue.append(checkout)

    def get_changing_shift_workers(self) -> Tuple[Deque[Checkout], Deque[Checkout]]:
        starting_shift_workers = deque(maxlen=self.n_workers)
        completing_shift_workers = deque(maxlen=self.n_workers)
        for worker in self._workers.values():
            if worker.status == WorkerStatus.STARTING_SHIFT:
                starting_shift_workers.append(worker)
            elif worker.status == WorkerStatus.COMPLETING_SHIFT:
                completing_shift_workers.append(worker)

        return starting_shift_workers, completing_shift_workers

    def step(self) -> None:
        super().step()

        current_datetime = self.current_step()
        current_date = current_datetime.date()

        if self.place.last_update_date() < current_date:
            self.place.update(current_date)

        # if current_datetime.second == 0 \
        #     and current_datetime.minute % 15 == 0:
        #     print(current_datetime.isoformat())

        active_workers = self.get_active_workers()

        # Open hour
        if len(active_workers) == 0 \
                and current_datetime.hour >= self.open_hour \
                and current_datetime.hour < self.close_hour:
            print(current_datetime.isoformat(), 'Store is opened.')
            shift_hour = (self.open_hour + self.close_hour) / 2
            shift_datetime = datetime(
                current_datetime.year,
                current_datetime.month,
                current_datetime.day,
                int(shift_hour),
                int((shift_hour % 1) * 60)
            )

            workers = list(self.workers)
            self._rng.shuffle(workers)
            for shift, worker in enumerate(workers):
                worker: Worker
                worker._attendance_shift = shift + 1
                worker._today_shift_datetime = shift_datetime

                if worker._attendance_shift == 1:
                    print('First shift:', worker.person.name)
                    worker.status = WorkerStatus.IDLE

            print('Current potential customers:', len([
                customer
                for customer in self.potential_customers
                if customer.next_step.date() == self.current_step().date()
            ]))

        # Close hour
        elif len(active_workers) > 0 \
            and current_datetime.hour >= self.close_hour:
            print(current_datetime.isoformat(), 'Store is closed')
            for worker in self.workers:
                worker: Worker
                worker.status = WorkerStatus.OFF
                worker._attendance_shift = 0
                worker._today_shift_datetime = None

            print('Total checkouts:', self.total_checkouts)
            self.total_checkouts = 0

        # Skip step when store is close
        if len(active_workers) == 0:
            return

        # Working shift transition
        starting_shift_workers, completing_shift_workers = self.get_changing_shift_workers()
        if len(completing_shift_workers) > 0 \
                and len(starting_shift_workers) > 0:
            for i, worker in enumerate(completing_shift_workers):
                if i >= len(starting_shift_workers):
                    break
                worker.status = WorkerStatus.OFF
                starting_shift_workers[i].status = WorkerStatus.IDLE

                print(current_datetime.isoformat(), 'Change working shift from ', worker, 'to', starting_shift_workers[i])

        # Process checkout
        queue_items = [queue_item for queue_item in self._checkout_queue]
        for queue_item in queue_items:
            if queue_item.status == CheckoutStatus.QUEUEING:
                for worker in self.get_active_workers():
                    if worker.status != WorkerStatus.IDLE:
                        continue

                    # print(current_datetime.isoformat(), 'Processing ', queue_item, 'by', worker.person.name)
                    queue_item.process(
                        worker=worker,
                        env=self
                    )
                    queue_item.worker.status = WorkerStatus.PROCESSING_CHECKOUT
                    break

            if queue_item.status == CheckoutStatus.PROCESSING \
                    and queue_item.processed_datetime < self.current_step():
                queue_item.pay()
                # print(current_datetime.isoformat(), 'Paying', queue_item, 'using', queue_item.payment_method.name)

            if queue_item.status == CheckoutStatus.WAITING_PAYMENT \
                    and queue_item.paid_datetime < self.current_step():
                # print(current_datetime.isoformat(), 'Complete', queue_item)
                queue_item.worker.status = WorkerStatus.IDLE
                queue_item.complete()
                self._checkout_queue.popleft()
                self.total_checkouts += 1
