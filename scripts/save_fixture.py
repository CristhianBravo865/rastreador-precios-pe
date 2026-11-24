"""Guarda una respuesta real de tienda como fixture de prueba, recortada.

Las respuestas completas pesan cientos de KB (Falabella: ~1.7 MB de HTML).
Este script conserva solo los campos que leen los adaptadores, más algunos
vecinos, para que las pruebas sigan siendo realistas sin guardar páginas
enteras en el repo.

Uso:
    uv run python scripts/save_fixture.py <url-de-producto> <nombre>
    -> tests/fixtures/<nombre>.json  (VTEX)  o  tests/fixtures/<nombre>.html  (Falabella)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from rastreador.adapters.falabella import NEXT_DATA_RE
from rastreador.adapters.vtex import ATTRIBUTE_KEYS
from rastreador.http import PoliteClient
from rastreador.stores import store_for_url

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"

VTEX_PRODUCT_KEYS = {"productId", "productName", "brand", "link", "linkText", "items", *ATTRIBUTE_KEYS}
VTEX_ITEM_KEYS = {"itemId", "name", "sellers"}
VTEX_OFFER_KEYS = {"Price", "ListPrice", "PriceWithoutDiscount", "AvailableQuantity", "IsAvailable"}

FALABELLA_PRODUCT_KEYS = {"id", "name", "brandName", "slug", "variants", "isOutOfStock", "stockUnits"}
FALABELLA_VARIANT_KEYS = {"id", "name", "prices", "offerings", "attributes", "isPurchaseable"}


def trim_vtex(body: str) -> str:
    products = json.loads(body)
    out = []
    for p in products:
        q = {k: v for k, v in p.items() if k in VTEX_PRODUCT_KEYS}
        q["items"] = []
        for it in p["items"]:
            item = {k: v for k, v in it.items() if k in VTEX_ITEM_KEYS}
            item["sellers"] = [
                {
                    "sellerId": s["sellerId"],
                    "sellerName": s["sellerName"],
                    "commertialOffer": {k: s["commertialOffer"].get(k) for k in VTEX_OFFER_KEYS},
                }
                for s in it["sellers"]
            ]
            q["items"].append(item)
        out.append(q)
    return json.dumps(out, ensure_ascii=False, indent=1)


def trim_falabella(body: str) -> str:
    data = json.loads(NEXT_DATA_RE.search(body).group(1))
    pd = data["props"]["pageProps"]["productData"]
    trimmed = {k: v for k, v in pd.items() if k in FALABELLA_PRODUCT_KEYS}
    trimmed["variants"] = [{k: v for k, v in var.items() if k in FALABELLA_VARIANT_KEYS} for var in pd["variants"]]
    next_data = {"props": {"pageProps": {"productData": trimmed}}}
    return (
        "<!DOCTYPE html><html><head></head><body>\n"
        '<script id="__NEXT_DATA__" type="application/json">'
        + json.dumps(next_data, ensure_ascii=False)
        + "</script>\n</body></html>\n"
    )


def main() -> int:
    url, name = sys.argv[1], sys.argv[2]
    store = store_for_url(url)
    with PoliteClient() as client:
        body = client.get(store.adapter.request_url(url)).text
    if store.adapter.name == "vtex":
        path, content = FIXTURES / f"{name}.json", trim_vtex(body)
    else:
        path, content = FIXTURES / f"{name}.html", trim_falabella(body)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"guardado {path} ({len(content):,} bytes, original {len(body):,})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
