"""Cliente HTTP con la política de peticiones del proyecto.

Pocas peticiones, espaciadas e identificadas: un User-Agent propio que apunta
al repositorio, una pausa mínima entre peticiones al mismo dominio y
reintentos con espera solo ante errores transitorios.
"""

from __future__ import annotations

import time
from urllib.parse import urlparse

import httpx

from rastreador import __version__
from rastreador.adapters.base import AdapterError, ErrorKind

USER_AGENT = (
    f"rastreador-precios-pe/{__version__} "
    "(+https://github.com/CristhianBravo865/rastreador-precios-pe)"
)
MIN_DELAY_SECONDS = 2.0
RETRY_STATUSES = {429, 500, 502, 503, 504}
BLOCK_MARKERS = ("Just a moment...", "cf-chl", "captcha", "Access Denied")


class PoliteClient:
    def __init__(self, min_delay: float = MIN_DELAY_SECONDS, retries: int = 2, timeout: float = 30.0):
        self._client = httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept-Language": "es-PE,es;q=0.9"},
            timeout=timeout,
            follow_redirects=True,
        )
        self._min_delay = min_delay
        self._retries = retries
        self._last_request: dict[str, float] = {}

    def _wait_turn(self, host: str) -> None:
        last = self._last_request.get(host)
        if last is not None:
            remaining = self._min_delay - (time.monotonic() - last)
            if remaining > 0:
                time.sleep(remaining)
        self._last_request[host] = time.monotonic()

    def get(self, url: str, **kwargs) -> httpx.Response:
        host = urlparse(url).netloc
        for attempt in range(self._retries + 1):
            self._wait_turn(host)
            try:
                resp = self._client.get(url, **kwargs)
            except httpx.TransportError as exc:
                if attempt == self._retries:
                    raise AdapterError(ErrorKind.NETWORK, f"{type(exc).__name__}: {exc}") from exc
                time.sleep(2 ** (attempt + 1))
                continue

            if resp.status_code in RETRY_STATUSES and attempt < self._retries:
                time.sleep(2 ** (attempt + 1))
                continue
            check_blocked(resp)
            return resp
        raise AssertionError("inalcanzable")

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> PoliteClient:
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def check_blocked(resp: httpx.Response) -> None:
    """Distingue un bloqueo anti-bot de un error HTTP corriente."""
    if resp.status_code < 400:
        return
    # Solo se buscan marcadores en respuestas de error: una página normal puede
    # mencionar "captcha" en sus scripts sin estar bloqueándonos.
    head = resp.text[:5000] if resp.headers.get("content-type", "").startswith("text/") else ""
    if resp.status_code in (403, 429) or any(m in head for m in BLOCK_MARKERS):
        raise AdapterError(ErrorKind.BLOCKED, f"HTTP {resp.status_code}, posible protección anti-bot")
    if resp.status_code == 404:
        raise AdapterError(ErrorKind.NOT_FOUND, "HTTP 404")
    if resp.status_code >= 400:
        raise AdapterError(ErrorKind.HTTP, f"HTTP {resp.status_code}")
