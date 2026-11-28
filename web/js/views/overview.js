// Vista principal: estado de las tiendas y una tarjeta por producto.

import { el } from "../dom.js";
import { formatAgo } from "../format.js";
import { TEXT } from "../labels.js";
import { flagBadges, priceBlock, sellerText, storeHealthStrip, storeNames } from "./shared.js";

function productCard(product, names) {
  const best = product.best;
  const available = product.offers.filter((o) => o.fresh && o.price != null && o.available).length;
  return el(
    "article",
    { class: "card stack" },
    el("a", { href: `#/producto/${encodeURIComponent(product.id)}` }, el("strong", {}, product.name)),
    best
      ? [
          priceBlock(best, { large: true }),
          el("div", { class: "muted" },
            `${TEXT.bestOffer}: ${names[best.store] ?? best.store} · ${sellerText(best)} · ${formatAgo(best.observed_at)}`),
        ]
      : el("p", { class: "muted" }, TEXT.noOffers),
    el("div", { class: "muted" }, `${available} de ${product.offers.length} tiendas con precio actual`),
    product.flags.length ? flagBadges(product.flags) : null,
  );
}

export function overviewView(meta, products) {
  const names = storeNames(meta);
  return [
    el("section", {}, el("h2", {}, "Tiendas"), storeHealthStrip(meta)),
    el(
      "section",
      {},
      el("h2", {}, "Productos"),
      products.length
        ? el("div", { class: "grid" }, products.map((p) => productCard(p, names)))
        : el("p", { class: "card empty muted" }, TEXT.noProducts),
    ),
  ];
}
