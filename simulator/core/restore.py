from __future__ import annotations

import orjson
import os
from collections import OrderedDict
from datetime import date, datetime, timedelta
from enum import Enum
from pathlib import Path, PosixPath
from typing import Any, Dict, Union

from .utils import cast

BUILTIN_TYPES = ( str, int, float, bool, list, dict )


class RestoreTypes(dict):
    def __init__(self, *args) -> None:
        super().__init__()
        for arg in args:
            self.add(arg)

    def add(self, _type: type):
        self[_type.__name__] = _type


class RestorableMixin:
    __additional_types__ = RestoreTypes()
    __instances__: Dict[str, RestorableMixin]

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        cls.__instances__ = {}

    @property
    def restore_attrs(self) -> Dict[str, Any]: raise NotImplementedError()

    def pull_restore(self, file: Path = None) -> None:
        if not hasattr(self, 'restore_file') \
                and file is None:
            raise ValueError

        file = file if file is not None else self.restore_file
        attrs = self.read_restore(file)
        self._pull_restore(attrs)

    def _pull_restore(self, attrs: Dict[str, Any]) -> None:
        for name, value in attrs.items():
            setattr(self, name, value)

    def push_restore(self, file: Path = None) -> None:
        if not hasattr(self, 'restore_file'):
            if file is None:
                raise ValueError
            self.restore_file = file

        self._push_restore(self.restore_file)

    def _push_restore(self, file: Path = None) -> None:
        attrs = [
            [ k, type(v).__name__, self._encode(v).decode() ]
            for k, v in self.restore_attrs.items()
        ]
        with open(file, 'wb') as f:
            data = [
                type(self).__name__,
                attrs
            ]
            f.write(orjson.dumps(data))

    def delete_restore(self) -> None:
        if not hasattr(self, 'restore_file'):
            raise LookupError

        os.remove(self.restore_file)
        del self.restore_file

    @classmethod
    def read_restore(cls, file: Path) -> Dict[str, Any]:
        with open(file, 'rb') as f:
            type_, attrs = orjson.loads(f.read())

        if type_ != cls.__name__:
            raise TypeError

        attrs = {
            name: cls._decode(value, type)
            for name, type, value in attrs
        }
        return attrs

    @classmethod
    def restore(cls, file: Path, **kwargs):
        try:
            return cls.__instances__[str(file.resolve())]
        except:
            pass

        attrs = cls.read_restore(file)
        obj = cls._restore(attrs, file=file, **kwargs)
        obj.restore_file = file
        cls.__instances__[str(obj.restore_file)] = obj
        return obj

    @classmethod
    def _restore(cls, attrs: Dict[str, Any], file: Path, **kwargs):
        obj = cls()
        obj.pull_restore(file)
        return obj

    @classmethod
    def _encode(cls, value: Any) -> bytes:
        try:
            return orjson.dumps(value)
        except TypeError:
            return orjson.dumps(cls._encode_fallback(value))

    @classmethod
    def _encode_fallback(cls, value: Any) -> Any:
        if value is None \
                or isinstance(value, ( str, int, float, bool )):
            pass

        elif isinstance(value, bytes):
            value = value.decode()

        elif isinstance(value, PosixPath):
            value = str(value)

        elif isinstance(value, ( date, datetime )):
            value = cast(value, str)

        elif isinstance(value, timedelta):
            value = value.total_seconds()

        elif isinstance(value, Enum):
            value = value.name

        elif isinstance(value, list):
            value = [ cls._encode_fallback(value_) for value_ in value ]

        elif isinstance(value, ( set, tuple )):
            value = list(value)

        elif isinstance(value, OrderedDict):
            value = [ [ k, v ] for k, v in value.items() ]

        else:
            raise TypeError(f"Unable to decode {repr(value)} with type of '{type(value).__name__}'.")

        return value

    @classmethod
    def _decode(cls, value: str, type_: Union[type, str]) -> Any:
        if isinstance(type_, str):
            type_ = cls.__additional_types__[type_]

        value = orjson.loads(value)        
        if value is None or type_ in BUILTIN_TYPES:
            return value

        return cast(value, type_)
