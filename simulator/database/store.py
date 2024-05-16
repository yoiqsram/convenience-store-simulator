from .base import *

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

    created_datetime = column_created_datetime()
    modified_datetime = column_modified_datetime()

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

    created_datetime = column_created_datetime()
    modified_datetime = column_modified_datetime()

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

    created_datetime = column_created_datetime()
    modified_datetime = column_modified_datetime()

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

    created_datetime = column_created_datetime()
    modified_datetime = column_modified_datetime()

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

    created_datetime = column_created_datetime()
    modified_datetime = column_modified_datetime()

    class Meta:
        table_name = 'subdistricts'


class StoreModel(BaseModel):
    id = AutoField(primary_key=True)
    subdistrict = ForeignKeyField(
        SubdistrictModel,
        backref='stores',
        on_delete='CASCADE',
        unique=True
    )

    created_datetime = column_created_datetime()

    class Meta:
        table_name = 'stores'
