# 000. Dónde corre la revisión diaria

- Estado: **pendiente del resultado de la prueba en GitHub Actions**
- Fecha: 2026-11-24

## Contexto

Las primeras pruebas se hicieron desde una IP residencial. Muchas tiendas tratan peor a las IP de datacenter (Ripley ya bloquea con Cloudflare incluso desde IP residencial). Si GitHub Actions es bloqueado, el cron no puede correr allí.

## Prueba

El workflow `probe.yml` descarga un producto por tienda y reporta el resultado de cada una.

| Tienda | Local (residencial), 2026-11-24 | GitHub Actions |
|---|---|---|
| Falabella | ✅ | _pendiente_ |
| Oechsle | ✅ | _pendiente_ |
| Plaza Vea | ✅ | _pendiente_ |
| Promart | ✅ | _pendiente_ |
| Coolbox | ✅ | _pendiente_ |
| Estilos | ✅ | _pendiente_ |

## Opciones

1. **GitHub Actions con cron**: gratis en un repo público y sin máquina propia.
2. **Runner autoalojado en una PC con IP residencial**: funciona aunque bloqueen a los datacenters, pero la PC debe estar encendida a la hora del cron.
3. **Mixto**: Actions para las tiendas que respondan y runner local para el resto.

## Decisión

_Se completa con el resultado de la prueba._
