"""Historial en archivos JSONL de solo agregar, versionados en git.

    data/observations/<tienda>/AAAA-MM.jsonl   una línea por oferta vista
    data/health/<tienda>.jsonl                 una línea por corrida y tienda

Un archivo por tienda permite que GitHub Actions (tiendas VTEX) y la PC local
(Falabella) hagan commit al mismo tiempo sin conflictos (ADR-000). JSONL se
lee bien en un diff de git, y la base SQLite para consultas se regenera a
partir de él.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from rastreador.adapters.base import ErrorKind
from rastreador.models import Observation

DATA_DIR = Path("data")


class Record(Observation):
    """Observación ligada al producto vigilado de config/products.yaml."""

    tracked_product: str
    identity_ok: bool = Field(description="False si el SKU ya no parece la variante que se agregó.")
    identity_issues: list[str] = Field(default_factory=list)


class OfferError(BaseModel):
    tracked_product: str
    sku_id: str
    url: str
    kind: ErrorKind
    detail: str


class StoreHealth(BaseModel):
    run_at: datetime
    store: str
    runner: str
    offers_checked: int
    offers_ok: int
    records_written: int
    identity_warnings: int
    errors: list[OfferError] = Field(default_factory=list)

    @property
    def status(self) -> str:
        if self.offers_ok == self.offers_checked and not self.identity_warnings:
            return "ok"
        if self.offers_ok == 0:
            return "down"
        return "degraded"


def _append(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        for line in lines:
            fh.write(line + "\n")


def append_records(records: list[Record], data_dir: Path = DATA_DIR) -> None:
    by_file: dict[Path, list[str]] = {}
    for r in records:
        path = data_dir / "observations" / r.store / f"{r.observed_at:%Y-%m}.jsonl"
        by_file.setdefault(path, []).append(r.model_dump_json(exclude_none=True))
    for path, lines in by_file.items():
        _append(path, lines)


def append_health(health: StoreHealth, data_dir: Path = DATA_DIR) -> None:
    _append(data_dir / "health" / f"{health.store}.jsonl", [health.model_dump_json()])


def read_records(data_dir: Path = DATA_DIR) -> list[Record]:
    records = []
    for path in sorted((data_dir / "observations").glob("*/*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(Record.model_validate_json(line))
    return records
