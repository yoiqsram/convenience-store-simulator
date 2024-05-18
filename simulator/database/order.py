from .base import *
from .employee import EmployeeModel
from .sku import SKUModel
from .store import StoreModel

__all__ = [
    'PaymentMethodModel',
    'OrderModel',
    'OrderSKUModel'
]


class PaymentMethodModel(BaseModel):
    id = AutoField(primary_key=True)
    name = CharField(unique=True)

    class Meta:
        table_name = 'payment_methods'


class OrderModel(BaseModel):
    id = BigAutoField(primary_key=True)
    store = ForeignKeyField(StoreModel)
    cashier_employee = ForeignKeyField(EmployeeModel)
    payment_method = ForeignKeyField(PaymentMethodModel, null=True)
    buyer_gender = CharField(null=True)
    buyer_age_group = CharField(null=True)

    complete_datetime = DateTimeField(null=True)

    class Meta:
        table_name = 'orders'


class OrderSKUModel(BaseModel):
    id = BigAutoField(primary_key=True)
    order = ForeignKeyField(
        OrderModel,
        backref='order_skus',
        on_delete='CASCADE'
    )
    sku = ForeignKeyField(SKUModel)
    price = FloatField()
    quantity = IntegerField()

    class Meta:
        table_name = 'order_skus'
