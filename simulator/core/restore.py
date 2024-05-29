from __future__ import annotations

import orjson
import os
from collections import OrderedDict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path, PosixPath
from typing import Any, Dict, Union

from .utils import cast

BUILTIN_TYPES = ( str, int, float, bool, list, dict )


class RestorableMixin:
    __restore_types__: Dict[str, type] = {}
    __restore_instances__: Dict[str, RestorableMixin]

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        cls.__restore_instances__ = {}

    @property
    def restore_file(self) -> str:
        return self._restore_file

    @property
    def restore_attrs(self) -> Dict[str, Any]: raise NotImplementedError()

    def pull_restore(self, file: Path = None) -> None:
        if not hasattr(self, '_restore_file') \
                and file is None:
            raise ValueError

        file = file if file is not None else self._restore_file
        attrs = self.read_restore(file)
        self._pull_restore(attrs)

    def _pull_restore(self, attrs: Dict[str, Any]) -> None:
        for name, value in attrs.items():
            setattr(self, name, value)

    def push_restore(self, file: Path = None) -> None:
        if not hasattr(self, '_restore_file'):
            if file is None:
                raise ValueError

            self._restore_file = file

        attrs = [
            {
                'name': k,
                'value': self._encode(v).decode(),
                'type': type(v).__name__
            }
            for k, v in self.restore_attrs.items()
        ]
        with open(file, 'wb') as f:
            data = {
                'type': type(self).__name__,
                'attrs': attrs,
                'modified_datetime': self._restore_datetime()
            }
            f.write(self._encode(data))

    def delete_restore(self) -> None:
        if not hasattr(self, '_restore_file'):
            raise LookupError

        os.remove(self._restore_file)
        del self._restore_file

    def _restore_datetime(self) -> datetime:
        return datetime.now()

    @classmethod
    def read_restore(cls, file: Path) -> Dict[str, Any]:
        with open(file, 'rb') as f:
            data = orjson.loads(f.read())

        if data['type'] != cls.__name__:
            raise TypeError

        attrs = {
            attr['name']: cls._decode(attr['value'], attr['type'])
            for attr in data['attrs']
        }
        return attrs

    @classmethod
    def restore(cls, file: Path, **kwargs):
        attrs = cls.read_restore(file)
        obj = cls._restore(attrs, file, **kwargs)
        obj._restore_file = file
        cls.__restore_instances__[str(obj._restore_file)] = obj
        return obj

    @classmethod
    def _restore(cls, attrs: Dict[str, Any], file: Path, **kwargs) -> object:
        obj = cls()
        obj.pull_restore(file)
        return obj

    @classmethod
    def _encode(cls, value: Any) -> bytes:
        try:
            return orjson.dumps(value)

        except TypeError:
            if isinstance(value, [ set, tuple ]):
                value = list(value)

            elif isinstance(value, OrderedDict):
                value = [ [ k, v ] for k, v in value.items() ]

            elif isinstance(value, timedelta):
                value = value.total_seconds()

            elif isinstance(value, Enum):
                value = value.name

            elif isinstance(value, PosixPath):
                value = str(value)

            else:
                raise TypeError(f"Unable to decode {repr(value)} with type of '{type(value).__name__}'.")

        return orjson.dumps(value)

    @classmethod
    def _decode(cls, value: str, type_: Union[type, str]) -> Any:
        if isinstance(type_, str):
            type_ = cls.__restore_types__[type_]

        value = orjson.loads(value)        
        if value is None or type_ in BUILTIN_TYPES:
            return value

        return cast(value, type_)
