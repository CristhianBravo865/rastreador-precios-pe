"""Hito 0: ¿las tiendas responden desde donde corre esto?

Descarga una URL de producto por tienda y reporta, por cada una, si se obtuvieron
observaciones válidas o qué tipo de error hubo. Se ejecuta igual en tu PC
(IP residencial) y en GitHub Actions (IP de datacenter) para comparar.

Uso:
    python -m rastreador.probe config/probe_urls.txt

En GitHub Actions escribe además una tabla en el resumen del workflow
($GITHUB_STEP_SUMMARY).
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from rastreador.adapters.base import AdapterError, fetch
from rastreador.http import PoliteClient
from rastreador.stores import store_for_url


@dataclass
class ProbeResult:
    store: str
    url: str
    ok: bool
    detail: str
    seconds: float


def read_urls(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]


def probe(urls: list[str]) -> list[ProbeResult]:
    results = []
    with PoliteClient() as client:
        for url in urls:
            start = time.monotonic()
            store_id = "?"
            try:
                store = store_for_url(url)
                store_id = store.id
                obs = fetch(store.adapter, client, url, store.id)
                if obs:
                    best = min(obs, key=lambda o: o.price)
                    detail = f"{len(obs)} oferta(s); mín. S/ {best.price} ({best.seller_name})"
                else:
                    detail = "respuesta válida pero sin ofertas con precio"
                ok = True
            except AdapterError as exc:
                ok, detail = False, str(exc)
            results.append(ProbeResult(store_id, url, ok, detail, time.monotonic() - start))
    return results


def to_markdown(results: list[ProbeResult]) -> str:
    runner = "GitHub Actions" if os.environ.get("GITHUB_ACTIONS") else "local"
    rows = [
        f"## Prueba de acceso a tiendas ({runner})",
        "",
        "| Tienda | Resultado | Detalle | Segundos |",
        "|---|---|---|---|",
    ]
    for r in results:
        rows.append(f"| {r.store} | {'✅' if r.ok else '❌'} | {r.detail} | {r.seconds:.1f} |")
    ok = sum(r.ok for r in results)
    rows += ["", f"**{ok}/{len(results)} tiendas respondieron con datos válidos.**"]
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    path = Path(argv[0] if argv else "config/probe_urls.txt")
    report = to_markdown(probe(read_urls(path)))
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(report + "\n")
    # Siempre 0: el objetivo es informar, no fallar el workflow.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
