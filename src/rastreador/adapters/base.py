"""Contrato común de los adaptadores de tienda.

Cada adaptador separa dos pasos para que se pueda probar sin red:

- `request_url(url)`: qué hay que descargar para la URL de producto que pegó el usuario.
- `parse(body, url, store)`: convertir esa respuesta en observaciones. Es una función
  pura, y las pruebas la ejecutan sobre respuestas reales guardadas (fixtures).
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from rastreador.http import PoliteClient
    from rastreador.models import Observation


class ErrorKind(StrEnum):
    NETWORK = "network"      # sin conexión, timeout, DNS
    BLOCKED = "blocked"      # 403 / anti-bot: la tienda nos rechaza
    NOT_FOUND = "not_found"  # el producto ya no existe en esa URL
    HTTP = "http"            # otro error HTTP
    SCHEMA = "schema"        # la respuesta llegó, pero su formato cambió
    BAD_URL = "bad_url"      # la URL no es de un producto reconocible


class AdapterError(Exception):
    def __init__(self, kind: ErrorKind, detail: str):
        super().__init__(f"[{kind}] {detail}")
        self.kind = kind
        self.detail = detail


class Adapter(Protocol):
    name: str

    def request_url(self, url: str) -> str: ...

    def parse(self, body: str, url: str, store: str) -> list[Observation]: ...


def fetch(adapter: Adapter, client: PoliteClient, url: str, store: str) -> list[Observation]:
    resp = client.get(adapter.request_url(url))
    return adapter.parse(resp.text, url, store)
