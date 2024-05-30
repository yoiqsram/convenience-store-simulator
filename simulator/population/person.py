from __future__ import annotations

import numpy as np
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Union, TYPE_CHECKING

from ..core import ReprMixin, IdentityMixin
from ..core.restore import RestorableMixin
from ..core.utils import cast
from ..context import DAYS_IN_YEAR
from ..enums import FamilyStatus, Gender

if TYPE_CHECKING:
    from .family import Family


class Person(
        RestorableMixin, ReprMixin, IdentityMixin,
        repr_attrs=('gender', 'status', 'birth_date')
        ):
    def __init__(
            self,
            gender: Gender,
            status: FamilyStatus,
            birth_date: datetime,
            _id: str = None
            ) -> None:
        self.gender = gender
        self.status = status
        self.birth_date = birth_date

        self.family: Union[Family, None] = None

        self.__init_id__(_id)

    def age(self, current_date: date) -> float:
        age = (current_date - self.birth_date).days / DAYS_IN_YEAR
        return age

    @property
    def restore_attrs(self) -> Dict[str, Any]:
        return {
            'params': [
                self.gender.name,
                self.status.name,
                self.birth_date,
                self.id
            ]
        }

    @classmethod
    def _restore(cls, attrs: Dict[str, Any], file: Path, **kwargs) -> Person:
        gender, status, birth_date, _id = attrs['params']
        obj = cls(
            getattr(Gender, gender),
            getattr(FamilyStatus, status),
            cast(birth_date, date),
            _id
        )
        return obj

    @classmethod
    def generate(
            cls,
            gender: Gender,
            age: float,
            status: FamilyStatus,
            current_date: date,
            seed: int = None,
            rng: np.random.RandomState = None
            ) -> Person:
        birth_date = current_date - timedelta(days=age * DAYS_IN_YEAR)
        return Person(
            gender,
            status,
            birth_date
        )
