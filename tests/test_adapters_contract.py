"""Pruebas de contrato: los adaptadores sobre respuestas reales guardadas.

Si una tienda cambia su formato, estas pruebas no lo detectan (usan respuestas
viejas). Para eso está el chequeo en vivo. Lo que sí garantizan es que el
parseo hace lo correcto con el formato conocido y que un formato roto produce
ErrorKind.SCHEMA en vez de datos basura.
"""

from decimal import Decimal
from pathlib import Path

import pytest

from rastreador.adapters.base import AdapterError, ErrorKind
from rastreador.adapters.falabella import FalabellaAdapter
from rastreador.adapters.vtex import VtexAdapter, slug_from_url
from rastreador.stores import store_for_url

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# --- VTEX -------------------------------------------------------------------

PLAZAVEA_URL = "https://www.plazavea.com.pe/xiaomi-poco-x8-pro-512gb-12gb-black-102067258/p"


def test_vtex_request_url_uses_slug_not_search():
    assert VtexAdapter().request_url(PLAZAVEA_URL + "?utm_source=x") == (
        "https://www.plazavea.com.pe/api/catalog_system/pub/products/search/"
        "xiaomi-poco-x8-pro-512gb-12gb-black-102067258/p"
    )


@pytest.mark.parametrize("url", ["https://www.oechsle.pe/celulares", "https://www.oechsle.pe/"])
def test_vtex_rejects_non_product_urls(url):
    with pytest.raises(AdapterError) as exc:
        slug_from_url(url)
    assert exc.value.kind is ErrorKind.BAD_URL


def test_vtex_third_party_seller_and_store_without_offer():
    obs = VtexAdapter().parse(load("vtex_plazavea_tercero.json"), PLAZAVEA_URL, "plazavea")
    # El vendedor "1" (Plaza Vea) aparece con precio 0: no es una oferta y se descarta.
    assert len(obs) == 1
    o = obs[0]
    assert o.seller_name == "Telcelperu"
    assert o.sold_by_store is False
    assert o.price == Decimal("1699.00")
    assert o.list_price == Decimal("2299.00")
    assert o.stock == 5 and o.available
    assert o.attributes == {"Color": "Negro", "Memoria RAM": "12GB", "Memoria Interna": "512GB"}


def test_vtex_store_own_seller():
    obs = VtexAdapter().parse(load("vtex_estilos_tienda.json"), "https://www.estilos.com.pe/x/p", "estilos")
    assert len(obs) == 1
    assert obs[0].sold_by_store is True
    assert obs[0].seller_id == "1"


def test_vtex_empty_result_is_not_found():
    with pytest.raises(AdapterError) as exc:
        VtexAdapter().parse("[]", PLAZAVEA_URL, "plazavea")
    assert exc.value.kind is ErrorKind.NOT_FOUND


@pytest.mark.parametrize(
    "body",
    [
        "<html>mantenimiento</html>",
        '{"error": "x"}',
        '[{"productId": "1", "productName": "x", "link": "y"}]',  # sin "items"
    ],
)
def test_vtex_schema_change_is_reported(body):
    with pytest.raises(AdapterError) as exc:
        VtexAdapter().parse(body, PLAZAVEA_URL, "plazavea")
    assert exc.value.kind is ErrorKind.SCHEMA


# --- Falabella --------------------------------------------------------------

FALABELLA_URL = "https://www.falabella.com.pe/falabella-pe/product/152322333/poco-x8-pro-negro-12gb-512gb"


def test_falabella_product_page():
    obs = FalabellaAdapter().parse(load("falabella_producto.html"), FALABELLA_URL, "falabella")
    assert len(obs) == 1
    o = obs[0]
    assert (o.product_id, o.sku_id) == ("152322333", "152322334")
    assert o.price == Decimal("1799.00")
    assert o.list_price == Decimal("1999.00")
    assert o.seller_name == "XIAOMI TIENDA OFICIAL"
    assert o.sold_by_store is None  # Falabella no lo expone de forma fiable
    assert o.stock is None  # stockUnits no es fiable
    assert o.available
    assert o.attributes == {"Color": "Negro", "Tamaño": "512 GB"}


def test_falabella_card_price_is_kept_apart():
    html = load("falabella_producto.html").replace(
        '"prices": [',
        '"prices": [{"type": "cmrPrice", "price": ["1,649"], "crossed": false}, ',
        1,
    )
    o = FalabellaAdapter().parse(html, FALABELLA_URL, "falabella")[0]
    assert o.card_price == Decimal("1649.00")
    assert o.price == Decimal("1799.00")  # el precio para cualquiera no cambia


def test_falabella_page_without_next_data_is_schema_error():
    with pytest.raises(AdapterError) as exc:
        FalabellaAdapter().parse("<html><body>nuevo diseño</body></html>", FALABELLA_URL, "falabella")
    assert exc.value.kind is ErrorKind.SCHEMA


def test_falabella_rejects_non_product_url():
    with pytest.raises(AdapterError) as exc:
        FalabellaAdapter().request_url("https://www.falabella.com.pe/falabella-pe/category/cat760706/Celulares")
    assert exc.value.kind is ErrorKind.BAD_URL


# --- Registro de tiendas ----------------------------------------------------


def test_store_lookup_by_domain():
    assert store_for_url("https://plazavea.com.pe/algo/p").id == "plazavea"
    assert store_for_url(PLAZAVEA_URL).source_group == store_for_url("https://www.promart.pe/x/p").source_group


def test_unsupported_store():
    with pytest.raises(AdapterError) as exc:
        store_for_url("https://simple.ripley.com.pe/producto")
    assert exc.value.kind is ErrorKind.BAD_URL
