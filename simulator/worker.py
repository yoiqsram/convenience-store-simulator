from __future__ import annotations

import numpy as np
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from .base import Agent
from .population import Person, Gender, FamilyStatus
from .utils import add_years

if TYPE_CHECKING:
    from .checkout import Checkout
    from .store import Store


class WorkerStatus(Enum):
    OFF = 0
    OUT_OF_OFFICE = 1
    STARTING_SHIFT = 2
    IDLE = 3
    PROCESSING_CHECKOUT = 4
    COMPLETING_SHIFT = 5


class Worker(Agent):
    def __init__(
            self,
            person: Person,
            age_recognition_rate: float = None,
            counting_skill_rate: float = None,
            content_rate: float = None,
            discipline_rate: float = None
        ) -> None:
        super().__init__()

        self.person = person
        self.age_recognition_rate = age_recognition_rate
        self.counting_skill_rate = counting_skill_rate
        self.content_rate = content_rate
        self.discipline_rate = discipline_rate
        self.status = WorkerStatus.OFF

        self._attendance_shift: int = 0
        self._today_shift_datetime: datetime = None

    def __repr__(self) -> str:
        return f"Worker(name='{self.person.name}', status={self.status.name})"

    def step(self, env: Store) -> None:
        super().step(env=env)

        # Shift transition
        if self._today_shift_datetime is not None \
                and env.current_step() >= self._today_shift_datetime:
            if self._attendance_shift == 2 \
                    and self.status == WorkerStatus.OFF:
                self.status = WorkerStatus.STARTING_SHIFT

            elif self._attendance_shift == 1 \
                    and self.status == WorkerStatus.IDLE:
                self.status = WorkerStatus.COMPLETING_SHIFT

    def calculate_checkout(self, checkout: Checkout) -> float:
        checkout_time = 2.5
        for _, quantity in checkout.quantities:
            checkout_time += np.clip(
                self._rng.normal(
                    6.0 - self.counting_skill_rate,
                    (5.1 - self.counting_skill_rate)
                ),
                1.0,
                10.0
            )
            checkout_time += (quantity - 1) * np.clip(
                self._rng.normal(1.0, 0.25),
                0.5,
                5.0
            )

        return checkout_time

    @classmethod
    def generate(
            cls,
            env: Store,
            age_recognition_loc: float = 4.0,
            age_recognition_scale: float = 0.5,
            counting_skill_loc: float = 4.5,
            counting_skill_scale: float = 0.050,
            content_rate_loc: float = 4.5,
            content_rate_scale: float = 0.5,
            discipline_rate_loc: float = 4.5,
            discipline_rate_scale: float = 0.5
        ) -> Worker:
        from numpy import clip

        age_recognition_rate = clip(
            env._rng.normal(
                age_recognition_loc,
                age_recognition_scale
            ),
            1.0,
            5.0
        )
        counting_skill_rate = clip(
            env._rng.normal(
                counting_skill_loc,
                counting_skill_scale
            ),
            1.0,
            5.0
        )
        content_rate = clip(
            env._rng.normal(
                content_rate_loc,
                content_rate_scale
            ),
            1.0,
            5.0
        )
        discipline_rate = clip(
            env._rng.normal(
                discipline_rate_loc,
                discipline_rate_scale
            ),
            1.0,
            5.0
        )

        gender = Gender.MALE if env._rng.random() < 0.5 else Gender.FEMALE
        age = clip(
            env._rng.normal(24.0, 2.0),
            18.0,
            30.0
        )

        person = Person(
            name=Person.generate_name(gender, seed=env._rng.get_state()[1][0]),
            gender=gender,
            status=FamilyStatus.SINGLE,
            birth_date=add_years(env.current_step(), -age),
            birth_place=env.place
        )
        return cls(
            person=person,
            age_recognition_rate=age_recognition_rate,
            counting_skill_rate=counting_skill_rate,
            content_rate=content_rate,
            discipline_rate=discipline_rate
        )