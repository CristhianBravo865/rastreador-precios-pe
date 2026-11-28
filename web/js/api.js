// Único módulo que sabe dónde están los datos y cómo se llaman los archivos.
// Si el contrato cambia (SCHEMA_VERSION en contract.py), se ajusta aquí.

const BASE = "data/";
export const SUPPORTED_SCHEMA = 1;

async function getJson(path) {
  const resp = await fetch(BASE + path, { cache: "no-cache" });
  if (!resp.ok) throw new Error(`No se pudo cargar ${path} (HTTP ${resp.status})`);
  const data = await resp.json();
  if (data.schema_version !== SUPPORTED_SCHEMA) {
    throw new Error(`Versión de datos ${data.schema_version} no soportada (se espera ${SUPPORTED_SCHEMA})`);
  }
  return data;
}

export const loadMeta = () => getJson("meta.json");
export const loadProducts = () => getJson("products.json").then((d) => d.products);
export const loadHistory = (productId) => getJson(`history/${encodeURIComponent(productId)}.json`);
