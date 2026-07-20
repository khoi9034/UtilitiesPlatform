export function label(value = "") {
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function compactNumber(value: number | string | null | undefined) {
  const number = typeof value === "string" ? Number(value) : value;
  if (number === null || number === undefined || Number.isNaN(number)) return "Unavailable";
  return new Intl.NumberFormat("en-US", { notation: Math.abs(number) >= 10000 ? "compact" : "standard" }).format(number);
}

export function percent(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "Unavailable";
  return `${(value * 100).toFixed(1)}%`;
}

export function shortDate(value?: string) {
  if (!value) return "Unavailable";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export function safeText(value: unknown, fallback = "Unavailable") {
  if (value === null || value === undefined || value === "") return fallback;
  return String(value);
}
