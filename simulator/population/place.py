from __future__ import annotations

import numpy as np
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Generator, Iterable, Tuple

from ..core import ReprMixin, RandomGeneratorMixin
from ..core.restore import RestorableMixin
from ..context import GlobalContext, DAYS_IN_YEAR
from ..database import ModelMixin, SubdistrictModel
from .family import Family, FamilyStatus, Gender


class Place(
        RestorableMixin, ModelMixin, RandomGeneratorMixin, ReprMixin,
        model=SubdistrictModel,
        repr_attrs=( 'name', 'n_families', 'total_population' )
    ):
    def __init__(
            self,
            code: str,
            name: str,
            initial_date: date,
            initial_population: int,
            fertility_rate: float,
            life_expectancy: float,
            marry_age: float,
            seed: int = None,
            rng: np.random.RandomState = None,
            _families: List[Family] = None
        ) -> None:
        self.code = code
        self.name = name
        self.initial_population = int(initial_population)
        self.fertility_rate = float(fertility_rate)
        self.life_expectancy = float(life_expectancy)
        self.marry_age = float(marry_age)

        self._prefix_id_counts: Dict[str, int] = {}
        self.last_updated_date: date = initial_date

        super().__init_rng__(seed, rng)

        self.families = _families
        if _families is None:
            self.families: List[Family] = Family.bulk_generate(
                int(self.initial_population / 3.0),
                initial_date,
                self,
                rng=self._rng
            )

        super().__init_model__(
            unique_identifiers={ 'code': self.code }
        )

    @property
    def n_families(self) -> int:
        return len(self.families)

    def total_population(self) -> int:
        return int(
            np.sum([
                family.n_members
                for family in self.families
            ])
        )

    def update_population(self, current_date: date) -> None:
        days_to_go = (current_date - self.last_updated_date).days
        if days_to_go < 1:
            return

        fertility_rate = self.fertility_rate / DAYS_IN_YEAR
        for _ in range(days_to_go):
            self.last_updated_date += timedelta(days=1)

            n_families = len(self.families)

            max_members = Family.random_max_n_members(size=n_families, rng=self._rng)

            _birth_probs = self._rng.random(n_families)
            would_births = _birth_probs < fertility_rate
            new_born_males = (_birth_probs / fertility_rate) < 0.5

            die_ages = self._rng.normal(
                self.life_expectancy,
                self.life_expectancy * 0.1,
                size=n_families
            )
            would_dies = self._rng.random(n_families) < fertility_rate

            marry_ages = self._rng.normal(
                self.marry_age,
                self.marry_age * 0.1,
                size=n_families
            )
            would_marries = self._rng.random(n_families) < (fertility_rate * 2.0)

            unmarried_adults: List[Family] = []
            for family, max_members_, would_birth, new_born_male, die_age, would_die, marry_age, would_marry in zip(
                    self.families,
                    max_members,
                    would_births,
                    new_born_males,
                    die_ages,
                    would_dies,
                    marry_ages,
                    would_marries
                ):
                family: Family
                max_members_: int
                would_birth: bool
                new_born_male: bool
                die_age: float
                would_die: bool
                marry_age: float
                would_marry: bool

                # Born new babies
                if family.n_parents == 2 \
                        and family.youngest_age(current_date) > 1.0:
                    if family.n_members < max_members_ \
                            and would_birth:
                        family.birth(
                            place=self,
                            current_date=current_date,
                            gender=Gender.MALE if new_born_male else Gender.FEMALE,
                            rng=self._rng
                        )

                for person in family.members:
                    age = person.age(current_date)
                    if age > die_age \
                            and would_die:
                        family.die(person)

                    # Gather unmarried adults
                    elif person.status in (FamilyStatus.SINGLE, FamilyStatus.CHILD) \
                            and age > marry_age \
                            and would_marry:
                        unmarried_adults.append(person)

            # Marry the unmarried adults
            if len(unmarried_adults) > 0:
                for male, female in self.match_adults(( adult for adult in unmarried_adults )):
                    new_family = Family.from_marriage(male, female)
                    self.families.append(new_family)

            # Filter non-empty family
            self.families = [
                family
                for family in self.families
                if family.n_members > 0
            ]

    def register_birth(self, person: Family) -> None:
        prefix_id = (
            self.id[:6]
            + (str(person.birth_date.day) if person.gender == Gender.MALE else str(person.birth_date.day + 40))
            + person.birth_date.strftime('%m%y')
        )

        if prefix_id not in self._prefix_id_counts:
            self._prefix_id_counts[prefix_id] = 1
        else:
            self._prefix_id_counts[prefix_id] += 1

        person.id = prefix_id + str(self._prefix_id_counts[prefix_id]).rjust(4, '0')

    @property
    def restore_attrs(self) -> Dict[str, Any]:
        return {
            'code': self.code,
            'name': self.name,
            'initial_population': self.initial_population,
            'fertility_rate': self.fertility_rate,
            'life_expectancy': self.life_expectancy,
            'marry_age': self.marry_age,
            'prefix_id_counts': self._prefix_id_counts,
            'last_updated_date': self.last_updated_date,
            'rng_state': self.dump_rng_state()
        }

    def _push_restore(self, file: Path = None) -> None:
        base_dir = file.parent
        for family in self.families:
            if hasattr(family, 'restore_file'):
                family.push_restore()
            else:
                family_dir = base_dir / f'Family_{uuid.uuid4()}'
                family_dir.mkdir(exist_ok=True)
                family.push_restore(family_dir / 'family.json')

        super()._push_restore(file)

    @classmethod
    def _restore(cls, attrs: Dict[str, Any], file: Path, **kwargs) -> Place:
        base_dir = file.parent

        families = [
            Family.restore(base_dir / str(family_restore_file))
            for family_restore_file in base_dir.rglob('Family_*/family.json')
        ]

        obj = cls(
            attrs['code'],
            attrs['name'],
            attrs['initial_date'],
            attrs['initial_population'],
            attrs['fertility_rate'],
            attrs['life_expectancy'],
            attrs['marry_age'],
            None,
            families
        )

        obj._prefix_id_counts = attrs['_prefix_id_counts']
        obj.last_updated_date = attrs['last_updated_date']
        return obj

    @staticmethod
    def match_adults(adults: Iterable[Family]) -> Iterable[Tuple[Family, Family]]:
        males: List[Family] = []
        females: List[Family] = []
        for adult in adults:
            if adult.gender == Gender.MALE:
                males.append(adult)
            else:
                females.append(adult)

        total_matches = min(len(males), len(females))
        return zip(males[:total_matches], females[:total_matches])

    @classmethod
    def generate(
            cls,
            n: int,
            initial_date: date = None,
            initial_population: int = None,
            fertility_rate: float = None,
            life_expectancy: float = None,
            seed: int = None,
            rng: np.random.RandomState = None
        ) -> Generator[Place]:
        from ..database import SubdistrictModel

        if rng is None:
            rng = np.random.RandomState(seed)

        initial_date = initial_date if initial_date is not None else GlobalContext.INITIAL_DATE

        initial_population = initial_population if initial_population is not None else GlobalContext.STORE_MARKET_POPULATION
        initial_populations = np.clip(
            rng.normal(
                initial_population,
                initial_population * 0.25,
                size=n
            ),
            50.0, np.Inf
        )

        fertility_rate = fertility_rate if fertility_rate is not None else GlobalContext.POPULATION_FERTILITY_RATE
        fertility_rates = np.clip(
            rng.normal(
                fertility_rate,
                fertility_rate * 0.1,
                size=n
            ),
            0.0, np.Inf
        )

        life_expectancy = life_expectancy if life_expectancy is not None else GlobalContext.POPULATION_LIFE_EXPECTANCY
        life_expectancies = np.clip(
            rng.normal(
                life_expectancy,
                life_expectancy * 0.05,
                size=n
            ),
            50.0, np.Inf
        )

        marry_age = life_expectancy if life_expectancy is not None else GlobalContext.POPULATION_LIFE_EXPECTANCY
        marry_ages = np.clip(
            rng.normal(
                marry_age,
                marry_age * 0.05,
                size=n
            ),
            50.0, np.Inf
        )

        if seed is None:
            seeds = [ int(num) for num in rng.random(n) * 1_000_000 ]
        else:
            seeds = [ None ] * n

        total_subdistricts = SubdistrictModel.select().count()
        subdistrict_ids = rng.choice(total_subdistricts, n, replace=False)
        for subdistrict_id, initial_population_, fertility_rate_, life_expectancy_, marry_age_, seed in zip(
                subdistrict_ids,
                initial_populations,
                fertility_rates,
                life_expectancies,
                marry_ages,
                seeds
            ):
            subdistrict: SubdistrictModel = (
                SubdistrictModel.select()
                .limit(1)
                .offset(int(subdistrict_id))
                .execute()
                .iterate()
            )
            yield cls(
                code=subdistrict.code,
                name=subdistrict.name,
                initial_date=initial_date,
                initial_population=initial_population_,
                fertility_rate=fertility_rate_,
                life_expectancy=life_expectancy_,
                marry_age=marry_age_,
                seed=seed,
                rng=rng
            )
