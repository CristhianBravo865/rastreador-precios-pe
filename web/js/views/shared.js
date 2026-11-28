// Piezas de interfaz que usan varias vistas.

import { badge, el } from "../dom.js";
import { formatAgo, formatMoney } from "../format.js";
import { FLAGS, RUNNER, STORE_STATUS } from "../labels.js";

export function storeNames(meta) {
  return Object.fromEntries(meta.stores.map((s) => [s.id, s.name]));
}

export function flagBadges(flags) {
  return el("div", { class: "row" }, flags.map((f) => badge(FLAGS[f] ?? { text: f })));
}

export function priceBlock(offer, { large = false } = {}) {
  if (!offer || offer.price == null) return el("span", { class: "muted" }, "Sin precio");
  return el(
    "span",
    { class: "row" },
    el("span", { class: `price ${large ? "price-lg" : ""}` }, formatMoney(offer.price)),
    offer.list_price ? el("span", { class: "price strike" }, formatMoney(offer.list_price)) : null,
  );
}

export function sellerText(offer) {
  if (!offer?.seller_name) return "—";
  const who = offer.sold_by_store === true ? " (la tienda)" : offer.sold_by_store === false ? " (tercero)" : "";
  return offer.seller_name + who;
}

export function storeHealthStrip(meta) {
  return el(
    "div",
    { class: "row" },
    meta.stores.map((s) => {
      const status = STORE_STATUS[s.status] ?? { text: s.status };
      const hint = [
        `Corre en: ${RUNNER[s.runner] ?? s.runner}`,
        `Última corrida: ${formatAgo(s.last_run_at)}`,
        `Último dato válido: ${formatAgo(s.last_ok_at)}`,
        s.detail,
      ].filter(Boolean).join("\n");
      return badge({ text: `${s.name}: ${status.text}`, tone: status.tone, hint });
    }),
  );
}
