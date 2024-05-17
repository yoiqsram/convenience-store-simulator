from datetime import datetime
from peewee import (
    AutoField, BigAutoField, BigIntegerField,
    CharField, DateField, DateTimeField, DoesNotExist,
    FloatField, ForeignKeyField, IntegerField,
    Model, PostgresqlDatabase, SQL, SqliteDatabase
)
from typing import Any, Dict, Type, Union

from ..context import GlobalContext

# import logging
# peewee_logger = logging.getLogger('peewee')
# peewee_logger.addHandler(logging.StreamHandler())
# peewee_logger.setLevel(logging.DEBUG)


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


class ModelMixin:
    __model__: Type[BaseModel]

    def init_model(
            self,
            unique_identifiers: Dict[str, Any],
            **kwargs
        ) -> None:
        self._unique_identifiers = unique_identifiers

        self._record: BaseModel
        try:
            query = self.__class__.__model__.select()
            for name, value in self._unique_identifiers.items():
                query = query.where(getattr(self.__class__.__model__, name) == value)

            self._record = query.get()

            for name, value in kwargs.items():
                if hasattr(self._record, name) \
                        and getattr(self._record, name) != value:
                    setattr(self._record, name, value)

        except DoesNotExist:
            self._record = self.__class__.__model__(**kwargs)

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
