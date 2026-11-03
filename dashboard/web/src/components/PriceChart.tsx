import { timeET } from "../format";
import type { Bar, StrategyRecords } from "../types";

interface Marker { x: string; label: string; kind: "signal" | "decision" | "entry" | "exit" }

const W = 560, H = 240, PAD = { l: 70, r: 12, t: 14, b: 32 };

// Draws the current session's bars and markers taken from this strategy's own records.
export default function PriceChart({ rec }: { rec: StrategyRecords }) {
  const bars: Bar[] = rec.bars;
  if (!bars.length) return <p className="empty">No bars received yet for this session.</p>;

  const session = rec.session;
  const inSession = (ts: string) => {
    const t = Date.parse(ts);
    return t >= Date.parse(bars[0].t) && t <= Date.parse(bars[bars.length - 1].t) + 60_000;
  };
  const markers: Marker[] = [
    ...rec.signals.filter((s) => inSession(s.ts_utc)).map((s) => ({ x: s.ts_utc, label: "signal", kind: "signal" as const })),
    ...rec.decisions.filter((d) => inSession(d.ts_utc)).map((d) => ({ x: d.ts_utc, label: `decision: ${d.action}`, kind: "decision" as const })),
    ...rec.fills.filter((f) => inSession(f.ts_utc)).map((f) => ({
      x: f.ts_utc, label: `${f.leg} ${f.side}`, kind: (f.leg === "entry" ? "entry" : "exit") as Marker["kind"],
    })),
  ];
  const stop = rec.strategy.position?.stop_price ?? null;

  const t0 = Date.parse(bars[0].t);
  const t1 = Math.max(Date.parse(bars[bars.length - 1].t) + 60_000, t0 + 60_000);
  const prices = bars.flatMap((b) => [b.h, b.l]).concat(stop ? [stop] : []);
  const lo = Math.min(...prices), hi = Math.max(...prices);
  const span = hi - lo || 1;
  const x = (ts: number) => PAD.l + ((ts - t0) / (t1 - t0)) * (W - PAD.l - PAD.r);
  const y = (p: number) => PAD.t + (1 - (p - lo) / span) * (H - PAD.t - PAD.b);
  const path = bars.map((b, i) => `${i ? "L" : "M"}${x(Date.parse(b.t) + 60_000).toFixed(1)},${y(b.c).toFixed(1)}`).join("");
  const ticks = [lo, lo + span / 2, hi];

  return (
    <figure className="chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img"
           aria-label={`Price chart for ${rec.strategy.instrument_label}, session ${session}, ${bars.length} one-minute bars`}>
        {ticks.map((p) => (
          <g key={p}>
            <line x1={PAD.l} x2={W - PAD.r} y1={y(p)} y2={y(p)} className="grid" />
            <text x={PAD.l - 6} y={y(p) + 4} className="axis" textAnchor="end">{p.toFixed(2)}</text>
          </g>
        ))}
        <text x={PAD.l} y={H - 8} className="axis">{timeET(bars[0].t)}</text>
        <text x={W - PAD.r} y={H - 8} className="axis" textAnchor="end">{timeET(new Date(t1).toISOString())}</text>
        <path d={path} className="price" />
        {stop !== null && (
          <g>
            <line x1={PAD.l} x2={W - PAD.r} y1={y(stop)} y2={y(stop)} className="stop" />
            <text x={W - PAD.r - 4} y={y(stop) - 4} className="axis" textAnchor="end">stop {stop.toFixed(2)}</text>
          </g>
        )}
        {markers.map((m) => (
          <g key={m.x + m.label}>
            <line x1={x(Date.parse(m.x))} x2={x(Date.parse(m.x))} y1={PAD.t} y2={H - PAD.b} className={`mk mk-${m.kind}`} />
          </g>
        ))}
      </svg>
      <figcaption>
        {rec.strategy.instrument_label} · session {session} · 1-minute bars, synthetic feed.{" "}
        Markers: {markers.length ? markers.map((m) => `${m.label} ${timeET(m.x)}`).join("; ") : "none yet"}.
        {stop !== null && " Dashed line: protective stop of the open simulated position."}
      </figcaption>
    </figure>
  );
}
