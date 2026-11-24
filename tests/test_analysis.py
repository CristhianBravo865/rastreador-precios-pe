"""Cálculos del dashboard: mejor oferta, descuento real, banderas, estado de tiendas y build."""

import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from rastreador.analysis import build_contract, lima_day
from rastreador.config import (
    Expected,
    OfferConfig,
    ProductConfig,
    ProductsConfig,
    Runner,
    StoreSettings,
    save_products,
)
from rastreador.site.build import build_site
from rastreador.site.contract import SCHEMA_VERSION, Flag, StoreStatus
from rastreador.storage import OfferError, Record, StoreHealth, append_health, append_records

NOW = datetime(2026, 12, 20, 16, 0, tzinfo=timezone.utc)
SETTINGS = {s: StoreSettings(runner=Runner.ACTIONS) for s in ("plazavea", "oechsle", "falabella")}


def product(target=None):
    return ProductConfig(
        id="poco", name="POCO", target_price=target,
        offers=[OfferConfig(store=s, url=f"https://{s}/p", sku_id=f"{s}-1", added_at=date(2026, 11, 24),
                            expected=Expected(title="POCO X8 Pro 12GB 512GB Negro"))
                for s in ("plazavea", "oechsle", "falabella")],
    )


def rec(store, price, days_ago=0, *, list_price=None, seller="Tienda", own=True, stock=5, available=True,
        identity_ok=True, hour=11):
    at = (NOW - timedelta(days=days_ago)).replace(hour=hour)
    return Record(
        store=store, product_id="x", sku_id=f"{store}-1", title="POCO X8 Pro 12GB 512GB Negro", url="u",
        seller_id="1" if own else "t", seller_name=seller, sold_by_store=own, price=Decimal(price),
        list_price=Decimal(list_price) if list_price else None, available=available, stock=stock,
        observed_at=at, tracked_product="poco", identity_ok=identity_ok,
    )


def contract(records, health=None, target=None):
    return build_contract(ProductsConfig(products=[product(target)]), records, health or {}, SETTINGS, NOW)


def test_best_offer_ignores_stale_unavailable_and_wrong_variant():
    records = [
        rec("plazavea", "1700"),
        rec("oechsle", "1500", days_ago=3),                       # barato pero viejo
        rec("falabella", "1400", identity_ok=False),              # otra variante
        rec("falabella", "1450", seller="Otro", available=False),  # agotado
    ]
    _, products, _ = contract(records)
    p = products.products[0]
    assert p.best.store == "plazavea" and p.best.price == Decimal("1700")
    assert Flag.IDENTITY_WARNING in p.flags
    oechsle = next(o for o in p.offers if o.store == "oechsle")
    assert oechsle.fresh is False and oechsle.price == Decimal("1500")


def test_best_seller_per_offer_and_other_sellers():
    records = [rec("plazavea", "1700"), rec("plazavea", "1650", seller="Tercero", own=False, stock=1)]
    _, products, _ = contract(records)
    best = products.products[0].best
    assert (best.seller_name, best.other_sellers) == ("Tercero", 1)
    assert {Flag.THIRD_PARTY, Flag.LOW_STOCK} <= set(products.products[0].flags)


def test_daily_series_uses_lima_day_and_min_price():
    # 03:00 UTC del 20 dic sigue siendo 19 dic en Lima.
    late = rec("plazavea", "1600", days_ago=0, hour=3)
    records = [late, rec("plazavea", "1650", days_ago=1), rec("plazavea", "1700", days_ago=0)]
    assert lima_day(late.observed_at) == date(2026, 12, 19)
    _, _, [history] = contract(records)
    points = {p.date: p.price for p in history.series[0].points}
    assert points == {date(2026, 12, 19): Decimal("1600"), date(2026, 12, 20): Decimal("1700")}


def test_real_discount_needs_a_week():
    few = [rec("plazavea", "1700", days_ago=d) for d in range(3)]
    stats = contract(few)[1].products[0].stats
    assert stats.days_observed == 3 and stats.real_discount_pct is None

    # 10 días a 2000 y hoy 1800: 10 % más barato que la mediana (2000).
    many = [rec("plazavea", "2000", days_ago=d) for d in range(1, 11)] + [rec("plazavea", "1800")]
    stats = contract(many)[1].products[0].stats
    assert stats.median_30d == Decimal("2000.00")
    assert stats.real_discount_pct == pytest.approx(10.0)


def test_inflated_list_price_and_target():
    history = [rec("plazavea", "1700", days_ago=d) for d in range(1, 10)]
    today = rec("plazavea", "1650", list_price="2299")  # 2299 > 1700 * 1.15
    p = contract(history + [today], target=Decimal("1660"))[1].products[0]
    assert Flag.INFLATED_LIST_PRICE in p.flags and Flag.BELOW_TARGET in p.flags
    assert p.stats.advertised_discount_pct == pytest.approx(28.2)


def test_store_status_from_health():
    def h(store, hours_ago, ok, checked=1):
        errors = [] if ok else [OfferError(tracked_product="poco", sku_id="s", url="u", kind="blocked", detail="403")]
        return StoreHealth(run_at=NOW - timedelta(hours=hours_ago), store=store, runner="actions",
                           offers_checked=checked, offers_ok=int(ok), records_written=int(ok),
                           identity_warnings=0, errors=errors)

    health = {"plazavea": [h("plazavea", 30, True), h("plazavea", 5, False)],
              "oechsle": [h("oechsle", 50, True)]}
    meta, _, _ = contract([], health)
    status = {s.id: s for s in meta.stores}
    assert status["plazavea"].status is StoreStatus.DOWN
    assert status["plazavea"].last_ok_at == NOW - timedelta(hours=30)
    assert "403" in status["plazavea"].detail
    assert status["oechsle"].status is StoreStatus.STALE
    assert status["falabella"].status is StoreStatus.NEVER


def test_build_site_writes_contract(tmp_path):
    config = tmp_path / "products.yaml"
    stores = tmp_path / "stores.yaml"
    data = tmp_path / "data"
    stores.write_text("plazavea: {runner: actions}\noechsle: {runner: actions}\nfalabella: {runner: local}\n")
    save_products(ProductsConfig(products=[product()]), config)
    append_records([rec("plazavea", "1700")], data)
    append_health(StoreHealth(run_at=NOW, store="plazavea", runner="actions", offers_checked=1, offers_ok=1,
                              records_written=1, identity_warnings=0), data)
    web = Path(__file__).resolve().parent.parent / "web"
    out = tmp_path / "site"

    build_site(out=out, web=web, data_dir=data, config_path=config, stores_path=stores, now=NOW)

    assert (out / "index.html").exists() and (out / "js" / "main.js").exists()
    meta = json.loads((out / "data" / "meta.json").read_text(encoding="utf-8"))
    products = json.loads((out / "data" / "products.json").read_text(encoding="utf-8"))
    history = json.loads((out / "data" / "history" / "poco.json").read_text(encoding="utf-8"))
    assert meta["schema_version"] == products["schema_version"] == history["schema_version"] == SCHEMA_VERSION
    assert products["products"][0]["best"]["price"] == "1700"  # decimales como string
    assert history["series"][0]["points"][0]["date"] == "2026-12-20"
