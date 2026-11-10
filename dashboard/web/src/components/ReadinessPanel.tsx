import { useEffect, useState } from "react";
import { useLiveJson } from "../useLiveJson";

// Market readiness (GET /api/monitor/readiness): deterministic checks over real records, the session
// reliability summary under the existing written criterion, and the incident history. Missing evidence
// is UNKNOWN, never PASS. A closed market is expected, not a failure. No orders exist.

interface Check { id: string; label: string; status: string; summary: string; checked_utc: string; changed_utc: string | null; recorded: boolean }
type N = number | null;
interface Session {
  session_date: string; state: string; qualifies: boolean; why: string; scheduled_minutes?: N;
  live_on_time_min?: N; live_late_recovery_min?: N; live_missing_max?: N; unplanned_downtime_minutes?: N;
  restarts?: N; request_failures?: N; access_refusals?: N; comparisons_outstanding_min?: N;
  anomalies?: N; revisions?: N;
}
interface Incident {
  id: number; kind: string; state: string; opened_utc: string; last_seen_utc: string; observations: number; detail: string;
  recovery: string; acknowledged_utc: string | null; resolved_utc: string | null; resolution: string | null;
}
interface Readiness {
  label: string; evaluated_utc: string; overall: string; counts: Record<string, number>; checks: Check[];
  reliability: { criterion: string; target: number; current_consecutive: number; best_consecutive: number; gap: string;
                 reliability_gate: string; sessions: Session[] } | null;
  incidents: Incident[]; pending_storage_incidents: unknown[]; operating_note: string;
}

const et = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleString("en-US", { timeZone: "America/New_York", hour12: false, month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit" }) + " ET" : "—";
const cls = (s: string) => `ready-${s.toLowerCase()}`;
// Unavailable evidence is shown as "unknown", never as 0 or a blank that could read as "none".
const u = (v: number | null | undefined) => (v === null || v === undefined ? <span className="ready-unknown">unknown</span> : v);

export default function ReadinessPanel() {
  const [tick, setTick] = useState(0);
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => { const id = window.setInterval(() => setTick((t) => t + 1), 15000); return () => window.clearInterval(id); }, []);
  const { data, error } = useLiveJson<Readiness>("/api/monitor/readiness", tick);

  const ack = async (id: number) => {
    try {
      const r = await fetch("/api/monitor/incidents/ack", { method: "POST", body: JSON.stringify({ id }),
        headers: { "Content-Type": "application/json", "X-Dashboard-Control": "1" } });
      const j = await r.json();
      setMsg(j.result ?? j.error ?? `HTTP ${r.status}`);
      setTick((t) => t + 1);
    } catch (e) { setMsg(String(e)); }
  };

  if (error) {
    // "HTTP nnn" means the server answered but the readiness evaluation failed: that is UNKNOWN, not "server down".
    const answered = /^HTTP \d+/.test(error);
    return (
      <section className="panel wide readiness" aria-label="Market readiness">
        {answered ? (
          <>
            <h2>Market readiness: <span className="ready-unknown">UNKNOWN</span></h2>
            <p><strong>Server responding: PASS</strong>, but the readiness evaluation failed ({error}). No check result is
              shown, because none could be computed. See the Events list below.</p>
          </>
        ) : (
          <>
            <h2>Market readiness: <span className="ready-fail">FAIL</span></h2>
            <p><strong>Server responding: FAIL</strong> ({error}). Start it with <code>.venv\Scripts\python -m trading.dashboard.server</code>.</p>
          </>
        )}
      </section>
    );
  }
  if (!data) return <section className="panel wide readiness" aria-label="Market readiness"><h2>Market readiness</h2><p>Checking…</p></section>;
  const rel = data.reliability;
  const openInc = data.incidents.filter((i) => i.state !== "resolved");
  return (
    <section className="panel wide readiness" aria-label="Market readiness">
      <h2>Market readiness: <span className={cls(data.overall)}>{data.overall}</span>
        <small> · {data.counts.PASS} pass · {data.counts.WARNING} warning · {data.counts.FAIL} fail · {data.counts.UNKNOWN} unknown · evaluated {et(data.evaluated_utc)}</small></h2>
      <p className="note">{data.label}. Missing evidence shows UNKNOWN, never PASS. A closed market is expected, not a failure. {data.operating_note}</p>
      <div className="table-scroll">
        <table className="job-table" aria-label="Readiness checks">
          <thead><tr><th>Status</th><th>Check</th><th>Result</th><th>Last checked</th><th>Status since</th></tr></thead>
          <tbody>{data.checks.map((c) => (
            <tr key={c.id}><td className={cls(c.status)}><strong>{c.status}</strong></td><td>{c.label}</td><td>{c.summary}</td>
              <td>{et(c.checked_utc)}{c.recorded ? "" : " (not recorded)"}</td><td>{et(c.changed_utc)}</td></tr>
          ))}</tbody>
        </table>
      </div>

      <h3>Incidents ({openInc.length} unresolved)</h3>
      {msg && <p className="note" role="status">{msg}</p>}
      {data.incidents.length === 0 ? <p>No incident recorded.</p> : (
        <div className="table-scroll">
          <table className="job-table" aria-label="Incident history">
            <thead><tr><th>State</th><th>Incident</th><th>Opened</th><th>Last seen</th><th>Seen</th><th>Detail and recovery</th><th></th></tr></thead>
            <tbody>{data.incidents.map((i) => (
              <tr key={i.id}><td><strong>{i.state.toUpperCase()}</strong>{i.resolved_utc ? <><br />{et(i.resolved_utc)}</> : null}</td>
                <td>{i.kind.replace(/_/g, " ")}</td><td>{et(i.opened_utc)}</td><td>{et(i.last_seen_utc)}</td><td>{i.observations}×</td>
                <td>{i.detail}<br /><em>{i.state === "resolved" ? i.resolution : i.recovery}</em>{i.acknowledged_utc ? <><br />acknowledged {et(i.acknowledged_utc)}</> : null}</td>
                <td>{i.state === "open" && <button type="button" onClick={() => ack(i.id)}>Acknowledge</button>}</td></tr>
            ))}</tbody>
          </table>
        </div>
      )}

      {rel && (
        <>
          <h3>Report completion: {rel.current_consecutive} of {rel.target} consecutive sessions (best {rel.best_consecutive})</h3>
          <p className="note">Criterion: {rel.criterion} <strong>Gap:</strong> {rel.gap} <strong>Reliability gate:</strong> {rel.reliability_gate}.</p>
          <div className="table-scroll">
            <table className="job-table" aria-label="Report completion by session">
              <thead><tr><th>Session</th><th>State</th><th>Qualifies</th><th>Live on time (min)</th><th>Late recovery</th><th>Missing live</th>
                <th>Unplanned downtime</th><th>Restarts</th><th>Request failures</th><th>Refusals</th><th>Comparisons outstanding</th>
                <th>Anomalies</th><th>Revisions</th><th>Why</th></tr></thead>
              <tbody>{rel.sessions.slice().reverse().map((s) => (
                <tr key={s.session_date}><td>{s.session_date}</td><td>{s.state}</td><td>{s.qualifies ? "yes" : "no"}</td>
                  <td>{u(s.live_on_time_min)}{s.scheduled_minutes ? ` / ${s.scheduled_minutes}` : ""}</td><td>{u(s.live_late_recovery_min)}</td>
                  <td>{u(s.live_missing_max)}</td><td>{u(s.unplanned_downtime_minutes)}</td><td>{u(s.restarts)}</td>
                  <td>{u(s.request_failures)}</td><td>{u(s.access_refusals)}</td><td>{u(s.comparisons_outstanding_min)}</td>
                  <td>{u(s.anomalies)}</td><td>{u(s.revisions)}</td><td>{s.why}</td></tr>
              ))}</tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
