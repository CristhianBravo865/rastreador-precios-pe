"""Corrida diaria sin red: tiendas simuladas que responden, fallan o cambian el producto."""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from rastreador.adapters.base import AdapterError, ErrorKind
from rastreador.config import Expected, OfferConfig, ProductConfig, ProductsConfig, Runner, save_products
from rastreador.models import Observation
from rastreador.run import run, summary_markdown
from rastreador.storage import read_records

NOW = datetime(2026, 11, 25, 11, 17, tzinfo=timezone.utc)
FALA_URL = "https://www.falabella.com.pe/falabella-pe/product/1/poco"
PV_URL = "https://www.plazavea.com.pe/poco/p"
OE_URL = "https://www.oechsle.pe/poco/p"


def offer(store, url, sku, title):
    return OfferConfig(store=store, url=url, sku_id=sku, added_at=date(2026, 11, 24), expected=Expected(title=title))


def obs(store, sku, title, price, seller="Vendedor"):
    return Observation(
        store=store, product_id="x", sku_id=sku, title=title, url="u", seller_id=seller, seller_name=seller,
        sold_by_store=False, price=Decimal(price), available=True, stock=2,
    )


@pytest.fixture
def env(tmp_path):
    products = tmp_path / "products.yaml"
    stores = tmp_path / "stores.yaml"
    stores.write_text("falabella: {runner: local}\nplazavea: {runner: actions}\noechsle: {runner: actions}\n")
    save_products(ProductsConfig(products=[ProductConfig(
        id="poco", name="POCO X8 Pro 12/512 Negro",
        offers=[
            offer("falabella", FALA_URL, "F1", "POCO X8 Pro Negro 12GB + 512GB"),
            offer("plazavea", PV_URL, "P1", "Xiaomi Poco X8 Pro 512gb 12gb Black"),
            offer("oechsle", OE_URL, "O1", "POCO X8 Pro Negro 12GB RAM 512GB"),
        ],
    )]), products)
    return {"config_path": products, "stores_path": stores, "data_dir": tmp_path / "data", "now": NOW}


def test_runner_filter_and_records(env):
    calls = []

    def fetcher(store, url):
        calls.append(store)
        if store == "plazavea":
            return [obs("plazavea", "P1", "Xiaomi Poco X8 Pro 512gb 12gb Black", "1699", "Telcelperu"),
                    obs("plazavea", "P1", "Xiaomi Poco X8 Pro 512gb 12gb Black", "1750", "Otro")]
        return [obs("oechsle", "O1", "POCO X8 Pro Negro 12GB RAM 512GB", "1700")]

    results = run(runner=Runner.ACTIONS, fetcher=fetcher, **env)
    assert sorted(calls) == ["oechsle", "plazavea"]  # falabella es local
    assert {h.store: h.status for h in results} == {"plazavea": "ok", "oechsle": "ok"}
    records = read_records(env["data_dir"])
    assert len(records) == 3  # dos vendedores en Plaza Vea + uno en Oechsle
    assert all(r.tracked_product == "poco" and r.identity_ok and r.observed_at == NOW for r in records)
    assert (env["data_dir"] / "observations" / "plazavea" / "2026-11.jsonl").exists()
    assert (env["data_dir"] / "health" / "oechsle.jsonl").exists()


def test_blocked_store_is_recorded_as_down(env):
    def fetcher(store, url):
        raise AdapterError(ErrorKind.BLOCKED, "HTTP 403")

    [health] = run(runner=Runner.LOCAL, fetcher=fetcher, **env)
    assert health.store == "falabella" and health.status == "down"
    assert health.errors[0].kind is ErrorKind.BLOCKED
    assert read_records(env["data_dir"]) == []
    # La caída queda registrada como dato.
    assert "blocked" in (env["data_dir"] / "health" / "falabella.jsonl").read_text(encoding="utf-8")


def test_missing_sku_is_not_found(env):
    def fetcher(store, url):
        return [obs(store, "OTRO", "algo", "10")]

    results = run(only_stores={"oechsle"}, fetcher=fetcher, **env)
    assert results[0].status == "down"
    assert results[0].errors[0].kind is ErrorKind.NOT_FOUND


def test_sku_reused_for_another_variant_is_flagged(env):
    # La tienda cambió el producto detrás del mismo SKU: se guarda el precio,
    # pero marcado, para que no entre en las comparaciones.
    def fetcher(store, url):
        return [obs("oechsle", "O1", "Poco X8 Pro 5G 8RAM 256GB Verde", "1669")]

    [health] = run(only_stores={"oechsle"}, fetcher=fetcher, **env)
    assert health.status == "degraded" and health.identity_warnings == 1
    [record] = read_records(env["data_dir"])
    assert not record.identity_ok
    assert any("capacidades distintas" in i for i in record.identity_issues)


def test_runs_append_history(env):
    def fetcher(store, url):
        return [obs("oechsle", "O1", "POCO X8 Pro Negro 12GB RAM 512GB", "1700")]

    run(only_stores={"oechsle"}, fetcher=fetcher, **env)
    run(only_stores={"oechsle"}, fetcher=fetcher, **{**env, "now": NOW.replace(day=26)})
    assert [r.observed_at.day for r in read_records(env["data_dir"])] == [25, 26]


def test_store_without_runner_setting_is_an_error(env):
    env["stores_path"].write_text("falabella: {runner: local}\n")
    with pytest.raises(ValueError, match="falta indicar su runner"):
        run(fetcher=lambda s, u: [], **env)


def test_summary_mentions_problems(env):
    def fetcher(store, url):
        raise AdapterError(ErrorKind.SCHEMA, "la página no contiene __NEXT_DATA__")

    text = summary_markdown(run(runner=Runner.LOCAL, fetcher=fetcher, **env))
    assert "falabella" in text and "down" in text and "__NEXT_DATA__" in text
