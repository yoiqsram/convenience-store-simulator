from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any, List


def cast(_value: Any, _type: type) -> Any:
    if not isinstance(_type, type):
        raise TypeError(
            f"Cast type must be a type, not {type(_type).__name__}."
        )

    elif _value is None or isinstance(_value, _type):
        return _value

    elif _type is bool:
        if isinstance(_value, str):
            return _value.lower() == 'true'
        return bool(_value)

    elif _type in (date, datetime):
        if isinstance(_value, (int, float)):
            return _type.fromtimestamp(_value)
        elif isinstance(_value, str):
            return _type.fromisoformat(_value)

    elif _type is date \
            and isinstance(_value, datetime):
        return _value.date()

    elif _type is timedelta \
            and isinstance(_value, (int, float)):
        return timedelta(seconds=_value)

    elif isinstance(_value, (date, datetime)) and _type is float:
        return _value.timestamp()

    elif isinstance(_value, (date, datetime)) and _type is int:
        return int(_value.timestamp())

    elif issubclass(_type, Enum):
        return getattr(_type, _value)

    try:
        return _type(_value)
    except Exception:
        raise TypeError(
            f"Failed to cast value {repr(_value)} "
            f"to type '{_type.__name__}'."
        )


def get_dict_value(
        d: dict,
        name: str,
        type: type = None,
        default: Any = None,
        none_values: List[str] = None,
        none_error: bool = False
        ) -> Any:
    if default is not None \
            and type is not None \
            and not isinstance(default, type):
        raise ValueError(
            f"Argument 'default' should have been '{type.__class__.__name__}' "
            f"as type, not '{default.__class__.__name__}'.")

    env_var = d.get(name, default)

    if none_values is not None \
            and env_var in none_values:
        env_var = None

    if default is not None \
            and none_error \
            and env_var is None:
        raise ValueError(f"Key '{name}' is not exists.")
    elif env_var is None:
        return env_var

    if type is None:
        return env_var

    return cast(env_var, type)
