# 000. Dónde corre la revisión diaria

- Estado: **aceptada**
- Fecha: 2026-11-24

## Contexto

Las primeras pruebas se hicieron desde una IP residencial. Muchas tiendas tratan peor a las IP de datacenter que a las residenciales (Ripley ya bloquea con Cloudflare incluso a las residenciales). Si GitHub Actions es bloqueado, el cron no puede correr allí.

## Prueba

El workflow `probe.yml` descarga un producto por tienda y reporta el resultado de cada una.

| Tienda | Local (residencial), 2026-11-24 | GitHub Actions (IP de datacenter), 2026-11-24 |
|---|---|---|
| Falabella | ✅ | ❌ HTTP 403 en 0.1 s |
| Oechsle | ✅ | ✅ |
| Plaza Vea | ✅ | ✅ |
| Promart | ✅ | ✅ |
| Coolbox | ✅ | ✅ |
| Estilos | ✅ | ✅ |

Corrida: [workflow 45424963342](https://github.com/CristhianBravo865/rastreador-precios-pe/actions/runs/45424963342). Es una sola muestra: el bloqueo de Falabella fue inmediato y por IP, no por volumen de peticiones. Con el mismo código, desde la IP residencial respondió.

Responder a un bloqueo por IP con proxies residenciales o rotando IP sería evadir una protección de forma deliberada, y este proyecto no lo hace (ver la política de peticiones del README).

## Opciones

1. **Todo en GitHub Actions**: gratis en un repo público y sin máquina propia, pero se pierde Falabella.
2. **Todo en la PC del autor**: un solo lugar de ejecución, pero no hay datos de ninguna tienda los días en que la PC está apagada.
3. **Mixto**: Actions para las tiendas VTEX y la PC del autor para Falabella.

Para la parte local había dos mecanismos:

- **Runner autoalojado de GitHub**: se descartó. En un repo público, un runner autoalojado puede terminar ejecutando código de cualquier PR externo en la PC, y GitHub desaconseja combinar las dos cosas.
- **Tarea programada de Windows** que corre `rastreador` localmente y hace `git push` de los datos: solo ejecuta código que ya está en la PC.

## Decisión

**Mixto, con tarea programada local para Falabella.**

- `daily.yml` (Actions, cron diario) revisa las tiendas VTEX y hace commit de sus observaciones.
- Una tarea del Programador de tareas de Windows revisa Falabella una vez al día. Si la PC está apagada a esa hora, corre cuando se encienda.
- Para que las dos fuentes no choquen al hacer commit, cada tienda escribe en su propio archivo: `data/observations/<tienda>/AAAA-MM.jsonl`. El script local hace `git pull --rebase` antes de `git push`.
- Dónde corre la revisión de cada tienda se define en la configuración de tiendas (`runner: actions | local`), no en el código.

## Consecuencias

- Los datos de Falabella pueden faltar algunos días. El dashboard muestra la antigüedad del dato de cada tienda ("hace X horas") en vez de esconder el hueco.
- La alerta de "adaptador caído" debe distinguir entre "Falabella no respondió" y "la tarea local no corrió", que se detecta porque no hay commit de Falabella en más de 48 h.
- Si Falabella deja de bloquear a los datacenters, migrar es solo cambiar `runner: local` por `actions`. El `probe.yml` se puede volver a lanzar a mano para comprobarlo.
