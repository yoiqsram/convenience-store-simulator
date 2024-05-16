from .base import *

__all__ = [
    'CategoryModel',
    'ProductModel',
    'SKUModel'
]


class CategoryModel(BaseModel):
    id = AutoField(primary_key=True)
    name = CharField(unique=True)
    created_datetime = column_created_datetime()

    class Meta:
        table_name = 'categories'


class ProductModel(BaseModel):
    id = AutoField(primary_key=True)
    category = ForeignKeyField(CategoryModel)
    name = CharField(unique=True)
    created_datetime = column_created_datetime()

    class Meta:
        table_name = 'products'


class SKUModel(BaseModel):
    id = AutoField(primary_key=True)
    product = ForeignKeyField(ProductModel)
    brand = CharField()
    name = CharField(unique=True)
    price = FloatField()
    cost = FloatField()

    created_datetime = column_created_datetime()
    modified_datetime = column_modified_datetime()

    class Meta:
        table_name = 'skus'
