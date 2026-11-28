"""Interfaz de línea de comandos.

    rastreador add <url>     agrega un producto a vigilar a partir de su URL
    rastreador list          muestra los productos vigilados
    rastreador run           revisa precios y los agrega al historial
    rastreador build-site    genera el dashboard estático en site/

`add` es interactivo si la terminal lo permite. Todas sus preguntas tienen una
opción equivalente (--sku, --product, --new, --name, --yes) para usarlo desde
scripts y pruebas.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from pathlib import Path

from rastreador.adapters.base import AdapterError, fetch
from rastreador.config import (
    PRODUCTS_FILE,
    Runner,
    Expected,
    OfferConfig,
    ProductConfig,
    load_products,
    save_products,
    slugify,
)
from rastreador.http import PoliteClient
from rastreador.matching import Candidate, compare, rank, signature
from rastreador.models import Observation
from rastreador.run import run, summary_markdown, write_github_summary
from rastreador.stores import store_for_url

AUTO_MATCH_SCORE = 0.6

Fetcher = Callable[[str], tuple[str, list[Observation]]]


class UsageError(Exception):
    pass


def default_fetcher(url: str) -> tuple[str, list[Observation]]:
    store = store_for_url(url)
    with PoliteClient() as client:
        return store.id, fetch(store.adapter, client, url, store.id)


def _group_by_sku(obs: list[Observation]) -> dict[str, list[Observation]]:
    groups: dict[str, list[Observation]] = {}
    for o in obs:
        groups.setdefault(o.sku_id, []).append(o)
    return groups


def _describe_sku(offers: list[Observation]) -> str:
    first = offers[0]
    attrs = ", ".join(f"{k}: {v}" for k, v in first.attributes.items())
    sellers = "; ".join(
        f"S/ {o.price} {o.seller_name}{'' if o.available else ' (sin stock)'}"
        for o in sorted(offers, key=lambda o: o.price)
    )
    return f"{first.title}\n      {attrs or 'sin atributos'}\n      {sellers}"


def _ask(prompt: str, valid: Callable[[str], bool], default: str | None = None) -> str:
    while True:
        suffix = f" [{default}]" if default else ""
        try:
            answer = input(f"{prompt}{suffix}: ").strip() or (default or "")
        except EOFError:
            print()
            raise UsageError(
                "no hay entrada para responder; usa las opciones --sku, --product, --new o --yes"
            ) from None
        if valid(answer):
            return answer
        print("  Respuesta no válida.")


def add(
    url: str,
    *,
    sku: str | None = None,
    product_id: str | None = None,
    new: bool = False,
    name: str | None = None,
    target_price: Decimal | None = None,
    assume_yes: bool = False,
    interactive: bool = False,
    config_path: Path = PRODUCTS_FILE,
    fetcher: Fetcher = default_fetcher,
    out: Callable[[str], None] = print,
    today: date | None = None,
) -> ProductConfig:
    if product_id and new:
        raise UsageError("usa --product o --new, no ambos")

    config = load_products(config_path)
    store_id, observations = fetcher(url)
    groups = _group_by_sku(observations)
    if not groups:
        raise UsageError("la tienda no muestra ninguna oferta con precio para esta URL")

    # 1) Qué SKU (variante) vigilar
    sku_ids = list(groups)
    if sku:
        if sku not in groups:
            raise UsageError(f"el SKU {sku} no está en esta página. Disponibles: {', '.join(sku_ids)}")
        chosen_sku = sku
    elif len(sku_ids) == 1:
        chosen_sku = sku_ids[0]
    elif interactive:
        out("La página tiene varias variantes:")
        for i, s in enumerate(sku_ids, 1):
            out(f"  {i}. {_describe_sku(groups[s])}")
        n = _ask("¿Cuál vigilar?", lambda a: a.isdigit() and 1 <= int(a) <= len(sku_ids))
        chosen_sku = sku_ids[int(n) - 1]
    else:
        raise UsageError(f"la página tiene varias variantes; elige una con --sku: {', '.join(sku_ids)}")

    offers = groups[chosen_sku]
    first = offers[0]
    out(f"[{store_id}] SKU {chosen_sku}\n      {_describe_sku(offers)}")

    existing = config.find_offer(store_id, chosen_sku)
    if existing:
        raise UsageError(f"ya se vigila: {store_id} SKU {chosen_sku} en el producto '{existing[0].id}'")

    # 2) ¿A qué producto pertenece? (la misma variante en otras tiendas)
    candidates = rank(config, first.title, first.attributes)
    sig = signature(first.title, first.attributes)
    product = _choose_product(config, candidates, sig, product_id, new, assume_yes, interactive, out)

    offer = OfferConfig(
        store=store_id,
        url=url,
        sku_id=chosen_sku,
        added_at=today or date.today(),
        expected=Expected(title=first.title, attributes=first.attributes),
    )

    if product is None:
        product_name = name or first.title.strip().rstrip(".")
        if interactive and not name and not assume_yes:
            product_name = _ask("Nombre del producto", lambda a: bool(a), product_name)
        base_id = slugify(product_name)
        new_id, n = base_id, 2
        while config.get(new_id):
            new_id, n = f"{base_id}-{n}", n + 1
        product = ProductConfig(id=new_id, name=product_name, target_price=target_price, offers=[offer])
        config.products.append(product)
        out(f"Nuevo producto: {product.id}")
    else:
        product.offers.append(offer)
        if target_price is not None:
            product.target_price = target_price
        out(f"Agregado a: {product.id} ({len(product.offers)} tiendas)")

    save_products(config, config_path)
    return product


def _choose_product(config, candidates: list[Candidate], sig, product_id, new, assume_yes, interactive, out):
    if new:
        return None
    if product_id:
        product = config.get(product_id)
        if product is None:
            raise UsageError(f"no existe el producto '{product_id}'")
        cand = compare(product, sig)
        if cand.conflicts:
            out("  Aviso: " + "; ".join(cand.conflicts))
            if not assume_yes and not (interactive and _ask("¿Agregarlo igual? (s/n)", lambda a: a in "sn", "n") == "s"):
                raise UsageError("cancelado: el SKU no parece la misma variante (usa --yes para forzarlo)")
        return product

    if not candidates:
        return None
    if interactive:
        out("¿Es la misma variante que alguno de estos productos?")
        for i, c in enumerate(candidates, 1):
            note = "  ⚠ " + "; ".join(c.conflicts) if c.conflicts else ""
            out(f"  {i}. {c.product.id} (parecido {c.score:.0%}){note}")
        out("  0. No, es un producto nuevo")
        best = candidates[0]
        default = "1" if best.compatible and best.score >= AUTO_MATCH_SCORE else "0"
        n = int(_ask("Elige", lambda a: a.isdigit() and 0 <= int(a) <= len(candidates), default))
        return candidates[n - 1].product if n else None

    # Sin terminal no se adivina en ningún sentido: si hay un parecido fuerte,
    # no se guarda nada y se pide decidir de forma explícita.
    best = candidates[0]
    if best.compatible and best.score >= AUTO_MATCH_SCORE:
        raise UsageError(
            f"parece la misma variante que '{best.product.id}' (parecido {best.score:.0%}). "
            f"Usa --product {best.product.id} para agruparlo o --new para crear otro producto"
        )
    return None


def list_products(config_path: Path = PRODUCTS_FILE, out: Callable[[str], None] = print) -> None:
    config = load_products(config_path)
    if not config.products:
        out("No hay productos. Agrega uno con: rastreador add <url>")
        return
    for p in config.products:
        target = f"  (aviso bajo S/ {p.target_price})" if p.target_price else ""
        out(f"{p.id}: {p.name}{target}")
        for o in p.offers:
            out(f"    - {o.store:<10} SKU {o.sku_id:<12} {o.url}")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="rastreador", description="Rastreador de precios por URL.")
    parser.add_argument("--config", type=Path, default=PRODUCTS_FILE, help="ruta de products.yaml")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="vigilar un producto a partir de su URL")
    p_add.add_argument("url")
    p_add.add_argument("--sku", help="SKU a vigilar si la página tiene varias variantes")
    g = p_add.add_mutually_exclusive_group()
    g.add_argument("--product", dest="product_id", help="agregar al producto existente con este id")
    g.add_argument("--new", action="store_true", help="crear un producto nuevo aunque haya parecidos")
    p_add.add_argument("--name", help="nombre del producto nuevo")
    p_add.add_argument("--target-price", type=Decimal, help="avisar si el precio baja de este valor")
    p_add.add_argument("--yes", "-y", action="store_true", help="no preguntar; aceptar avisos")

    sub.add_parser("list", help="mostrar los productos vigilados")

    p_run = sub.add_parser("run", help="revisar precios y agregarlos al historial")
    p_run.add_argument("--runner", choices=[r.value for r in Runner],
                       help="solo las tiendas asignadas a este runner en config/stores.yaml")
    p_run.add_argument("--store", action="append", dest="stores", help="solo esta tienda (repetible)")

    p_site = sub.add_parser("build-site", help="generar el dashboard estático en site/")
    p_site.add_argument("--out", type=Path, default=Path("site"))
    p_site.add_argument("--data-dir", type=Path, default=Path("data"))

    args = parser.parse_args(argv)
    try:
        if args.command == "add":
            add(
                args.url,
                sku=args.sku,
                product_id=args.product_id,
                new=args.new,
                name=args.name,
                target_price=args.target_price,
                assume_yes=args.yes,
                interactive=sys.stdin.isatty() and not args.yes,
                config_path=args.config,
            )
        elif args.command == "run":
            results = run(
                runner=Runner(args.runner) if args.runner else None,
                only_stores=set(args.stores) if args.stores else None,
                config_path=args.config,
            )
            report = summary_markdown(results)
            print(report)
            write_github_summary(report)
        elif args.command == "build-site":
            from rastreador.site.build import build_site

            counts = build_site(out=args.out, data_dir=args.data_dir, config_path=args.config)
            print(f"Sitio generado en {args.out}: {counts['products']} productos, {counts['stores']} tiendas")
        else:
            list_products(args.config)
    except (UsageError, AdapterError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
