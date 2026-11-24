"""Genera un historial de EJEMPLO para trabajar en el dashboard sin esperar semanas.

Los datos son inventados, se escriben fuera de data/ y cubren los casos que el
frontend debe saber mostrar: una tienda caída, una sin datos recientes, un
precio tachado inflado, pocas unidades, un vendedor tercero y un SKU
reutilizado para otra variante.

    uv run python scripts/demo_data.py demo-data
    uv run rastreador build-site --data-dir demo-data --out site
    uv run python -m http.server -d site 8000
"""

from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from rastreador.adapters.base import ErrorKind
from rastreador.config import load_products
from rastreador.storage import OfferError, Record, StoreHealth, append_health, append_records

DAYS = 45


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "demo-data")
    if (out / "observations").exists():
        print(f"{out} ya tiene datos; bórralo antes de regenerar.")
        return 1
    rng = random.Random(42)
    config = load_products()
    now = datetime.now(timezone.utc).replace(hour=11, minute=17, second=0, microsecond=0)
    offers = [(p, o) for p in config.products for o in p.offers]
    stores = sorted({o.store for _, o in offers})
    down_store = stores[0] if len(stores) > 1 else None  # deja de responder los últimos 3 días
    stale_store = stores[1] if len(stores) > 2 else None  # su runner dejó de correr hace 2 días
    third = stores[-1]                                    # ofertas de un vendedor tercero con 1 unidad

    base = {o.store: Decimal(rng.randint(1650, 1900)) for _, o in offers}
    for day in range(DAYS, -1, -1):
        at = now - timedelta(days=day)
        for store in stores:
            if store == stale_store and day < 2:
                continue
            records, errors = [], []
            store_offers = [(p, o) for p, o in offers if o.store == store]
            for p, o in store_offers:
                if store == down_store and day < 3:
                    errors.append(OfferError(tracked_product=p.id, sku_id=o.sku_id, url=o.url,
                                             kind=ErrorKind.BLOCKED, detail="HTTP 403 (ejemplo)"))
                    continue
                base[store] = max(Decimal(1400), base[store] + Decimal(rng.randint(-25, 22)))
                price = (base[store] - (Decimal(150) if 10 <= day <= 12 else 0)).quantize(Decimal("0.01"))
                inflated = store == third
                identity_bad = store == third and day == 0
                records.append(Record(
                    store=store, product_id="demo", sku_id=o.sku_id, title=o.expected.title, url=o.url,
                    seller_id="1" if not inflated else "demo-seller",
                    seller_name="Tienda" if not inflated else "Vendedor Ejemplo SAC",
                    sold_by_store=not inflated, price=price,
                    list_price=(price * Decimal("1.45")).quantize(Decimal("0.01")) if inflated
                    else (price * Decimal("1.12")).quantize(Decimal("0.01")),
                    available=True, stock=1 if inflated else 8, attributes=o.expected.attributes,
                    observed_at=at, tracked_product=p.id, identity_ok=not identity_bad,
                    identity_issues=["capacidades distintas: 12gb, 512gb vs 256gb, 8gb (ejemplo)"]
                    if identity_bad else [],
                ))
            append_records(records, out)
            append_health(StoreHealth(
                run_at=at, store=store, runner="demo", offers_checked=len(store_offers),
                offers_ok=len(store_offers) - len(errors), records_written=len(records),
                identity_warnings=sum(not r.identity_ok for r in records), errors=errors,
            ), out)
    print(f"Datos de ejemplo en {out}: {DAYS + 1} días, tiendas {', '.join(stores)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
