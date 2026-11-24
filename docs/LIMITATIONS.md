# Límites conocidos

Este proyecto no usa APIs oficiales para consumidores, porque ninguna de estas tiendas las ofrece. Todo lo que lee es público, pero **no está documentado ni garantizado**: puede cambiar o cerrarse sin aviso. Por eso los adaptadores validan el formato y reportan `schema` cuando cambia, en lugar de guardar datos incorrectos.

## Tiendas fuera de alcance

| Tienda | Motivo |
|---|---|
| Ripley | Cloudflare responde 403 ("Just a moment...") a peticiones que no vienen de un navegador. Entrar requeriría un navegador automatizado para evadir la protección, y el proyecto no lo hace. |
| Mercado Libre | La API pública responde 400/403 sin autenticación de desarrollador y la web muestra verificación anti-bot. Podría añadirse con OAuth de desarrollador en el futuro. |
| Hiraoka, La Curacao, Tai Loy | Solo HTML sin datos estructurados. Hiraoka está prevista para la fase 2. |
| Tottus | Misma plataforma que Falabella; prevista para la fase 2. |

## Datos que no son fiables

- **Stock en Falabella:** `stockUnits` vale 0 incluso en productos que se pueden comprar. Se guarda solo la disponibilidad.
- **Vendedor propio en Falabella:** no se expone de forma fiable si vende Falabella o un tercero (`sold_by_store = null`).
- **Precio "normal" tachado:** lo fija cada tienda y puede estar inflado. El descuento real se calculará contra el historial propio (hito 5).
- **Stock en VTEX:** algunas tiendas informan cantidades simbólicas. Se guarda el valor tal cual.

## Términos de uso

Los `robots.txt` de las tiendas probadas no prohíben las rutas usadas, pero eso no equivale a un permiso. El volumen es mínimo (una petición por producto vigilado al día) y el uso es personal y no comercial.
