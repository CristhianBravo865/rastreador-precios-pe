"""Adaptador para Falabella (y, en la fase 2, Tottus, que usa la misma plataforma).

La página de producto es Next.js e incluye todos los datos en
`<script id="__NEXT_DATA__">`, en `props.pageProps.productData`. Se lee ese
JSON: no se interpreta el HTML visible.

Precios: cada variante trae `prices[]` con un `type`:
- `cmrPrice`: precio con tarjeta CMR (solo para quien la tiene).
- `eventPrice` / `internetPrice`: precio de oferta para cualquiera.
- `normalPrice`: precio normal; si `crossed` es True, se muestra tachado.

Stock: `stockUnits` vale 0 incluso en productos que sí se pueden comprar, así
que no es fiable. Solo se guarda si está disponible.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, ValidationError

from rastreador.adapters.base import AdapterError, ErrorKind
from rastreador.models import Observation

NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__" type="application/json"[^>]*>(.*?)</script>', re.S)
PRODUCT_URL_RE = re.compile(r"/product/(\d+)")
CARD_PRICE_TYPES = {"cmrPrice"}


class _Price(BaseModel):
    type: str
    price: list[str]
    crossed: bool = False


class _Offering(BaseModel):
    sellerId: str
    sellerName: str


class _Variant(BaseModel):
    id: str
    name: str
    prices: list[_Price]
    offerings: list[_Offering]
    isPurchaseable: bool = True
    attributes: dict = {}


class _ProductData(BaseModel):
    id: str
    name: str
    variants: list[_Variant]
    isOutOfStock: bool = False


def _money(text: str) -> Decimal:
    # Falabella usa "1,799" o "1,799.90": la coma separa miles.
    try:
        return Decimal(text.replace(",", "").strip()).quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise AdapterError(ErrorKind.SCHEMA, f"precio ilegible: {text!r}") from exc


class FalabellaAdapter:
    name = "falabella"

    def request_url(self, url: str) -> str:
        if not PRODUCT_URL_RE.search(url):
            raise AdapterError(ErrorKind.BAD_URL, f"no parece una URL de producto Falabella (…/product/<id>/…): {url}")
        return url

    def parse(self, body: str, url: str, store: str) -> list[Observation]:
        match = NEXT_DATA_RE.search(body)
        if not match:
            raise AdapterError(ErrorKind.SCHEMA, "la página no contiene __NEXT_DATA__")
        try:
            data = json.loads(match.group(1))
            product = _ProductData.model_validate(data["props"]["pageProps"]["productData"])
        except (json.JSONDecodeError, KeyError, TypeError, ValidationError) as exc:
            raise AdapterError(ErrorKind.SCHEMA, f"{type(exc).__name__}: {exc}") from exc

        observations = []
        for variant in product.variants:
            price, list_price, card_price = self._prices(variant.prices)
            if price is None:
                continue
            attrs = variant.attributes
            attributes = {
                k: str(v) for k, v in (("Color", attrs.get("colorName")), ("Tamaño", attrs.get("size"))) if v
            }
            for offering in variant.offerings or [_Offering(sellerId="", sellerName="")]:
                observations.append(
                    Observation(
                        store=store,
                        product_id=product.id,
                        sku_id=variant.id,
                        title=variant.name,
                        url=url,
                        seller_id=offering.sellerId,
                        seller_name=offering.sellerName,
                        # Falabella no expone de forma fiable si el vendedor es la propia tienda.
                        sold_by_store=None,
                        price=price,
                        list_price=list_price,
                        card_price=card_price,
                        available=variant.isPurchaseable and not product.isOutOfStock,
                        stock=None,
                        attributes=attributes,
                    )
                )
        return observations

    @staticmethod
    def _prices(prices: list[_Price]) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
        regular, crossed, card = [], [], []
        for p in prices:
            if not p.price:
                continue
            value = _money(p.price[0])
            if p.type in CARD_PRICE_TYPES:
                card.append(value)
            elif p.crossed:
                crossed.append(value)
            else:
                regular.append(value)
        price = min(regular) if regular else None
        list_price = max(crossed) if crossed else None
        card_price = min(card) if card else None
        return price, list_price, card_price
