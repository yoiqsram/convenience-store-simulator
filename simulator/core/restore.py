from __future__ import annotations

import orjson
import os
import shutil
from collections import OrderedDict
from datetime import date, datetime, timedelta
from enum import Enum
from pathlib import Path, PosixPath
from typing import Any, Dict, Union

from .utils import cast

BUILTIN_TYPES = {
    t.__name__: t
    for t in (str, int, float, bool, list, dict)
}
EXTENDED_TYPES = {
    t.__name__: t
    for t in (
        set, tuple,
        Path, PosixPath, OrderedDict,
        date, datetime, timedelta
        )
}


class RestoreTypes(dict):
    def __init__(self, *args) -> None:
        super().__init__()
        for arg in args:
            self.add(arg)

    def add(self, _type: type):
        self[_type.__name__] = _type


class RestorableMixin:
    __additional_types__ = RestoreTypes()

    @property
    def restore_attrs(self) -> Dict[str, Any]: raise NotImplementedError()

    def pull_restore(
            self,
            file: Path = None,
            tmp: bool = False,
            **kwargs
            ) -> None:
        if not hasattr(self, 'restore_file') \
                and file is None:
            raise ValueError

        file = file if file is not None else self.restore_file
        if tmp:
            file = file.parent / (file.name + '.tmp')
        attrs = self.read_restore(file)
        self._pull_restore(attrs, file=file, **kwargs)

    def _pull_restore(
            self,
            attrs: Dict[str, Any],
            file: Path,
            **kwargs
            ) -> None:
        for name, value in attrs.items():
            setattr(self, name, value)

    def push_restore(
            self,
            file: Path = None,
            tmp: bool = False,
            **kwargs
            ) -> None:
        if not hasattr(self, 'restore_file'):
            if file is None:
                raise ValueError

            self.restore_file = file

        file = self.restore_file
        temp_file = file.parent / (file.name + '.tmp')

        if tmp:
            self._push_restore(temp_file, tmp=tmp, **kwargs)
            if not file.exists():
                shutil.copy(temp_file, file)
        else:
            self._push_restore(file, tmp=tmp, **kwargs)
            if temp_file.exists():
                shutil.copy(file, temp_file)

    def _push_restore(
            self,
            file: Path = None,
            tmp: bool = False,
            **kwargs
            ) -> None:
        attrs = [
            [k, type(v).__name__, self._encode(v).decode()]
            for k, v in self.restore_attrs.items()
        ]
        with open(file, 'wb') as f:
            data = [
                type(self).__name__,
                attrs
            ]
            f.write(orjson.dumps(data))

    def delete_restore(self, tmp: bool = False) -> None:
        if not hasattr(self, 'restore_file'):
            raise LookupError

        file = self.restore_file
        if tmp:
            file = file.parent / (file.name + '.tmp')
        else:
            del self.restore_file

        os.remove(file)

    @classmethod
    def read_restore(
            cls,
            file: Path,
            tmp: Path
            ) -> Dict[str, Any]:
        with open(file, 'rb') as f:
            type_, attrs = orjson.loads(f.read())

        if type_ != cls.__name__:
            raise TypeError

        attrs = {
            name: cls._decode(value, type_)
            for name, type_, value in attrs
        }
        return attrs

    @classmethod
    def restore(cls, file: Path, tmp: bool = False, **kwargs):
        file_ = file
        if tmp:
            file_ = file.parent / (file.name + '.tmp')

        attrs = cls.read_restore(file_, tmp=tmp)
        obj = cls._restore(attrs, file=file, tmp=tmp, **kwargs)
        obj.restore_file = file
        return obj

    @classmethod
    def _restore(
            cls,
            attrs: Dict[str, Any],
            file: Path,
            tmp: bool,
            **kwargs
            ):
        obj = cls()
        obj.pull_restore(file, tmp=tmp)
        return obj

    @classmethod
    def _encode(cls, value: Any) -> bytes:
        try:
            if value is None \
                    or isinstance(
                        value,
                        tuple(BUILTIN_TYPES.values())
                    ):
                return orjson.dumps(value)

        except TypeError:
            pass

        return orjson.dumps(cls._encode_fallback(value))

    @classmethod
    def _encode_fallback(cls, value: Any) -> Any:
        if value is None \
                or isinstance(value, (str, int, float, bool)):
            pass

        elif isinstance(value, bytes):
            value = value.decode()

        elif isinstance(value, PosixPath):
            value = str(value)

        elif isinstance(value, (date, datetime)):
            value = cast(value, str)

        elif isinstance(value, timedelta):
            value = value.total_seconds()

        elif isinstance(value, Enum):
            value = value.name

        elif isinstance(value, list):
            value = [cls._encode_fallback(value_) for value_ in value]

        elif isinstance(value, (set, tuple)):
            value = list(value)

        elif isinstance(value, OrderedDict):
            value = [[k, v] for k, v in value.items()]

        else:
            raise TypeError(
                f"Unable to decode {repr(value)} "
                f"with type of '{type(value).__name__}'."
            )

        return value

    @classmethod
    def _decode(cls, value: str, type_: Union[type, str]) -> Any:
        value = orjson.loads(value)
        if isinstance(type_, str):
            if value is None:
                return None
            elif type_ in BUILTIN_TYPES:
                type_ = BUILTIN_TYPES[type_]
            elif type_ in EXTENDED_TYPES:
                type_ = EXTENDED_TYPES[type_]
            else:
                type_ = cls.__additional_types__[type_]

        return cast(value, type_)
