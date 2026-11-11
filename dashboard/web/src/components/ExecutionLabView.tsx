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
  flags: { emergency_stop: boolean; reconciliation_required: boolean; restart_pending_reconciliation: boolean; unresolved_discrepancies?: boolean };
  protection?: Prot[]; discrepancies?: number;
}
interface Prot { symbol: string; position: number; protected_qty: number; held_inactive_qty: number; unprotected_qty: number; unprotected_since: string | null }
interface PolicyRow { field: string; decision: string; meaning: string; value: unknown; status: string }
interface Readiness {
  overall: string; strategy: string; real_money: string; adapter: { status: string; evidence: string };
  items: { id: string; item: string; status: string; evidence: string }[];
  crash_drills: { recorded_utc: string; passed: boolean; drills: { drill: string; title: string; checks: Check[]; steps: { step: string; crash_at: string | null; exit_code: number }[] }[] } | null;
}
interface Check { check: string; passed: boolean; detail?: string }
interface Stop { active: boolean; overall?: string; steps?: { step: string; status: string }[]; cancellations?: any[]; unresolved?: string[]; remaining_exposure?: number; note?: string }
interface Scenario {
  id: string; title: string; seed: number; config_version: string; passed: boolean; expectations: Check[]; invariants: Check[];
  events: Ev[]; duplicates: { event_id: string; ts_utc: string }[]; snapshots: Snap[]; orders: OrderRow[]; cash: number; equity: number;
  fees: number; held_exposure: number; pending_exposure: number; gross_exposure: number; unknown_outcomes: string[]; unresolved: string[];
  risk_rejections: { order_id: string; reasons: string[] }[]; emergency_stop: Stop; broker_submit_calls: Record<string, number>;
  protection: Prot[]; unprotected_intervals: { symbol: string; from_utc: string; to_utc: string }[];
  discrepancies: Record<string, any>[]; attention: { order_id: string | null; what: string; age_s: number | null; action: string }[];
  policy_label: string; policy: PolicyRow[];
  intents: { order_id: string; seq: number; purpose: string; symbol: string; side: string; qty: number; spec: Record<string, any> | null;
    source: string; validation: string; reasons: string[] }[];
}
interface Data {
  mode: string; label: string; notice: string; policy_gaps: string[];
  config: { version: string; limits: string; cost_model: string; start_cash: number; max_data_age_s: number; max_data_age_note: string; session: string };
  scenarios: { id: string; title: string; passed: boolean; events: number; checks: number; failed_checks: number; unknown_outcomes: number;
    unresolved: number; risk_rejections: number; emergency_stop: string | null }[];
  selected: Scenario; approved_policy: PolicyRow[]; strategy_status: string; readiness?: Readiness;
  controls?: { control: string; status: string; evidence: string }[];
}
// Enforced by code (with named evidence) vs proposed, unset, missing or not connected: never inferred from a document.
const CTRL_COL = (s: string) => s.startsWith("ENFORCED") ? "#14b8a6" : s.startsWith("PROPOSED") ? "#eab308" : "#ef4444";

const STATE_COLOR: Record<string, number> = {
  CREATED: 0x64748b, VALIDATED: 0x64748b, SUBMISSION_PENDING: 0x38bdf8, ACCEPTED: 0x22d3ee, PARTIALLY_FILLED: 0xa78bfa,
  FILLED: 0x14b8a6, REJECTED: 0xef4444, BLOCKED: 0xf97316, CANCEL_PENDING: 0xeab308, CANCELLED: 0x94a3b8, UNKNOWN: 0xe11d48,
  HELD: 0x78716c,
};
// Specialist FUNCTIONS of the desk: deterministic code paths, not agents. A building lights only for the recorded
// event at the current timeline step that belongs to that function.
const FUNCTIONS: { id: string; title: string; slot: [number, number]; kinds: string[] }[] = [
  { id: "f_intents", title: "Intent desk", slot: [-36, -10], kinds: ["intent_created"] },
  { id: "f_risk", title: "Risk & policy gate", slot: [-24, -30], kinds: ["validated", "blocked"] },
  { id: "f_broker", title: "Broker port (FAKE)", slot: [0, -38], kinds: ["submit_requested", "broker_ack", "broker_reject", "submit_outcome_unknown",
    "fill", "cancel_requested", "cancel_rejected", "cancel_request_failed", "broker_cancelled", "broker_unreachable", "resubmit_refused"] },
  { id: "f_recon", title: "Reconciliation", slot: [24, -30], kinds: ["reconciliation", "reconciliation_complete", "reconciliation_incomplete",
    "reconciliation_failed", "intent_expired_unsent"] },
  { id: "f_protect", title: "Protection", slot: [36, -10], kinds: ["leg_held", "leg_active", "protection_alert"] },
  { id: "f_stop", title: "Emergency stop", slot: [30, 18], kinds: ["emergency_stop", "stop_action"] },
  { id: "f_journal", title: "Journal (ledger)", slot: [-30, 18], kinds: ["mark", "process_start"] },
];
const FN_OF: Record<string, string> = Object.fromEntries(FUNCTIONS.flatMap((f) => f.kinds.map((k) => [k, f.id])));
const RCOL: Record<string, string> = { MET: "#14b8a6", "NOT MET": "#ef4444", "NOT GIVEN": "#ef4444", UNKNOWN: "#a855f7" };
const hex = (c: number) => `#${c.toString(16).padStart(6, "0")}`;
const short = (id: string) => id.split(":").pop() ?? id;
const money = (n: number) => n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const KIND: Record<string, "arrival" | "start" | "complete" | "fail"> = {
  submit_requested: "start", broker_ack: "arrival", fill: "arrival", broker_cancelled: "complete", cancel_requested: "start",
  broker_reject: "fail", submit_outcome_unknown: "fail", blocked: "fail", cancel_request_failed: "fail", reconciliation: "complete",
  leg_held: "start", leg_active: "complete", protection_alert: "fail", reconciliation_complete: "complete",
  reconciliation_incomplete: "fail", reconciliation_failed: "fail", intent_expired_unsent: "fail", validated: "complete",
  intent_created: "arrival", emergency_stop: "fail", stop_action: "start", cancel_rejected: "fail",
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
    const evNow = ev ? { id: `${sc.id}:${ev.event_id}`, kind: KIND[ev.kind] ?? ("arrival" as const) } : undefined;
    const upto = sc.events.slice(0, i + 1);
    const unprot = (snap.protection ?? []).reduce((a, p) => a + p.unprotected_qty, 0);
    const held = Object.values(snap.positions).reduce((a, q) => a + q, 0);
    const fnStatus: Record<string, [string, boolean, boolean]> = {   // [status, warn, dim]
      f_intents: [`${upto.filter((e) => e.kind === "intent_created").length} intent(s)`, false, false],
      f_risk: [`${upto.filter((e) => e.kind === "blocked").length} blocked · ${upto.filter((e) => e.kind === "validated").length} validated`,
        upto.some((e) => e.kind === "blocked"), false],
      f_broker: ["FAKE broker · offline", Object.values(snap.orders).some((o) => o.state === "UNKNOWN"), false],
      f_recon: [snap.flags.reconciliation_required ? `REQUIRED${snap.discrepancies ? ` · ${snap.discrepancies} discrepancy(ies)` : ""}` : "clear",
        snap.flags.reconciliation_required, false],
      f_protect: [held === 0 ? "no position" : unprot > 0 ? `UNPROTECTED ${unprot}` : "all filled shares protected", unprot > 0, held === 0],
      f_stop: [snap.flags.emergency_stop ? "ACTIVE" : "off", snap.flags.emergency_stop, !snap.flags.emergency_stop],
      f_journal: [`${i + 1} events (append-only)`, false, false],
    };
    const exec: TowerSpec = {
      id: "execution", color: snap.flags.emergency_stop ? 0xef4444 : snap.flags.reconciliation_required ? 0xe11d48 : 0x6366f1,
      slot: [0, 0], archetype: "command", category: "EXECUTION · offline simulation", title: "Execution",
      status: `step ${i + 1}/${n} · NO APPROVED ACTIVE STRATEGY`,
      warn: snap.flags.emergency_stop || snap.flags.reconciliation_required, labelMode: "full",
      lines: [{ cls: "tl-name", text: "Execution" }, { cls: "tl-status", text: `step ${i + 1}/${n}` }],
      ariaLabel: "Execution building: scenario details", pulseKey: "",
    };
    const fns = FUNCTIONS.map((f): TowerSpec => {
      const [status, warn, dim] = fnStatus[f.id];
      return {
        id: f.id, color: warn ? 0xf59e0b : 0x475569, slot: f.slot, archetype: "finned", category: "FUNCTION · deterministic code",
        title: f.title, status, warn, dim, labelMode: sel && sel !== "execution" ? "hidden" : "compact",
        event: ev && FN_OF[ev.kind] === f.id ? evNow : undefined,
        lines: [{ cls: "tl-name", text: f.title }, { cls: "tl-status", text: status }],
        ariaLabel: `${f.title} (deterministic function): ${status}`, pulseKey: "",
      };
    });
    const orders = ids.map((id, k): TowerSpec => {
      const s = snap.orders[id];
      const a = (2 * Math.PI * k) / Math.max(ids.length, 1);
      const state = s?.state ?? "not yet created";
      return {
        id, color: STATE_COLOR[state] ?? 0x1e293b, slot: [Math.round(Math.sin(a) * 15), Math.round(Math.cos(a) * 15) + 4],
        archetype: state === "UNKNOWN" ? "twisted" : "terraced", category: id.includes(":stop") ? "PROTECTIVE ORDER · synthetic" : "ORDER · synthetic",
        title: `order ${short(id)}`,
        status: s ? `${state} · ${s.filled_qty}/${s.filled_qty + s.remaining_qty + s.cancelled_qty}` : "not yet created",
        dim: !s || ["CANCELLED", "REJECTED", "BLOCKED", "HELD"].includes(state), warn: state === "UNKNOWN" || state === "CANCEL_PENDING",
        active: ["SUBMISSION_PENDING", "ACCEPTED", "PARTIALLY_FILLED"].includes(state), labelMode: "compact",
        event: ev && cur === id ? evNow : undefined,          // the recorded event at this step only (never replayed)
        lines: [{ cls: "tl-name", text: `order ${short(id)}` }, { cls: "tl-status", text: state }],
        ariaLabel: `Order ${short(id)}: ${state}. Show order details.`, pulseKey: "",
      };
    });
    return [exec, ...fns, ...orders];
  }, [sc, snap, ev, i, n, sel]);
  const edges = useMemo<EdgeSpec[]>(() => [
    ...FUNCTIONS.map((f) => ({ from: f.id, to: "execution", style: "declared" as const })),
    ...(sc?.orders ?? []).map((o) => ({ from: "execution", to: o.order_id,
      style: (snap?.orders[o.order_id] ? "recorded" : "declared") as "recorded" | "declared" })),
  ], [sc, snap]);

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

      <div className="desk-cc" aria-label="Paper-test readiness">
        <h3>Supervised paper-order test: <span style={{ color: data.readiness?.overall === "NOT READY" ? "#ef4444" : "#eab308" }}>
          {data.readiness?.overall ?? "UNKNOWN"}</span> <span className="small muted">derived from records; code or documents existing is not completion</span></h3>
        <p className="small"><strong>{data.strategy_status}.</strong> Strategies may later hand versioned intents to this core
          (trading/execution_lab/intents.py); every strategy intent is refused until the owner approves one. {data.readiness?.real_money}</p>
        {data.readiness && (<div className="scroll"><table className="q-table" aria-label="Readiness prerequisites">
          <thead><tr><th>Prerequisite</th><th>Status</th><th>Evidence</th></tr></thead>
          <tbody>{data.readiness.items.map((r) => (
            <tr key={r.id}><td>{r.item}</td><td><strong style={{ color: RCOL[r.status] ?? "#eab308" }}>{r.status}</strong></td>
              <td className="small">{r.evidence}</td></tr>))}
            <tr><td>Paper order adapter</td><td><strong style={{ color: "#eab308" }}>{data.readiness.adapter.status}</strong></td>
              <td className="small">{data.readiness.adapter.evidence}</td></tr></tbody>
        </table></div>)}
        <details><summary className="small">Approved execution policy: {data.approved_policy.filter((r) => r.status === "UNSET").length} of {data.approved_policy.length} fields UNSET</summary>
          <div className="scroll"><table className="q-table" aria-label="Approved execution policy">
            <thead><tr><th>Field</th><th>Decision</th><th>Meaning</th><th>Approved value</th></tr></thead>
            <tbody>{data.approved_policy.map((r) => <tr key={r.field}><td><code>{r.field}</code></td><td>{r.decision}</td>
              <td className="small">{r.meaning}</td><td><strong style={{ color: "#ef4444" }}>{r.status}</strong></td></tr>)}</tbody>
          </table></div></details>
        {data.controls && (<details open><summary className="small">Controls: enforced by code vs proposed / unset (a proposed control is not an enforced control)</summary>
          <div className="scroll"><table className="q-table" aria-label="Controls">
            <thead><tr><th>Control</th><th>Status</th><th>Evidence</th></tr></thead>
            <tbody>{data.controls.map((c) => <tr key={c.control}><td>{c.control}</td>
              <td><strong style={{ color: CTRL_COL(c.status) }}>{c.status}</strong></td><td className="small">{c.evidence}</td></tr>)}</tbody>
          </table></div></details>)}
      </div>

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
              <h3>Execution · step {i + 1}/{n} <span className="small muted">SIMULATED (fake broker)</span></h3>
              <dl className="small desk-dl">
                <dt>Cash</dt><dd>{money(snap!.cash)}</dd><dt>Equity</dt><dd>{money(snap!.equity)}</dd>
                <dt>Positions</dt><dd>{Object.entries(snap!.positions).map(([s, q]) => `${s} ${q}`).join(", ") || "none"}</dd>
                <dt>Held exposure</dt><dd>{money(snap!.held_exposure)}</dd>
                <dt>Pending entries</dt><dd>{money(snap!.pending_exposure)} (counts toward exposure, incl. unknown outcomes)</dd>
                <dt>Emergency stop</dt><dd>{snap!.flags.emergency_stop ? <span className="warn">ACTIVE</span> : "off"}</dd>
                <dt>Reconciliation</dt><dd>{snap!.flags.reconciliation_required ? <span className="warn">REQUIRED</span> : "not required"}</dd>
              </dl>
              <h4 className="floor-h">Operational board at this step</h4>
              {(() => {
                const os = Object.entries(snap!.orders);
                const pick = (states: string[]) => os.filter(([, o]) => states.includes(o.state));
                const row = (title: string, list: [string, Snap["orders"][string]][], warn = false) => (
                  <p className="small"><strong className={warn && list.length ? "warn" : ""}>{title}: {list.length}</strong>{list.length > 0 && " · "}
                    {list.map(([id, o], k) => { const tot = o.filled_qty + o.remaining_qty + o.cancelled_qty;
                      return <span key={id}>{k ? ", " : ""}<button type="button" className="cite" onClick={() => setSel(id)}>{short(id)}</button> {tot ? `${o.filled_qty}/${tot} filled` : "not sent"}</span>; })}</p>);
                return (<>
                  {row("Working (accepted or sent, nothing filled)", pick(["SUBMISSION_PENDING", "ACCEPTED"]).filter(([, o]) => o.filled_qty === 0))}
                  {row("Partially filled", pick(["PARTIALLY_FILLED"]))}
                  {row("Uncertain (outcome unknown or cancel not confirmed)", pick(["UNKNOWN", "CANCEL_PENDING"]), true)}
                  {row("Held legs (inactive: NOT protection)", pick(["HELD"]))}
                  {row("Blocked before submission", pick(["BLOCKED"]))}
                </>);
              })()}
              <h4 className="floor-h">Protection at this step</h4>
              {(snap!.protection ?? []).length === 0 ? <p className="small">no filled long position</p> : (
                <ul className="notes">{snap!.protection!.map((p) => <li key={p.symbol} className={`small ${p.unprotected_qty ? "warn" : ""}`}>
                  {p.symbol}: {p.position} held · {p.protected_qty} protected by an ACTIVE broker-side stop · {p.unprotected_qty} unprotected
                  {p.unprotected_since ? ` since ${p.unprotected_since.slice(11, 19)}` : ""}{p.held_inactive_qty ? ` · ${p.held_inactive_qty} in an inactive (held) leg` : ""}</li>)}</ul>)}
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
              <ul className="notes">{order.history.map((h, k) => <li key={k} className="small">
                <button type="button" className="cite" title="Show this ledger event in the timeline" onClick={() => { const at = sc.events.findIndex((e) => e.seq === h.seq); if (at >= 0) setStep(at); }}>#{h.seq}</button> {h.from ?? "—"} → {h.to} ({h.event})</li>)}</ul>
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

        <h3>Intents and validation <span className="small muted">policy for this scenario: {sc.policy_label}</span></h3>
        <div className="scroll"><table className="q-table" aria-label="Intents">
          <thead><tr><th>#</th><th>Intent</th><th>Purpose</th><th>Source</th><th>Order spec (from policy)</th><th>Validation</th></tr></thead>
          <tbody>{sc.intents.map((t) => (
            <tr key={t.order_id} onClick={() => setStep(sc.events.findIndex((e) => e.seq === t.seq))}>
              <td>{t.seq}</td><td><button type="button" className="cite" onClick={() => setSel(t.order_id)}>{short(t.order_id)}</button> {t.side} {t.qty} {t.symbol}</td>
              <td>{t.purpose}</td><td className="small">{t.source}</td>
              <td className="small"><code>{t.spec ? Object.entries(t.spec).map(([k, v]) => `${k}=${typeof v === "object" ? JSON.stringify(v) : v}`).join(" ") : "none (policy unset)"}</code></td>
              <td className="small"><strong>{t.validation}</strong>{t.reasons.length > 0 && <div className="warn">{t.reasons.join("; ")}</div>}</td>
            </tr>))}</tbody>
        </table></div>

        <h3>Protection <span className="small muted">only an ACTIVE broker-side stop counts; a HELD bracket leg is not protection</span></h3>
        {sc.protection.length === 0 ? <p className="small">No filled position at the end of this scenario.</p> : (
          <div className="scroll"><table className="q-table" aria-label="Protection">
            <thead><tr><th>Symbol</th><th>Filled position</th><th>Protected (active stop)</th><th>Held inactive leg</th><th>Unprotected</th><th>Unprotected since</th></tr></thead>
            <tbody>{sc.protection.map((p) => (
              <tr key={p.symbol}><td>{p.symbol}</td><td>{p.position}</td><td>{p.protected_qty}</td><td>{p.held_inactive_qty}</td>
                <td><strong style={{ color: p.unprotected_qty ? "#ef4444" : "#14b8a6" }}>{p.unprotected_qty}</strong></td>
                <td className="small">{p.unprotected_since ?? "—"}</td></tr>))}</tbody>
          </table></div>)}
        {sc.unprotected_intervals.length > 0 && <p className="small">Recorded unprotected intervals: {sc.unprotected_intervals.map((u) =>
          `${u.symbol} ${u.from_utc.slice(11, 19)} → ${u.to_utc.slice(11, 19)}`).join(" · ")}</p>}

        <h3>Unresolved actions and timing <span className="small muted">timing comes from the policy; UNSET means an owner decision</span></h3>
        {sc.attention.length === 0 ? <p className="small">Nothing unresolved at the end of this scenario.</p> : (
          <ul className="notes">{sc.attention.map((a, k) => <li key={k} className="small"><strong>{a.what}</strong>
            {a.order_id ? ` (${short(a.order_id)})` : ""}{a.age_s !== null ? ` · ${Math.round(a.age_s)} s` : ""} → <span className="warn">{a.action}</span></li>)}</ul>)}

        <h3>Reconciliation discrepancies <span className="small muted">shown as found; never forced to balance</span></h3>
        {sc.discrepancies.length === 0 ? <p className="small">None at the end of this scenario.</p> : (
          <div className="scroll"><table className="q-table" aria-label="Discrepancies">
            <thead><tr><th>Kind</th><th>Details</th></tr></thead>
            <tbody>{sc.discrepancies.map((d, k) => <tr key={k}><td><strong className="warn">{d.kind}</strong></td>
              <td className="small">{Object.entries(d).filter(([key]) => key !== "kind").map(([key, v]) => `${key}: ${v}`).join(" · ")}</td></tr>)}</tbody>
          </table></div>)}

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

      {data.readiness?.crash_drills && (<>
        <h3>Fresh-process crash drills <span className="small muted">recorded run {data.readiness.crash_drills.recorded_utc} ·
          python -m trading.execution_lab.crashdrill run-all · each step a separate process</span></h3>
        <div className="scroll"><table className="q-table" aria-label="Crash drills">
          <thead><tr><th>Drill</th><th>Steps (crash point → exit code)</th><th>Checks</th></tr></thead>
          <tbody>{data.readiness.crash_drills.drills.map((d) => (
            <tr key={d.drill}><td className="small"><strong>{d.title}</strong></td>
              <td className="small">{d.steps.map((s) => `${s.step}${s.crash_at ? ` ✖ ${s.crash_at} → ${s.exit_code}` : ` → ${s.exit_code}`}`).join(" · ")}</td>
              <td className="small">{d.checks.map((c) => <div key={c.check}><strong style={{ color: c.passed ? "#14b8a6" : "#ef4444" }}>
                {c.passed ? "PASS" : "FAIL"}</strong> {c.check}</div>)}</td></tr>))}</tbody>
        </table></div>
      </>)}

      <h3>Execution-policy decisions still open (not chosen by the lab)</h3>
      <ul className="notes">{data.policy_gaps.map((g, k) => <li key={k} className="small">{g}</li>)}</ul>
    </section>
  );
}
