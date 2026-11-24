"""Adaptador para tiendas sobre VTEX (Oechsle, Plaza Vea, Promart, Coolbox, Estilos).

La URL pública de un producto VTEX termina en `/<slug>/p`. El catálogo público
acepta ese mismo slug: `/api/catalog_system/pub/products/search/<slug>/p`, así
que no hace falta buscar por texto (la búsqueda devuelve resultados ruidosos).

Convención de VTEX: el vendedor con id "1" es la propia tienda. Los demás son
terceros del marketplace. Una oferta con precio 0 es un vendedor sin stock.
"""

from __future__ import annotations

import json
from decimal import Decimal
from urllib.parse import urlparse

from pydantic import BaseModel, ValidationError

from rastreador.adapters.base import AdapterError, ErrorKind
from rastreador.models import Observation

STORE_SELLER_ID = "1"
# Especificaciones de producto que, si existen, describen la variante.
ATTRIBUTE_KEYS = ("Color", "Memoria RAM", "Memoria Interna", "Memoria interna", "Talla", "Tamaño", "Capacidad")


# Esquema mínimo que necesitamos de la respuesta. Si VTEX cambia estos campos,
# la validación falla con ErrorKind.SCHEMA en vez de guardar datos basura.
class _Offer(BaseModel):
    Price: float
    ListPrice: float
    AvailableQuantity: int
    IsAvailable: bool


class _Seller(BaseModel):
    sellerId: str
    sellerName: str
    commertialOffer: _Offer


class _Item(BaseModel):
    itemId: str
    name: str
    sellers: list[_Seller]


class _Product(BaseModel):
    productId: str
    productName: str
    link: str
    items: list[_Item]
    model_config = {"extra": "allow"}


def slug_from_url(url: str) -> str:
    parts = [p for p in urlparse(url).path.split("/") if p]
    if len(parts) < 2 or parts[-1] != "p":
        raise AdapterError(ErrorKind.BAD_URL, f"no parece una URL de producto VTEX (…/<slug>/p): {url}")
    return parts[-2]


def _money(value: float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


class VtexAdapter:
    name = "vtex"

    def request_url(self, url: str) -> str:
        u = urlparse(url)
        return f"{u.scheme}://{u.netloc}/api/catalog_system/pub/products/search/{slug_from_url(url)}/p"

    def parse(self, body: str, url: str, store: str) -> list[Observation]:
        try:
            raw = json.loads(body)
        except json.JSONDecodeError as exc:
            raise AdapterError(ErrorKind.SCHEMA, f"la respuesta no es JSON: {exc}") from exc
        if not isinstance(raw, list):
            raise AdapterError(ErrorKind.SCHEMA, f"se esperaba una lista, llegó {type(raw).__name__}")
        if not raw:
            raise AdapterError(ErrorKind.NOT_FOUND, "el catálogo no devolvió el producto")

        try:
            product = _Product.model_validate(raw[0])
        except ValidationError as exc:
            raise AdapterError(ErrorKind.SCHEMA, str(exc)) from exc

        extra = product.model_extra or {}
        attributes = {
            k: ", ".join(map(str, extra[k])) for k in ATTRIBUTE_KEYS if isinstance(extra.get(k), list) and extra[k]
        }

        observations = []
        for item in product.items:
            for seller in item.sellers:
                offer = seller.commertialOffer
                if offer.Price <= 0:
                    continue  # vendedor listado sin oferta real
                list_price = _money(offer.ListPrice) if offer.ListPrice > offer.Price else None
                observations.append(
                    Observation(
                        store=store,
                        product_id=product.productId,
                        sku_id=item.itemId,
                        title=item.name,
                        url=product.link,
                        seller_id=seller.sellerId,
                        seller_name=seller.sellerName,
                        sold_by_store=seller.sellerId == STORE_SELLER_ID,
                        price=_money(offer.Price),
                        list_price=list_price,
                        available=offer.IsAvailable and offer.AvailableQuantity > 0,
                        stock=offer.AvailableQuantity,
                        attributes=attributes,
                    )
                )
        return observations
