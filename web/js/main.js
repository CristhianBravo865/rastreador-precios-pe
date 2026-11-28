// Punto de entrada: carga los datos y decide qué vista mostrar según la URL (#/...).

import { loadHistory, loadMeta, loadProducts } from "./api.js";
import { el, render } from "./dom.js";
import { formatAgo } from "./format.js";
import { overviewView } from "./views/overview.js";
import { productView } from "./views/product.js";

const app = document.getElementById("app");
let state = null;
let chart = null;

async function route() {
  chart?.destroy();
  chart = null;
  const match = location.hash.match(/^#\/producto\/(.+)$/);
  if (!match) {
    render(app, ...overviewView(state.meta, state.products));
    return;
  }
  const id = decodeURIComponent(match[1]);
  const product = state.products.find((p) => p.id === id);
  if (!product) {
    render(app, el("p", {}, "Producto no encontrado. ", el("a", { href: "#/" }, "Volver")));
    return;
  }
  const { nodes, afterRender } = productView(state.meta, product, await loadHistory(id));
  render(app, ...nodes.filter(Boolean));
  chart = afterRender();
}

async function start() {
  try {
    const [meta, products] = await Promise.all([loadMeta(), loadProducts()]);
    state = { meta, products };
    document.getElementById("generated-at").textContent = `Actualizado ${formatAgo(meta.generated_at)}`;
    window.addEventListener("hashchange", route);
    await route();
  } catch (err) {
    render(app, el("p", { class: "card empty" }, `Error: ${err.message}`));
  }
}

start();
