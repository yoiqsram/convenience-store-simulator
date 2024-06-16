from .base import (
    AutoField, CharField, DateTimeField,
    FloatField, ForeignKeyField, IntegerField,
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
    category = ForeignKeyField(
        CategoryModel,
        backref='products',
        on_delete='CASCADE'
    )
    name = CharField(unique=True)

    class Meta:
        table_name = 'products'


class SKUModel(BaseModel):
    id = AutoField(primary_key=True)
    product = ForeignKeyField(
        ProductModel,
        backref='skus',
        on_delete='CASCADE'
    )
    brand = CharField()
    name = CharField(unique=True)
    pax = IntegerField()
    price = FloatField()
    cost = FloatField()

    modified_datetime = DateTimeField()

    class Meta:
        table_name = 'skus'
