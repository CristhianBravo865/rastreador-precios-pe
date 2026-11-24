"""Corrida diaria: revisar cada oferta vigilada y agregar el resultado al historial.

    rastreador run --runner actions    tiendas que corren en GitHub Actions
    rastreador run --runner local      tiendas que corren en la PC (Falabella)

Por cada tienda escribe una línea de salud, aunque todo falle. Así una tienda
caída queda registrada como dato, no como ausencia de datos.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from rastreador.adapters.base import AdapterError, ErrorKind, fetch
from rastreador.config import (
    PRODUCTS_FILE,
    STORES_FILE,
    OfferConfig,
    Runner,
    load_products,
    load_store_settings,
)
from rastreador.http import PoliteClient
from rastreador.matching import conflicts, signature
from rastreador.models import Observation
from rastreador.storage import DATA_DIR, OfferError, Record, StoreHealth, append_health, append_records
from rastreador.stores import STORES

StoreFetcher = Callable[[str, str], list[Observation]]


@dataclass
class _Tracked:
    product_id: str
    offer: OfferConfig


def _default_fetcher(client: PoliteClient) -> StoreFetcher:
    by_id = {s.id: s for s in STORES}

    def _fetch(store_id: str, url: str) -> list[Observation]:
        store = by_id[store_id]
        return fetch(store.adapter, client, url, store.id)

    return _fetch


def identity_issues(offer: OfferConfig, current: Observation) -> list[str]:
    expected = signature(offer.expected.title, offer.expected.attributes)
    return conflicts(expected, signature(current.title, current.attributes))


def run(
    *,
    runner: Runner | None = None,
    only_stores: set[str] | None = None,
    config_path: Path = PRODUCTS_FILE,
    stores_path: Path = STORES_FILE,
    data_dir: Path = DATA_DIR,
    fetcher: StoreFetcher | None = None,
    now: datetime | None = None,
) -> list[StoreHealth]:
    now = now or datetime.now(timezone.utc)
    runner_name = runner.value if runner else "manual"
    settings = load_store_settings(stores_path)
    config = load_products(config_path)

    def selected(store: str) -> bool:
        if only_stores is not None and store not in only_stores:
            return False
        if store not in settings:
            raise ValueError(f"la tienda '{store}' no está en {stores_path}: falta indicar su runner")
        return runner is None or settings[store].runner == runner

    # tienda -> url -> ofertas vigiladas en esa URL (una sola descarga por URL)
    plan: dict[str, dict[str, list[_Tracked]]] = {}
    for product in config.products:
        for offer in product.offers:
            if selected(offer.store):
                plan.setdefault(offer.store, {}).setdefault(offer.url, []).append(_Tracked(product.id, offer))

    client = PoliteClient() if fetcher is None else None
    fetch_fn = fetcher or _default_fetcher(client)
    results = []
    try:
        for store, urls in plan.items():
            health = StoreHealth(
                run_at=now, store=store, runner=runner_name, offers_checked=0, offers_ok=0,
                records_written=0, identity_warnings=0,
            )
            records: list[Record] = []
            for url, tracked in urls.items():
                health.offers_checked += len(tracked)
                try:
                    observations = fetch_fn(store, url)
                except AdapterError as exc:
                    health.errors += [
                        OfferError(tracked_product=t.product_id, sku_id=t.offer.sku_id, url=url,
                                   kind=exc.kind, detail=exc.detail)
                        for t in tracked
                    ]
                    continue
                for t in tracked:
                    current = [o for o in observations if o.sku_id == t.offer.sku_id]
                    if not current:
                        health.errors.append(OfferError(
                            tracked_product=t.product_id, sku_id=t.offer.sku_id, url=url,
                            kind=ErrorKind.NOT_FOUND, detail="el SKU ya no aparece o no tiene ofertas con precio",
                        ))
                        continue
                    health.offers_ok += 1
                    issues = identity_issues(t.offer, current[0])
                    if issues:
                        health.identity_warnings += 1
                    for o in current:
                        records.append(Record(
                            **o.model_dump(exclude={"observed_at"}), observed_at=now,
                            tracked_product=t.product_id, identity_ok=not issues, identity_issues=issues,
                        ))
            append_records(records, data_dir)
            health.records_written = len(records)
            append_health(health, data_dir)
            results.append(health)
    finally:
        if client is not None:
            client.close()
    return results


def summary_markdown(results: list[StoreHealth]) -> str:
    if not results:
        return "No había ofertas que revisar para este runner."
    icon = {"ok": "✅", "degraded": "⚠️", "down": "❌"}
    lines = [
        f"## Corrida {results[0].run_at:%Y-%m-%d %H:%M} UTC ({results[0].runner})",
        "",
        "| Tienda | Estado | Ofertas OK | Registros | Problemas |",
        "|---|---|---|---|---|",
    ]
    for h in results:
        problems = "; ".join(f"{e.sku_id}: [{e.kind}] {e.detail}" for e in h.errors)
        if h.identity_warnings:
            problems = (problems + "; " if problems else "") + f"{h.identity_warnings} SKU con identidad dudosa"
        lines.append(
            f"| {h.store} | {icon[h.status]} {h.status} | {h.offers_ok}/{h.offers_checked} "
            f"| {h.records_written} | {problems or '—'} |"
        )
    return "\n".join(lines)


def write_github_summary(text: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")
