from __future__ import annotations

import numpy as np
import yaml
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Union, TYPE_CHECKING

from ..core import ReprMixin
from ..core.restore import RestorableMixin
from ..context import GlobalContext, DAYS_IN_YEAR
from ..enums import FamilyStatus, Gender

if TYPE_CHECKING:
    from .family import Family

DEFAULT_CONFIG_NAMES = None
DEFAULT_CONFIG_LOCATIONS = None


class Person(
        RestorableMixin, ReprMixin,
        repr_attrs=('name', 'gender', 'status')
        ):
    def __init__(
            self,
            name: str,
            gender: Gender,
            status: FamilyStatus,
            birth_date: datetime,
            birth_place_code: str = None,
            _id: str = None
            ) -> None:
        self.id = _id
        self.name = name
        self.gender = gender
        self.status = status
        self.birth_date = birth_date
        self.birth_place_code = birth_place_code

        self.family: Union[Family, None] = None

    def age(self, current_date: date) -> float:
        age = (current_date - self.birth_date).days / DAYS_IN_YEAR
        return age

    @property
    def restore_attrs(self) -> Dict[str, Any]:
        return {
            'params': [
                self.name,
                self.gender.name,
                self.status.name,
                self.birth_date,
                self.birth_place_code,
                self.id
            ]
        }

    @classmethod
    def _restore(cls, attrs: Dict[str, Any], file: Path, **kwargs) -> Person:
        name, gender, status, birth_date, birth_place_code, _id = \
            attrs['params']
        obj = cls(
            name,
            getattr(Gender, gender),
            getattr(FamilyStatus, status),
            birth_date,
            birth_place_code,
            _id
        )
        return obj

    @staticmethod
    def generate_name(
            gender: Gender,
            config_path: Path = None,
            seed: int = None,
            rng: np.random.RandomState = None
            ) -> str:
        if rng is None:
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
            cls,
            gender: Gender,
            age: float,
            status: FamilyStatus,
            current_date: date,
            birth_place_code: str,
            anonymous: bool = True,
            seed: int = None,
            rng: np.random.RandomState = None
            ) -> Person:
        name = None
        if not anonymous:
            name = Person.generate_name(gender, seed=seed, rng=rng)

        birth_date = current_date - timedelta(days=age * DAYS_IN_YEAR)
        return Person(
            name,
            gender,
            status,
            birth_date,
            birth_place_code
        )
