from __future__ import annotations

import numpy as np
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Tuple, Union, TYPE_CHECKING

from .base import Agent
from .checkout import Checkout, CheckoutStatus
from .database import EmployeeModel, ModelMixin
from .place import Place
from .population import AgeGroup, Gender, Person, FamilyStatus

if TYPE_CHECKING:
    from .simulation import Simulator
    from .store import Store


class WorkerShift(Enum):
    OFF = 0
    FIRST = 1
    SECOND = 2


class WorkerStatus(Enum):
    OFF = 0
    OUT_OF_OFFICE = 1
    STARTING_SHIFT = 2
    IDLE = 3
    PROCESSING_CHECKOUT = 4


class Worker(Agent, ModelMixin):
    __repr_attrs__ = ( 'id', 'name', 'status', 'shift' )
    __model__ = EmployeeModel

    def __init__(
            self,
            person: Person,
            age_recognition_rate: float = None,
            counting_skill_rate: float = None,
            content_rate: float = None,
            discipline_rate: float = None,
            seed: int = None
        ) -> None:
        super().__init__(seed=seed)

        self.community: Store
        self.person = person
        self.age_recognition_rate = age_recognition_rate
        self.counting_skill_rate = counting_skill_rate
        self.content_rate = content_rate
        self.discipline_rate = discipline_rate
        self.status = WorkerStatus.OFF

        self.current_checkout: Union[Checkout, None] = None

        self.shift: WorkerShift = WorkerShift.OFF
        self.schedule_shift_start_datetime: datetime = None
        self.schedule_shift_end_datetime: datetime = None
        self.today_shift_start_datetime: datetime = None
        self.today_shift_end_datetime: datetime = None

        super().init_model(
            unique_identifiers={ 'person_id': self.person.id },
            person_id=person.id,
            name=person.name,
            gender=person.gender.name,
            birth_date=person.birth_date,
            birth_place=person.birth_place.record.id
        )

    @property
    def id(self) -> str:
        self.record: EmployeeModel
        return self.record.id

    @property
    def name(self) -> str:
        return self.person.name

    def schedule_shift(self, shift_date: date, shift: WorkerShift) -> None:
        if shift == WorkerShift.OFF:
            return

        self.shift = shift
        self.today_shift_start_datetime = None
        self.today_shift_end_datetime = None

        shift_start_datetime = (
            datetime(shift_date.year, shift_date.month, shift_date.day)
            + timedelta(hours=self.community.schedule_shift_hours[self.shift])
        )
        self.schedule_shift_start_datetime = (
            shift_start_datetime
            + timedelta(seconds=int(self._rng.normal(-self.discipline_rate * 60, 150)))
        )
        self.schedule_shift_end_datetime = shift_start_datetime + self.community.long_shift_hours

    def step(self, env: Simulator) -> Tuple[datetime, Union[datetime, None]]:
        last_datetime, next_datetime = super().step(env)

        # Register to database for the first time
        if self.record.id is None:
            self.created_datetime = last_datetime

        # Join shift
        if self.today_shift_start_datetime is None \
                and self.schedule_shift_start_datetime <= last_datetime:
            print(f'Worker {self.id} join shift at', last_datetime, 'to', self.schedule_shift_end_datetime)
            self.status = WorkerStatus.STARTING_SHIFT
            self.today_shift_start_datetime = last_datetime

        # Wait for checkout
        if self.current_checkout is None:
            pass

        # Process checkout
        elif self.current_checkout.status == CheckoutStatus.QUEUING:
            self.status = WorkerStatus.PROCESSING_CHECKOUT
            self.community.remove_checkout_queue(self.current_checkout)
            self.current_checkout.set_status(
                CheckoutStatus.PROCESSING,
                last_datetime
            )

            processing_time = self.calculate_checkout_time(self.current_checkout)
            self._next_step = last_datetime + timedelta(seconds=processing_time)
            return last_datetime, self._next_step

        # Wait for checkout payment
        elif self.current_checkout.status == CheckoutStatus.PROCESSING:
            self.current_checkout.counting_end_datetime = last_datetime
            self.current_checkout.set_status(
                CheckoutStatus.WAITING_PAYMENT,
                last_datetime
            )

        # Complete checkout
        elif self.current_checkout.status == CheckoutStatus.PAID:
            buyer_gender, buyer_age_group = None, None
            if self._rng.random() > 0.05:
                buyer_gender = self.current_checkout.buyer.gender
                buyer_age_group = self.estimate_age_group(
                    self.current_checkout.buyer,
                    last_datetime.date()
                )

            self.current_checkout.submit(
                store_id=self.community.id,
                worker_id=self.id,
                buyer_gender=buyer_gender,
                buyer_age_group=buyer_age_group
            )

            self.community.total_checkout += 1
            self.current_checkout = None
            self.status = WorkerStatus.IDLE

        return last_datetime, next_datetime

    def calculate_checkout_time(self, checkout: Checkout) -> float:
        checkout_time = (
            2.5
            + np.sum(
                np.clip(
                    self._rng.normal(
                        6.0 - self.counting_skill_rate,
                        (5.1 - self.counting_skill_rate),
                        size=len(checkout.items)
                    ),
                    1.0,
                    3.0
                )
            )
            + np.sum(
                np.clip(
                    self._rng.normal(1.0, 0.25, size=sum([quantity - 1 for _, quantity in checkout.items])),
                    0.0,
                    5.0
                )
            )
        )
        return checkout_time

    def estimate_age_group(self, person: Person, last_date: date) -> AgeGroup:
        age = person.age(last_date) + self._rng.normal(0, (6.0 - self.age_recognition_rate) * 2)

        if age < AgeGroup.KID.value:
            return AgeGroup.KID

        elif age < AgeGroup.TEENAGE.value:
            return AgeGroup.TEENAGE

        elif age < AgeGroup.YOUNG_ADULT.value:
            return AgeGroup.YOUNG_ADULT

        elif age < AgeGroup.MIDDLE_ADULT.value:
            return AgeGroup.MIDDLE_ADULT

        return AgeGroup.OLDER_ADULT

    @classmethod
    def generate(
            cls,
            last_date: date,
            place: Place,
            age_recognition_loc: float = 4.0,
            age_recognition_scale: float = 0.5,
            counting_skill_loc: float = 4.5,
            counting_skill_scale: float = 0.050,
            content_rate_loc: float = 4.5,
            content_rate_scale: float = 0.5,
            discipline_rate_loc: float = 4.5,
            discipline_rate_scale: float = 0.5,
            seed: int = None,
            rng: np.random.RandomState = None
        ) -> Worker:
        if rng is None:
            rng = np.random.RandomState(seed)

        age_recognition_rate = np.clip(
            rng.normal(
                age_recognition_loc,
                age_recognition_scale
            ),
            1.0,
            5.0
        )
        counting_skill_rate = np.clip(
            rng.normal(
                counting_skill_loc,
                counting_skill_scale
            ),
            1.0,
            5.0
        )
        content_rate = np.clip(
            rng.normal(
                content_rate_loc,
                content_rate_scale
            ),
            1.0,
            5.0
        )
        discipline_rate = np.clip(
            rng.normal(
                discipline_rate_loc,
                discipline_rate_scale
            ),
            1.0,
            5.0
        )

        gender = Gender.MALE if rng.random() < 0.5 else Gender.FEMALE
        age = np.clip(
            rng.normal(24.0, 2.0),
            18.0,
            30.0
        )

        person = Person.generate(
            gender=gender,
            age=age,
            status=FamilyStatus.SINGLE,
            a_date=last_date,
            birth_place=place,
            anonymous=False,
            seed=rng.get_state()[1][0]
        )
        return cls(
            person=person,
            age_recognition_rate=age_recognition_rate,
            counting_skill_rate=counting_skill_rate,
            content_rate=content_rate,
            discipline_rate=discipline_rate
        )

    @classmethod
    def bulk_generate(
            cls,
            n: int,
            last_date: date,
            place: Place,
            age_recognition_loc: float = 4.0,
            age_recognition_scale: float = 0.5,
            counting_skill_loc: float = 4.5,
            counting_skill_scale: float = 0.050,
            content_rate_loc: float = 4.5,
            content_rate_scale: float = 0.5,
            discipline_rate_loc: float = 4.5,
            discipline_rate_scale: float = 0.5,
            seed: int = None,
            rng: np.random.RandomState = None,
        ) -> Worker:
        if rng is None:
            rng = np.random.RandomState(seed)

        return [
            cls.generate(
                last_date,
                place,
                age_recognition_loc,
                age_recognition_scale,
                counting_skill_loc,
                counting_skill_scale,
                content_rate_loc,
                content_rate_scale,
                discipline_rate_loc,
                discipline_rate_scale,
                rng=rng
            )
            for _ in range(n)
        ]
