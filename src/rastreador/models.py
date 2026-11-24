"""Modelos de datos compartidos por todos los adaptadores."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, Field


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class Observation(BaseModel):
    """Un precio visto en una tienda, para un SKU y un vendedor, en un momento dado.

    Es la unidad que se guarda en el historial. Un producto con varias variantes
    (SKU) o varios vendedores produce varias observaciones.
    """

    store: str = Field(description="Identificador de la tienda, p. ej. 'plazavea'.")
    product_id: str
    sku_id: str
    title: str
    url: str

    seller_id: str
    seller_name: str
    sold_by_store: bool | None = Field(
        description="True si vende la propia tienda, False si es un tercero "
        "(marketplace), None si la tienda no permite saberlo."
    )

    price: Decimal = Field(description="Precio que paga cualquier cliente, sin tarjeta de la tienda.")
    list_price: Decimal | None = Field(default=None, description="Precio 'normal' tachado, si existe.")
    card_price: Decimal | None = Field(default=None, description="Precio con tarjeta de la tienda (p. ej. CMR).")

    available: bool
    stock: int | None = Field(default=None, description="Unidades informadas por la tienda; None si no es fiable.")

    attributes: dict[str, str] = Field(default_factory=dict, description="Color, talla, capacidad... tal como los da la tienda.")
    observed_at: datetime = Field(default_factory=now_utc)
