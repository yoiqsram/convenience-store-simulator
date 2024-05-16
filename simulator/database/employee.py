from .base import *

__all__ = [ 'EmployeeModel' ]


class EmployeeModel(BaseModel):
    id = AutoField(primary_key=True)
    person_id = CharField(unique=True)
    name = CharField()
    gender = CharField()
    birth_date = DateField()
    birth_place = CharField()

    created_datetime = column_created_datetime()
    modified_datetime = column_modified_datetime()
