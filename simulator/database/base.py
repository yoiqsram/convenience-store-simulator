from datetime import datetime
from peewee import (
    AutoField, BigAutoField, BigIntegerField,
    CharField, DateField, DateTimeField,
    FloatField, ForeignKeyField, IntegerField,
    Model, PostgresqlDatabase, SQL, SqliteDatabase
)

from ..context import GlobalContext

# import logging
# peewee_logger = logging.getLogger('peewee')
# peewee_logger.addHandler(logging.StreamHandler())
# peewee_logger.setLevel(logging.DEBUG)

class BaseModel(Model):
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


def column_created_datetime():
    return DateTimeField(default=datetime.now)


def column_modified_datetime():
    return DateTimeField(default=datetime.now)
