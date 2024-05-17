import os
import yaml
from datetime import date, datetime
from pathlib import Path
from typing import Any, List, Union

_STR_NONE = Union[str, None]


def get_dict_value(
        d: dict,
        name: str,
        type: type = None,
        default: Any = None,
        none_error: bool = False
    ) -> Any:
    if default is not None \
            and type is not None \
            and not isinstance(default, type):
        raise ValueError(f"Argument 'default' should have been '{type.__class__.__name__}' as type, not '{default.__class__.__name__}'.")

    env_var = d.get(name, default)
    cast = type
    if type is None:
        pass
    elif isinstance(env_var, type):
        return env_var
    elif isinstance(type, date):
        cast = date.fromisoformat
    elif isinstance(type, datetime):
        cast = date.fromisoformat

    if default is not None \
            and none_error \
            and env_var is None:
        raise ValueError(f"Environment variable '{name}' is not exists.")
    elif env_var is None:
        return env_var

    if type is None:
        return env_var
    return cast(env_var)


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
        none_error=none_error
    )


class GlobalContext:
    BASE_DIR: Path = get_environment_variable('SIMULATOR_BASE_DIR', Path, Path(__file__).resolve().parents[1])
    CONFIG_DIR: Path = get_environment_variable('SIMULATOR_CONFIG_DIR', Path, BASE_DIR / 'config')

    SQLITE_DB_PATH: Path = get_environment_variable('SQLITE_DB_PATH', Path, BASE_DIR / 'data' / 'stores.db')

    POSTGRES_DB_NAME: str = get_environment_variable('POSTGRES_DB_NAME', default='store')
    POSTGRES_DB_USERNAME: _STR_NONE = get_environment_variable('POSTGRES_DB_USERNAME')
    POSTGRES_DB_PASSWORD: _STR_NONE = get_environment_variable('POSTGRES_DB_PASSWORD')
    POSTGRES_DB_HOST: _STR_NONE = get_environment_variable('POSTGRES_DB_HOST')
    POSTGRES_DB_PORT: _STR_NONE = get_environment_variable('POSTGRES_DB_PORT')

    INITIAL_DATE: date = get_environment_variable('SIMULATOR_INITIAL_DATE', date, date.today())
    CLOCK_SPEED: float = get_environment_variable('SIMULATOR_SPEED', float, 1.0)
    CLOCK_INTERVAL: float = get_environment_variable('SIMULATOR_INTERVAL', float, 1.0)
    CURRENCY_MULTIPLIER: float = get_environment_variable('SIMULATOR_CURRENCY_MULTIPLIER', float, 1.0)
    MAX_THREADS: int = get_environment_variable('SIMULATOR_MAX_THREADS', int, 1)

    POPULATION_FAMILY_SIZE: float = get_environment_variable('SIMULATOR_POPULATION_FAMILY_SIZE', float, 3.0)
    POPULATION_FERTILITY_RATE: float = get_environment_variable('SIMULATOR_POPULATION_FERTILITY_RATE', float, 0.1)
    POPULATION_LIFE_EXPECTANCY: float = get_environment_variable('SIMULATOR_POPULATION_LIFE_EXPECTANCY', float, 71.0)
    POPULATION_MARRY_AGE: float = get_environment_variable('SIMULATOR_POPULATION_MARRY_AGE', float, 22.5)
    POPULATION_PURCHASING_POWER: float = get_environment_variable('SIMULATOR_POPULATION_PURCHASING_POWER', float, 3400.0)
    POPULATION_SPENDING_RATE: float = get_environment_variable('SIMULATOR_POPULATION_SPENDING_RATE', float, 0.4)

    INITIAL_STORES: int = get_environment_variable('SIMULATOR_INITIAL_STORES', int, 1)
    STORE_POPULATION: int = get_environment_variable('SIMULATOR_STORE_POPULATION', int, 10_000)
    STORE_GROWTH_RATE: int = get_environment_variable('SIMULATOR_STORE_GROWTH_RATE', float, 0.5)

    STORE_MAX_CASHIERS: int = get_environment_variable('SIMULATOR_STORE_MAX_CASHIERS', int, 2)
    STORE_INITIAL_WORKERS: int = get_environment_variable('SIMULATOR_STORE_INITIAL_WORKERS', int, 2)
    STORE_OPEN_HOUR: float = get_environment_variable('SIMULATOR_STORE_OPEN_HOUR', float, 7.0)
    STORE_CLOSE_HOUR: float = get_environment_variable('SIMULATOR_STORE_OPEN_HOUR', float, 22.0)
    STORE_PEAK_HOURS: List[float] = [ 12.5, 19.0 ]

    CONFIG_ITEM_PATH: Path = get_environment_variable('SIMULATOR_CONFIG_ITEM_PATH', Path, CONFIG_DIR / 'items.yaml')
    CONFIG_ITEM = None

    CONFIG_LOCATION_PATH: Path = get_environment_variable('SIMULATOR_CONFIG_LOCATION_PATH', Path, CONFIG_DIR / 'locations.yaml')
    CONFIG_LOCATION = None

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
