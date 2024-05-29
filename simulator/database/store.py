from .base import (
    AutoField, CharField, DateTimeField,
    ForeignKeyField, BaseModel
)

__all__ = [
    'CountryModel',
    'ProvinceModel',
    'CityModel',
    'DistrictModel',
    'SubdistrictModel',
    'StoreModel'
]


class CountryModel(BaseModel):
    id = AutoField(primary_key=True)
    code = CharField(unique=True)
    name = CharField()

    modified_datetime = DateTimeField()

    class Meta:
        table_name = 'countries'


class ProvinceModel(BaseModel):
    id = AutoField(primary_key=True)
    country = ForeignKeyField(
        CountryModel,
        backref='provinces',
        on_delete='CASCADE'
    )
    code = CharField(unique=True)
    name = CharField()

    modified_datetime = DateTimeField()

    class Meta:
        table_name = 'provinces'


class CityModel(BaseModel):
    id = AutoField(primary_key=True)
    province = ForeignKeyField(
        ProvinceModel,
        backref='cities',
        on_delete='CASCADE'
    )
    code = CharField(unique=True)
    name = CharField()

    modified_datetime = DateTimeField()

    class Meta:
        table_name = 'cities'


class DistrictModel(BaseModel):
    id = AutoField(primary_key=True)
    city = ForeignKeyField(
        CityModel,
        backref='districts',
        on_delete='CASCADE'
    )
    code = CharField(unique=True)
    name = CharField()

    modified_datetime = DateTimeField()

    class Meta:
        table_name = 'districts'


class SubdistrictModel(BaseModel):
    id = AutoField(primary_key=True)
    district = ForeignKeyField(
        DistrictModel,
        backref='subdistricts',
        on_delete='CASCADE'
    )
    code = CharField(unique=True)
    name = CharField()

    modified_datetime = DateTimeField()

    class Meta:
        table_name = 'subdistricts'


class StoreModel(BaseModel):
    id = AutoField(primary_key=True)
    subdistrict = ForeignKeyField(
        SubdistrictModel,
        backref='store',
        on_delete='CASCADE',
        unique=True
    )

    modified_datetime = DateTimeField()

    class Meta:
        table_name = 'stores'
