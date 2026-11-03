// Display formatting only. No calculations of results happen here.

const ET = new Intl.DateTimeFormat("en-US", {
  timeZone: "America/New_York", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
});
const ET_DATE = new Intl.DateTimeFormat("en-CA", { timeZone: "America/New_York" });

export function timeET(iso: string | null | undefined): string {
  return iso ? `${ET.format(new Date(iso))} ET` : "—";
}

export function dateTimeET(iso: string | null | undefined): string {
  return iso ? `${ET_DATE.format(new Date(iso))} ${ET.format(new Date(iso))} ET` : "—";
}

export function utc(iso: string | null | undefined): string {
  return iso ? iso.replace("T", " ").replace("Z", " UTC") : "—";
}

export function money(v: number | null | undefined, signed = false): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "—";
  const s = Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const sign = v < 0 ? "−" : signed && v > 0 ? "+" : "";
  return `${sign}$${s}`;
}

export function pct(v: number | null | undefined, digits = 2): string {
  return v === null || v === undefined || !Number.isFinite(v) ? "—" : `${(v * 100).toFixed(digits)}%`;
}

export function num(v: unknown, digits = 2): string {
  return typeof v === "number" && Number.isFinite(v) ? v.toFixed(digits) : "—";
}

export function pnlClass(v: number | null | undefined): string {
  if (!v) return "pnl-zero";
  return v > 0 ? "pnl-pos" : "pnl-neg";
}

// Text category for a status, used with color so meaning never depends on color alone.
export function statusTone(status: string): string {
  if (status.startsWith("HALTED")) return "tone-danger";
  if (status.startsWith("IN POSITION")) return "tone-active";
  if (status.startsWith("SIGNAL") || status === "ENTERING") return "tone-signal";
  if (status === "SKIPPED") return "tone-muted";
  return "tone-idle";
}
