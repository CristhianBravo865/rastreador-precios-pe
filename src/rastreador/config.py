"""Configuración versionada en el repo: qué productos se vigilan y dónde corre cada tienda.

`config/products.yaml` lo escribe el comando `rastreador add`; se puede editar a
mano, pero al guardar se reescribe entero (los comentarios no se conservan).
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from decimal import Decimal
from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator

CONFIG_DIR = Path("config")
PRODUCTS_FILE = CONFIG_DIR / "products.yaml"
STORES_FILE = CONFIG_DIR / "stores.yaml"

PRODUCTS_HEADER = """\
# Productos vigilados. Lo mantiene `rastreador add <url>`.
# Cada producto agrupa la MISMA variante (mismo modelo, capacidad, color...)
# en distintas tiendas. Cada oferta fija un SKU exacto: nunca se busca por texto.
"""


class Expected(BaseModel):
    """Cómo era el SKU al agregarlo. Sirve para detectar si la tienda lo cambió."""

    title: str
    attributes: dict[str, str] = Field(default_factory=dict)


class OfferConfig(BaseModel):
    store: str
    url: str
    sku_id: str
    added_at: date
    expected: Expected


class ProductConfig(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str
    target_price: Decimal | None = Field(default=None, description="Avisar si el precio baja de esto.")
    offers: list[OfferConfig] = Field(default_factory=list)


class ProductsConfig(BaseModel):
    products: list[ProductConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique(self) -> ProductsConfig:
        ids = [p.id for p in self.products]
        dup_ids = {i for i in ids if ids.count(i) > 1}
        if dup_ids:
            raise ValueError(f"ids de producto repetidos: {sorted(dup_ids)}")
        keys = [(o.store, o.sku_id) for p in self.products for o in p.offers]
        dup_keys = {k for k in keys if keys.count(k) > 1}
        if dup_keys:
            raise ValueError(f"el mismo SKU está en más de un producto: {sorted(dup_keys)}")
        return self

    def get(self, product_id: str) -> ProductConfig | None:
        return next((p for p in self.products if p.id == product_id), None)

    def find_offer(self, store: str, sku_id: str) -> tuple[ProductConfig, OfferConfig] | None:
        for p in self.products:
            for o in p.offers:
                if (o.store, o.sku_id) == (store, sku_id):
                    return p, o
        return None


def load_products(path: Path = PRODUCTS_FILE) -> ProductsConfig:
    if not path.exists():
        return ProductsConfig()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return ProductsConfig.model_validate(data)


def save_products(config: ProductsConfig, path: Path = PRODUCTS_FILE) -> None:
    ProductsConfig.model_validate(config.model_dump())  # revalidar antes de escribir
    data = config.model_dump(mode="json", exclude_none=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=120)
    path.write_text(PRODUCTS_HEADER + body, encoding="utf-8", newline="\n")


class Runner(StrEnum):
    ACTIONS = "actions"
    LOCAL = "local"


class StoreSettings(BaseModel):
    runner: Runner


def load_store_settings(path: Path = STORES_FILE) -> dict[str, StoreSettings]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {k: StoreSettings.model_validate(v) for k, v in data.items()}


def slugify(text: str, max_len: int = 60) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:max_len].rstrip("-") or "producto"
