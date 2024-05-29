from .base import (
    BaseModel, AutoField, CharField,
    DateField, DateTimeField, ForeignKeyField
)
from .store import SubdistrictModel


class EmployeeModel(BaseModel):
    id = AutoField(primary_key=True)
    person_id = CharField(unique=True)
    name = CharField()
    gender = CharField()
    birth_date = DateField()
    birth_place_code = ForeignKeyField(
        SubdistrictModel,
        field=SubdistrictModel.code
    )

    modified_datetime = DateTimeField()

    class Meta:
        table_name = 'employees'


class EmployeeShiftScheduleModel(BaseModel):
    id = AutoField(primary_key=True)
    employee = ForeignKeyField(EmployeeModel)
    shift_start_datetime = DateTimeField()
    shift_end_datetime = DateTimeField()

    class Meta:
        table_name = 'employee_shift_schedules'


class EmployeeAttendanceModel(BaseModel):
    id = AutoField(primary_key=True)
    employee = ForeignKeyField(EmployeeModel)
    status = CharField()

    class Meta:
        table_name = 'employee_attendances'
