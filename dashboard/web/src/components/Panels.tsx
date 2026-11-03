import { describe } from "../describe";
import { dateTimeET, money, pct, pnlClass, statusTone, timeET, utc } from "../format";
import type { Account, Connection, InstrumentView, ReplayStatus, Research, Snapshot, StrategyView, TradingEvent } from "../types";

const MODE_KEYS: [string, string][] = [
  ["DEMO", "DEMO_REPLAY"], ["HISTORICAL_REPLAY", "HISTORICAL_REPLAY"], ["SIMULATION", "SIMULATION"], ["PAPER_ACCOUNT", "PAPER_ACCOUNT"],
];

// All four modes, with the active one marked. Balances from different modes are never combined.
export function ModeStrip({ active, research }: { active: string; research: Research | null }) {
  return (
    <div className="mode-strip" aria-label="Modes">
      {MODE_KEYS.map(([key, modeId]) => {
        const info = research?.modes[key];
        const isActive = modeId === active;
        return (
          <span key={key} className={`mode-chip ${isActive ? "on" : info?.available ? "" : "off"}`} title={info?.reason}>
            {key.replace("_", " ")}: {isActive ? "ACTIVE" : info ? (info.available ? "available" : "unavailable") : "…"}
          </span>
        );
      })}
    </div>
  );
}

export function ResearchView({ research }: { research: Research | null }) {
  if (!research) return <p className="empty panel">Loading research status…</p>;
  return (
    <section className="panel wide" aria-label="Research lab status">
      <h2>Research &amp; Simulation Lab</h2>
      <h3>Modes</h3>
      <table><thead><tr><th>Mode</th><th>Available</th><th>Reason</th></tr></thead>
        <tbody>{Object.entries(research.modes).map(([k, v]) => (
          <tr key={k}><td>{k.replace("_", " ")}</td><td>{v.available ? "yes" : "no"}</td><td>{v.reason}</td></tr>))}</tbody></table>
      <h3>Responsibilities</h3>
      <div className="scroll">
        <table><thead><tr><th>Responsibility</th><th>Implementation</th><th>Module</th><th>Status</th><th>Notes</th></tr></thead>
          <tbody>{research.responsibilities.map((x) => (
            <tr key={x.id}><td>{x.name}{x.veto ? " (veto)" : ""}</td><td>{x.implementation.replace("_", " ")}</td>
              <td>{x.module ? <code>{x.module}</code> : "—"}</td><td>{x.status}</td><td>{x.notes}</td></tr>))}</tbody></table>
      </div>
      <p className="muted small">{research.skills_note} No responsibility currently uses an AI agent. Specification: <code>{research.product_spec}</code>.</p>
    </section>
  );
}

export const MODE_LABELS: Record<string, string> = { DEMO_REPLAY: "DEMO REPLAY", HISTORICAL_REPLAY: "HISTORICAL REPLAY" };

export function Banner({ text, mode = "DEMO_REPLAY" }: { text: string; mode?: string }) {
  return (
    <div className={`banner banner-${mode}`} role="status">
      <strong>{MODE_LABELS[mode] ?? mode}</strong> <span>{text}</span> <span className="banner-off">Order submission: DISABLED</span>
    </div>
  );
}

const SPEEDS = [60, 300, 600, 1800, 3600];

export function Controls({ status, connection, lastMessageAt, control, controlError, view, setView,
  reducedMotion, setReducedMotion }: {
  status: ReplayStatus | null; connection: Connection; lastMessageAt: number | null;
  control: (a: string, s?: number) => void; controlError: string | null;
  view: string; setView: (v: string) => void; reducedMotion: boolean; setReducedMotion: (b: boolean) => void;
}) {
  const views = ["City", "Table", "Sessions", "Leaderboard", "Research"];
  return (
    <div className="controls">
      <div className="group" role="group" aria-label="Replay controls">
        {status?.playing
          ? <button type="button" onClick={() => control("pause")}>Pause</button>
          : <button type="button" onClick={() => control("resume")} disabled={!!status?.finished}>Resume</button>}
        <button type="button" onClick={() => control("restart")}>Restart</button>
        <label>Speed{" "}
          <select value={status?.speed ?? 600} onChange={(e) => control("speed", Number(e.target.value))}>
            {SPEEDS.map((s) => <option key={s} value={s}>{s}×</option>)}
          </select>
        </label>
      </div>
      <div className="group clock" aria-live="off">
        <span>Replay clock: <strong>{dateTimeET(status?.replay_clock_utc)}</strong></span>
        <span className="muted">{utc(status?.replay_clock_utc)}</span>
        <span>{status ? `${status.playing ? "PLAYING" : status.finished ? "FINISHED" : "PAUSED"} · ${status.cursor}/${status.total} events` : "—"}</span>
      </div>
      <div className={`group conn conn-${connection}`}>
        Backend: <strong>{connection.toUpperCase()}</strong>
        {lastMessageAt && <span className="muted"> last message {new Date(lastMessageAt).toLocaleTimeString()}</span>}
      </div>
      <div className="group" role="tablist" aria-label="Views">
        {views.map((v) => (
          <button key={v} type="button" role="tab" aria-selected={view === v} className={view === v ? "active" : ""}
                  onClick={() => setView(v)}>{v}</button>
        ))}
        <label className="rm">
          <input type="checkbox" aria-label="Reduced motion" checked={reducedMotion}
                 onChange={(e) => setReducedMotion(e.target.checked)} /> Reduced motion
        </label>
      </div>
      {controlError && <p className="error" role="alert">{controlError}</p>}
    </div>
  );
}

export function AccountPanel({ account, snapshot, instruments }: { account: Account; snapshot: Snapshot; instruments: InstrumentView[] }) {
  return (
    <section className="panel account" aria-label="Simulated account">
      <h2>Account <span className="sim-tag">SIMULATED</span></h2>
      <dl className="kv">
        <dt>Equity</dt><dd>{money(account.equity)}</dd>
        <dt>Realized P&amp;L</dt><dd className={pnlClass(account.realized_pnl)}>{money(account.realized_pnl, true)}</dd>
        <dt>Unrealized P&amp;L</dt><dd className={pnlClass(account.unrealized_pnl)}>{money(account.unrealized_pnl, true)} <span className="muted">(mark, before exit costs)</span></dd>
        <dt>Exposure</dt><dd>{money(account.gross_exposure)} ({pct(account.exposure_pct)} of equity) · {account.open_positions} open</dd>
        <dt>Risk</dt><dd className={account.risk_status === "OK" ? "tone-idle" : "tone-danger"}>{account.risk_status}</dd>
      </dl>
      {account.risk_notes.length > 0 && <ul className="notes">{account.risk_notes.map((n) => <li key={n}>{n}</li>)}</ul>}
      <p className="muted small">Start {money(account.start_equity)} · as of {dateTimeET(snapshot.as_of_utc)} · duplicates ignored {snapshot.duplicates_ignored} · rejected {snapshot.rejected}</p>
      <h3>Data feeds</h3>
      {instruments.length ? (
        <ul className="feeds">{instruments.map((i) => (
          <li key={i.id}>
            {i.label}: <strong className={i.feed_status === "stale" ? "tone-danger" : ""}>{i.feed_status.toUpperCase()}</strong>{" "}
            <span className="muted">({i.feed} feed, last bar ends {timeET(i.last_bar_end_utc)})</span>
          </li>))}</ul>
      ) : <p className="empty">No instruments configured.</p>}
    </section>
  );
}

export function ActivityFeed({ events, names }: { events: TradingEvent[]; names: Record<string, string> }) {
  const shown = events.slice(-60).reverse();
  return (
    <section className="panel feed" aria-label="Activity feed">
      <h2>Activity <span className="muted small">(newest first, replayed events)</span></h2>
      {shown.length ? (
        <ol>{shown.map((e) => (
          <li key={e.event_id}>
            <time dateTime={e.ts_utc}>{e.ts_utc.slice(0, 10)} {timeET(e.ts_utc)}</time>
            <span className={`etype et-${e.type}`}>{e.type.replace("_", " ")}</span>
            <span className="who">{e.strategy_id ? names[e.strategy_id] ?? e.strategy_id : e.instrument ?? "session"}</span>
            <span>{describe(e)}</span>
          </li>))}</ol>
      ) : <p className="empty">No events yet. The replay may be paused or just starting.</p>}
    </section>
  );
}

export function SessionHistory({ snapshot }: { snapshot: Snapshot }) {
  const strategies = snapshot.strategies;
  if (!snapshot.sessions.length) return <p className="empty panel">No sessions replayed yet.</p>;
  return (
    <section className="panel wide" aria-label="Session history">
      <h2>Session history <span className="sim-tag">SIMULATED</span></h2>
      <div className="scroll">
        <table>
          <thead><tr><th>Session</th><th>Status</th>{strategies.map((s) => <th key={s.id}>{s.id}<br /><span className="muted">realized · trades · skips</span></th>)}<th>Account equity at close</th></tr></thead>
          <tbody>{snapshot.sessions.map((r) => (
            <tr key={r.date}>
              <td>{r.date}{r.early_close ? " (early close)" : ""}</td><td>{r.status}</td>
              {strategies.map((s) => {
                const c = r.per_strategy[s.id];
                return <td key={s.id} title={c?.skip_reasons.join("; ")}>
                  <span className={pnlClass(c?.realized_pnl)}>{money(c?.realized_pnl, true)}</span> · {c?.trades ?? 0} · {c?.skips ?? 0}
                </td>;
              })}
              <td>{r.end_equity === null ? "session open" : money(r.end_equity)}</td>
            </tr>))}</tbody>
        </table>
      </div>
    </section>
  );
}

export function Leaderboard({ snapshot }: { snapshot: Snapshot }) {
  const byId = Object.fromEntries(snapshot.strategies.map((s) => [s.id, s]));
  if (!snapshot.leaderboard.length) return <p className="empty panel">No strategy instances configured.</p>;
  return (
    <section className="panel wide" aria-label="Strategy leaderboard">
      <h2>Leaderboard <span className="sim-tag">SIMULATED</span></h2>
      <p className="muted small">Ranked by realized P&amp;L in this synthetic replay. A few days of made-up data is not evidence of skill. Win rate alone is not a quality measure: compare average win and loss, drawdown, and costs.</p>
      <div className="scroll">
        <table>
          <thead><tr><th>#</th><th>Instance</th><th>Instrument</th><th>Realized</th><th>Unrealized</th><th>Trades</th><th>Win rate</th><th>Avg win</th><th>Avg loss</th><th>Profit factor</th><th>Max DD</th><th>Risk</th></tr></thead>
          <tbody>{snapshot.leaderboard.map(({ rank, id }) => {
            const s = byId[id];
            return (
              <tr key={id}>
                <td>{rank}</td><td>{s.name}<br /><span className="muted">{s.id}</span></td><td>{s.instrument_label}</td>
                <td className={pnlClass(s.realized_pnl)}>{money(s.realized_pnl, true)}</td>
                <td>{s.position ? money(s.unrealized_pnl, true) : "—"}</td>
                <td>{s.trades}</td><td>{pct(s.win_rate, 0)}</td><td>{money(s.avg_win)}</td><td>{money(s.avg_loss)}</td>
                <td>{s.profit_factor === null ? "—" : s.profit_factor.toFixed(2)}</td><td>{pct(s.max_drawdown)}</td>
                <td>{s.risk_status}</td>
              </tr>);
          })}</tbody>
        </table>
      </div>
    </section>
  );
}

export function StrategyTable({ strategies, selectedId, onSelect }: { strategies: StrategyView[]; selectedId: string | null; onSelect: (id: string) => void }) {
  if (!strategies.length) return <p className="empty panel">No strategy instances configured. Add instances to dashboard/demo_config.json.</p>;
  return (
    <section className="panel wide" aria-label="Strategy instances table">
      <h2>Strategy instances <span className="sim-tag">SIMULATED</span></h2>
      <div className="scroll">
        <table>
          <thead><tr><th>Instance</th><th>Instrument</th><th>Status</th><th>Data</th><th>Position</th><th>Realized</th><th>Unrealized</th><th>Trades</th><th>Risk</th><th></th></tr></thead>
          <tbody>{strategies.map((s) => (
            <tr key={s.id} className={s.id === selectedId ? "selected" : ""}>
              <td>{s.name}<br /><span className="muted">{s.id}</span></td><td>{s.instrument_label}</td>
              <td className={statusTone(s.status)}>{s.status}<br /><span className="muted">{s.status_detail}</span></td>
              <td>{(s.feed_status ?? "—").toUpperCase()}</td>
              <td>{s.position ? `${s.position.direction > 0 ? "LONG" : "SHORT"} ${s.position.shares}` : "flat"}</td>
              <td className={pnlClass(s.realized_pnl)}>{money(s.realized_pnl, true)}</td>
              <td>{s.position ? money(s.unrealized_pnl, true) : "—"}</td>
              <td>{s.trades}</td><td>{s.risk_status}</td>
              <td><button type="button" onClick={() => onSelect(s.id)}>Details</button></td>
            </tr>))}</tbody>
        </table>
      </div>
    </section>
  );
}
