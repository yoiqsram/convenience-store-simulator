from __future__ import annotations

import asyncio
import numpy as np
from collections import deque
from datetime import date, datetime, timedelta
from typing import Deque, Dict, Iterable, List, Tuple, TYPE_CHECKING

from .base import Community, Environment, DatetimeStepMixin
from .checkout import Checkout, CheckoutStatus
from .context import GlobalContext
from .customer import Customer
from .database import StoreModel, ModelMixin, SubdistrictModel
from .worker import Worker, WorkerShift, WorkerStatus

if TYPE_CHECKING:
    from .place import Place


class Store(Community, DatetimeStepMixin, ModelMixin):
    __repr_attrs__ = ( 'place', 'n_workers', 'last_step' )
    __model__ = StoreModel

    def __init__(
            self,
            place: Place,
            max_cashiers: int = None,
            max_workers: int = None,
            max_queue: int = 15,
            seed: int = None
        ) -> None:
        super().__init__(seed=seed)

        self.place = place
        self._potential_customers: List[Customer] = [
            customer
            for customer in Customer.from_families(self.place.families, rng=self._rng)
        ]
        self.add_agents(
            self._potential_customers,
            self._last_step,
            None,
            self._max_step
        )

        self.long_shift_hours = timedelta(hours=(GlobalContext.STORE_CLOSE_HOUR - GlobalContext.STORE_OPEN_HOUR) / 2)
        self.schedule_shift_hours = {
            WorkerShift.FIRST: GlobalContext.STORE_OPEN_HOUR,
            WorkerShift.SECOND: (GlobalContext.STORE_OPEN_HOUR + GlobalContext.STORE_CLOSE_HOUR) / 2
        }
        self.max_cashiers = max_cashiers if max_cashiers is not None else GlobalContext.STORE_MAX_CASHIERS
        self.max_workers = max_workers if max_workers is not None else GlobalContext.STORE_INITIAL_WORKERS
        self._workers: Dict[int, Worker] = dict()
        self._cashiers: List[Worker] = []

        self._checkout_queue: Deque[Checkout] = deque(maxlen=max_queue)
        self._checkout_queue_lock = asyncio.Lock()

        place_record: SubdistrictModel = self.place.record
        super().init_model(
            unique_identifiers={ 'subdistrict': place_record.id },
            subdistrict=place_record.id
        )

        self.total_checkout = 0

    @property
    def potential_customers(self) -> Iterable[Customer]:
        for customer in self._potential_customers:
            yield customer

    def workers(self) -> Iterable[Worker]:
        return self._workers.values()

    @property
    def n_workers(self) -> int:
        return len(self._workers)

    def add_worker(self, worker: Worker) -> None:
        worker.created_datetime = self._last_step
        self.add_agent(
            worker,
            self._last_step,
            self._next_step,
            self._max_step
        )

        if worker.id in self._workers:
            raise IndexError()

        self._workers[worker.id] = worker

    def add_workers(self, workers: Iterable[Worker]) -> None:
        for worker in workers:
            self.add_worker(worker)

    def remove_worker(self, cashier) -> None:
        self.remove_agent(cashier)

        if cashier.id not in self._workers:
            raise IndexError()

        del self._workers[cashier.id]

    def get_active_workers(self) -> List[Worker]:
        return [
            worker
            for worker in self.workers()
            if worker.status not in (
                WorkerStatus.OFF,
                WorkerStatus.OUT_OF_OFFICE
            )
        ]

    def is_open(self) -> bool:
        for worker in self.workers():
            if worker.status not in (
                WorkerStatus.OFF,
                WorkerStatus.OUT_OF_OFFICE
            ):
                return True
        return False

    def is_full_queue(self) -> bool:
        return len(self._checkout_queue) == self._checkout_queue.maxlen

    async def add_checkout_queue_async(self, checkout: Checkout) -> None:
        async with self._checkout_queue_lock:
            self._checkout_queue.append(checkout)

    def add_checkout_queue(self, checkout: Checkout) -> None:
        if checkout not in self._checkout_queue:
            self._checkout_queue.append(checkout)

    async def remove_checkout_queue_async(self, checkout: Checkout) -> None:
        async with self._checkout_queue_lock:
            self._checkout_queue.remove(checkout)

    def remove_checkout_queue(self, checkout: Checkout) -> None:
        try:
            self._checkout_queue.remove(checkout)
        except:
            pass

    def step(self, env: Environment) -> Tuple[datetime, datetime]:
        last_datetime, next_datetime = super().step(env)
        last_date = last_datetime.date()

        # Register to database for the first time
        if self.record.id is None:
            self.created_datetime = last_datetime

        # Daily update
        if self.place.last_updated_date < last_date:
            print(self.place.name, '- Daily updates', last_date.isoformat())
            # Update population from place
            self.place.update(last_date)

            # Update potential customer needs
            for customer in self._potential_customers:
                customer.update(last_date)

            print('Current potential customers:', len([
                customer
                for customer in self.potential_customers
                if customer.next_step() is not None
                    and customer.next_step().date() == last_date
            ]))
            print()

            # Hire worker if has not enough worker
            if self.n_workers < self.max_workers:
                workers = Worker.bulk_generate(
                    self.max_workers - self.n_workers,
                    last_date,
                    self.place
                )
                self.add_workers(workers)

            # Schedule working shifts
            self.schedule_shifts(last_date)

            self.total_checkout = 0

        # Transition working shift
        active_workers = self.get_active_workers()
        self.transition_working_shift(active_workers, last_datetime)

        # Assign checkout queue to worker
        if len(self._checkout_queue) > 0:
            self.assign_checkout_queue(active_workers, last_datetime)

        return last_datetime, next_datetime

    def schedule_shifts(self, last_date: date) -> None:
        shifts = ([1, 2] * int(np.ceil(self.n_workers / 2)))[:self.n_workers]
        self._rng.shuffle(shifts)
        for worker, shift in zip(self.workers(), shifts):
            worker: Worker
            worker.schedule_shift(last_date, WorkerShift(shift))
            print(last_date, worker)
        print()

    def transition_working_shift(
            self,
            active_workers: List[Worker],
            last_datetime: datetime
        ) -> None:
        next_shift_workers = [
            worker
            for worker in active_workers
            if worker.status == WorkerStatus.STARTING_SHIFT
        ]
        for worker in active_workers:
            # Assign to cashier who is going to start shift and there's still unused cashier
            if worker.status == WorkerStatus.STARTING_SHIFT \
                    and worker.today_shift_start_datetime <= last_datetime \
                    and len(self._cashiers) < self.max_cashiers:
                print(f'Worker {worker.id} begin working at', last_datetime)
                self._cashiers.append(worker)
                worker.status = WorkerStatus.IDLE

            # Withdraw cashier who is ending shift that is not busy and there'll be enough cashiers
            elif worker.schedule_shift_end_datetime <= last_datetime \
                    and  worker.current_checkout is None \
                    and (len(self._cashiers) + len(next_shift_workers) - 1) > 0:
                print(f'Worker {worker.id} complete working at', last_datetime)
                self._cashiers.remove(worker)
                worker.status = WorkerStatus.OFF
                worker.shift = WorkerShift.OFF
                worker.today_shift_end_datetime = last_datetime

    def assign_checkout_queue(
            self,
            active_workers: List[Worker],
            last_datetime: datetime
        ) -> None:
        for queue_item in self._checkout_queue.copy():
            if queue_item.status != CheckoutStatus.QUEUING:
                continue

            for worker in active_workers:
                # Don't assign worker who is not a cashier
                if worker not in self._cashiers:
                    continue

                # Don't assign worker who is still busy
                if worker.current_checkout is not None:
                    continue

                # Don't assign worker who is going to end shift and no other cashiers
                if worker in self._cashiers \
                        and worker.schedule_shift_end_datetime <= last_datetime \
                        and len(self._cashiers) - 1 > 0:
                    continue

                worker.current_checkout = queue_item
