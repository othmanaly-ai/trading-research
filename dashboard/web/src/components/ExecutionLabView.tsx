import { Component, Suspense, lazy, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { useLiveJson } from "../useLiveJson";
import type { EdgeSpec, TowerSpec } from "./CityView";

// LOCAL EXECUTION SIMULATION (trading/execution_lab via /api/execution-lab). Synthetic scenarios against an in-memory
// fake broker. Every number here comes from the server's ledger derivation: the snapshot after each recorded event.
// The city animates only recorded events, one at a time, as the timeline is stepped. No broker, no orders, no strategy.

const CityView = lazy(() => import("./CityView"));

interface OrderRow {
  order_id: string; symbol: string; side: string; purpose: string; qty: number; ref_price: number; state: string; state_label: string;
  broker_order_id: string | null; filled_qty: number; remaining_qty: number; cancelled_qty: number; avg_fill_price: number | null;
  fees: number; exec_ids: string[]; submit_attempts: number; reasons: string[];
  history: { seq: number; from: string | null; to: string; event: string }[]; ignored: { seq: number; event: string; why: string }[];
  anomalies: string[]; config_version: string | null;
}
interface Ev { seq: number; event_id: string; ts_utc: string; kind: string; order_id: string | null; source: string; config_version: string; payload: Record<string, any> }
interface Snap {
  orders: Record<string, { state: string; filled_qty: number; remaining_qty: number; cancelled_qty: number }>;
  cash: number; equity: number; positions: Record<string, number>; held_exposure: number; pending_exposure: number;
  flags: { emergency_stop: boolean; reconciliation_required: boolean; restart_pending_reconciliation: boolean };
}
interface Check { check: string; passed: boolean; detail?: string }
interface Stop { active: boolean; overall?: string; steps?: { step: string; status: string }[]; cancellations?: any[]; unresolved?: string[]; remaining_exposure?: number; note?: string }
interface Scenario {
  id: string; title: string; seed: number; config_version: string; passed: boolean; expectations: Check[]; invariants: Check[];
  events: Ev[]; duplicates: { event_id: string; ts_utc: string }[]; snapshots: Snap[]; orders: OrderRow[]; cash: number; equity: number;
  fees: number; held_exposure: number; pending_exposure: number; gross_exposure: number; unknown_outcomes: string[]; unresolved: string[];
  risk_rejections: { order_id: string; reasons: string[] }[]; emergency_stop: Stop; broker_submit_calls: Record<string, number>;
}
interface Data {
  mode: string; label: string; notice: string; policy_gaps: string[];
  config: { version: string; limits: string; cost_model: string; start_cash: number; max_data_age_s: number; max_data_age_note: string; session: string };
  scenarios: { id: string; title: string; passed: boolean; events: number; checks: number; failed_checks: number; unknown_outcomes: number;
    unresolved: number; risk_rejections: number; emergency_stop: string | null }[];
  selected: Scenario;
}

const STATE_COLOR: Record<string, number> = {
  CREATED: 0x64748b, VALIDATED: 0x64748b, SUBMISSION_PENDING: 0x38bdf8, ACCEPTED: 0x22d3ee, PARTIALLY_FILLED: 0xa78bfa,
  FILLED: 0x14b8a6, REJECTED: 0xef4444, BLOCKED: 0xf97316, CANCEL_PENDING: 0xeab308, CANCELLED: 0x94a3b8, UNKNOWN: 0xe11d48,
};
const hex = (c: number) => `#${c.toString(16).padStart(6, "0")}`;
const short = (id: string) => id.split(":").pop() ?? id;
const money = (n: number) => n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const KIND: Record<string, "arrival" | "start" | "complete" | "fail"> = {
  submit_requested: "start", broker_ack: "arrival", fill: "arrival", broker_cancelled: "complete", cancel_requested: "start",
  broker_reject: "fail", submit_outcome_unknown: "fail", blocked: "fail", cancel_request_failed: "fail", reconciliation: "complete",
};

class Boundary extends Component<{ onError: (m: string) => void; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(e: Error) { this.props.onError(`3D view unavailable (${e.message}). The tables below hold the same records.`); }
  render() { return this.state.failed ? null : this.props.children; }
}

function St({ s }: { s: string }) {
  return <strong className="desk-state" style={{ color: hex(STATE_COLOR[s] ?? 0x94a3b8) }}>{s}</strong>;
}

function summary(e: Ev): string {
  const p = e.payload;
  switch (e.kind) {
    case "intent_created": return `${p.side} ${p.qty} ${p.symbol} @ ref ${p.ref_price} (${p.purpose})`;
    case "blocked": return (p.reasons ?? []).join("; ");
    case "fill": return `exec ${p.exec_id}: ${p.qty} @ ${p.price}${p.via ? ` (via ${p.via})` : ""}`;
    case "broker_reject": return p.reason;
    case "submit_outcome_unknown": return p.error;
    case "broker_cancelled": return `cancel confirmed; filled at cancel ${p.filled_qty}`;
    case "cancel_rejected": return p.reason;
    case "reconciliation": return p.broker ? `broker says ${p.broker.status}, filled ${p.broker.filled_qty}` : p.note;
    case "reconciliation_complete": case "reconciliation_incomplete": return `positions match: ${p.positions_match}; still unknown: ${(p.still_unknown ?? []).length}`;
    case "stop_action": return `${p.step}${p.order_id ? ` ${short(p.order_id)}` : ""}: ${p.status}`;
    case "mark": return `${p.symbol} mark ${p.price} (synthetic)`;
    default: return Object.keys(p).length ? JSON.stringify(p).slice(0, 120) : "";
  }
}

export default function ExecutionLabView({ reducedMotion }: { reducedMotion: boolean }) {
  const [sid, setSid] = useState("s01");
  const { data, error } = useLiveJson<Data>(`/api/execution-lab?scenario=${sid}`, 0);
  const sc = data?.selected?.id === sid ? data.selected : null;
  const [step, setStep] = useState<number | null>(null);
  const [sel, setSel] = useState<string | null>("execution");
  const [cityError, setCityError] = useState<string | null>(() =>
    new URLSearchParams(window.location.search).get("3d") === "off" ? "3D view turned off (?3d=off)." : null);
  const onCityFailure = useCallback((m: string) => setCityError(m), []);
  useEffect(() => { setStep(null); setSel("execution"); }, [sid]);
  const n = sc?.events.length ?? 0;
  const i = step === null ? n - 1 : Math.min(step, n - 1);
  const snap = sc?.snapshots[i];
  const ev = sc?.events[i];

  const towers = useMemo<TowerSpec[]>(() => {
    if (!sc || !snap) return [];
    const ids = sc.orders.map((o) => o.order_id);
    const cur = ev?.order_id;
    const exec: TowerSpec = {
      id: "execution", color: snap.flags.emergency_stop ? 0xef4444 : snap.flags.reconciliation_required ? 0xe11d48 : 0x6366f1,
      slot: [0, 0], archetype: "command", category: "EXECUTION · simulation", title: "Execution",
      status: snap.flags.emergency_stop ? "EMERGENCY STOP" : snap.flags.reconciliation_required ? "RECONCILIATION REQUIRED" : "entries allowed by flags",
      warn: snap.flags.emergency_stop || snap.flags.reconciliation_required, labelMode: "full",
      event: ev && !ev.order_id ? { id: `${sc.id}:${ev.event_id}`, kind: KIND[ev.kind] ?? "arrival" } : undefined,
      lines: [{ cls: "tl-name", text: "Execution" }, { cls: "tl-status", text: `step ${i + 1}/${n}` }],
      ariaLabel: "Execution building: scenario details", pulseKey: "",
    };
    const orders = ids.map((id, k): TowerSpec => {
      const s = snap.orders[id];
      const a = (2 * Math.PI * k) / Math.max(ids.length, 1);
      const state = s?.state ?? "not yet created";
      return {
        id, color: STATE_COLOR[state] ?? 0x1e293b, slot: [Math.round(Math.sin(a) * 26), Math.round(-Math.cos(a) * 26)],
        archetype: state === "UNKNOWN" ? "twisted" : "terraced", category: "ORDER · synthetic", title: `order ${short(id)}`,
        status: s ? `${state} · ${s.filled_qty}/${s.filled_qty + s.remaining_qty + s.cancelled_qty}` : "not yet created",
        dim: !s || ["CANCELLED", "REJECTED", "BLOCKED"].includes(state), warn: state === "UNKNOWN" || state === "CANCEL_PENDING",
        active: ["SUBMISSION_PENDING", "ACCEPTED", "PARTIALLY_FILLED"].includes(state), labelMode: "compact",
        // the effect for the recorded event at this step only (never invented, never replayed)
        event: ev && cur === id ? { id: `${sc.id}:${ev.event_id}`, kind: KIND[ev.kind] ?? "arrival" } : undefined,
        lines: [{ cls: "tl-name", text: `order ${short(id)}` }, { cls: "tl-status", text: state }],
        ariaLabel: `Order ${short(id)}: ${state}. Show order details.`, pulseKey: "",
      };
    });
    return [exec, ...orders];
  }, [sc, snap, ev, i, n]);
  const edges = useMemo<EdgeSpec[]>(() => (sc?.orders ?? []).map((o) => ({ from: "execution", to: o.order_id,
    style: snap?.orders[o.order_id] ? "recorded" : "declared" })), [sc, snap]);

  if (error) return <p className={`panel ${error.includes("404") ? "warn" : "error"}`}>{error.includes("404")
    ? "This city server was started before the execution lab existed. Use the execution-lab preview (read-only, port 8770)."
    : `Could not load the execution lab: ${error}`}</p>;
  if (!data) return <p className="empty panel">Running synthetic scenarios…</p>;

  const order = sc?.orders.find((o) => o.order_id === sel) ?? null;
  return (
    <section className="panel wide depmap desk xlab" aria-label="Local execution simulation">
      <h2>Execution lab <span className="small muted">LOCAL EXECUTION SIMULATION · config {data.config.version}</span></h2>
      <p className="warn small"><strong>{data.label}.</strong> {data.notice}</p>
      <p className="small">Risk limits: <code>{data.config.limits}</code> (owner baseline, reused unchanged) · costs: <code>{data.config.cost_model}</code> ·
        synthetic start equity {money(data.config.start_cash)} · stale-data threshold {data.config.max_data_age_s} s ({data.config.max_data_age_note}) ·
        session {data.config.session}</p>

      <div className="scroll"><table className="q-table" aria-label="Scenarios">
        <thead><tr><th>Scenario</th><th>Result</th><th>Events</th><th>Checks</th><th>Unknown outcomes</th><th>Unresolved</th><th>Blocked by gates</th><th>Emergency stop</th></tr></thead>
        <tbody>{data.scenarios.map((s) => (
          <tr key={s.id} className={s.id === sid ? "sel" : ""}>
            <td><button type="button" className="cite" aria-pressed={s.id === sid} onClick={() => setSid(s.id)}>{s.id} · {s.title}</button></td>
            <td><strong style={{ color: s.passed ? "#14b8a6" : "#ef4444" }}>{s.passed ? "EXPECTED" : "UNEXPECTED"}</strong></td>
            <td>{s.events}</td><td>{s.checks - s.failed_checks}/{s.checks}</td><td>{s.unknown_outcomes}</td><td>{s.unresolved}</td>
            <td>{s.risk_rejections}</td><td>{s.emergency_stop ?? "—"}</td>
          </tr>))}</tbody>
      </table></div>

      {!sc ? <p className="empty">Loading scenario…</p> : (<>
        <h3>{sc.id} · {sc.title} <span className="small muted">seed {sc.seed} · {sc.events.length} recorded events · {sc.duplicates.length} duplicate update(s) stored once</span></h3>
        <div className="xlab-step" role="group" aria-label="Event timeline">
          <button type="button" onClick={() => setStep(Math.max(0, i - 1))} disabled={i <= 0}>◀ Previous</button>
          <input type="range" min={0} max={n - 1} value={i} onChange={(e) => setStep(Number(e.target.value))} aria-label="Timeline step" />
          <button type="button" onClick={() => setStep(Math.min(n - 1, i + 1))} disabled={i >= n - 1}>Next ▶</button>
          <span className="small">Step {i + 1}/{n} · <code>{ev?.kind}</code> {ev?.order_id ? `order ${short(ev.order_id)}` : ""} · {ev?.ts_utc} · {ev ? summary(ev) : ""}</span>
        </div>
        <div className="district">
          {cityError ? <p className="warn">{cityError}</p> : (
            <Boundary onError={onCityFailure}>
              <Suspense fallback={<p className="empty">Loading 3D view…</p>}>
                <CityView variant="depmap" towers={towers} edges={edges} coreColor={null} selectedId={sel} onSelect={setSel}
                          reducedMotion={reducedMotion} onFailure={onCityFailure}
                          mode={{ label: "LOCAL EXECUTION SIMULATION", tone: "demo", detail: "fake broker · synthetic · an effect plays only for the recorded event at the current step" }}
                          legend={["ACCEPTED", "PARTIALLY_FILLED", "FILLED", "CANCEL_PENDING", "UNKNOWN", "REJECTED", "BLOCKED"].map((k) => ({ color: STATE_COLOR[k], label: k.toLowerCase() }))} />
              </Suspense>
            </Boundary>
          )}
          <aside className="district-detail dep-detail" aria-label="Execution building">
            {sel === "execution" || !order ? (<>
              <h3>Execution · step {i + 1}/{n}</h3>
              <dl className="small desk-dl">
                <dt>Cash</dt><dd>{money(snap!.cash)}</dd><dt>Equity</dt><dd>{money(snap!.equity)}</dd>
                <dt>Positions</dt><dd>{Object.entries(snap!.positions).map(([s, q]) => `${s} ${q}`).join(", ") || "none"}</dd>
                <dt>Held exposure</dt><dd>{money(snap!.held_exposure)}</dd>
                <dt>Pending entries</dt><dd>{money(snap!.pending_exposure)} (counts toward exposure, incl. unknown outcomes)</dd>
                <dt>Emergency stop</dt><dd>{snap!.flags.emergency_stop ? <span className="warn">ACTIVE</span> : "off"}</dd>
                <dt>Reconciliation</dt><dd>{snap!.flags.reconciliation_required ? <span className="warn">REQUIRED</span> : "not required"}</dd>
              </dl>
              <h4 className="floor-h">Orders at this step</h4>
              <ul className="desk-tasks">{Object.entries(snap!.orders).map(([id, o]) => (
                <li key={id}><button type="button" className="cite" onClick={() => setSel(id)}>{short(id)}</button> <St s={o.state} />
                  {" "}<span className="small">filled {o.filled_qty} · remaining {o.remaining_qty}{o.cancelled_qty ? ` · cancelled ${o.cancelled_qty}` : ""}</span></li>))}</ul>
              {sc.unknown_outcomes.length > 0 && <p className="small warn">Unknown outcomes (final): {sc.unknown_outcomes.map(short).join(", ")}</p>}
              {sc.unresolved.length > 0 && (<><h4 className="floor-h">Unresolved actions (final)</h4>
                <ul className="notes">{sc.unresolved.map((u, k) => <li key={k} className="small warn">{u}</li>)}</ul></>)}
            </>) : (<>
              <h3>Order {short(order.order_id)} <button type="button" className="small" onClick={() => setSel("execution")}>Execution</button></h3>
              <p className="small"><code>{order.order_id}</code> · broker id {order.broker_order_id ?? "none"}</p>
              <dl className="small desk-dl">
                <dt>At this step</dt><dd>{snap!.orders[order.order_id] ? <St s={snap!.orders[order.order_id].state} /> : "not yet created"}</dd>
                <dt>Final</dt><dd><St s={order.state} /> {order.state_label !== order.state ? `· ${order.state_label}` : ""}</dd>
                <dt>Quantity</dt><dd>{order.qty} {order.side} {order.symbol} @ ref {order.ref_price}</dd>
                <dt>Filled / remaining / cancelled</dt><dd>{order.filled_qty} / {order.remaining_qty} / {order.cancelled_qty}</dd>
                <dt>Average fill · fees</dt><dd>{order.avg_fill_price ?? "—"} · {order.fees}</dd>
                <dt>Executions</dt><dd>{order.exec_ids.join(", ") || "none"}</dd>
                <dt>Submissions sent</dt><dd>{sc.broker_submit_calls[order.order_id] ?? 0}</dd>
                {order.reasons.length > 0 && <><dt>Reasons</dt><dd className="warn">{order.reasons.join("; ")}</dd></>}
                <dt>Config</dt><dd><code>{order.config_version}</code></dd>
              </dl>
              <h4 className="floor-h">State history</h4>
              <ul className="notes">{order.history.map((h, k) => <li key={k} className="small">#{h.seq} {h.from ?? "—"} → {h.to} ({h.event})</li>)}</ul>
              {order.ignored.length > 0 && (<><h4 className="floor-h">Recorded but not applied</h4>
                <ul className="notes">{order.ignored.map((h, k) => <li key={k} className="small">#{h.seq} {h.event}: {h.why}</li>)}</ul></>)}
            </>)}
          </aside>
        </div>

        <h3>Event timeline (append-only ledger)</h3>
        <div className="scroll"><table className="q-table xlab-events" aria-label="Event timeline">
          <thead><tr><th>#</th><th>Time (synthetic)</th><th>Event</th><th>Order</th><th>Source</th><th>Details</th><th>Event id</th></tr></thead>
          <tbody>{sc.events.map((e, k) => (
            <tr key={e.seq} className={k === i ? "sel" : ""} onClick={() => setStep(k)}>
              <td>{e.seq}</td><td className="small">{e.ts_utc.slice(11, 19)}</td><td><code>{e.kind}</code></td>
              <td>{e.order_id ? short(e.order_id) : "—"}</td><td>{e.source}</td><td className="small">{summary(e)}</td><td className="small"><code>{e.event_id}</code></td>
            </tr>))}</tbody>
        </table></div>
        {sc.duplicates.length > 0 && <p className="small">Repeated updates (stored once, kept here for evidence): {sc.duplicates.map((d) => d.event_id).join(", ")}</p>}

        <h3>Orders (final)</h3>
        <div className="scroll"><table className="q-table" aria-label="Orders">
          <thead><tr><th>Order</th><th>State</th><th>Qty</th><th>Filled</th><th>Remaining</th><th>Cancelled</th><th>Avg price</th><th>Fees</th><th>Submits</th><th>Reasons</th></tr></thead>
          <tbody>{sc.orders.map((o) => (
            <tr key={o.order_id} className={sel === o.order_id ? "sel" : ""}>
              <td><button type="button" className="cite" onClick={() => setSel(o.order_id)}>{short(o.order_id)}</button></td>
              <td><St s={o.state} /></td><td>{o.qty}</td><td>{o.filled_qty}</td><td>{o.remaining_qty}</td><td>{o.cancelled_qty}</td>
              <td>{o.avg_fill_price ?? "—"}</td><td>{o.fees}</td><td>{sc.broker_submit_calls[o.order_id] ?? 0}</td><td className="small">{o.reasons.join("; ") || "—"}</td>
            </tr>))}</tbody>
        </table></div>
        <p className="small">Final: cash {money(sc.cash)} · equity {money(sc.equity)} · fees {sc.fees} · held exposure {money(sc.held_exposure)} ·
          pending entries {money(sc.pending_exposure)} · gross {money(sc.gross_exposure)}</p>

        {sc.risk_rejections.length > 0 && (<><h3>Blocked before submission (risk limits, stale data, reconciliation, emergency stop)</h3>
          <ul className="notes">{sc.risk_rejections.map((r) => <li key={r.order_id} className="small">{short(r.order_id)}: {r.reasons.join("; ")}</li>)}</ul></>)}

        {sc.emergency_stop.active && (<>
          <h3>Emergency stop: <span style={{ color: sc.emergency_stop.overall === "COMPLETE" ? "#14b8a6" : "#ef4444" }}>{sc.emergency_stop.overall}</span></h3>
          <p className="small warn">{sc.emergency_stop.note} Remaining exposure: {money(sc.emergency_stop.remaining_exposure ?? 0)}.</p>
          <div className="scroll"><table className="q-table" aria-label="Emergency stop steps">
            <thead><tr><th>Step</th><th>Status</th></tr></thead>
            <tbody>{sc.emergency_stop.steps!.map((s) => <tr key={s.step}><td>{s.step}</td><td>{s.status}</td></tr>)}</tbody>
          </table></div>
        </>)}

        <h3>Checks against the records</h3>
        <div className="scroll"><table className="q-table" aria-label="Scenario checks">
          <thead><tr><th>Kind</th><th>Check</th><th>Result</th><th>Evidence</th></tr></thead>
          <tbody>{[...sc.expectations.map((c) => ["expected outcome", c] as const), ...sc.invariants.map((c) => ["invariant", c] as const)].map(([k, c], j) => (
            <tr key={j}><td className="small">{k}</td><td className="small">{c.check}</td>
              <td><strong style={{ color: c.passed ? "#14b8a6" : "#ef4444" }}>{c.passed ? "PASS" : "FAIL"}</strong></td>
              <td className="small">{(c.detail ?? "").slice(0, 200)}</td></tr>))}</tbody>
        </table></div>
      </>)}

      <h3>Execution-policy decisions still open (not chosen by the lab)</h3>
      <ul className="notes">{data.policy_gaps.map((g, k) => <li key={k} className="small">{g}</li>)}</ul>
    </section>
  );
}
