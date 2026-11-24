# 002. Dashboard estático con contrato JSON versionado

- Estado: **aceptada**
- Fecha: 2026-11-24

## Contexto

El primer dashboard no necesita un gran diseño, pero tiene que ser fácil de mejorar después: cambiar el estilo, rehacer pantallas o pasar a un framework sin rehacer el cálculo. Además debe publicarse gratis, sin servidor (ADR-000).

## Decisión

1. **Todo el cálculo vive en Python** (`analysis.py`) y se publica como JSON con un contrato versionado (`contract.py`, `schema_version`). El frontend no recalcula precios ni reglas.
2. **Frontend sin paso de build**: HTML y módulos ES nativos, con una sola dependencia externa (Chart.js, con versión fija) aislada en `charts.js`. Cada responsabilidad tiene un solo archivo: tokens de diseño, textos, formato, acceso a datos y vistas.
3. **Sitio estático en GitHub Pages**, regenerado en cada push a `main` y después de cada revisión diaria.
4. **Datos de ejemplo reproducibles** (`scripts/demo_data.py`) para trabajar en el frontend sin esperar semanas de historial.

## Alternativas descartadas

- **Un framework (React, Svelte) desde el inicio**: agrega toolchain y dependencias antes de saber qué se quiere mostrar. Con el contrato fijo, migrar después es un cambio contenido en `web/`.
- **Calcular en el navegador a partir del JSONL**: duplicaría la lógica (Python para alertas, JS para mostrar) y las reglas podrían divergir. Además, el navegador tendría que descargar todo el historial.
- **Generar HTML desde Python (plantillas)**: mezcla cálculo y presentación, que es justo lo que se quiere separar.

## Consecuencias

- Un cambio de diseño solo toca `web/`. Un cambio en el cálculo solo toca Python, y si cambia el contrato, se ve como un error de versión.
- Chart.js se carga desde un CDN. Si el CDN falla, el gráfico muestra un aviso y el resto de la página funciona igual.
- El sitio es público, como el repo: muestra los productos vigilados y sus precios.
