import os
import yaml
from datetime import date
from pathlib import Path
from typing import Any, List, Union

from .utils import get_dict_value

DAYS_IN_YEAR = 365.2425


def get_environment_variable(
        name: str,
        type: type = str,
        default: Any = None,
        none_error: bool = False
    ) -> Any:
    return get_dict_value(
        os.environ,
        name=name,
        type=type,
        default=default,
        none_values=[ '' ],
        none_error=none_error
    )


class GlobalContext:
    BASE_DIR: Path = get_environment_variable('SIMULATOR_BASE_DIR', Path, Path(__file__).resolve().parents[1])
    CONFIG_DIR: Path = get_environment_variable('SIMULATOR_CONFIG_DIR', Path, BASE_DIR / 'config')
    DATA_DIR: Path = get_environment_variable('SIMULATOR_DATA_DIR', Path, BASE_DIR / 'data')

    SQLITE_DB_PATH: Path = get_environment_variable('SQLITE_DB_PATH', Path, DATA_DIR / 'stores.db')

    POSTGRES_DB_NAME: str = get_environment_variable('POSTGRES_DB_NAME', default='store')
    POSTGRES_DB_USERNAME: Union[str, None] = get_environment_variable('POSTGRES_DB_USERNAME')
    POSTGRES_DB_PASSWORD: Union[str, None] = get_environment_variable('POSTGRES_DB_PASSWORD')
    POSTGRES_DB_HOST: Union[str, None] = get_environment_variable('POSTGRES_DB_HOST')
    POSTGRES_DB_PORT: Union[str, None] = get_environment_variable('POSTGRES_DB_PORT')

    CHECKPOINT_SESSION_PATH: Path = get_environment_variable('SIMULATOR_CHECKPOINT_SESSION_PATH', Path, DATA_DIR / 'checkpoint.pkl')
    CHECKPOINT_INTERVAL: int = get_environment_variable('SIMULATOR_CHECKPOINT_INTERVAL', int, 86400)

    INITIAL_DATE: date = get_environment_variable('SIMULATOR_INITIAL_DATE', date, date.today())
    SIMULATOR_SPEED: float = get_environment_variable('SIMULATOR_SPEED', float, 1.0)
    SIMULATOR_INTERVAL: float = get_environment_variable('SIMULATOR_INTERVAL', float, 1.0)
    SIMULATOR_INTERVAL_MIN: float = get_environment_variable('SIMULATOR_INTERVAL_MIN', float)
    SIMULATOR_INTERVAL_MAX: float = get_environment_variable('SIMULATOR_INTERVAL_MAX', float)
    CURRENCY_MULTIPLIER: float = get_environment_variable('SIMULATOR_CURRENCY_MULTIPLIER', float, 1.0)

    POPULATION_FAMILY_SIZE: float = get_environment_variable('SIMULATOR_POPULATION_FAMILY_SIZE', float, 3.0)
    POPULATION_FERTILITY_RATE: float = get_environment_variable('SIMULATOR_POPULATION_FERTILITY_RATE', float, 0.1)
    POPULATION_LIFE_EXPECTANCY: float = get_environment_variable('SIMULATOR_POPULATION_LIFE_EXPECTANCY', float, 71.0)
    POPULATION_MARRY_AGE: float = get_environment_variable('SIMULATOR_POPULATION_MARRY_AGE', float, 22.5)
    POPULATION_PURCHASING_POWER: float = get_environment_variable('SIMULATOR_POPULATION_PURCHASING_POWER', float, 3400.0)
    POPULATION_SPENDING_RATE: float = get_environment_variable('SIMULATOR_POPULATION_SPENDING_RATE', float, 0.4)
    POPULATION_FAMILY_MARRIED_PROB: float = get_environment_variable('SIMULATOR_POPULATION_FAMILY_MARRIED', float, 0.75)
    POPULATION_FAMILY_MARRIED_AND_ELDER_PROB: float = get_environment_variable('SIMULATOR_POPULATION_FAMILY_SINGLE_AND_MALE', float, 0.1)
    POPULATION_FAMILY_SINGLE_AND_MALE_PROB: float = get_environment_variable('SIMULATOR_POPULATION_FAMILY_SINGLE_AND_MALE', float, 0.7)
    POPULATION_FAMILY_SINGLE_PARENT_AND_MALE_PROB: float = get_environment_variable('SIMULATOR_POPULATION_FAMILY_SINGLE_AND_MALE', float, 0.4)

    INITIAL_STORES: int = get_environment_variable('SIMULATOR_INITIAL_STORES', int, 1)
    INITIAL_STORES_RANGE_DAYS: int = get_environment_variable('SIMULATOR_INITIAL_STORES_RANGE_DAYS', int, 0)
    STORE_MARKET_POPULATION: int = get_environment_variable('SIMULATOR_STORE_MARKET_POPULATION', int, 10_000)
    STORE_GROWTH_RATE: int = get_environment_variable('SIMULATOR_STORE_GROWTH_RATE', float, 0.5)

    STORE_MAX_CASHIERS: int = get_environment_variable('SIMULATOR_STORE_MAX_CASHIERS', int, 2)
    STORE_INITIAL_EMPLOYEES: int = get_environment_variable('SIMULATOR_STORE_INITIAL_EMPLOYEES', int, 2)
    STORE_OPEN_HOUR: float = get_environment_variable('SIMULATOR_STORE_OPEN_HOUR', float, 7.0)
    STORE_CLOSE_HOUR: float = get_environment_variable('SIMULATOR_STORE_OPEN_HOUR', float, 22.0)
    STORE_PEAK_HOURS: List[float] = [ 12.5, 19.0 ]

    CONFIG_ITEM_PATH: Path = get_environment_variable('SIMULATOR_CONFIG_ITEM_PATH', Path, CONFIG_DIR / 'items.yaml')
    CONFIG_ITEM = None

    CONFIG_LOCATION_PATH: Path = get_environment_variable('SIMULATOR_CONFIG_LOCATION_PATH', Path, CONFIG_DIR / 'locations.yaml')
    CONFIG_LOCATION = None

    DEBUG_DATABASE: bool = get_environment_variable('DEBUG_DATABASE', bool, False)
    DEBUG_SIMULATOR: bool = get_environment_variable('DEBUG_SIMULATOR', bool, False)
    DEBUG_STORE: bool = get_environment_variable('DEBUG_STORE', bool, False)
    DEBUG_ORDER: bool = get_environment_variable('DEBUG_ORDER', bool, False)

    @classmethod
    def get(
            cls,
            name: str,
            default: Any = None,
            type: type = None,
            none_error: bool = False
        ) -> Any:
        return get_dict_value(
            cls.__dict__,
            name=name.upper(),
            default=default,
            type=type,
            none_error=none_error
        )

    @classmethod
    def get_config_item(cls, config_path: Path = None) -> dict:
        config_path = config_path if config_path is not None else cls.CONFIG_ITEM_PATH

        if cls.CONFIG_ITEM is None:
            with open(config_path) as f:
                cls.CONFIG_ITEM = yaml.safe_load(f)

        return cls.CONFIG_ITEM

    @classmethod
    def get_config_location(cls, config_path: Path = None) -> dict:
        config_path = config_path if config_path is not None else cls.CONFIG_LOCATION_PATH

        if cls.CONFIG_LOCATION is None:
            with open(config_path) as f:
                cls.CONFIG_LOCATION = yaml.safe_load(f)

        return cls.CONFIG_LOCATION
