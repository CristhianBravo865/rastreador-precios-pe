# 001. Productos por URL y emparejamiento confirmado por una persona

- Estado: **aceptada**
- Fecha: 2026-11-24

## Contexto

El problema original era comparar ofertas entre tiendas sin mezclar variantes: la misma búsqueda devolvía el POCO X8 Pro de 8 GB y el de 12 GB, o el Pro y el Pro Max, como si fueran el mismo producto. El proyecto debe servir para cualquier categoría, no solo celulares.

## Opciones descartadas

- **Buscador libre**: la búsqueda VTEX es ruidosa (devolvió un lápiz de cejas al buscar "poco x8 pro") y falla con espacios en algunas tiendas. Además obliga a emparejar productos entre tiendas de forma automática (resolución de entidades), que en cualquier categoría es un problema abierto. Un historial de cualquier producto también exigiría recorrer catálogos enteros a diario.
- **Emparejamiento automático**: un error agrupa variantes distintas en silencio, y ese era justamente el problema que había que resolver.

## Decisión

1. **El usuario pega la URL del producto.** Cada oferta fija `(tienda, sku_id)`. La revisión diaria nunca busca por texto.
2. **El sistema propone y una persona decide.** `rastreador add` compara el SKU nuevo con los productos ya vigilados y:
   - calcula un parecido (Jaccard de palabras normalizadas y capacidades), solo para ordenar sugerencias;
   - detecta **conflictos** que indican otra variante: capacidades distintas (`12gb/512gb` frente a `8gb/256gb`, con "8RAM" de Oechsle normalizado), color distinto (con equivalencias inglés y español) y modificadores de modelo (`pro`, `max`, `plus`, `ultra`, `lite`, `mini`…);
   - en modo interactivo pregunta y ofrece la mejor sugerencia por defecto;
   - sin terminal **no adivina**: si hay un parecido fuerte, falla sin guardar nada y pide `--product` o `--new`. Agrupar una variante con conflictos exige confirmarlo o pasar `--yes`.
3. **Se guarda el título y los atributos del SKU al agregarlo** (`expected`). La revisión diaria podrá detectar si la tienda reutilizó el SKU o la URL para otro producto.

## Consecuencias

- Agregar un producto lleva unos segundos de trabajo humano. A cambio, ninguna comparación mezcla variantes por un error de emparejamiento.
- Las reglas de conflicto son genéricas (capacidades, color y modelo) y sirven también para laptops, discos o memorias. Otras categorías (tallas, pulgadas) pueden añadir reglas sin cambiar el flujo.
- Las reglas tienen falsos negativos: si un título no menciona capacidades, no se puede afirmar que sean distintas y se deja a criterio de la persona.
