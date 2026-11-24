"""Cálculos sobre el historial. Son funciones puras: entran datos y sale el contrato.

Reglas de qué cuenta como precio comparable:
- Solo observaciones disponibles (`available`) y con identidad confirmada
  (`identity_ok`). Un SKU reutilizado para otra variante no contamina los cálculos.
- El precio de un día, por tienda, es el más bajo entre sus vendedores.
- La "mejor oferta" solo considera ofertas vistas en las últimas STALE_AFTER_HOURS:
  el último precio de una tienda caída no compite contra precios de hoy.
- Las fechas son días de Lima (UTC-5, sin horario de verano).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from statistics import median

from rastreador.config import ProductConfig, ProductsConfig, StoreSettings
from rastreador.site.contract import (
    DailyPoint,
    Flag,
    HistoryFile,
    Meta,
    OfferSnapshot,
    PriceStats,
    ProductsFile,
    ProductSummary,
    StoreInfo,
    StoreSeries,
    StoreStatus,
)
from rastreador.storage import Record, StoreHealth
from rastreador.stores import STORES

LIMA = timezone(timedelta(hours=-5))
STALE_AFTER_HOURS = 36
LOW_STOCK_UNITS = 2
MIN_DAYS_FOR_REAL_DISCOUNT = 7
INFLATED_FACTOR = Decimal("1.15")  # precio tachado > mediana propia + 15 %


def lima_day(dt: datetime) -> date:
    return dt.astimezone(LIMA).date()


def comparable(r: Record) -> bool:
    return r.available and r.identity_ok


def _pct(part: Decimal, whole: Decimal) -> float:
    return round(float((whole - part) / whole * 100), 1)


# --- Ofertas -----------------------------------------------------------------


def latest_snapshot(store: str, sku_id: str, url: str, records: list[Record]) -> OfferSnapshot:
    mine = [r for r in records if r.store == store and r.sku_id == sku_id]
    if not mine:
        return OfferSnapshot(store=store, sku_id=sku_id, url=url)
    last_at = max(r.observed_at for r in mine)
    batch = [r for r in mine if r.observed_at == last_at]
    pool = [r for r in batch if r.available] or batch
    best = min(pool, key=lambda r: r.price)
    return OfferSnapshot(
        store=store, sku_id=sku_id, url=url, observed_at=best.observed_at, price=best.price,
        list_price=best.list_price, card_price=best.card_price, seller_name=best.seller_name,
        sold_by_store=best.sold_by_store, available=best.available, stock=best.stock,
        identity_ok=best.identity_ok, identity_issues=best.identity_issues, other_sellers=len(batch) - 1,
    )


def daily_series(product: ProductConfig, records: list[Record]) -> list[StoreSeries]:
    keys = {(o.store, o.sku_id) for o in product.offers}
    per_store: dict[str, dict[date, Record]] = defaultdict(dict)
    for r in records:
        if (r.store, r.sku_id) not in keys or not comparable(r):
            continue
        day = lima_day(r.observed_at)
        current = per_store[r.store].get(day)
        if current is None or r.price < current.price:
            per_store[r.store][day] = r
    return [
        StoreSeries(
            store=store,
            points=[
                DailyPoint(date=d, price=r.price, list_price=r.list_price, seller_name=r.seller_name)
                for d, r in sorted(days.items())
            ],
        )
        for store, days in sorted(per_store.items())
    ]


def price_stats(series: list[StoreSeries], best: OfferSnapshot | None, today: date) -> PriceStats:
    # Precio del producto por día = el más bajo entre tiendas ese día.
    by_day: dict[date, Decimal] = {}
    for s in series:
        for p in s.points:
            by_day[p.date] = min(by_day.get(p.date, p.price), p.price)
    window = [v for d, v in by_day.items() if today - timedelta(days=30) < d <= today]
    stats = PriceStats(days_observed=len(by_day))
    if window:
        stats.min_30d = min(window)
        stats.median_30d = Decimal(str(median(window))).quantize(Decimal("0.01"))
    if best and best.price is not None:
        if best.list_price and best.list_price > best.price:
            stats.advertised_discount_pct = _pct(best.price, best.list_price)
        if stats.median_30d and len(window) >= MIN_DAYS_FOR_REAL_DISCOUNT:
            stats.real_discount_pct = _pct(best.price, stats.median_30d)
    return stats


def flags_for(product: ProductConfig, best: OfferSnapshot | None, offers: list[OfferSnapshot],
              stats: PriceStats) -> list[Flag]:
    flags = []
    if best and best.price is not None:
        if product.target_price is not None and best.price <= product.target_price:
            flags.append(Flag.BELOW_TARGET)
        if best.stock is not None and best.stock <= LOW_STOCK_UNITS:
            flags.append(Flag.LOW_STOCK)
        if best.sold_by_store is False:
            flags.append(Flag.THIRD_PARTY)
        if (best.list_price and stats.median_30d and stats.days_observed >= MIN_DAYS_FOR_REAL_DISCOUNT
                and best.list_price > stats.median_30d * INFLATED_FACTOR):
            flags.append(Flag.INFLATED_LIST_PRICE)
    if any(not o.identity_ok for o in offers):
        flags.append(Flag.IDENTITY_WARNING)
    return flags


def summarize(product: ProductConfig, records: list[Record], now: datetime) -> tuple[ProductSummary, HistoryFile]:
    today = lima_day(now)
    fresh_since = now - timedelta(hours=STALE_AFTER_HOURS)
    offers = [latest_snapshot(o.store, o.sku_id, o.url, records) for o in product.offers]
    for o in offers:
        o.fresh = o.observed_at is not None and o.observed_at >= fresh_since
    valid = [o for o in offers if o.fresh and o.price is not None and o.available and o.identity_ok]
    best = min(valid, key=lambda o: o.price) if valid else None
    series = daily_series(product, records)
    stats = price_stats(series, best, today)
    summary = ProductSummary(
        id=product.id, name=product.name, target_price=product.target_price, best=best,
        offers=sorted(offers, key=lambda o: (o.price is None, o.price or 0)),
        stats=stats, flags=flags_for(product, best, offers, stats),
    )
    return summary, HistoryFile(product_id=product.id, series=series)


# --- Tiendas -----------------------------------------------------------------


def store_info(health: list[StoreHealth], settings: StoreSettings | None, now: datetime) -> dict:
    if not health:
        return {"status": StoreStatus.NEVER, "runner": settings.runner.value if settings else "?"}
    last = max(health, key=lambda h: h.run_at)
    oks = [h.run_at for h in health if h.offers_ok > 0]
    status = StoreStatus(last.status)
    if now - last.run_at > timedelta(hours=STALE_AFTER_HOURS):
        status = StoreStatus.STALE
    detail = "; ".join(f"{e.sku_id}: [{e.kind}] {e.detail}" for e in last.errors) or None
    return {
        "status": status, "runner": settings.runner.value if settings else last.runner,
        "last_run_at": last.run_at, "last_ok_at": max(oks) if oks else None, "detail": detail,
    }


def build_contract(
    config: ProductsConfig,
    records: list[Record],
    health: dict[str, list[StoreHealth]],
    settings: dict[str, StoreSettings],
    now: datetime,
) -> tuple[Meta, ProductsFile, list[HistoryFile]]:
    tracked_stores = {o.store for p in config.products for o in p.offers}
    stores = [
        StoreInfo(id=s.id, name=s.name, source_group=s.source_group,
                  **store_info(health.get(s.id, []), settings.get(s.id), now))
        for s in STORES
        if s.id in tracked_stores or s.id in health
    ]
    meta = Meta(generated_at=now, stale_after_hours=STALE_AFTER_HOURS, stores=stores)
    pairs = [summarize(p, records, now) for p in config.products]
    return meta, ProductsFile(products=[s for s, _ in pairs]), [h for _, h in pairs]
