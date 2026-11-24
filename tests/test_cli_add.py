"""`rastreador add` sin red: el fetcher devuelve observaciones fijas."""

from datetime import date
from decimal import Decimal

import pytest
import yaml

from rastreador.cli import UsageError, add
from rastreador.config import load_products
from rastreador.models import Observation

TODAY = date(2026, 11, 24)


def obs(store, sku, title, price, seller="Tienda", attributes=None, product_id="p1"):
    return Observation(
        store=store, product_id=product_id, sku_id=sku, title=title, url="https://x/p",
        seller_id="1", seller_name=seller, sold_by_store=True, price=Decimal(price),
        available=True, stock=3, attributes=attributes or {},
    )


def fake(store, *observations):
    return lambda url: (store, list(observations))


FALABELLA_URL = "https://www.falabella.com.pe/falabella-pe/product/152322333/poco-x8-pro-negro-12gb-512gb"
PLAZAVEA_URL = "https://www.plazavea.com.pe/xiaomi-poco-x8-pro-512gb-12gb-black-102067258/p"


@pytest.fixture
def cfg(tmp_path):
    return tmp_path / "products.yaml"


def add_falabella(cfg):
    return add(FALABELLA_URL, config_path=cfg, today=TODAY, out=lambda s: None,
               fetcher=fake("falabella", obs("falabella", "152322334", "POCO X8 Pro Negro 12GB + 512GB.", "1799")))


def test_first_add_creates_product(cfg):
    product = add_falabella(cfg)
    assert product.id == "poco-x8-pro-negro-12gb-512gb"
    saved = load_products(cfg)
    assert saved.products[0].offers[0].sku_id == "152322334"
    assert saved.products[0].offers[0].added_at == TODAY
    assert cfg.read_text(encoding="utf-8").startswith("# Productos vigilados")
    yaml.safe_load(cfg.read_text(encoding="utf-8"))


def test_non_interactive_never_guesses(cfg):
    add_falabella(cfg)
    with pytest.raises(UsageError, match="--product poco-x8-pro-negro-12gb-512gb"):
        add(PLAZAVEA_URL, config_path=cfg, today=TODAY, out=lambda s: None,
            fetcher=fake("plazavea", obs("plazavea", "12397348", "Xiaomi Poco X8 Pro 512gb 12gb Black", "1699")))
    assert len(load_products(cfg).products) == 1  # no se guardó nada


def test_interactive_without_input_fails_cleanly(cfg, monkeypatch):
    add_falabella(cfg)

    def no_input(prompt=""):
        raise EOFError

    monkeypatch.setattr("builtins.input", no_input)
    with pytest.raises(UsageError, match="no hay entrada"):
        add(PLAZAVEA_URL, interactive=True, config_path=cfg, today=TODAY, out=lambda s: None,
            fetcher=fake("plazavea", obs("plazavea", "12397348", "Xiaomi Poco X8 Pro 512gb 12gb Black", "1699")))
    assert len(load_products(cfg).products) == 1


def test_interactive_choice_groups_product(cfg, monkeypatch):
    add_falabella(cfg)
    monkeypatch.setattr("builtins.input", lambda prompt="": "")  # Enter = opción sugerida
    product = add(PLAZAVEA_URL, interactive=True, config_path=cfg, today=TODAY, out=lambda s: None,
                  fetcher=fake("plazavea", obs("plazavea", "12397348", "Xiaomi Poco X8 Pro 512gb 12gb Black", "1699")))
    assert product.id == "poco-x8-pro-negro-12gb-512gb"
    assert len(product.offers) == 2


def test_unrelated_product_is_created_without_asking(cfg):
    add_falabella(cfg)
    add("https://www.coolbox.pe/x/p", config_path=cfg, today=TODAY, out=lambda s: None,
        fetcher=fake("coolbox", obs("coolbox", "77", "Audífonos Sony WH-1000XM6 Negro", "1299")))
    assert len(load_products(cfg).products) == 2


def test_explicit_product_groups_stores(cfg):
    add_falabella(cfg)
    product = add(PLAZAVEA_URL, product_id="poco-x8-pro-negro-12gb-512gb", config_path=cfg, today=TODAY,
                  out=lambda s: None,
                  fetcher=fake("plazavea", obs("plazavea", "12397348", "Xiaomi Poco X8 Pro 512gb 12gb Black", "1699")))
    assert [o.store for o in product.offers] == ["falabella", "plazavea"]


def test_conflicting_variant_is_refused_without_yes(cfg):
    add_falabella(cfg)
    wrong = fake("oechsle", obs("oechsle", "1001889971", "Poco X8 Pro 5G 8RAM 256GB Verde", "1669"))
    with pytest.raises(UsageError, match="no parece la misma variante"):
        add("https://www.oechsle.pe/x/p", product_id="poco-x8-pro-negro-12gb-512gb", config_path=cfg,
            today=TODAY, out=lambda s: None, fetcher=wrong)
    assert len(load_products(cfg).products[0].offers) == 1  # no se guardó nada


def test_duplicate_sku_is_refused(cfg):
    add_falabella(cfg)
    with pytest.raises(UsageError, match="ya se vigila"):
        add_falabella(cfg)


def test_multiple_skus_require_choice(cfg):
    two = fake("coolbox", obs("coolbox", "A", "Producto talla S", "10"), obs("coolbox", "B", "Producto talla M", "12"))
    with pytest.raises(UsageError, match="--sku"):
        add("https://www.coolbox.pe/x/p", config_path=cfg, today=TODAY, out=lambda s: None, fetcher=two)
    product = add("https://www.coolbox.pe/x/p", sku="B", config_path=cfg, today=TODAY, out=lambda s: None, fetcher=two)
    assert product.offers[0].sku_id == "B"


def test_same_name_gets_unique_id(cfg):
    add_falabella(cfg)
    other = fake("oechsle", obs("oechsle", "9", "POCO X8 Pro Negro 12GB + 512GB.", "1700"))
    product = add("https://www.oechsle.pe/x/p", new=True, config_path=cfg, today=TODAY, out=lambda s: None, fetcher=other)
    assert product.id == "poco-x8-pro-negro-12gb-512gb-2"
