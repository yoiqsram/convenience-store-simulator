from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, TYPE_CHECKING

from ..core import ReprMixin
from ..context import GlobalContext
from ..database import ModelMixin, SKUModel, ProductModel

if TYPE_CHECKING:
    from ..population.family import Person


class Product(ModelMixin, ReprMixin):
    __model__ = ProductModel
    __repr_attrs__ = ( 'name', 'category', 'modifier' )
    __products__: Dict[str, Product] = dict()

    def __init__(
            self,
            name: str,
            category: str,
            modifier: float,
            interval_days_need: int,
            associations: Dict[str, float] = None,
            demographic_modifiers: List[dict] = None,
            skus: List[SKU] = None
        ) -> None:
        self.name = name
        self.category = category
        self.modifier = modifier
        self.interval_days_need = interval_days_need

        if associations is None:
            associations = dict()
        self.associations = associations

        if demographic_modifiers is None:
            demographic_modifiers = []
        self.demographic_modifiers = demographic_modifiers

        super().__init_model__({ 'name': self.name })

        if skus is None:
            skus = []
        self.skus = skus

    def adjusted_modifier(
            self,
            person: Person,
            current_date: date
        ) -> float:
        multiplier = 1.0

        # Adjust modifier based on demographic
        age = person.age(current_date)
        for modifier in self.demographic_modifiers:
            if modifier['gender'] is not None \
                    and person.gender != modifier['gender']:
                continue

            if modifier['age_min'] is not None \
                    and age < modifier['age_min']:
                continue

            if modifier['age_max'] is not None \
                    and age >= modifier['age_max']:
                continue

            multiplier += modifier['value']

        # Adjust modifier based on weekday
        weekday = current_date.weekday()
        if weekday == 0:
            multiplier += 0.1
        elif weekday == 5:
            multiplier += 0.25
        elif weekday == 6:
            multiplier += 0.5

        return self.modifier * multiplier

    @classmethod
    def all(cls) -> List[Product]:
        if len(cls.__products__) == 0:
            cls.load()

        return list(cls.__products__.values())

    @classmethod
    def get(cls, name: str) -> Product:
        return cls.__products__[name]

    @classmethod
    def clear(cls) -> None:
        cls.__products__ = dict()

    @classmethod
    def load(cls, config_path: Path = None) -> None:
        item_config = GlobalContext.get_config_item(config_path)
        for category in item_config['categories']:
            for product_name in category['products']:
                product = cls(
                    name=product_name['name'],
                    category=category['name'],
                    modifier=product_name.get('modifier', 0.01),
                    interval_days_need=product_name.get('interval_days_need', 30),
                )
                product.skus = [
                    SKU(
                        name=sku['name'],
                        brand=sku['brand'],
                        product=product,
                        price=sku['price'],
                        cost=sku['cost'],
                        pax=sku['pax']
                    )
                    for sku in product_name['skus']
                ]

                cls.__products__[product_name['name']] = product

        for association in item_config['associations']:
            association_products = [
                {
                    'name': name,
                    'value': value
                }
                for name, value in association['products'].items()
                if name in cls.__products__
            ]
            if len(association_products) < 2:
                continue

            for i in range(len(association_products)):
                for j in range(len(association_products)):
                    if i == j:
                        continue

                    product_name = association_products[i]['name']
                    associated_product_name = association_products[j]['name']
                    cls.__products__[product_name].associations[associated_product_name] = association_products[i]['value']

        for demographic_modifier in item_config['demographic_modifiers']:
            for product_name, value in demographic_modifier['products'].items():
                cls.__products__[product_name].demographic_modifiers.append({
                    'gender': demographic_modifier.get('gender'),
                    'age_min': demographic_modifier.get('age_min'),
                    'age_max': demographic_modifier.get('age_max'),
                    'value': value
                })


class SKU(ModelMixin):
    __model__ = SKUModel

    def __init__(
            self,
            name: str,
            brand: str,
            product: Product,
            price: float,
            cost: float,
            pax: int
        ) -> None:
        self.name = name
        self.brand = brand
        self.product = product
        self.price = price
        self.cost = cost
        self.pax = pax

        super().__init_model__(
            unique_identifiers={ 'name': name },
            brand=brand,
            product=product.record.id,
            price=price,
            cost=cost,
            pax=pax
        )

    def update(self, current_datetime: datetime) -> None:
        self.created_datetime = current_datetime
