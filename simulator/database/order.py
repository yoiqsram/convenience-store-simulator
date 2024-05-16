from .base import *
from .item import SKUModel
from .employee import EmployeeModel

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
    cashier_employee_id = ForeignKeyField(EmployeeModel)
    customer_gender = CharField()
    customer_age = CharField()
    payment_method = ForeignKeyField(PaymentMethodModel, null=True)

    paid_datetime = DateTimeField(null=True)

    class Meta:
        table_name = 'orders'


class OrderSKUModel(BaseModel):
    id = BigAutoField(primary_key=True)
    order = ForeignKeyField(OrderModel)
    sku = ForeignKeyField(SKUModel)
    quantity = IntegerField()

    class Meta:
        table_name = 'order_skus'
