import { useEffect, useState } from "react";
import { useLiveJson } from "../useLiveJson";

// Monitoring session history and the daily evidence report (trading/monitor/reliability.py).
// Live capture, later IEX revisions and delayed SIP are shown separately on purpose.

interface SessionRow {
  session_date: string; state: string; detail: string | null; scheduled_minutes: number | null; early_close: boolean | null;
  live_received_min: number; compared_min: number; downtime_minutes: number | null; unplanned_downtime_minutes: number | null;
  request_failures: number | null; access_refusals: number | null; report_versions: number;
}
interface Sessions {
  sessions: SessionRow[]; operating_note: string;
  comparison_health: { state: string; detail: string; backoff_until_utc: string | null; last_success_utc: string | null };
}
type Dict = Record<string, any>;  // report sections are rendered generically but labelled explicitly

const STATE_CLASS: Record<string, string> = {
  finalized: "tone-ok", provisional: "tone-warn", in_progress: "", incomplete: "tone-danger", not_monitored: "muted",
};
const STATE_LABEL: Record<string, string> = {
  finalized: "FINALIZED", provisional: "PROVISIONAL", in_progress: "IN PROGRESS", incomplete: "INCOMPLETE",
  not_monitored: "NOT MONITORED",
};

function et(ts: string | null | undefined): string {
  if (!ts) return "—";
  return new Date(ts).toLocaleString("en-US", { timeZone: "America/New_York", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit", hour12: false }) + " ET";
}
const n = (x: number | null | undefined, d = 2) => (x === null || x === undefined ? "—" : Number(x).toFixed(d));
const pct = (x: number | null | undefined) => (x === null || x === undefined ? "—" : `${(x * 100).toFixed(1)}%`);
const secs = (x: number | null | undefined) => (x === null || x === undefined ? "—" : x < 120 ? `${Math.round(x)} s` : `${Math.round(x / 60)} min`);

export default function SessionHistory({ tick }: { tick: number }) {
  const { data, error } = useLiveJson<Sessions>("/api/monitor/sessions", Math.floor(tick / 15));
  const [date, setDate] = useState<string | null>(null);
  const [report, setReport] = useState<Dict | null>(null);
  const [minute, setMinute] = useState<{ symbol: string; t: string } | null>(null);
  const [rec, setRec] = useState<unknown>(null);
  useEffect(() => { if (!date && data?.sessions.length) setDate(data.sessions[0].session_date); }, [data, date]);
  useEffect(() => {
    if (!date) return;
    fetch(`/api/monitor/report?date=${date}`).then((r) => r.json()).then(setReport).catch(() => setReport(null));
  }, [date, Math.floor(tick / 15)]);
  useEffect(() => {
    if (!minute) { setRec(null); return; }
    fetch(`/api/quality/minute?symbol=${minute.symbol}&t=${encodeURIComponent(minute.t)}`).then((r) => r.json()).then(setRec);
  }, [minute]);

  if (error) return <p className="error">Could not load session history: {error}</p>;
  if (!data) return <p className="empty">Loading session history…</p>;
  const ev: Dict = report?.evidence ?? {};
  const syms = Object.keys(ev.live ?? {});
  return (
    <div className="sessions" aria-label="Monitoring session history">
      <p className="warn small" role="note">{data.operating_note}</p>
      <p className="small">Comparison worker: <strong>{data.comparison_health.state.toUpperCase()}</strong> · {data.comparison_health.detail}
        {data.comparison_health.backoff_until_utc ? ` · retry after ${et(data.comparison_health.backoff_until_utc)}` : ""}</p>
      {data.sessions.length === 0 ? <p className="empty">No monitored session yet.</p> : (
        <table className="q-table" aria-label="Monitored sessions">
          <thead><tr><th>Session</th><th>State</th><th>Scheduled min</th><th>Received live (min of symbols)</th><th>Compared with SIP</th>
            <th>Downtime (unplanned)</th><th>Request failures · refusals</th><th>Report versions</th><th></th></tr></thead>
          <tbody>{data.sessions.map((s) => (
            <tr key={s.session_date} className={date === s.session_date ? "sel" : ""}>
              <td>{s.session_date}{s.early_close ? " (early close)" : ""}</td>
              <td className={STATE_CLASS[s.state] ?? ""} title={s.detail ?? ""}>{STATE_LABEL[s.state] ?? s.state}</td>
              <td>{s.scheduled_minutes ?? "—"}</td><td>{s.live_received_min}</td><td>{s.compared_min}</td>
              <td>{s.downtime_minutes ?? "—"} ({s.unplanned_downtime_minutes ?? "—"})</td>
              <td>{s.request_failures ?? 0} · {s.access_refusals ?? 0}</td><td>{s.report_versions}</td>
              <td><button type="button" aria-pressed={date === s.session_date} onClick={() => setDate(s.session_date)}>Report</button></td>
            </tr>))}</tbody>
        </table>
      )}

      {report && (
        <div className="report" aria-label={`Evidence report ${report.session_date}`}>
          <h4>Evidence report · {report.session_date} · <span className={STATE_CLASS[report.status?.state] ?? ""}>{STATE_LABEL[report.status?.state] ?? report.status?.state}</span>
            {report.stored_version ? ` · stored version ${report.stored_version} (${et(report.stored_utc)})` : " · computed now (not stored: session not finalized)"}</h4>
          <p className="small muted">{report.label}. {report.status?.detail}</p>
          {ev.schedule && <p className="small">Scheduled: {et(ev.schedule.open_utc)} – {et(ev.schedule.close_utc)} · {ev.schedule.scheduled_minutes ?? "—"} minutes{ev.schedule.early_close ? " (early close)" : ""}{ev.schedule.note ? ` · ${ev.schedule.note}` : ""}</p>}

          {syms.length > 0 && (<>
            <h5>1 · What the live monitor received (IEX, real time) — never filled in from later re-fetches</h5>
            <table className="q-table"><thead><tr><th>Symbol</th><th>Minutes received</th><th>Normal · by catch-up</th><th>Latency normal · catch-up (median) · max</th>
              <th>Not received</th><th>…while SIP had a bar</th><th>Stale intervals (&gt;3 min)</th></tr></thead>
              <tbody>{syms.map((s) => { const l = ev.live[s]; return (
                <tr key={s}><td>{s}</td><td>{l.received_minutes}</td><td>{l.received_normal} · {l.received_by_catch_up}</td>
                  <td>{secs(l.latency_normal_median_s)} · {secs(l.latency_catch_up_median_s)} · {secs(l.latency_max_s)}</td>
                  <td>{l.not_received_minutes ?? "session open"}</td><td>{l.not_received_while_sip_had_a_bar}</td>
                  <td>{l.stale_intervals.length === 0 ? "none" : l.stale_intervals.slice(0, 4).map((x: Dict) => `${et(x.from_utc)}–${et(x.to_utc).replace(/^.*, /, "")} (${x.minutes} min, worker alive ${pct(x.worker_alive_share)})`).join("; ")}</td></tr>); })}</tbody></table>

            <h5>2 · Later IEX revisions (provider re-fetch vs the live capture)</h5>
            <table className="q-table"><thead><tr><th>Symbol</th><th>Minutes in both</th><th>Live differs from re-fetch</th><th>Re-fetch only (live missed)</th><th>Live only</th><th>Later IEX revisions</th></tr></thead>
              <tbody>{syms.map((s) => { const r = ev.iex_revisions[s]; return (
                <tr key={s}><td>{s}</td><td>{r.minutes_in_both}</td><td>{r.live_differs_from_refetch}</td><td>{r.refetch_only_minutes}</td><td>{r.live_only_minutes}</td><td>{r.later_iex_revisions}</td></tr>); })}</tbody></table>
            <p className="small muted">A later re-fetch is a different observation: it does not show that the live capture was complete or accurate.</p>

            <h5>3 · Delayed SIP comparison (eligible = bar end + 15 min under the free plan; received = actual arrival)</h5>
            <table className="q-table"><thead><tr><th>Symbol</th><th>Compared</th><th>Close diff vs re-fetched IEX |bps| median · max · max $</th>
              <th>Close diff vs live IEX |bps| median · max</th><th>High · low diff bps (median)</th><th>IEX volume share total · median</th>
              <th>Received after eligible: normal · catch-up (median)</th><th>SIP revisions</th></tr></thead>
              <tbody>{syms.map((s) => { const c = ev.sip_comparison[s]; return (
                <tr key={s}><td>{s}</td><td>{c.minutes_compared}</td>
                  <td>{n(c.close_diff_vs_refetched_iex_bps.median_abs)} · {n(c.close_diff_vs_refetched_iex_bps.max_abs)} · ${n(c.close_diff_vs_refetched_iex_bps.max_abs_usd)}</td>
                  <td>{n(c.close_diff_vs_live_iex_bps.median_abs)} · {n(c.close_diff_vs_live_iex_bps.max_abs)}</td>
                  <td>{n(c.high_diff_bps_median)} · {n(c.low_diff_bps_median)}</td>
                  <td>{pct(c.iex_volume_share_total)} · {pct(c.iex_volume_share_median)}</td>
                  <td>{secs(c.sip_received_after_eligible_s.normal_median)} · {secs(c.sip_received_after_eligible_s.catch_up_median)} ({c.sip_received_after_eligible_s.catch_up_minutes} min)</td>
                  <td>{c.sip_revisions}</td></tr>); })}</tbody></table>
            <table className="q-table"><thead><tr><th>Symbol</th>{Object.keys(ev.sip_comparison[syms[0]].categories).map((k) => <th key={k}>{k}</th>)}</tr></thead>
              <tbody>{syms.map((s) => (<tr key={s}><td>{s}</td>{Object.values(ev.sip_comparison[s].categories).map((v: any, i) => <td key={i}>{v}</td>)}</tr>))}</tbody></table>
            {syms.some((s) => ev.sip_comparison[s].flagged.length) && (<>
              <p className="small">Flagged minutes (click for supporting records):</p>
              <ul className="notes">{syms.flatMap((s) => ev.sip_comparison[s].flagged.map((f: Dict) => (
                <li key={s + f.t_utc}><button type="button" className="cite" onClick={() => setMinute({ symbol: s, t: f.t_utc })}>{s} {et(f.t_utc)}</button> {f.category}: {f.detail}</li>)))}</ul></>)}
          </>)}

          {ev.operations && (<>
            <h5>4 · Operations</h5>
            <p className="small">Downtime {ev.operations.downtime_minutes} min (unplanned {ev.operations.unplanned_downtime_minutes}) · restarts during the session {ev.operations.restarts_during_session} ·
              API request failures {ev.operations.request_failures} · access refusals {ev.operations.access_refusals} · other errors (supervisor, crash) {ev.operations.other_errors ?? 0} · comparison runs {ev.operations.comparison_runs.ok}/{ev.operations.comparison_runs.total} ok
              ({ev.operations.comparison_runs.requests} requests; cycle {ev.operations.comparison_runs.by_kind.cycle}, recovery {ev.operations.comparison_runs.by_kind.recovery}, post-close {ev.operations.comparison_runs.by_kind.eod_recheck})</p>
            {[...ev.operations.downtime_intervals, ...(ev.operations.unrecorded_intervals ?? [])].length > 0 && <ul className="notes">{[...ev.operations.downtime_intervals, ...(ev.operations.unrecorded_intervals ?? [])].map((d: Dict, i: number) => <li key={i}>{et(d.from_utc)} – {et(d.to_utc)}: {d.minutes} min, {d.kind}</li>)}</ul>}
            <table className="q-table"><thead><tr><th>Worker pid</th><th>Started</th><th>Last alive</th><th>Stopped</th><th>Exit</th><th>Code version</th></tr></thead>
              <tbody>{ev.operations.worker_runs.map((r: Dict, i: number) => <tr key={i}><td>{r.pid}</td><td>{et(r.started_utc)}</td><td>{et(r.last_alive_utc)}</td><td>{et(r.stopped_utc)}</td><td>{r.exit_reason ?? "no clean stop recorded"}</td><td><code>{r.code_version}</code></td></tr>)}</tbody></table>
            {ev.operations.failure_events.length > 0 && <details><summary>Failure events ({ev.operations.failure_events.length})</summary>
              <ul className="notes">{ev.operations.failure_events.map((e: Dict, i: number) => <li key={i}>{et(e.ts_utc)} {e.kind}: {e.message}</li>)}</ul></details>}
          </>)}
          {ev.unresolved && (<>
            <h5>5 · Unresolved</h5>
            {ev.unresolved.length === 0 ? <p className="small tone-ok">Nothing unresolved.</p> :
              <ul className="notes">{ev.unresolved.map((u: Dict, i: number) => <li key={i}>{u.what}{u.from_utc ? `: ${et(u.from_utc)} – ${et(u.to_utc)}` : ""}{u.minutes ? ` (${u.minutes} min)` : ""}{u.error ? ` · ${u.error}` : ""}</li>)}</ul>}
          </>)}
          {ev.provenance && <details><summary>6 · Provenance and code/configuration version</summary><pre className="json">{JSON.stringify(ev.provenance, null, 2)}</pre></details>}
          {report.status?.reports?.length > 0 && <p className="small muted">Stored versions: {report.status.reports.map((r: Dict) => `v${r.version} ${r.status} ${et(r.created_utc)}${r.amends_version ? ` (amends v${r.amends_version})` : ""}`).join(" · ")}</p>}
        </div>
      )}
      {minute && (
        <div className="evidence-item" role="region" aria-label="Supporting records">
          <h4>Supporting records · {minute.symbol} {minute.t} <button type="button" className="small" onClick={() => setMinute(null)}>Close</button></h4>
          <pre className="json">{rec ? JSON.stringify(rec, null, 2).slice(0, 8000) : "loading…"}</pre>
        </div>
      )}
    </div>
  );
}
