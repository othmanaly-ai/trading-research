// One-line text for an event, built only from its own fields.
import { money, num, pct } from "./format";
import type { TradingEvent } from "./types";

export function describe(ev: TradingEvent): string {
  const p = ev.payload as Record<string, any>;
  switch (ev.type) {
    case "session_open":
      return `Session ${p.session_date} opened${p.early_close ? " (early close day)" : ""}`;
    case "session_close":
      return `Session ${p.session_date} closed`;
    case "feed_status":
      if (p.status === "stale") return `Data STALE on ${p.feed} feed (no bar since ${p.last_bar_end_utc})`;
      if (p.recovered_after_missing_minutes) return `Data LIVE again after ${p.recovered_after_missing_minutes} missing minute(s)`;
      return `Data LIVE (${p.feed} feed)`;
    case "signal":
      if (p.skip_reason && p.r1 !== null) return `Signal filtered, r1 ${pct(p.r1, 3)}: ${p.skip_reason}`;
      if (p.skip_reason) return `Signal not formed: ${p.skip_reason}`;
      return `Signal ${p.direction > 0 ? "LONG" : p.direction < 0 ? "SHORT" : "NONE"}, r1 ${pct(p.r1, 3)}`;
    case "risk_status":
      return `Risk ${String(p.status).toUpperCase()}: ${p.reason}`;
    case "decision":
      return p.action === "skip"
        ? `Decision SKIP: ${p.reason}`
        : `Decision ENTER ${p.direction > 0 ? "LONG" : "SHORT"} ${p.shares} sh (cap: ${p.binding_cap}, risk check ${p.risk_check})`;
    case "fill":
      return `Simulated fill ${p.leg}: ${p.side} ${p.shares} @ ${num(p.fill_price)}${p.reason ? ` (${p.reason})` : ""}`;
    case "position_closed":
      return `Closed ${p.direction > 0 ? "long" : "short"}: realized ${money(p.net_pnl, true)} net of simulated costs (${p.exit_reason})`;
    default:
      return ev.type;
  }
}
