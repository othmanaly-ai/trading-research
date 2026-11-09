import { useEffect, useState } from "react";
import { useLiveJson } from "../useLiveJson";

// Milestone 1 dry run (trading/operations). Read-only view of GET /api/operations: environment,
// approved strategy, order gate, kill switch, runner health, entry permission with reasons, and the
// session classifications. No orders exist; every entry decision is DENIED in DRY_RUN.

interface Ops {
  label: string; environment: string; now_utc: string; phase: string;
  today: { date: string; trading_day: boolean; open?: { et: string }; close?: { et: string }; report?: { et: string }; decision_minutes?: number };
  approved_strategy: string; approval_reasons: string[];
  order_gate: { enabled: boolean; trading_mode: string };
  kill_switch: { on: boolean; reason: string };
  broker_reconciliation: string;
  available: boolean; note?: string; records?: string;
  runner?: { run_id: string; started_utc: string; start_class: string; ended_utc: string | null; exit_reason: string | null;
             heartbeat_age_s: number | null; alive: boolean; code_fingerprint: string } | null;
  today_decisions?: { recorded: number; expected: number; allowed: number };
  latest_decision?: { minute_utc: string; allowed: boolean; reasons: string[]; clock_ok: boolean | null;
                      data: { worker_alive: boolean; feed: string | null; symbols: Record<string, { age_s: number | null; fresh: boolean }> } | null } | null;
  recent_reports?: { session_date: string; version: number; classification: string; created_utc: string }[];
  acceptance?: { current_streak: number; required_consecutive_passes: number; accepted: boolean; accepted_on: string | null;
                 sessions: { session_date: string; classification: string; reasons?: string[] }[] };
}

const et = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleTimeString("en-US", { timeZone: "America/New_York", hour12: false }) + " ET" : "—";

export default function OperationsView() {
  const [tick, setTick] = useState(0);
  useEffect(() => { const id = window.setInterval(() => setTick((t) => t + 1), 10000); return () => window.clearInterval(id); }, []);
  const { data, error } = useLiveJson<Ops>("/api/operations", tick);
  if (error) return <section className="panel wide"><h2>Operations (dry run)</h2><p className="error">Could not load: {error}</p></section>;
  if (!data) return <section className="panel wide"><h2>Operations (dry run)</h2><p>Loading…</p></section>;
  const ld = data.latest_decision;
  return (
    <section className="panel wide" aria-label="Operations dry run">
      <h2>Operations · {data.environment}</h2>
      <p className="note">{data.label}</p>
      <table className="artifacts" aria-label="Operating state">
        <tbody>
          <tr><th>Environment</th><td>{data.environment} (no order code exists)</td></tr>
          <tr><th>Entry permission</th><td><strong>{ld ? (ld.allowed ? "ALLOWED" : "DENIED") : "no decision recorded today"}</strong>
            {ld && <> at {et(ld.minute_utc)}</>}</td></tr>
          <tr><th>Approved strategy</th><td>{data.approved_strategy}{data.approval_reasons.length ? ` (${data.approval_reasons.join("; ")})` : ""}</td></tr>
          <tr><th>Order gate</th><td>{data.order_gate.enabled ? "ENABLED (the runner refuses to operate)" : "disabled"} · mode {data.order_gate.trading_mode}</td></tr>
          <tr><th>Kill switch</th><td>{data.kill_switch.on ? `ON: ${data.kill_switch.reason}` : "off"}</td></tr>
          <tr><th>Broker reconciliation</th><td>{data.broker_reconciliation}</td></tr>
          <tr><th>Today</th><td>{data.today.trading_day ? `${data.today.date}: open ${data.today.open?.et}, close ${data.today.close?.et}, report ${data.today.report?.et} ET · phase ${data.phase}` : `${data.today.date}: no session`}</td></tr>
          <tr><th>Runner</th><td>{!data.available ? (data.note ?? "no records") : data.runner
            ? `${data.runner.alive ? "RUNNING" : data.runner.ended_utc ? `ended (${data.runner.exit_reason})` : "NOT RESPONDING"} · started ${et(data.runner.started_utc)} (${data.runner.start_class}) · heartbeat ${data.runner.heartbeat_age_s ?? "—"} s ago`
            : "never run"}</td></tr>
          {data.today_decisions && <tr><th>Decisions today</th><td>{data.today_decisions.recorded} of {data.today_decisions.expected} recorded · {data.today_decisions.allowed} allowed</td></tr>}
          {ld?.data && <tr><th>Feed and freshness</th><td>{ld.data.feed ?? "unknown"} · worker {ld.data.worker_alive ? "alive" : "NOT alive"} · {Object.entries(ld.data.symbols).map(([s, v]) => `${s} ${v.fresh ? "fresh" : "STALE"} (${v.age_s ?? "—"} s)`).join(", ")}</td></tr>}
          {ld && <tr><th>Broker clock</th><td>{ld.clock_ok === null ? "not verified" : ld.clock_ok ? "within tolerance" : "beyond tolerance"}</td></tr>}
          <tr><th>Records</th><td><code>{data.records ?? "—"}</code></td></tr>
        </tbody>
      </table>
      {ld && (<><h3>Why no entry (latest decision)</h3><ul>{ld.reasons.map((r) => <li key={r}>{r}</li>)}</ul></>)}
      {data.acceptance && (
        <>
          <h3>Acceptance: {data.acceptance.current_streak} of {data.acceptance.required_consecutive_passes} consecutive PASS
            {data.acceptance.accepted ? ` · accepted on ${data.acceptance.accepted_on}` : ""}</h3>
          <p className="note">Verifies operation, not profitability. Rules: docs/DRY_RUN_ACCEPTANCE.md. Missing evidence never counts as a pass.</p>
          <table className="job-table" aria-label="Session classifications">
            <thead><tr><th>Session</th><th>Classification</th><th>Main reasons</th></tr></thead>
            <tbody>{data.acceptance.sessions.slice().reverse().map((s) => (
              <tr key={s.session_date}><td>{s.session_date}</td><td>{s.classification}</td><td>{(s.reasons ?? []).join(" · ") || "—"}</td></tr>
            ))}</tbody>
          </table>
        </>
      )}
    </section>
  );
}
