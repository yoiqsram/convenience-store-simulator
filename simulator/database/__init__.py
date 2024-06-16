from datetime import datetime
from peewee import Database, SqliteDatabase, IntegrityError

from ..context import GlobalContext
from ..enums import PaymentMethod
from .base import BaseModel, VersionModel, ModelMixin
from .employee import (
    EmployeeModel,
    EmployeeShiftScheduleModel,
    EmployeeAttendanceModel
)
from .order import (
    PaymentMethodModel,
    OrderModel,
    OrderSKUModel
)
from .sku import (
    CategoryModel,
    ProductModel,
    SKUModel
)
from .store import (
    CountryModel,
    ProvinceModel,
    CityModel,
    DistrictModel,
    SubdistrictModel,
    StoreModel
)

__all__ = [
    'MODELS',
    'BaseModel',
    'VersionModel',
    'ModelMixin',
    'EmployeeModel',
    'EmployeeShiftScheduleModel',
    'EmployeeAttendanceModel',
    'PaymentMethodModel',
    'OrderModel',
    'OrderSKUModel',
    'CategoryModel',
    'ProductModel',
    'SKUModel',
    'CountryModel',
    'ProvinceModel',
    'CityModel',
    'DistrictModel',
    'SubdistrictModel',
    'StoreModel',
    'Database',
    'SqliteDatabase',
    'create_database'
]

MODELS: list[BaseModel] = [
    EmployeeModel,
    EmployeeShiftScheduleModel,
    EmployeeAttendanceModel,
    PaymentMethodModel,
    OrderModel,
    OrderSKUModel,
    CategoryModel,
    ProductModel,
    SKUModel,
    CountryModel,
    ProvinceModel,
    CityModel,
    DistrictModel,
    SubdistrictModel,
    StoreModel
]


def create_database(created_datetime: datetime = None) -> Database:
    if created_datetime is None:
        created_datetime = datetime.now()

    database: Database = BaseModel._meta.database
    database.create_tables(MODELS)

    _populate_payment_method(created_datetime)
    _populate_items(created_datetime)
    _populate_locations(created_datetime)

    database.create_tables([VersionModel])
    if VersionModel.select().count() > 0:
        VersionModel.select().delete().execute()
    VersionModel.create(
        created_datetime=created_datetime,
        modified_datetime=created_datetime
    )
    return database


def _populate_payment_method(created_datetime: datetime) -> None:
    for payment_method in PaymentMethod:
        PaymentMethodModel.create(
            id=payment_method.value,
            name=payment_method.name,
            created_datetime=created_datetime
        )


def _populate_items(created_datetime: datetime) -> None:
    import numpy as np

    item_config = GlobalContext.get_config_item()
    for category in item_config['categories']:
        try:
            category_record = CategoryModel.create(
                name=category['name'],
                created_datetime=created_datetime
            )
        except IntegrityError:
            category_record = (
                CategoryModel.select()
                .where(CategoryModel.name == category['name'])
                .get()
            )

        for product in category['products']:
            try:
                product_record = ProductModel.create(
                    name=product['name'],
                    category=category_record.id,
                    created_datetime=created_datetime
                )
            except IntegrityError:
                product_record = (
                    ProductModel.select()
                    .where(ProductModel.name == product['name'])
                    .get()
                )

            for sku in product['skus']:
                try:
                    price = 100 * np.ceil(
                        sku['price']
                        * GlobalContext.CURRENCY_MULTIPLIER
                        / 100
                    )
                    SKUModel.create(
                        name=sku['name'],
                        brand=sku['brand'],
                        price=price,
                        cost=sku['cost'] * GlobalContext.CURRENCY_MULTIPLIER,
                        pax=sku['pax'],
                        product=product_record.id,
                        created_datetime=created_datetime,
                        modified_datetime=created_datetime
                    )
                except IntegrityError:
                    continue


def _populate_locations(created_datetime: datetime) -> None:
    location_config = GlobalContext.get_config_location()
    for country in location_config['countries']:
        try:
            country_record = CountryModel.create(
                code=country['id'],
                name=country['name'],
                created_datetime=created_datetime,
                modified_datetime=created_datetime
            )
        except IntegrityError:
            country_record = (
                CountryModel.select()
                .where(CountryModel.code == country['id'])
                .get()
            )

        for province in country['provinces']:
            try:
                province_record = ProvinceModel.create(
                    code=province['id'],
                    name=province['name'],
                    country=country_record.id,
                    created_datetime=created_datetime,
                    modified_datetime=created_datetime
                )
            except IntegrityError:
                province_record = (
                    ProvinceModel.select()
                    .where(ProvinceModel.code == province['id'])
                    .get()
                )

            for city in province['cities']:
                try:
                    city_record = CityModel.create(
                        code=city['id'],
                        name=city['name'],
                        province=province_record.id,
                        created_datetime=created_datetime,
                        modified_datetime=created_datetime
                    )
                except IntegrityError:
                    city_record = (
                        CityModel.select()
                        .where(CityModel.code == city['id'])
                        .get()
                    )

                for district in city['districts']:
                    try:
                        district_record = DistrictModel.create(
                            code=district['id'],
                            name=district['name'],
                            city=city_record.id,
                            created_datetime=created_datetime,
                            modified_datetime=created_datetime
                        )
                    except IntegrityError:
                        district_record = (
                            DistrictModel.select()
                            .where(DistrictModel.code == district['id'])
                            .get()
                        )

                    for subdistrict in district['subdistricts']:
                        try:
                            SubdistrictModel.create(
                                code=subdistrict['id'],
                                name=subdistrict['name'],
                                district=district_record.id,
                                created_datetime=created_datetime,
                                modified_datetime=created_datetime
                            )
                        except IntegrityError:
                            continue
