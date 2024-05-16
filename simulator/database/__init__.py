from datetime import datetime
from peewee import Database, IntegrityError

from ..context import GlobalContext
from .base import BaseModel
from .employee import *
from .item import *
from .order import *
from .store import *


def create_database():
    database: Database = BaseModel._meta.database
    database.create_tables([
        EmployeeModel,
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
    ])

    created_datetime = datetime(
        GlobalContext.INITIAL_DATE.year,
        GlobalContext.INITIAL_DATE.month,
        GlobalContext.INITIAL_DATE.day
    )
    populate_items(created_datetime)
    populate_locations(created_datetime)


def populate_items(created_datetime: datetime):
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
                    SKUModel.create(
                        name=sku['name'],
                        brand=sku['brand'],
                        price=sku['price'],
                        cost=sku['cost'],
                        product=product_record.id,
                        created_datetime=created_datetime,
                        modified_datetime=created_datetime
                    )
                except IntegrityError:
                    continue


def populate_locations(created_datetime: datetime):
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
