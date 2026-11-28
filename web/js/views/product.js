// Vista de detalle: historial por tienda, descuento real y tabla de ofertas.

import { priceChart } from "../charts.js";
import { el, table } from "../dom.js";
import { formatAgo, formatDiscount, formatMoney } from "../format.js";
import { TEXT } from "../labels.js";
import { flagBadges, priceBlock, sellerText, storeNames } from "./shared.js";

function statsBlock(product) {
  const s = product.stats;
  return el(
    "div",
    { class: "grid" },
    el("div", { class: "card stack" },
      el("div", { class: "muted" }, TEXT.bestOffer),
      priceBlock(product.best, { large: true })),
    el("div", { class: "card stack" },
      el("div", { class: "muted" }, TEXT.advertisedDiscount),
      el("strong", {}, formatDiscount(s.advertised_discount_pct))),
    el("div", { class: "card stack" },
      el("div", { class: "muted" }, TEXT.realDiscount),
      s.real_discount_pct == null
        ? el("span", { class: "muted" }, TEXT.needMoreDays(s.days_observed))
        : el("strong", {}, formatDiscount(s.real_discount_pct)),
      s.min_30d ? el("div", { class: "muted" }, `Mínimo 30 días: ${formatMoney(s.min_30d)}`) : null),
  );
}

function offersTable(product, names) {
  const headers = [
    { text: "Tienda" }, { text: "Precio", num: true }, { text: "Tachado", num: true },
    { text: "Vendedor" }, { text: "Stock", num: true }, { text: "Visto" }, { text: "" },
  ];
  const rows = product.offers.map((o) => [
    names[o.store] ?? o.store,
    o.price != null ? formatMoney(o.price) : "—",
    o.list_price != null ? formatMoney(o.list_price) : "—",
    sellerText(o) + (o.other_sellers ? ` (+${o.other_sellers})` : ""),
    o.observed_at == null ? "—" : !o.available ? "agotado" : o.stock ?? "?",
    o.fresh ? formatAgo(o.observed_at) : el("span", { class: "badge warn", title: TEXT.staleOffer }, formatAgo(o.observed_at)),
    el("span", {},
      el("a", { href: o.url, target: "_blank", rel: "noopener" }, "Ver"),
      o.identity_ok ? null : el("span", { class: "badge bad", title: o.identity_issues.join("; ") }, " variante")),
  ]);
  return table(headers, rows);
}

export function productView(meta, product, history) {
  const names = storeNames(meta);
  const canvas = el("canvas", { "aria-label": `Historial de precios de ${product.name}`, role: "img" });
  const nodes = [
    el("p", {}, el("a", { href: "#/" }, TEXT.back)),
    el("h1", {}, product.name),
    product.flags.length ? flagBadges(product.flags) : null,
    statsBlock(product),
    el("h2", {}, "Historial por tienda"),
    el("div", { class: "card chart-box" }, canvas),
    el("h2", {}, "Ofertas"),
    offersTable(product, names),
  ];
  // El gráfico se dibuja después de insertar el canvas en la página.
  const afterRender = () => priceChart(canvas, history.series, names);
  return { nodes, afterRender };
}
