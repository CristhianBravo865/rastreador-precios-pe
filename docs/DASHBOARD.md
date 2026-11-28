# Dashboard: cómo está hecho y cómo mejorarlo

El dashboard está separado en dos mitades que se pueden cambiar por separado:

```
data/*.jsonl ──► analysis.py ──► contract.py ──► site/data/*.json ──► web/ (HTML + JS)
                 (Python: calcula todo)          (contrato versionado)   (solo dibuja)
```

- **Python decide qué es verdad**: la mejor oferta, el descuento real, las banderas y el estado de cada tienda se calculan en [`analysis.py`](../src/rastreador/analysis.py), y además están probados.
- **El frontend solo presenta**: lee los JSON y no recalcula nada. Se puede reescribir entero (otro diseño, React, Svelte, una app) sin tocar Python, siempre que lea el mismo contrato.

## Trabajar en el frontend

```bash
uv run python scripts/demo_data.py demo-data           # 46 días de datos de EJEMPLO
uv run rastreador build-site --data-dir demo-data      # -> site/
python -m http.server 8000 -d site                     # http://localhost:8000
```

Los datos de ejemplo cubren los casos que hay que saber mostrar: una tienda caída, una sin datos recientes, un precio tachado inflado, pocas unidades, un vendedor tercero y un SKU reutilizado para otra variante. Después de editar `web/`, vuelve a correr `build-site`, que copia `web/` a `site/`.

## Dónde cambiar cada cosa

| Quiero cambiar… | Archivo |
|---|---|
| Colores, tipografía, espacios, modo oscuro | [`web/css/tokens.css`](../web/css/tokens.css) (base.css solo usa sus variables) |
| Textos, nombres de banderas y estados | [`web/js/labels.js`](../web/js/labels.js) |
| Formato de dinero y fechas | [`web/js/format.js`](../web/js/format.js) |
| Librería de gráficos | [`web/js/charts.js`](../web/js/charts.js) (el único archivo que conoce Chart.js) |
| Dónde y cómo se cargan los datos | [`web/js/api.js`](../web/js/api.js) |
| Una pantalla | [`web/js/views/`](../web/js/views/) |
| Qué se calcula | [`analysis.py`](../src/rastreador/analysis.py) y luego [`contract.py`](../src/rastreador/site/contract.py) |

El frontend no tiene paso de build ni dependencias que instalar, salvo Chart.js desde un CDN con versión fija. Si algún día conviene usar Vite, React u otra herramienta, el cambio queda dentro de `web/`, siempre que su resultado se copie a `site/`.

## El contrato (`schema_version: 1`)

Definido con pydantic en [`contract.py`](../src/rastreador/site/contract.py), que es la referencia exacta.

| Archivo | Contenido |
|---|---|
| `data/meta.json` | `generated_at`, `stale_after_hours` y `stores[]` con `status` (`ok`, `degraded`, `down`, `stale`, `never`), `runner`, `last_run_at`, `last_ok_at` y `detail`. |
| `data/products.json` | `products[]` con `best` (la mejor oferta), `offers[]` (lo último visto por tienda, con `fresh`, vendedor, stock e identidad), `stats` (mínimo y mediana de 30 días, descuento anunciado y real) y `flags[]`. |
| `data/history/<id>.json` | `series[]` por tienda, con un punto por día de Lima: el precio más bajo entre vendedores ese día. |

Convenciones:

- Los precios son **strings decimales** (`"1799.00"`), para no perder exactitud en JSON.
- Las fechas y horas están en ISO 8601. Las horas van en UTC y los días (`date`) son días de Lima.
- **Agregar** un campo opcional no rompe a nadie. **Quitar, renombrar o cambiar el significado** de un campo obliga a subir `SCHEMA_VERSION`. `web/js/api.js` rechaza versiones que no conoce, así que una incompatibilidad se ve como un error claro y no como una pantalla rota en silencio.

## Reglas de cálculo que el frontend da por hechas

- Solo compiten por la "mejor oferta" las ofertas **frescas** (vistas en las últimas 36 h), **disponibles** y con **identidad confirmada**.
- El **descuento real** compara contra la mediana propia de 30 días y solo existe con 7 días o más de historial. Antes de eso es `null`, y la interfaz lo dice en vez de mostrar 0.
- **Precio tachado inflado**: el precio "normal" supera en más de 15 % la mediana propia.
