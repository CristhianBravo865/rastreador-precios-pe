// Pequeños ayudantes para construir el DOM.
// Todo el texto entra como textContent: los nombres de productos y vendedores
// vienen de las tiendas y nunca se interpretan como HTML.

export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value == null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child == null || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

export function badge({ text, tone, hint }) {
  return el("span", { class: `badge ${tone ?? ""}`, title: hint }, text);
}

export function table(headers, rows) {
  const head = el("tr", {}, headers.map((h) => el("th", { class: h.num ? "num" : null }, h.text)));
  const body = rows.map((cells) =>
    el("tr", {}, cells.map((c, i) => el("td", { class: headers[i].num ? "num" : null }, c))),
  );
  return el("div", { class: "table-wrap" }, el("table", {}, el("thead", {}, head), el("tbody", {}, body)));
}

export function render(root, ...nodes) {
  root.replaceChildren(...nodes);
}
