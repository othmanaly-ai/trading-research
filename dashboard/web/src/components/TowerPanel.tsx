import { useState } from "react";
import { money, num, pct, pnlClass, statusTone, timeET } from "../format";
import type { Evaluation, Instance, Research, StrategyRecords, StrategyView } from "../types";
import { useLiveJson } from "../useLiveJson";
import PriceChart from "./PriceChart";

const TABS = ["Rules & version", "Scanner & news", "Historical replay", "Results", "Paper account", "Decisions & risk"] as const;
type Tab = (typeof TABS)[number];

interface Props {
  strategy: StrategyView;
  instance: Instance | undefined;
  research: Research | null;
  mode: string;
  lastBar: string | null;
  onClose: () => void;
}

export function ModeBadge({ mode }: { mode: string }) {
  const label = mode === "DEMO_REPLAY" ? "DEMO" : mode === "HISTORICAL_REPLAY" ? "HISTORICAL" : mode.replace("_", " ");
  return <span className={`mode-badge mode-${mode}`}>{label}</span>;
}

function Unavailable({ title, reason }: { title: string; reason: string }) {
  return (
    <div className="unavailable" role="note">
      <strong>{title}: not available</strong>
      <p>{reason}</p>
      <p className="muted small">Nothing is shown here rather than placeholder data.</p>
    </div>
  );
}

export default function TowerPanel({ strategy, instance, research, mode, lastBar, onClose }: Props) {
  const [tab, setTab] = useState<Tab>("Results");
  const s = strategy;
  const trigger = `${s.version}|${lastBar}`;
  const recUrl = tab === "Decisions & risk" || tab === "Results" ? `/api/strategies/${encodeURIComponent(s.id)}` : null;
  const evalUrl = tab === "Results" ? `/api/strategies/${encodeURIComponent(s.id)}/evaluation` : null;
  const { data: rec, error: recError } = useLiveJson<StrategyRecords>(recUrl, trigger);
  const { data: ev, error: evError } = useLiveJson<Evaluation>(evalUrl, trigger);

  return (
    <aside className="panel tower-panel" aria-label={`Details for ${s.name}`}>
      <header>
        <div>
          <h2>{s.name}</h2>
          <p className="sub">{s.instrument_label} · id {s.id} · <ModeBadge mode={mode} /></p>
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
      </dl>

      <div className="tabs" role="tablist" aria-label="Strategy detail tabs">
        {TABS.map((t) => (
          <button key={t} type="button" role="tab" aria-selected={tab === t} className={tab === t ? "active" : ""}
                  onClick={() => setTab(t)}>{t}</button>
        ))}
      </div>

      <div role="tabpanel" aria-label={tab} className="tab-body">
        {tab === "Rules & version" && <RulesTab instance={instance} />}
        {tab === "Scanner & news" && (
          <Unavailable title="Scanner & news" reason={research?.scanner_news.reason ?? "Loading…"} />
        )}
        {tab === "Historical replay" && <HistoricalTab research={research} />}
        {tab === "Results" && <ResultsTab ev={ev} error={evError ?? recError} rec={rec} />}
        {tab === "Paper account" && (
          <Unavailable title="PAPER ACCOUNT mode" reason={research?.modes.PAPER_ACCOUNT?.reason ?? "Loading…"} />
        )}
        {tab === "Decisions & risk" && <DecisionsTab rec={rec} error={recError} strategy={s} />}
      </div>
    </aside>
  );
}

function RulesTab({ instance }: { instance: Instance | undefined }) {
  if (!instance) return <p className="empty">No specification found for this instance.</p>;
  const sp = instance.spec;
  const placeholder = instance.risk_limits.placeholder === true;
  return (
    <>
      <dl className="kv">
        <dt>Strategy</dt><dd>{sp.title}</dd>
        <dt>Spec version</dt><dd>{sp.spec_version} <span className="muted">(file hash {sp.spec_sha256})</span></dd>
        <dt>Spec file</dt><dd><code>{sp.spec_path}</code></dd>
        <dt>Variant id</dt><dd>{sp.variant_id}</dd>
        <dt>Profit target</dt><dd>{sp.target_defined ? "defined" : "none in this version (stop + time exit)"}</dd>
      </dl>
      <h3>Parameters</h3>
      <table><tbody>{Object.entries(sp.params).map(([k, v]) => (
        <tr key={k}><td>{k}</td><td>{v === null ? "none" : String(v)}</td></tr>))}</tbody></table>
      <h3>Risk limits {placeholder && <span className="sim-tag">PLACEHOLDER (D1 open)</span>}</h3>
      <table><tbody>{Object.entries(instance.risk_limits).filter(([k]) => k !== "placeholder").map(([k, v]) => (
        <tr key={k}><td>{k}</td><td>{typeof v === "number" ? pct(v, 2) : String(v)}</td></tr>))}</tbody></table>
    </>
  );
}

function HistoricalTab({ research }: { research: Research | null }) {
  if (!research) return <p className="empty">Loading…</p>;
  const m = research.modes.HISTORICAL_REPLAY;
  return (
    <>
      {!m.available && <Unavailable title="HISTORICAL REPLAY mode" reason={m.reason} />}
      <h3>Defined periods (experiment 001)</h3>
      <table>
        <thead><tr><th>Period</th><th>Dates</th><th>Expected sessions</th><th>With verified data</th></tr></thead>
        <tbody>{research.historical_periods.map((p) => (
          <tr key={p.period}><td>{p.period}</td><td>{p.start} to {p.end}</td><td>{p.expected_sessions}</td>
            <td>{p.sessions_with_verified_data} ({pct(p.sessions_with_verified_data / p.expected_sessions, 0)})</td></tr>))}
        </tbody>
      </table>
      <p className="muted small">The final period is locked in code and runs once. Repeating an identical run checks reproducibility; it is not extra evidence.</p>
    </>
  );
}

function ResultsTab({ ev, error, rec }: { ev: Evaluation | null; error: string | null; rec: StrategyRecords | null }) {
  if (error) return <p className="error">Could not load the evaluation: {error}</p>;
  if (!ev) return <p className="empty">Loading evaluation…</p>;
  const o = ev.outcomes;
  const na = (v: number | null) => (v === null ? "n/a" : String(v));
  return (
    <>
      <p className="notice"><ModeBadge mode={ev.mode} /> evaluation of replayed records up to {timeET(ev.as_of_utc)} {ev.as_of_utc?.slice(0, 10)}.{" "}
        {ev.mode === "DEMO_REPLAY"
          ? "Synthetic fixture prices: this tests the software, not a strategy."
          : "Historical prices with simulated fills: an inspection sample, not evidence of an edge."}{" "}
        Result hash <code>{ev.result_hash}</code>.</p>
      <div className="grid2">
        <dl className="kv">
          <dt>Net P&amp;L</dt><dd className={pnlClass(ev.pnl.net)}>{money(ev.pnl.net, true)} ({pct(ev.pnl.net_return_on_allocation, 3)} of allocation)</dd>
          <dt>Gross P&amp;L</dt><dd>{money(ev.pnl.gross, true)}</dd>
          <dt>Modeled costs</dt><dd>{money(ev.pnl.modeled_costs)}</dd>
          <dt>Max drawdown</dt><dd>{pct(ev.risk.max_drawdown)}</dd>
          <dt>Time in market</dt><dd>{pct(ev.risk.time_in_market, 1)}</dd>
          <dt>Avg notional</dt><dd>{pct(ev.risk.avg_notional_to_allocation, 0)} of allocation</dd>
        </dl>
        <dl className="kv">
          <dt>Trades</dt><dd>{ev.sample.trades}</dd>
          <dt>Unique sessions traded</dt><dd>{ev.sample.unique_sessions_traded}</dd>
          <dt>Sessions evaluated</dt><dd>{ev.sample.sessions_evaluated} of {ev.sample.expected_sessions} ({pct(ev.sample.coverage, 0)})</dd>
          <dt>Avg gain / loss</dt><dd>{money(ev.trades.avg_gain)} / {money(ev.trades.avg_loss)}</dd>
          <dt>Wins / losses</dt><dd>{ev.trades.wins} / {ev.trades.losses}</dd>
          <dt>Avg holding</dt><dd>{ev.trades.avg_holding_minutes === null ? "—" : `${ev.trades.avg_holding_minutes.toFixed(1)} min`}</dd>
        </dl>
      </div>
      <h3>Outcome classification</h3>
      <table>
        <thead><tr><th>Target first</th><th>Stop first</th><th>Neither</th><th>Ambiguous</th><th>Unfillable</th></tr></thead>
        <tbody><tr><td>{na(o.target_first)}</td><td>{o.stop_first}</td><td>{o.neither}</td><td>{na(o.ambiguous)}</td><td>{o.unfillable}</td></tr></tbody>
      </table>
      <p className="muted small">Ambiguous = one bar reached both stop and target; it is never counted as a target hit. "n/a" = this strategy version defines no target. Reaching a level is not the same as profit after costs.</p>
      <h3>Cost sensitivity (net P&amp;L at multiples of modeled costs)</h3>
      <table>
        <thead><tr>{Object.keys(ev.pnl.cost_sensitivity).map((k) => <th key={k}>{k}</th>)}</tr></thead>
        <tbody><tr>{Object.values(ev.pnl.cost_sensitivity).map((v, i) => <td key={i} className={pnlClass(v)}>{money(v, true)}</td>)}</tr></tbody>
      </table>
      {Object.keys(ev.sample.skips).length > 0 && (
        <><h3>Skipped sessions</h3>
          <ul className="notes">{Object.entries(ev.sample.skips).map(([k, v]) => <li key={k}>{k}: {v}</li>)}</ul></>
      )}
      <h3>Trade history</h3>
      {rec && rec.trades.length ? (
        <table><thead><tr><th>Closed</th><th>Side</th><th>Sh</th><th>Entry</th><th>Exit</th><th>Net</th><th>Outcome</th></tr></thead>
          <tbody>{rec.trades.slice().reverse().map((x) => (
            <tr key={x.event_id}><td>{String(x.ts_utc).slice(0, 10)} {timeET(x.ts_utc)}</td>
              <td>{x.direction === 1 ? "LONG" : "SHORT"}</td><td>{String(x.shares)}</td>
              <td>{num(x.entry_fill)}</td><td>{num(x.exit_fill)}</td>
              <td className={pnlClass(x.net_pnl as number)}>{money(x.net_pnl as number, true)}</td>
              <td>{String(x.outcome)} · {String(x.exit_reason)}</td></tr>))}
          </tbody></table>
      ) : <p className="empty">No closed trades yet in this replay.</p>}
      <h3>Limitations</h3>
      <ul className="notes">{ev.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
    </>
  );
}

function DecisionsTab({ rec, error, strategy }: { rec: StrategyRecords | null; error: string | null; strategy: StrategyView }) {
  if (error) return <p className="error">Could not load records: {error}</p>;
  if (!rec) return <p className="empty">Loading records…</p>;
  return (
    <>
      <PriceChart rec={rec} />
      <h3>Risk checks</h3>
      <p>Current: {strategy.risk_status}{strategy.risk_reason ? ` — ${strategy.risk_reason}` : ""}</p>
      {rec.risk.length > 0 && (
        <table><thead><tr><th>Time</th><th>Status</th><th>Reason</th></tr></thead>
          <tbody>{rec.risk.slice().reverse().map((x) => (
            <tr key={x.event_id}><td>{String(x.ts_utc).slice(0, 10)} {timeET(x.ts_utc)}</td><td>{String(x.status).toUpperCase()}</td><td>{String(x.reason)}</td></tr>))}
          </tbody></table>
      )}
      <h3>Decisions</h3>
      {rec.decisions.length ? (
        <table><thead><tr><th>Time</th><th>Action</th><th>Detail</th></tr></thead>
          <tbody>{rec.decisions.slice().reverse().map((x) => (
            <tr key={x.event_id}><td>{String(x.ts_utc).slice(0, 10)} {timeET(x.ts_utc)}</td>
              <td>{String(x.action).toUpperCase()}</td>
              <td>{x.action === "skip" ? String(x.reason) : `${x.direction === 1 ? "long" : "short"} ${x.shares} sh, cap ${x.binding_cap}, risk check ${x.risk_check}`}</td></tr>))}
          </tbody></table>
      ) : <p className="empty">No decisions yet.</p>}
      <h3>Signals</h3>
      {rec.signals.length ? (
        <table><thead><tr><th>Time</th><th>Direction</th><th>r1</th><th>Note</th></tr></thead>
          <tbody>{rec.signals.slice().reverse().map((x) => (
            <tr key={x.event_id}><td>{String(x.ts_utc).slice(0, 10)} {timeET(x.ts_utc)}</td>
              <td>{x.direction === 1 ? "LONG" : x.direction === -1 ? "SHORT" : "NONE"}</td>
              <td>{pct(x.r1 as number, 3)}</td><td>{(x.skip_reason as string) || ""}</td></tr>))}
          </tbody></table>
      ) : <p className="empty">No signals yet.</p>}
    </>
  );
}
