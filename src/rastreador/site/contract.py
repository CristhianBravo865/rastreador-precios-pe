"""Contrato de datos entre el cálculo (Python) y el dashboard (web/).

El build escribe estos modelos como JSON en `site/data/`. El frontend solo lee
esos archivos y no recalcula nada: cualquier frontend nuevo (otro diseño, React,
una app) puede reemplazar a `web/` mientras respete este contrato.

Reglas para cambiarlo:
- Agregar un campo opcional: no cambia SCHEMA_VERSION (cambio compatible).
- Quitar o renombrar un campo, o cambiar su significado: subir SCHEMA_VERSION
  y actualizar docs/DASHBOARD.md.

Los precios van como strings decimales ("1799.00") para no perder exactitud en
JSON; el frontend los formatea.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

SCHEMA_VERSION = 1


class StoreStatus(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"
    STALE = "stale"      # la última corrida es demasiado vieja
    NEVER = "never"      # nunca corrió


class Flag(StrEnum):
    BELOW_TARGET = "below_target"            # precio bajo el umbral del usuario
    INFLATED_LIST_PRICE = "inflated_list_price"  # el "precio normal" supera mucho la mediana propia
    LOW_STOCK = "low_stock"                  # la mejor oferta tiene pocas unidades
    THIRD_PARTY = "third_party"              # la mejor oferta es de un vendedor tercero
    IDENTITY_WARNING = "identity_warning"    # alguna tienda cambió el producto detrás del SKU


class StoreInfo(BaseModel):
    id: str
    name: str
    source_group: str
    runner: str
    status: StoreStatus
    last_run_at: datetime | None = None
    last_ok_at: datetime | None = None
    detail: str | None = Field(default=None, description="Errores de la última corrida, si los hubo.")


class Meta(BaseModel):
    schema_version: int = SCHEMA_VERSION
    generated_at: datetime
    stale_after_hours: int
    stores: list[StoreInfo]


class OfferSnapshot(BaseModel):
    """Lo último que se vio de una oferta (tienda + SKU), con su mejor vendedor."""

    store: str
    sku_id: str
    url: str
    observed_at: datetime | None = None
    price: Decimal | None = None
    list_price: Decimal | None = None
    card_price: Decimal | None = None
    seller_name: str | None = None
    sold_by_store: bool | None = None
    available: bool = False
    stock: int | None = None
    identity_ok: bool = True
    identity_issues: list[str] = Field(default_factory=list)
    other_sellers: int = Field(default=0, description="Otros vendedores con precio para el mismo SKU.")
    fresh: bool = Field(default=False, description="Visto dentro de Meta.stale_after_hours; solo estas compiten.")


class PriceStats(BaseModel):
    days_observed: int
    min_30d: Decimal | None = None
    median_30d: Decimal | None = None
    advertised_discount_pct: float | None = Field(
        default=None, description="Descuento contra el precio tachado de la tienda."
    )
    real_discount_pct: float | None = Field(
        default=None, description="Descuento contra la mediana propia de 30 días; null con menos de 7 días."
    )


class ProductSummary(BaseModel):
    id: str
    name: str
    target_price: Decimal | None = None
    best: OfferSnapshot | None = None
    offers: list[OfferSnapshot]
    stats: PriceStats
    flags: list[Flag] = Field(default_factory=list)


class ProductsFile(BaseModel):
    schema_version: int = SCHEMA_VERSION
    products: list[ProductSummary]


class DailyPoint(BaseModel):
    date: date
    price: Decimal
    list_price: Decimal | None = None
    seller_name: str


class StoreSeries(BaseModel):
    store: str
    points: list[DailyPoint]


class HistoryFile(BaseModel):
    schema_version: int = SCHEMA_VERSION
    product_id: str
    series: list[StoreSeries]
