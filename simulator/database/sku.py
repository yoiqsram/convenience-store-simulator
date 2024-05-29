from .base import (
    AutoField, CharField, DateTimeField,
    FloatField, ForeignKeyField,
    BaseModel
)

__all__ = [
    'CategoryModel',
    'ProductModel',
    'SKUModel'
]


class CategoryModel(BaseModel):
    id = AutoField(primary_key=True)
    name = CharField(unique=True)

    class Meta:
        table_name = 'categories'


class ProductModel(BaseModel):
    id = AutoField(primary_key=True)
    category = ForeignKeyField(CategoryModel)
    name = CharField(unique=True)

    class Meta:
        table_name = 'products'


class SKUModel(BaseModel):
    id = AutoField(primary_key=True)
    product = ForeignKeyField(ProductModel)
    brand = CharField()
    name = CharField(unique=True)
    price = FloatField()
    cost = FloatField()

    modified_datetime = DateTimeField()

    class Meta:
        table_name = 'skus'
