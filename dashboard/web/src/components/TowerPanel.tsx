import { useEffect, useRef, useState } from "react";
import { money, num, pct, pnlClass, statusTone, timeET } from "../format";
import type { StrategyRecords, StrategyView } from "../types";
import PriceChart from "./PriceChart";

interface Props { strategy: StrategyView; lastBar: string | null; onClose: () => void }

export default function TowerPanel({ strategy, lastBar, onClose }: Props) {
  const [rec, setRec] = useState<StrategyRecords | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inFlight = useRef(false);
  const pending = useRef(false);
  const currentId = useRef(strategy.id);
  currentId.current = strategy.id;

  // Refetch this strategy's records when its version or its instrument's bars change.
  // At most one request is in flight; changes during it trigger one follow-up request,
  // and the last records stay on screen meanwhile.
  useEffect(() => {
    const load = () => {
      if (inFlight.current) { pending.current = true; return; }
      inFlight.current = true;
      const id = currentId.current;
      fetch(`/api/strategies/${encodeURIComponent(id)}`)
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
        .then((d: StrategyRecords) => { if (d.strategy.id === currentId.current) { setRec(d); setError(null); } })
        .catch((e: Error) => setError(e.message))
        .finally(() => {
          inFlight.current = false;
          if (pending.current || id !== currentId.current) { pending.current = false; load(); }
        });
    };
    load();
  }, [strategy.id, strategy.version, lastBar]);

  useEffect(() => { setRec(null); }, [strategy.id]);

  const s = strategy;
  return (
    <aside className="panel tower-panel" aria-label={`Details for ${s.name}`}>
      <header>
        <div>
          <h2>{s.name}</h2>
          <p className="sub">{s.instrument_label} · id {s.id} · <span className="sim-tag">SIMULATED</span></p>
        </div>
        <button type="button" onClick={onClose} aria-label="Close details">Close</button>
      </header>
      <p className={`status ${statusTone(s.status)}`}>Status: {s.status}{s.status_detail ? ` — ${s.status_detail}` : ""}</p>
      {s.feed_status === "stale" && <p className="warn">Data for {s.instrument_label} is STALE: no new bar.</p>}
      <dl className="kv">
        <dt>Realized P&amp;L</dt><dd className={pnlClass(s.realized_pnl)}>{money(s.realized_pnl, true)}</dd>
        <dt>Unrealized P&amp;L</dt>
        <dd className={pnlClass(s.unrealized_pnl)}>{s.position ? `${money(s.unrealized_pnl, true)} (mark ${num(s.position.mark_price)} at ${timeET(s.position.mark_utc)}, before exit costs)` : "— (no open position)"}</dd>
        <dt>Position</dt>
        <dd>{s.position ? `${s.position.direction > 0 ? "LONG" : "SHORT"} ${s.position.shares} sh @ ${num(s.position.entry_fill)} since ${timeET(s.position.entry_utc)}` : "Flat"}</dd>
        <dt>Risk</dt><dd>{s.risk_status}{s.risk_reason ? ` — ${s.risk_reason}` : ""}</dd>
        <dt>Allocation</dt><dd>{money(s.allocation)}</dd>
        <dt>Max drawdown</dt><dd>{pct(s.max_drawdown)}</dd>
      </dl>
      {error && <p className="error">Could not load records: {error}</p>}
      {!rec && !error && <p className="empty">Loading records…</p>}
      {rec && (
        <>
          <PriceChart rec={rec} />
          <h3>Signals</h3>
          {rec.signals.length ? (
            <table><thead><tr><th>Time</th><th>Direction</th><th>r1</th><th>Note</th></tr></thead>
              <tbody>{rec.signals.slice().reverse().map((x) => (
                <tr key={x.event_id}><td>{timeET(x.ts_utc)} {String(x.ts_utc).slice(0, 10)}</td>
                  <td>{x.direction === 1 ? "LONG" : x.direction === -1 ? "SHORT" : "NONE"}</td>
                  <td>{pct(x.r1 as number, 3)}</td><td>{(x.skip_reason as string) || ""}</td></tr>))}
              </tbody></table>
          ) : <p className="empty">No signals yet.</p>}
          <h3>Decisions</h3>
          {rec.decisions.length ? (
            <table><thead><tr><th>Time</th><th>Action</th><th>Detail</th></tr></thead>
              <tbody>{rec.decisions.slice().reverse().map((x) => (
                <tr key={x.event_id}><td>{timeET(x.ts_utc)} {String(x.ts_utc).slice(0, 10)}</td>
                  <td>{String(x.action).toUpperCase()}</td>
                  <td>{x.action === "skip" ? String(x.reason) : `${x.direction === 1 ? "long" : "short"} ${x.shares} sh, cap ${x.binding_cap}, risk check ${x.risk_check}`}</td></tr>))}
              </tbody></table>
          ) : <p className="empty">No decisions yet.</p>}
          <h3>Trade history (simulated)</h3>
          {rec.trades.length ? (
            <table><thead><tr><th>Closed</th><th>Side</th><th>Shares</th><th>Entry fill</th><th>Exit fill</th><th>Realized</th><th>Exit</th></tr></thead>
              <tbody>{rec.trades.slice().reverse().map((x) => (
                <tr key={x.event_id}><td>{String(x.ts_utc).slice(0, 10)} {timeET(x.ts_utc)}</td>
                  <td>{x.direction === 1 ? "LONG" : "SHORT"}</td><td>{String(x.shares)}</td>
                  <td>{num(x.entry_fill)}</td><td>{num(x.exit_fill)}</td>
                  <td className={pnlClass(x.net_pnl as number)}>{money(x.net_pnl as number, true)}</td>
                  <td>{String(x.exit_reason)}</td></tr>))}
              </tbody></table>
          ) : <p className="empty">No closed trades yet in this replay.</p>}
        </>
      )}
    </aside>
  );
}
