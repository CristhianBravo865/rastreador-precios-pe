// Envoltorio de la librería de gráficos. Es el único archivo que conoce Chart.js:
// cambiar de librería (o dibujar SVG a mano) = reescribir este módulo.

import { formatDate, formatMoney } from "./format.js";

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function storeColor(store) {
  return cssVar(`--store-${store}`) || cssVar("--store-default");
}

/**
 * Gráfico de precio diario por tienda.
 * @param {HTMLCanvasElement} canvas
 * @param {{store: string, points: {date: string, price: string}[]}[]} series
 * @param {Record<string, string>} storeNames  id de tienda -> nombre visible
 */
export function priceChart(canvas, series, storeNames) {
  if (!window.Chart) {
    canvas.replaceWith(document.createTextNode("No se pudo cargar la librería de gráficos."));
    return null;
  }
  const dates = [...new Set(series.flatMap((s) => s.points.map((p) => p.date)))].sort();
  const datasets = series.map((s) => {
    const byDate = new Map(s.points.map((p) => [p.date, Number(p.price)]));
    const color = storeColor(s.store);
    return {
      label: storeNames[s.store] ?? s.store,
      data: dates.map((d) => byDate.get(d) ?? null),
      borderColor: color,
      backgroundColor: color,
      spanGaps: true,
      tension: 0.2,
      pointRadius: dates.length > 40 ? 0 : 3,
    };
  });
  const text = cssVar("--muted");
  const grid = cssVar("--border");
  return new window.Chart(canvas, {
    type: "line",
    data: { labels: dates.map(formatDate), datasets },
    options: {
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { color: text } },
        tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${formatMoney(ctx.parsed.y)}` } },
      },
      scales: {
        x: { ticks: { color: text }, grid: { color: grid } },
        y: { ticks: { color: text, callback: (v) => formatMoney(v) }, grid: { color: grid } },
      },
    },
  });
}
