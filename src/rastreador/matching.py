"""¿Es este SKU la misma variante que un producto ya vigilado?

No decide solo: propone y avisa. La decisión final la confirma quien agrega el
producto (ver ADR-001). Lo importante es detectar los conflictos que causan
mezclas como "8 GB con 12 GB" o "Pro con Pro Max", que en celulares, laptops
o discos cambian el precio por completo.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from rastreador.config import ProductConfig, ProductsConfig

CAPACITY_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(tb|gb|mb)\b")
RAM_SHORT_RE = re.compile(r"\b(\d+)\s*ram\b")  # "8RAM" en Oechsle
TOKEN_RE = re.compile(r"[a-z0-9]+")

COLORS = {
    "negro": "negro", "black": "negro",
    "blanco": "blanco", "white": "blanco",
    "azul": "azul", "blue": "azul",
    "verde": "verde", "green": "verde",
    "gris": "gris", "gray": "gris", "grey": "gris",
    "plata": "plata", "plateado": "plata", "silver": "plata",
    "dorado": "dorado", "gold": "dorado",
    "morado": "morado", "purple": "morado",
    "rosado": "rosado", "rosa": "rosado", "pink": "rosado",
    "rojo": "rojo", "red": "rojo",
}
# Palabras que distinguen modelos distintos de la misma línea.
MODEL_MODIFIERS = {"pro", "max", "plus", "ultra", "lite", "mini", "neo", "fe", "air"}
STOPWORDS = {
    "de", "con", "y", "el", "la", "los", "las", "en", "para", "a", "+", "celular", "smartphone",
    "telefono", "inteligente", "almacenamiento", "memoria", "ram", "rom", "interna", "camara",
    "potente", "rapido", "alto", "rendimiento", "gama", "android", "5g", "4g", "nuevo", "original",
}


def _fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


@dataclass(frozen=True)
class Signature:
    tokens: frozenset[str]
    capacities: frozenset[str]
    colors: frozenset[str]
    modifiers: frozenset[str]


def signature(title: str, attributes: dict[str, str] | None = None) -> Signature:
    text = _fold(" ".join([title, *(attributes or {}).values()]))
    capacities = {f"{n.replace(',', '.')}{u}" for n, u in CAPACITY_RE.findall(text)}
    capacities |= {f"{n}gb" for n in RAM_SHORT_RE.findall(text)}
    text_wo_caps = RAM_SHORT_RE.sub(" ", CAPACITY_RE.sub(" ", text))
    words = TOKEN_RE.findall(text_wo_caps)
    colors = {COLORS[w] for w in words if w in COLORS}
    modifiers = {w for w in words if w in MODEL_MODIFIERS}
    tokens = {w for w in words if w not in STOPWORDS and w not in COLORS}
    return Signature(frozenset(tokens), frozenset(capacities), frozenset(colors), frozenset(modifiers))


def conflicts(a: Signature, b: Signature) -> list[str]:
    """Diferencias que indican que NO es la misma variante."""
    out = []
    if a.capacities and b.capacities and not (a.capacities <= b.capacities or b.capacities <= a.capacities):
        out.append(f"capacidades distintas: {_fmt(a.capacities)} vs {_fmt(b.capacities)}")
    if a.colors and b.colors and not (a.colors & b.colors):
        out.append(f"color distinto: {_fmt(a.colors)} vs {_fmt(b.colors)}")
    if a.modifiers != b.modifiers:
        diff = a.modifiers ^ b.modifiers
        out.append(f"modelo distinto: aparece '{_fmt(diff)}' en uno y no en el otro")
    return out


def similarity(a: Signature, b: Signature) -> float:
    ta, tb = a.tokens | a.capacities, b.tokens | b.capacities
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _fmt(values: frozenset[str]) -> str:
    return ", ".join(sorted(values))


@dataclass
class Candidate:
    product: ProductConfig
    score: float
    conflicts: list[str] = field(default_factory=list)

    @property
    def compatible(self) -> bool:
        return not self.conflicts


def compare(product: ProductConfig, sig: Signature) -> Candidate:
    """Compara contra todas las ofertas del producto y se queda con la más parecida."""
    best = Candidate(product, 0.0, ["el producto no tiene ofertas"])
    for offer in product.offers:
        other = signature(offer.expected.title, offer.expected.attributes)
        cand = Candidate(product, similarity(sig, other), conflicts(sig, other))
        if (cand.compatible, cand.score) > (best.compatible, best.score):
            best = cand
    return best


def rank(config: ProductsConfig, title: str, attributes: dict[str, str], limit: int = 3) -> list[Candidate]:
    sig = signature(title, attributes)
    cands = [compare(p, sig) for p in config.products]
    cands.sort(key=lambda c: (c.compatible, c.score), reverse=True)
    return [c for c in cands if c.score > 0][:limit]
