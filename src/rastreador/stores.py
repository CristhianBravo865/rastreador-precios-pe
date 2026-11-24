"""Registro de tiendas soportadas: dominio → adaptador.

`source_group` agrupa tiendas que comparten catálogo (Plaza Vea y Promart
pertenecen al mismo grupo y a menudo muestran las mismas ofertas). Sirve para no
contarlas como dos fuentes independientes al comparar.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from rastreador.adapters.base import Adapter, AdapterError, ErrorKind
from rastreador.adapters.falabella import FalabellaAdapter
from rastreador.adapters.vtex import VtexAdapter


@dataclass(frozen=True)
class Store:
    id: str
    name: str
    domain: str
    adapter: Adapter
    source_group: str


_vtex = VtexAdapter()
_falabella = FalabellaAdapter()

STORES: tuple[Store, ...] = (
    Store("falabella", "Falabella", "www.falabella.com.pe", _falabella, "falabella"),
    Store("oechsle", "Oechsle", "www.oechsle.pe", _vtex, "oechsle"),
    Store("plazavea", "Plaza Vea", "www.plazavea.com.pe", _vtex, "intercorp-marketplace"),
    Store("promart", "Promart", "www.promart.pe", _vtex, "intercorp-marketplace"),
    Store("coolbox", "Coolbox", "www.coolbox.pe", _vtex, "coolbox"),
    Store("estilos", "Estilos", "www.estilos.com.pe", _vtex, "estilos"),
)

def _bare(host: str) -> str:
    return host.lower().removeprefix("www.")


_BY_DOMAIN = {_bare(s.domain): s for s in STORES}


def store_for_url(url: str) -> Store:
    host = _bare(urlparse(url).netloc)
    try:
        return _BY_DOMAIN[host]
    except KeyError:
        supported = ", ".join(s.domain for s in STORES)
        raise AdapterError(ErrorKind.BAD_URL, f"tienda no soportada: {host}. Soportadas: {supported}") from None
