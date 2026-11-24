# rastreador-precios-pe

Rastreador de precios para tiendas online de Perú. **Pegas la URL de un producto** (de cualquier categoría) y el sistema revisa su precio a diario, guarda el historial y avisa cuando baja o cuando una tienda deja de responder.

> Estado: **hito 0 terminado**. Las tiendas VTEX responden desde GitHub Actions; Falabella bloquea las IP de datacenter y se revisará desde una PC con IP residencial ([ADR-000](docs/decisions/000-donde-corre-el-cron.md)). Todavía no hay corrida diaria ni dashboard.

## Por qué por URL y no un buscador

Un buscador tendría que emparejar el mismo producto entre tiendas que lo nombran distinto (resolución de entidades), filtrar resultados ruidosos y hacer muchas más peticiones. Con la URL, el usuario fija el producto exacto y el sistema se dedica a lo que sí puede garantizar: seguir ese SKU, validar que no cambió y guardar su historial. Esto también evita mezclar variantes (8 GB con 12 GB, por ejemplo).

## Tiendas soportadas

| Tienda | Cómo se leen los datos | Grupo de catálogo | Dónde corre |
|---|---|---|---|
| Falabella | JSON `__NEXT_DATA__` de la página de producto | falabella | PC local (bloquea datacenters) |
| Oechsle | API pública de catálogo VTEX | oechsle | GitHub Actions |
| Plaza Vea | API pública de catálogo VTEX | intercorp-marketplace | GitHub Actions |
| Promart | API pública de catálogo VTEX | intercorp-marketplace | GitHub Actions |
| Coolbox | API pública de catálogo VTEX | coolbox | GitHub Actions |
| Estilos | API pública de catálogo VTEX | estilos | GitHub Actions |

Plaza Vea y Promart comparten catálogo y a menudo las mismas ofertas, así que cuentan como una sola fuente al comparar. Lo que queda fuera y por qué está en [docs/LIMITATIONS.md](docs/LIMITATIONS.md).

## Qué guarda cada observación

Precio para cualquier cliente, precio "normal" tachado, precio con tarjeta de la tienda (aparte), **vendedor** y si es la propia tienda o un tercero del marketplace, disponibilidad y stock (solo cuando la tienda lo informa de forma fiable). Ver [`models.py`](src/rastreador/models.py).

## Desarrollo

Requiere [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run pytest                                   # pruebas sin red, con fixtures reales recortados
uv run python -m rastreador.probe               # ¿responden las tiendas desde aquí?
uv run python scripts/save_fixture.py <url> <nombre>   # guardar una respuesta real como fixture
```

## Política de peticiones

Pocas, espaciadas e identificadas: un User-Agent propio que apunta a este repositorio, al menos 2 s entre peticiones al mismo dominio, reintentos con espera solo ante errores transitorios y una petición por producto al día. Se usan solo datos públicos de páginas de producto; no se usan cuentas, no se evaden protecciones anti-bot y no se recorren catálogos.

## Decisiones

Registradas en [docs/decisions/](docs/decisions/).
