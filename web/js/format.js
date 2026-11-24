// Formato de números y fechas. Sin dependencias.

const money = new Intl.NumberFormat("es-PE", { style: "currency", currency: "PEN" });
const shortDate = new Intl.DateTimeFormat("es-PE", { day: "numeric", month: "short", timeZone: "America/Lima" });
const relative = new Intl.RelativeTimeFormat("es", { numeric: "auto" });

export function formatMoney(value) {
  return value == null ? "—" : money.format(Number(value));
}

// Descuento positivo = más barato que la referencia.
export function formatDiscount(value) {
  if (value == null) return "—";
  const pct = `${Math.abs(value).toFixed(1)} %`;
  return value >= 0 ? `${pct} más barato` : `${pct} más caro`;
}

export function formatDate(isoDate) {
  // "2026-11-24" -> "24 nov". Se fija el mediodía para evitar saltos por zona horaria.
  return shortDate.format(new Date(`${isoDate}T12:00:00-05:00`));
}

export function formatAgo(isoDateTime, now = Date.now()) {
  if (!isoDateTime) return "nunca";
  const minutes = Math.round((new Date(isoDateTime).getTime() - now) / 60000);
  if (Math.abs(minutes) < 60) return relative.format(minutes, "minute");
  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 48) return relative.format(hours, "hour");
  return relative.format(Math.round(hours / 24), "day");
}
