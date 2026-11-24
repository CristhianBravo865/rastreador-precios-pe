"""Emparejamiento de variantes con títulos reales de las tiendas (2026-11-24)."""

import pytest

from rastreador.matching import conflicts, signature, similarity

FALABELLA = signature("POCO X8 Pro Negro 12GB + 512GB.", {"Color": "Negro", "Tamaño": "512 GB"})


@pytest.mark.parametrize(
    "title, attributes",
    [
        ("Xiaomi Poco X8 Pro 512gb 12gb Black", {"Color": "Negro", "Memoria RAM": "12GB", "Memoria Interna": "512GB"}),
        ("POCO X8 Pro Negro 12GB RAM 512GB Almacenamiento - Potente y Rápido", {}),
    ],
)
def test_same_variant_named_differently(title, attributes):
    other = signature(title, attributes)
    assert conflicts(FALABELLA, other) == []
    assert similarity(FALABELLA, other) >= 0.6


@pytest.mark.parametrize(
    "title, expected",
    [
        ("Poco X8 Pro 5G 8RAM 256GB Verde", "capacidades distintas"),
        ("Xiaomi Poco X8 Pro 512gb 8gb Negro Ps35960113", "capacidades distintas"),
        ("Celular Xiaomi Poco X8 Pro Max 5G 512GB, 12GB RAM, negro", "modelo distinto"),
        ("POCO X8 Pro Azul 12GB + 512GB", "color distinto"),
    ],
)
def test_different_variant_is_flagged(title, expected):
    found = conflicts(FALABELLA, signature(title))
    assert any(expected in c for c in found), found


def test_title_without_capacities_is_not_a_conflict():
    # Sin datos no se puede afirmar que sea distinto: se deja a criterio de quien agrega.
    assert conflicts(FALABELLA, signature("Poco X8 Pro Telefono Inteligente Alto Rendimiento")) == []


def test_works_outside_phones():
    laptop_a = signature("Laptop Lenovo IdeaPad Slim 3 16GB 512GB SSD Gris")
    laptop_b = signature("Lenovo IdeaPad Slim 3 Gray 16 GB RAM 512 GB")
    laptop_c = signature("Laptop Lenovo IdeaPad Slim 3 8GB 512GB SSD Gris")
    assert conflicts(laptop_a, laptop_b) == []
    assert conflicts(laptop_a, laptop_c)
