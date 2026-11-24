// Todos los textos visibles que dependen de valores del contrato.
// Traducir o cambiar el tono del dashboard = editar este archivo.

export const STORE_STATUS = {
  ok: { text: "OK", tone: "ok" },
  degraded: { text: "Con problemas", tone: "warn" },
  down: { text: "Caída", tone: "bad" },
  stale: { text: "Sin datos recientes", tone: "warn" },
  never: { text: "Sin corridas", tone: "warn" },
};

export const FLAGS = {
  below_target: { text: "Bajo tu precio objetivo", tone: "ok" },
  inflated_list_price: { text: "Precio tachado inflado", tone: "warn",
    hint: "El precio 'normal' de la tienda supera en más de 15 % la mediana de los últimos 30 días." },
  low_stock: { text: "Pocas unidades", tone: "warn" },
  third_party: { text: "Vendedor tercero", tone: "warn",
    hint: "La mejor oferta no la vende la tienda, sino un vendedor de su marketplace." },
  identity_warning: { text: "Revisar variante", tone: "bad",
    hint: "Una tienda cambió el producto detrás del SKU vigilado; ese precio no se compara." },
};

export const RUNNER = { actions: "GitHub Actions", local: "PC local" };

export const TEXT = {
  bestOffer: "Mejor oferta",
  noOffers: "Ninguna tienda tiene ofertas disponibles para comparar.",
  noProducts: "Todavía no hay productos vigilados. Agrega uno con: rastreador add <url>",
  realDiscount: "Contra la mediana de 30 días",
  advertisedDiscount: "Descuento anunciado",
  needMoreDays: (n) => `Se necesita una semana de historial para calcularlo (hay ${n} día${n === 1 ? "" : "s"}).`,
  back: "← Todos los productos",
  staleOffer: "Dato viejo: la tienda no respondió en las últimas corridas. No compite por la mejor oferta.",
};
