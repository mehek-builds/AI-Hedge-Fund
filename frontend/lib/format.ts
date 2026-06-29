/** Currency, percent, and signed number formatters. All use JetBrains Mono class via <Num>. */

export function fmtCurrency(v: number | null | undefined, decimals = 0): string {
  if (v == null) return "--";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(v);
}

export function fmtPct(v: number | null | undefined, decimals = 2): string {
  if (v == null) return "--";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(decimals)}%`;
}

export function fmtSigned(v: number | null | undefined, decimals = 2): string {
  if (v == null) return "--";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(decimals)}`;
}

export function fmtNum(v: number | null | undefined, decimals = 2): string {
  if (v == null) return "--";
  return v.toFixed(decimals);
}

export function fmtDate(v: string | Date | null | undefined): string {
  if (!v) return "--";
  return new Date(v).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function fmtTime(v: string | Date | null | undefined): string {
  if (!v) return "--";
  return new Date(v).toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export function fmtDatetime(v: string | Date | null | undefined): string {
  if (!v) return "--";
  const d = new Date(v);
  return `${d.toLocaleDateString("en-US", { month: "short", day: "numeric" })} ${d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false })}`;
}

export function signClass(v: number | null | undefined): string {
  if (v == null) return "";
  return v > 0 ? "pos" : v < 0 ? "neg" : "";
}
