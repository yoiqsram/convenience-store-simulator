from .base import (
    BaseModel, AutoField, CharField,
    DateField, DateTimeField, ForeignKeyField
)
from .store import StoreModel


class EmployeeModel(BaseModel):
    id = AutoField(primary_key=True)
    name = CharField()
    gender = CharField()
    birth_date = DateField()
    store = ForeignKeyField(
        StoreModel,
        backref='employees',
        on_delete='CASCADE'
    )

    modified_datetime = DateTimeField()

    class Meta:
        table_name = 'employees'


class EmployeeShiftScheduleModel(BaseModel):
    id = AutoField(primary_key=True)
    employee = ForeignKeyField(
        EmployeeModel,
        on_delete='CASCADE'
    )
    shift_start_datetime = DateTimeField()
    shift_end_datetime = DateTimeField()

    class Meta:
        table_name = 'employee_shift_schedules'


class EmployeeAttendanceModel(BaseModel):
    id = AutoField(primary_key=True)
    employee = ForeignKeyField(
        EmployeeModel,
        on_delete='CASCADE'
    )
    status = CharField()

    class Meta:
        table_name = 'employee_attendances'
