from __future__ import annotations

import yaml
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from .constants import CONFIG_DIR


@dataclass
class SKU:
    name: str
    brand: str
    product: str
    price: float
    cost: float
    pax: float


class Product:
    __products__: Dict[str, Product] = dict()

    def __init__(
            self,
            name: str,
            category: str,
            modifier: float,
            interval_days_need: int,
            associations: Dict[str, float] = None,
            skus: List[SKU] = None
        ) -> None:
        self.name = name
        self.category = category
        self.modifier = modifier
        self.interval_days_need = interval_days_need

        if associations is None:
            associations = dict()
        self.associations = associations

        if skus is None:
            skus = []
        self.skus = skus

    def __repr__(self) -> str:
        return f"Product(name={repr(self.name)}, caategory={repr(self.category)})"

    @classmethod
    def clear(cls) -> None:
        cls.__products__ = dict()

    @classmethod
    def load(cls, config_path: Path = None) -> None:
        if config_path is None:
            config_path = CONFIG_DIR / 'items.yaml'

        with open(config_path) as f:
            data = yaml.safe_load(f)

        for category in data['categories']:
            for product in category['products']:
                skus = [
                    SKU(
                        name=sku['name'],
                        brand=sku['brand'],
                        product=product['name'],
                        price=sku['price'],
                        cost=sku['cost'],
                        pax=sku['pax']
                    )
                    for sku in product['skus']
                ]

                cls.__products__[product['name']] = cls(
                    name=product['name'],
                    category=category['name'],
                    modifier=product.get('modifier', 0.01),
                    interval_days_need=product.get('interval_days_need', 30),
                    skus=skus
                )

        for association in data['associations']:
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

    @classmethod
    def get(cls, name: str) -> Product:
        return cls.__products__[name]

    @classmethod
    def all(cls) -> List[Product]:
        return list(cls.__products__.values())
