from __future__ import annotations

import numpy as np
import yaml
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Union, TYPE_CHECKING

from ..core import ReprMixin
from ..context import GlobalContext, DAYS_IN_YEAR
from ..enums import FamilyStatus, Gender

if TYPE_CHECKING:
    from .family import Family
    from .place import Place

DEFAULT_CONFIG_NAMES = None
DEFAULT_CONFIG_LOCATIONS = None


class Person(ReprMixin):
    __repr_attrs__ = ( 'id', 'name', 'gender', 'status' )

    def __init__(
            self,
            name: str,
            gender: Gender,
            status: FamilyStatus,
            birth_date: datetime,
            birth_place: Place = None
        ) -> None:
        self.id = None
        self.name = name
        self.gender = gender
        self.status = status
        self.birth_date = birth_date
        self.birth_place = birth_place
        self.birth_place.register_birth(self)

        self.min_purchasing_power = 0.0
        self.max_purchasing_power = 0.0

        self.family: Union[Family, None] = None

    def age(self, a_date: date) -> float:
        age = (a_date - self.birth_date).days / DAYS_IN_YEAR
        return age

    def purchasing_power(self, a_date: Union[datetime, date]) -> float:
        if self.max_purchasing_power == 0.0:
            return 0.0

        career_progress = (
            self.min_purchasing_power
            / self.max_purchasing_power
            / (1.0 + 10.0 * np.exp(-0.25 * (self.age(a_date) - 18.0) / 20.0))
        )
        return career_progress * self.max_purchasing_power

    @staticmethod
    def generate_name(
            gender: Gender,
            config_path: Path = None,
            seed: int = None
        ) -> str:
        rng = np.random.RandomState(seed)

        config = None
        if config_path is None:
            config_path = GlobalContext.CONFIG_DIR / 'names.yaml'
            config = DEFAULT_CONFIG_NAMES

        if config is None:
            with open(config_path) as f:
                config = yaml.safe_load(f)

        first_name_choices = config[gender.name]['first']
        return rng.choice(first_name_choices)

    @classmethod
    def generate(
            self,
            gender: Gender,
            age: float,
            status: FamilyStatus,
            a_date: date,
            birth_place: Place,
            anonymous: bool = True,
            seed: int = None,
            rng: np.random.RandomState = None
        ) -> Person:
        if rng is None:
            rng = np.random.RandomState(seed)

        name = Person.generate_name(gender, seed=int(rng.random() * 1_000_000)) if not anonymous else None
        birth_date = a_date - timedelta(days=age * DAYS_IN_YEAR)
        return Person(
            name=name,
            gender=gender,
            status=status,
            birth_date=birth_date,
            birth_place=birth_place
        )
