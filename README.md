# rastreador-precios-pe

Rastreador de precios para tiendas online de Perú. **Pegas la URL de un producto** (de cualquier categoría) y el sistema revisa su precio a diario, guarda el historial y avisa cuando baja o cuando una tienda deja de responder.

> Estado: **hito 3, corrida diaria**. Se agregan productos por URL y se revisan a diario. Todavía no hay dashboard ni alertas.

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

## Agregar un producto

```bash
uv run rastreador add "https://www.falabella.com.pe/falabella-pe/product/152322333/poco-x8-pro-negro-12gb-512gb"
uv run rastreador add "https://www.plazavea.com.pe/xiaomi-poco-x8-pro-512gb-12gb-black-102067258/p"
#  [plazavea] SKU 12397348
#        Xiaomi Poco X8 Pro 512gb 12gb Black
#        Color: Negro, Memoria RAM: 12GB, Memoria Interna: 512GB
#        S/ 1699.00 Telcelperu
#  ¿Es la misma variante que alguno de estos productos?
#    1. poco-x8-pro-12-gb-512-gb-negro (parecido 83%)
#    0. No, es un producto nuevo
#  Elige [1]:
uv run rastreador list
```

Si el SKU no parece la misma variante, avisa antes de agruparlo (por ejemplo, `capacidades distintas: 256gb, 8gb vs 12gb, 512gb`). Sin terminal, usa `--product <id>`, `--new`, `--sku` o `--yes`. Los productos quedan en [`config/products.yaml`](config/products.yaml). Por qué funciona así: [ADR-001](docs/decisions/001-productos-por-url-y-emparejamiento.md).

## Revisión diaria

```bash
uv run rastreador run --runner actions   # tiendas VTEX: lo hace el cron de GitHub Actions (daily.yml)
uv run rastreador run --runner local     # Falabella: lo hace una tarea programada en una PC
```

Falabella bloquea las IP de datacenter, así que se revisa desde una PC con IP residencial ([ADR-000](docs/decisions/000-donde-corre-el-cron.md)). [`scripts/install_task.ps1`](scripts/install_task.ps1) crea la tarea programada de Windows, que ejecuta [`scripts/run_local.ps1`](scripts/run_local.ps1) en un clon aparte del repo y sube los datos. Si la PC está apagada a la hora programada, la revisión corre al encenderla.

Cada corrida agrega:

- `data/observations/<tienda>/AAAA-MM.jsonl`: una línea por oferta (precio, precio tachado, vendedor, stock y `identity_ok`). Si la tienda cambió el producto detrás del mismo SKU, la línea se guarda con `identity_ok: false` y los motivos.
- `data/health/<tienda>.jsonl`: una línea por corrida con el estado `ok`, `degraded` o `down` y los errores tipados. Una tienda caída queda registrada como dato, no como un hueco.

Cada tienda escribe en su propio archivo, así que Actions y la PC pueden subir datos al mismo tiempo sin conflictos.

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
