from peewee import (
    AutoField, CharField,
    FloatField, ForeignKeyField, IntegerField,
    Model, SqliteDatabase, SQL
)

from ..context import GlobalContext

db_path = GlobalContext.SQLITE_CONFIG_DB_PATH
db_path.parent.mkdir(exist_ok=True)
config_database = SqliteDatabase(db_path)


class ConfigModel(Model):
    id = AutoField(primary_key=True)

    class Meta:
        database = config_database


class ProductConfigModel(ConfigModel):
    name = CharField(unique=True)
    interval_days_need = IntegerField()
    modifier = FloatField()

    class Meta:
        table_name = 'products'


class ProductFamilyModifierConfigModel(ConfigModel):
    product = ForeignKeyField(
        ProductConfigModel,
        on_delete='CASCADE'
    )
    age_group = CharField()
    gender = CharField()
    modifier = FloatField()

    class Meta:
        table_name = 'product_family_modifiers'
        constraints = [
            SQL('UNIQUE (product_id, age_group, gender)')
        ]


class ProductBuyerModifierConfigModel(ConfigModel):
    product = ForeignKeyField(
        ProductConfigModel,
        on_delete='CASCADE'
    )
    age_group = CharField()
    gender = CharField()
    modifier = FloatField()

    class Meta:
        table_name = 'product_buyer_modifiers'
        constraints = [
            SQL('UNIQUE (product_id, age_group, gender)')
        ]


class ProductAssociationConfigModel(ConfigModel):
    product = ForeignKeyField(
        ProductConfigModel,
        on_delete='CASCADE'
    )
    associated_product = ForeignKeyField(
        ProductConfigModel,
        on_delete='CASCADE'
    )
    strength = FloatField()

    class Meta:
        table_name = 'product_associations'
        constraints = [
            SQL('UNIQUE (product_id, associated_product_id)')
        ]


MODELS = [
    ProductConfigModel,
    ProductFamilyModifierConfigModel,
    ProductBuyerModifierConfigModel,
    ProductAssociationConfigModel
]


def create_config_database() -> None:
    database: SqliteDatabase = ConfigModel._meta.database
    database.create_tables(MODELS)

    config = GlobalContext.get_config_item(
        GlobalContext.CONFIG_ITEM_PATH
        )
    _populate_product_config(config)
    _populate_product_family_modifer(config)
    _populate_product_buyer_modifier(config)
    _populate_product_association(config)
    return database


def _populate_product_config(config: dict) -> None:
    with ConfigModel._meta.database.atomic():
        for category in config['categories']:
            for product_data in category['products']:
                ProductConfigModel.create(
                    name=product_data['name'],
                    modifier=product_data.get('modifier', 0.01),
                    interval_days_need=product_data.get(
                        'interval_days_need',
                        30
                    )
                )


def _populate_product_family_modifer(config: dict) -> None:
    with ConfigModel._meta.database.atomic():
        for family_modifier in config['family_modifiers']:
            for age_group in family_modifier['age_groups']:
                for gender in family_modifier['genders']:
                    product = (
                        ProductConfigModel
                        .get(ProductConfigModel.name == family_modifier['product'])
                    )
                    ProductFamilyModifierConfigModel.create(
                        product=product.id,
                        age_group=age_group,
                        gender=gender,
                        modifier=family_modifier.get('modifier', 1)
                    )


def _populate_product_buyer_modifier(config: dict) -> None:
    with ConfigModel._meta.database.atomic():
        for buyer_modifier in config['buyer_modifiers']:
            for age_group in buyer_modifier['age_groups']:
                for gender in buyer_modifier['genders']:
                    product = (
                        ProductConfigModel
                        .get(ProductConfigModel.name == buyer_modifier['product'])
                    )
                    ProductBuyerModifierConfigModel.create(
                        product=product.id,
                        age_group=age_group,
                        gender=gender,
                        modifier=buyer_modifier.get('modifier', 1)
                    )


def _populate_product_association(config: dict) -> None:
    with ConfigModel._meta.database.atomic():
        for product_name, associations in config['associations'].items():
            product = (
                ProductConfigModel
                .get(ProductConfigModel.name == product_name)
                )
            for associated_product_name, strength in associations.items():
                associated_product = (
                    ProductConfigModel
                    .get(ProductConfigModel.name == associated_product_name)
                    )
                ProductAssociationConfigModel.create(
                    product=product.id,
                    associated_product=associated_product.id,
                    strength=strength
                )
