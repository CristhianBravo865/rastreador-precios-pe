"""Genera el sitio estático: `web/` (frontend) + `data/` (JSON del contrato).

    rastreador build-site            -> site/
    site/
      index.html, css/, js/          copiados tal cual de web/
      data/meta.json                 tiendas, estado y antigüedad de los datos
      data/products.json             resumen por producto (mejor oferta, banderas...)
      data/history/<producto>.json   serie diaria por tienda

El frontend no tiene paso de build: se puede abrir con cualquier servidor
estático. Para cambiar el diseño solo se toca web/; para cambiar qué se
calcula, analysis.py y contract.py.
"""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from rastreador.analysis import build_contract
from rastreador.config import PRODUCTS_FILE, STORES_FILE, load_products, load_store_settings
from rastreador.storage import DATA_DIR, read_health, read_records

WEB_DIR = Path("web")
SITE_DIR = Path("site")


def _write(path: Path, model: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(model.model_dump_json(indent=1), encoding="utf-8", newline="\n")


def build_site(
    *,
    out: Path = SITE_DIR,
    web: Path = WEB_DIR,
    data_dir: Path = DATA_DIR,
    config_path: Path = PRODUCTS_FILE,
    stores_path: Path = STORES_FILE,
    now: datetime | None = None,
) -> dict[str, int]:
    meta, products, histories = build_contract(
        load_products(config_path),
        read_records(data_dir),
        read_health(data_dir),
        load_store_settings(stores_path),
        now or datetime.now(timezone.utc),
    )
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(web, out)
    _write(out / "data" / "meta.json", meta)
    _write(out / "data" / "products.json", products)
    for h in histories:
        _write(out / "data" / "history" / f"{h.product_id}.json", h)
    return {"products": len(products.products), "stores": len(meta.stores)}
