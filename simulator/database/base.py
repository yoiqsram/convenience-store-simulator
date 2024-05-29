from __future__ import annotations

from datetime import datetime
from peewee import (
    AutoField, BigAutoField, BigIntegerField,
    CharField, DateField, DateTimeField, DoesNotExist,
    FloatField, ForeignKeyField, IntegerField,
    Model, PostgresqlDatabase, SQL, SqliteDatabase
)
from typing import Any, Dict, Type, Union

from ..context import GlobalContext


class BaseModel(Model):
    created_datetime = DateTimeField()

    class Meta:
        if GlobalContext.POSTGRES_DB_HOST is not None:
            database = PostgresqlDatabase(
                database=GlobalContext.POSTGRES_DB_NAME,
                user=GlobalContext.POSTGRES_DB_USERNAME,
                password=GlobalContext.POSTGRES_DB_PASSWORD,
                host=GlobalContext.POSTGRES_DB_HOST,
                port=GlobalContext.POSTGRES_DB_PORT
            )
        else:
            GlobalContext.SQLITE_DB_PATH.parent.mkdir(exist_ok=True)
            database = SqliteDatabase(GlobalContext.SQLITE_DB_PATH)


class VersionModel(BaseModel):
    modified_datetime = DateTimeField()

    class Meta:
        table_name = 'version'


class ModelMixin:
    __model__: Type[BaseModel]

    def __init_subclass__(cls, model: Type[BaseModel], **kwargs) -> None:
        cls.__model__ = model

    def __init_model__(
            self,
            unique_identifiers: Dict[str, Any],
            **kwargs
        ) -> None:
        self._unique_identifiers = unique_identifiers

        self._record: BaseModel
        try:
            query = self.__model__.select()
            for name, value in self._unique_identifiers.items():
                query = query.where(getattr(self.__model__, name) == value)

            self._record = query.get()

            for name, value in kwargs.items():
                setattr(self._record, name, value)

        except:
            self._record = self.__model__(
                **self._unique_identifiers,
                **kwargs
            )

    @property
    def record_id(self) -> int:
        return self._record.id

    @property
    def record(self) -> BaseModel:
        return self._record

    @property
    def created_datetime(self) -> Union[datetime, None]:
        return self._record.created_datetime

    @created_datetime.setter
    def created_datetime(self, value: datetime) -> None:
        self._record.created_datetime = value
        if hasattr(self._record, 'modified_datetime'):
            setattr(self._record, 'modified_datetime', value)

        if self._record.id is None:
            self._record.save(force_insert=True)
        else:
            self._record.save()
