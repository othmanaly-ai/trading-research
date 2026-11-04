import { useEffect, useState } from "react";
import { useLiveJson } from "../useLiveJson";

// Daily data-quality report: delayed SIP (consolidated) vs IEX (one exchange). Displays backend
// records only. Differences are not errors by themselves; nothing here certifies a feed for trading.

interface SymbolQ {
  symbol: string; minutes_compared: number; minutes_expected_so_far: number; sip_present: number; iex_present: number;
  live_iex_present: number; both_present: number; iex_missing: number; sip_missing: number;
  categories: Record<string, number>; corrections: { sip: number; iex: number }; live_iex_gaps_filled_later: number;
  iex_volume_share_total: number | null; iex_volume_share_median: number | null; zero_volume_sip_minutes: number;
  close_diff_bps_median_abs: number | null; close_diff_bps_max_abs: number | null; close_diff_usd_max_abs: number | null;
  high_diff_bps_median: number | null; low_diff_bps_median: number | null;
  sip_retrieval_delay_s_median: number | null; sip_retrieval_delay_s_min: number | null;
}
interface Run {
  id: number; kind: string; started_utc: string; window_start_utc: string; window_end_utc: string; status: string;
  http_status: number | null; requests: number; sip_bars: number; iex_bars: number; new_obs: number; duplicate_obs: number;
  corrections: number; defects: number; compared: number; error: string | null;
}
interface Flag { symbol: string; t_utc: string; category: string; detail: string; sip_rev: number; iex_rev: number;
  sip_provider_available_utc: string | null; sip_retrieved_utc: string | null }
interface Report {
  label: string; session_date: string | null; delay_rule: string; boundary_utc: string; compared_through_utc: string | null;
  eod_recheck_utc: string | null; note?: string;
  health: { state: string; detail: string; failures: number; backoff_until_utc: string | null; last_success_utc: string | null };
  session?: { open_utc: string; close_utc: string; early_close: boolean; minutes: number };
  pending?: { from_utc: string; to_utc: string; comparable_now_until_utc: string };
  symbols: SymbolQ[]; runs: Run[]; flagged: Flag[];
  corrections_recent: { symbol: string; feed: string; t_utc: string; revision: number; retrieved_utc: string }[];
}

const CAT_LABEL: Record<string, string> = {
  consistent_subset: "consistent (IEX inside SIP)", expected_coverage_difference: "expected coverage difference",
  both_absent: "no bar in either feed", unresolved_anomaly: "unresolved anomaly", structural_defect: "structural defect",
};

function et(ts: string | null | undefined): string {
  if (!ts) return "—";
  return new Date(ts).toLocaleTimeString("en-US", { timeZone: "America/New_York", hour: "2-digit", minute: "2-digit", hour12: false }) + " ET";
}
const n2 = (x: number | null, d = 2) => (x === null || x === undefined ? "—" : x.toFixed(d));
const pct = (x: number | null) => (x === null || x === undefined ? "—" : `${(x * 100).toFixed(1)}%`);

export default function QualityPanel({ tick }: { tick: number }) {
  const { data, error } = useLiveJson<Report>("/api/quality", Math.floor(tick / 5));
  const [minute, setMinute] = useState<{ symbol: string; t: string } | null>(null);
  const [rec, setRec] = useState<unknown>(null);
  useEffect(() => {
    if (!minute) { setRec(null); return; }
    fetch(`/api/quality/minute?symbol=${minute.symbol}&t=${encodeURIComponent(minute.t)}`)
      .then((r) => r.json()).then(setRec).catch((e: Error) => setRec({ error: e.message }));
  }, [minute]);

  if (error) return <p className="error">Could not load the quality report: {error}</p>;
  if (!data) return <p className="empty">Loading the quality report…</p>;
  const h = data.health;
  return (
    <div className="quality" aria-label="Data quality report">
      <div className="q-banner"><strong>{data.label}</strong>. SIP observations are <strong>delayed</strong>: each shows when the
        free plan first made it available (bar end + 15 min) and when it was retrieved. Differences between the feeds are
        expected (IEX is one exchange); no tolerance is applied and neither feed is certified for trading.</div>
      <div className="row">
        <span>Session {data.session_date ?? "—"}{data.session?.early_close ? " (early close)" : ""} · comparison state{" "}
          <strong className={h.state === "ok" ? "tone-ok" : h.state === "waiting" || h.state === "idle" ? "" : "tone-danger"}>{h.state.toUpperCase()}</strong></span>
        <span className="small">{h.detail}{h.backoff_until_utc ? ` · retry after ${et(h.backoff_until_utc)}` : ""}</span>
      </div>
      <p className="small">Latest completed comparison: minutes before <strong>{et(data.compared_through_utc)}</strong>.
        {data.pending ? <> Pending: {et(data.pending.from_utc)} – {et(data.pending.to_utc)} (comparable now up to {et(data.pending.comparable_now_until_utc)};
          rule: {data.delay_rule}).</> : null}
        {data.eod_recheck_utc ? ` End-of-day re-observation done at ${et(data.eod_recheck_utc)}.` : " End-of-day re-observation not yet done."}</p>
      {data.note && <p className="empty">{data.note}</p>}

      <table className="q-table" aria-label="Daily quality report by symbol">
        <thead><tr><th>Symbol</th><th>Compared / comparable</th><th>SIP bars</th><th>IEX bars</th><th>Live IEX captured</th>
          <th>IEX missing</th><th>SIP missing</th><th>IEX volume share (total · median)</th><th>Close diff |bps| (median · max) · max $</th>
          <th>SIP retrieval delay (median · min)</th><th>Corrections SIP · IEX</th></tr></thead>
        <tbody>{data.symbols.map((s) => (
          <tr key={s.symbol}><td>{s.symbol}</td><td>{s.minutes_compared} / {s.minutes_expected_so_far}</td><td>{s.sip_present}</td>
            <td>{s.iex_present}</td><td>{s.live_iex_present}</td><td>{s.iex_missing}</td><td>{s.sip_missing}</td>
            <td>{pct(s.iex_volume_share_total)} · {pct(s.iex_volume_share_median)}</td>
            <td>{n2(s.close_diff_bps_median_abs)} · {n2(s.close_diff_bps_max_abs)} · ${n2(s.close_diff_usd_max_abs)}</td>
            <td>{s.sip_retrieval_delay_s_median === null ? "—" : `${Math.round(s.sip_retrieval_delay_s_median / 60)} min`} · {s.sip_retrieval_delay_s_min === null ? "—" : `${Math.round(s.sip_retrieval_delay_s_min / 60)} min`}</td>
            <td>{s.corrections.sip} · {s.corrections.iex}</td></tr>))}</tbody>
      </table>
      <table className="q-table" aria-label="Minutes by category">
        <thead><tr><th>Symbol</th>{Object.keys(CAT_LABEL).map((k) => <th key={k}>{CAT_LABEL[k]}</th>)}<th>SIP zero-volume minutes</th></tr></thead>
        <tbody>{data.symbols.map((s) => (
          <tr key={s.symbol}><td>{s.symbol}</td>{Object.keys(CAT_LABEL).map((k) => (
            <td key={k} className={k === "structural_defect" && s.categories[k] ? "tone-danger" : k === "unresolved_anomaly" && s.categories[k] ? "tone-warn" : ""}>{s.categories[k] ?? 0}</td>))}
            <td>{s.zero_volume_sip_minutes}</td></tr>))}</tbody>
      </table>

      <h4>Flagged minutes (unresolved anomalies and structural defects) · click for supporting records</h4>
      {data.flagged.length === 0 ? <p className="empty">None so far.</p> : (
        <table aria-label="Flagged minutes"><thead><tr><th>Symbol</th><th>Minute</th><th>Category</th><th>Detail</th><th>SIP available · retrieved</th><th></th></tr></thead>
          <tbody>{data.flagged.map((f) => (
            <tr key={f.symbol + f.t_utc}><td>{f.symbol}</td><td>{et(f.t_utc)}</td><td>{CAT_LABEL[f.category]}</td><td>{f.detail}</td>
              <td>{et(f.sip_provider_available_utc)} · {et(f.sip_retrieved_utc)}</td>
              <td><button type="button" onClick={() => setMinute({ symbol: f.symbol, t: f.t_utc })}>Records</button></td></tr>))}</tbody></table>
      )}
      {data.corrections_recent.length > 0 && (
        <><h4>Corrections observed (earlier revisions kept)</h4>
          <ul className="notes">{data.corrections_recent.map((c) => (
            <li key={c.feed + c.symbol + c.t_utc + c.revision}><button type="button" className="cite" onClick={() => setMinute({ symbol: c.symbol, t: c.t_utc })}>
              {c.feed.toUpperCase()} {c.symbol} {et(c.t_utc)} revision {c.revision}</button> retrieved {et(c.retrieved_utc)}</li>))}</ul></>)}
      {minute && (
        <div className="evidence-item" role="region" aria-label="Supporting records">
          <h4>Supporting records · {minute.symbol} {minute.t} <button type="button" className="small" onClick={() => setMinute(null)}>Close</button></h4>
          <pre className="json">{rec ? JSON.stringify(rec, null, 2).slice(0, 8000) : "loading…"}</pre>
        </div>
      )}

      <h4>Comparison runs (access and error states)</h4>
      {data.runs.length === 0 ? <p className="empty">No comparison run yet for this session.</p> : (
        <table aria-label="Comparison runs"><thead><tr><th>Run</th><th>Kind</th><th>Window</th><th>Status</th><th>HTTP</th><th>Requests</th>
          <th>Bars SIP · IEX</th><th>New · duplicate obs</th><th>Corrections</th><th>Defects</th><th>Error</th></tr></thead>
          <tbody>{data.runs.map((r) => (
            <tr key={r.id}><td>{r.id}</td><td>{r.kind}</td><td>{et(r.window_start_utc)} – {et(r.window_end_utc)}</td>
              <td className={r.status === "ok" ? "tone-ok" : "tone-danger"}>{r.status}</td><td>{r.http_status ?? "—"}</td><td>{r.requests}</td>
              <td>{r.sip_bars} · {r.iex_bars}</td><td>{r.new_obs} · {r.duplicate_obs}</td><td>{r.corrections}</td><td>{r.defects}</td>
              <td>{r.error ?? ""}</td></tr>))}</tbody></table>
      )}
    </div>
  );
}
