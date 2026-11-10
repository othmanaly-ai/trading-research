import { Component, Suspense, lazy, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { useLiveJson } from "../useLiveJson";
import type { EdgeSpec, TowerSpec } from "./CityView";
import { etTime } from "./Overview";

// Research desk (trading/dashboard/desk.py via /api/desk). Read-only: this view runs, starts and changes
// nothing. Buildings, tables, task panels and edges all come from the same /api/desk response. A building's
// colour is its worst task state; an edge is solid only when a stored task transition exists for it, and
// its once-only effect is keyed to that record's id.

const CityView = lazy(() => import("./CityView"));

interface Task {
  id: string; department: string; title: string; purpose: string; kind: string; handler: string; inputs: string[];
  data_mode: string; freshness: string | null; state: string; latest_run_utc: string | null; outcome: string | null;
  output: string | null; blocker: string | null; upstream: string[]; downstream: string[]; evidence: string[];
  note: string | null; record: Record<string, unknown> | null; simulation_only: boolean | null; execution_path: string | null;
}
interface Dept { id: string; name: string; scope: string; counts: Record<string, number>; headline: string; tasks: Task[] }
interface TraceTask {
  task: string; department: string; id: string; attempt: number; status: string; queued_utc: string; started_utc: string | null;
  finished_utc: string | null; error: string | null; reused_from: string | null; output_fingerprint: string | null;
  inputs: { input_refs?: Record<string, { ref: string; rows?: number; fingerprint: string }>; implementation_version?: string;
    config_version?: { fingerprint: string }; code_version?: string | null; source?: string; input_fingerprint?: string;
    depends_on?: string[]; handler?: string };
  output: Record<string, unknown> | null;
}
interface Trace { run_id: string; session_date: string; status: string; created_utc: string; finished_utc: string | null; tasks: TraceTask[] }
interface Data {
  label: string; generated_utc: string; departments: Dept[];
  edges: { from: string; to: string; declared: string; recorded: boolean; event_id: string | null; event_status: string | null }[];
  command_centre: {
    next_eligible: { task: string; action: string; why: string; command: string | null } | null;
    candidates: { task: string; action: string; why: string; command: string | null }[];
    current_activity: { task: string; title: string; since: string | null }[];
    blocked: { task: string; title: string; why: string | null }[]; failed: { task: string; title: string; why: string | null }[];
    not_implemented: { task: string; title: string }[]; untraced_finalized_sessions: string[]; prohibited: string[]; boundary: string;
  };
  trace: Trace | null; trace_runs: { run_id: string; session_date: string; status: string; created_utc: string; finished_utc: string | null }[];
  model_assist: { id: string; title: string; input: string; output: string; evaluation: string; cost_boundary: string }[];
  input_errors: string[];
}

export const STATE_COLOR: Record<string, number> = {
  RUNNING: 0x22d3ee, SUCCEEDED: 0x14b8a6, REUSED: 0x5eead4, IDLE: 0x64748b, BLOCKED: 0xeab308, FAILED: 0xef4444,
  UNKNOWN: 0xa855f7, DISABLED: 0x475569, CLOSED: 0x334155, "NOT IMPLEMENTED": 0x1e293b, OK: 0x14b8a6,
};
const hex = (c: number) => `#${c.toString(16).padStart(6, "0")}`;
const SLOT: Record<string, [number, number]> = {
  command: [0, 0], data: [-30, -14], operations: [0, -32], archive: [30, -14], research: [17, 24], risk: [-17, 24],
};
const ARCH: Record<string, TowerSpec["archetype"]> = {
  command: "command", data: "operations", operations: "finned", archive: "terraced", research: "twisted", risk: "terraced",
};
const TRACE_ORDER: Record<string, string> = {
  capture_inventory: "1 Capture inventory", structural_validation: "2 Structural validation", iex_sip_comparison: "3 IEX / SIP comparison",
  revision_tracking: "4 Revision tracking", reliability_assessment: "5 Reliability assessment", report_finalization: "6 Stored report check",
};

class Boundary extends Component<{ onError: (m: string) => void; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(e: Error) { this.props.onError(`3D view unavailable (${e.message}). The tables below hold the same records.`); }
  render() { return this.state.failed ? null : this.props.children; }
}

function State({ s }: { s: string }) {
  return <strong className="desk-state" style={{ color: hex(STATE_COLOR[s] ?? 0x64748b) }}>{s}</strong>;
}

export default function DeskView({ reducedMotion }: { reducedMotion: boolean }) {
  const [tick, setTick] = useState(0);
  useEffect(() => { const id = setInterval(() => setTick((t) => t + 1), 15000); return () => clearInterval(id); }, []);
  const [run, setRun] = useState<string | null>(null);
  const { data, error } = useLiveJson<Data>(run ? `/api/desk?run=${encodeURIComponent(run)}` : "/api/desk", tick);
  const [sel, setSel] = useState<string | null>(null);
  const [taskSel, setTaskSel] = useState<string | null>(null);
  const [cityError, setCityError] = useState<string | null>(() =>
    new URLSearchParams(window.location.search).get("3d") === "off" ? "3D view turned off (?3d=off)." : null);
  const onCityFailure = useCallback((m: string) => setCityError(m), []);

  const dept = data?.departments.find((d) => d.id === sel) ?? null;
  const allTasks = useMemo(() => (data?.departments ?? []).flatMap((d) => d.tasks), [data]);
  const task = allTasks.find((t) => t.id === taskSel) ?? null;

  const towers = useMemo<TowerSpec[]>(() => (data?.departments ?? []).map((d) => {
    const into = data!.edges.filter((e) => e.to === d.id && e.recorded && e.event_id);
    const ev = into[0];
    const head = d.headline;
    const summary = Object.entries(d.counts).map(([k, v]) => `${v} ${k.toLowerCase()}`).join(" · ");
    return {
      id: d.id, color: STATE_COLOR[head] ?? 0x64748b, slot: SLOT[d.id], archetype: ARCH[d.id],
      category: d.id === "command" ? "COORDINATOR · deterministic" : "DEPARTMENT", title: d.name,
      status: `${d.headline} · ${d.tasks.length} tasks`, dim: d.headline === "IDLE",
      warn: d.headline === "FAILED", active: d.headline === "RUNNING",
      labelMode: !sel ? "compact" : "full", related: !!sel && sel !== d.id && data!.edges.some((e) => (e.from === sel && e.to === d.id) || (e.to === sel && e.from === d.id)),
      // one effect per stored task transition into this department (never replayed on polling)
      event: ev ? { id: ev.event_id!, kind: ev.event_status === "FAILED" ? "fail" as const : "complete" as const } : undefined,
      lines: [{ cls: "tl-name", text: d.name }, { cls: "tl-status", text: d.headline }, { cls: "tl-inst", text: summary }],
      ariaLabel: `${d.name}: ${d.headline}, ${summary}. Show specialist tasks.`, pulseKey: "",
    };
  }), [data, sel]);

  const edgeSpecs = useMemo<EdgeSpec[]>(() => (data?.edges ?? [])
    .filter((e) => e.to !== "command" || e.from === sel || sel === "command")
    .map((e) => ({ from: e.from, to: e.to, style: e.recorded ? "recorded" : "declared",
      color: e.recorded ? (e.event_status === "FAILED" ? 0xef4444 : 0x22d3ee) : undefined })), [data, sel]);

  if (error) return <p className={`panel ${error.includes("404") ? "warn" : "error"}`}>{error.includes("404")
    ? "This city server was started before the research-desk endpoint existed. The view appears after the server's next restart (planned outside market hours). Records are available now: python -m trading.monitor.evidence_trace list."
    : `Could not load the research desk: ${error}`}</p>;
  if (!data) return <p className="empty panel">Loading research desk…</p>;
  const cc = data.command_centre;
  const tr = data.trace;

  return (
    <section className="panel wide depmap desk" aria-label="Research desk">
      <h2>Research desk <span className="small muted">six departments · real records · read-only · built {etTime(data.generated_utc)}</span></h2>
      <p className="small">{data.label}. Each department is a set of tasks; a state comes from a stored record, and with no record it is
        <strong> UNKNOWN</strong>. A building is not a worker: only the market-data worker and the dry-run runner are continuous processes.</p>
      {data.input_errors.length > 0 && <p className="warn small">Sources that could not be read (shown as UNKNOWN): {data.input_errors.join(" · ")}</p>}

      <div className="desk-cc" aria-label="Command Centre">
        <h3>Command Centre <span className="small muted">deterministic · runs nothing</span></h3>
        {cc.next_eligible ? (
          <p><strong>Next eligible task:</strong> {cc.next_eligible.action} — {cc.next_eligible.why}
            {cc.next_eligible.command && <> · <code>{cc.next_eligible.command}</code></>}</p>
        ) : <p><strong>Next eligible task:</strong> none. Every finalized session has a completed evidence trace and no record shows a failure.</p>}
        {cc.candidates.length > 1 && <details><summary className="small">{cc.candidates.length - 1} more eligible</summary>
          <ul className="notes">{cc.candidates.slice(1).map((c, i) => <li key={i} className="small">{c.action}: {c.why} {c.command && <code>{c.command}</code>}</li>)}</ul></details>}
        <p className="small"><strong>Current activity:</strong> {cc.current_activity.map((a) => a.title).join(" · ") || "none recorded"}</p>
        <p className="small"><strong>Blocked ({cc.blocked.length}):</strong> {cc.blocked.map((b) => b.title).join(" · ") || "none"}</p>
        <p className="small"><strong>Never done by the desk:</strong> {cc.prohibited.join(" · ")}.</p>
      </div>

      <div className="district">
        {cityError ? <p className="warn">{cityError}</p> : (
          <Boundary onError={onCityFailure}>
            <Suspense fallback={<p className="empty">Loading 3D view…</p>}>
              <CityView variant="depmap" towers={towers} edges={edgeSpecs} coreColor={null} selectedId={sel}
                        onSelect={(id) => { setSel(id); setTaskSel(null); }} reducedMotion={reducedMotion} onFailure={onCityFailure}
                        mode={{ label: "RESEARCH DESK · REAL RECORDS", tone: "real", detail: "read-only · solid line = stored task transition · dashed = declared code path" }}
                        legend={["RUNNING", "SUCCEEDED", "BLOCKED", "FAILED", "UNKNOWN"].map((k) => ({ color: STATE_COLOR[k], label: k.toLowerCase() }))} />
            </Suspense>
          </Boundary>
        )}
        <aside className="district-detail dep-detail" aria-label="Department tasks">
          {!dept ? (<><h3>Select a department</h3><p className="small">Click a building, a label or a row in the Departments table.</p></>) : (<>
            <h3>{dept.name} <button type="button" className="small" onClick={() => { setSel(null); setTaskSel(null); }}>Close</button></h3>
            <p className="small">{dept.scope}</p>
            <ul className="desk-tasks">{dept.tasks.map((t) => (
              <li key={t.id}><button type="button" className="cite" aria-pressed={taskSel === t.id} onClick={() => setTaskSel(t.id)}>{t.title}</button>
                {" "}<State s={t.state} />{t.blocker && <div className="small warn">{t.blocker}</div>}</li>))}</ul>
            {task && task.department === dept.id && <TaskDetail t={task} />}
          </>)}
        </aside>
      </div>

      <h3>Departments</h3>
      <div className="scroll"><table className="q-table" aria-label="Departments">
        <thead><tr><th>Department</th><th>Headline</th><th>Task states</th></tr></thead>
        <tbody>{data.departments.map((d) => (
          <tr key={d.id} className={sel === d.id ? "sel" : ""}>
            <td><button type="button" className="cite" aria-pressed={sel === d.id} onClick={() => { setSel(d.id); setTaskSel(null); }}>{d.name}</button></td>
            <td><State s={d.headline} /></td>
            <td className="small">{Object.entries(d.counts).map(([k, v]) => `${k} ${v}`).join(" · ")}</td>
          </tr>))}</tbody>
      </table></div>

      <h3>Evidence trace {tr ? <span className="small muted">session {tr.session_date} · run <code>{tr.run_id}</code></span> : null}</h3>
      <p className="small">One monitored session from stored evidence through the existing checks to the stored report. Run by hand:
        {" "}<code>python -m trading.monitor.evidence_trace run --date YYYY-MM-DD</code>. The monitoring store is read from a snapshot and never modified.</p>
      {data.trace_runs.length > 0 && <label className="small">Trace run{" "}
        <select value={tr?.run_id ?? ""} onChange={(e) => setRun(e.target.value)} aria-label="Trace run">
          {data.trace_runs.map((r) => <option key={r.run_id} value={r.run_id}>{r.session_date} · {r.status} · {etTime(r.created_utc)}</option>)}
        </select></label>}
      {!tr ? <p className="empty">No trace run recorded yet.</p> : (
        <div className="scroll"><table className="q-table" aria-label="Evidence trace tasks">
          <thead><tr><th>Step</th><th>Department</th><th>Status</th><th>Attempt</th><th>Finished</th><th>Inputs (fingerprint)</th><th>Output / reason</th></tr></thead>
          <tbody>{tr.tasks.map((t) => (
            <tr key={t.id}>
              <td>{TRACE_ORDER[t.task] ?? t.task}<div className="small muted">{t.inputs.handler}</div></td>
              <td>{t.department}</td><td><State s={t.status} />{t.reused_from && <div className="small">from <code>{t.reused_from}</code></div>}</td>
              <td>{t.attempt}</td><td className="small">{etTime(t.finished_utc)}</td>
              <td className="small">{Object.entries(t.inputs.input_refs ?? {}).map(([k, v]) => <div key={k}>{v.ref}{v.rows !== undefined ? ` (${v.rows} rows)` : ""} · <code>{v.fingerprint.slice(0, 10)}</code></div>)}
                <div className="muted">config <code>{t.inputs.config_version?.fingerprint}</code> · code {t.inputs.code_version ?? "?"} · {t.inputs.source}</div></td>
              <td className="small">{t.error ? <span className="warn">{t.error}</span> : <TraceOutput task={t.task} out={t.output} />}
                {t.output_fingerprint && <div className="muted">output <code>{t.output_fingerprint.slice(0, 12)}</code></div>}</td>
            </tr>))}</tbody>
        </table></div>
      )}

      <h3>All tasks</h3>
      <div className="scroll"><table className="q-table" aria-label="All desk tasks">
        <thead><tr><th>Task</th><th>Department</th><th>Kind</th><th>State</th><th>Latest</th><th>Outcome / blocker</th></tr></thead>
        <tbody>{allTasks.map((t) => (
          <tr key={t.id} className={taskSel === t.id ? "sel" : ""}>
            <td><button type="button" className="cite" onClick={() => { setSel(t.department); setTaskSel(t.id); }}>{t.title}</button></td>
            <td>{data.departments.find((d) => d.id === t.department)?.name}</td><td className="small">{t.kind}</td>
            <td><State s={t.state} /></td><td className="small">{etTime(t.latest_run_utc)}</td>
            <td className="small">{t.blocker ? <span className="warn">{t.blocker}</span> : t.outcome ?? "—"}</td>
          </tr>))}</tbody>
      </table></div>

      <h3>Model assistance (DISABLED)</h3>
      <p className="small">Paid model calls are revoked; nothing below runs. Several model answers are not independent market evidence, and a
        disagreement would be shown, not averaged into a consensus.</p>
      <ul className="notes">{data.model_assist.map((m) => <li key={m.id} className="small"><strong>{m.title}</strong>: input {m.input}; output {m.output};
        evaluation {m.evaluation}; cost boundary {m.cost_boundary}.</li>)}</ul>
    </section>
  );
}

function TraceOutput({ task, out }: { task: string; out: Record<string, unknown> | null }) {
  if (!out) return <>—</>;
  const o = out as Record<string, any>;
  if (task === "capture_inventory") return <>{Object.entries(o.per_symbol ?? {}).map(([s, v]: [string, any]) => `${s} ${v.received}/${o.scheduled_minutes} (${v.on_time} on time, ${v.late} late)`).join(" · ")}</>;
  if (task === "structural_validation") return <>{o.bars_checked} bars · defects {Object.entries(o.defects_per_symbol ?? {}).map(([k, v]) => `${k} ${v}`).join(", ")}</>;
  if (task === "iex_sip_comparison") return <>{o.runs_ok}/{o.runs} runs ok · {Object.entries(o.categories ?? {}).map(([k, v]) => `${k} ${v}`).join(", ")}</>;
  if (task === "revision_tracking") return <>{o.observations} observations · later revisions {Object.entries(o.revisions_by_feed ?? {}).map(([k, v]) => `${k} ${v}`).join(", ") || "none"}</>;
  if (task === "reliability_assessment") return <>{o.report_state} · unplanned downtime {o.unplanned_downtime_minutes} min · unresolved {o.unresolved_items} ·
    completion criterion {o.report_completion_criterion?.meets ? "met" : "not met"} · gate <strong>{o.reliability_gate?.status}</strong></>;
  if (task === "report_finalization") return <>v{o.latest_version} {o.latest_status} · {o.integrity} · evidence cutoff {o.evidence_cutoff_utc}
    {" "}({o.evidence_cutoff_source}) · calculation v{String(o.stored_calc_version)} → v{o.current_calc_version} · {o.reproduction}
    {o.difference_counts && Object.keys(o.difference_counts).length > 0 && (
      <ul className="notes">{Object.entries(o.difference_counts).map(([k, v]) => (
        <li key={k}><strong className={k === "defect" || k === "unexplained" ? "warn" : ""}>{k}</strong> {String(v)}: {o.explanations?.[k]}
          {k !== "amendment" && k !== "later_evidence" && <> ({(o.differences ?? []).filter((d: any) => d.category === k).map((d: any) => `${d.field}: ${d.stored} → ${d.recomputed}`).join("; ")})</>}
          {k === "later_evidence" && <> ({(o.later_evidence_fields ?? []).join(", ")})</>}</li>))}</ul>)}
    {(o.pending_correction ?? []).length > 0 && <div className="warn">Amend-only correction available, NOT applied: {o.pending_correction.map((c: any) => `${c.field} ${c.old} → ${c.new} (${c.why})`).join("; ")}</div>}
    {" "}<a href={o.report_link} target="_blank" rel="noreferrer">stored report</a></>;
  return <code>{JSON.stringify(out).slice(0, 200)}</code>;
}

function TaskDetail({ t }: { t: Task }) {
  return (
    <div className="desk-task-detail" aria-label={`Task ${t.title}`}>
      <h4 className="floor-h">{t.title} · <State s={t.state} /></h4>
      <p className="small">{t.purpose}</p>
      <dl className="small desk-dl">
        <dt>Kind</dt><dd>{t.kind}</dd>
        <dt>Handler</dt><dd><code>{t.handler}</code></dd>
        <dt>Inputs</dt><dd>{t.inputs.join("; ") || "—"}</dd>
        <dt>Data mode</dt><dd>{t.data_mode}{t.freshness ? ` · ${t.freshness}` : ""}</dd>
        <dt>Latest run</dt><dd>{t.latest_run_utc ? etTime(t.latest_run_utc) : "no run recorded"}</dd>
        <dt>Outcome</dt><dd>{t.outcome ?? "—"}</dd>
        {t.blocker && <><dt>Blocker / failure</dt><dd className="warn">{t.blocker}</dd></>}
        {t.simulation_only !== null && <><dt>Execution path</dt><dd>{t.simulation_only ? "simulation only · " : ""}{t.execution_path}</dd></>}
        <dt>Upstream</dt><dd>{t.upstream.join(", ") || "—"}</dd>
        <dt>Downstream</dt><dd>{t.downstream.join(", ") || "—"}</dd>
        {t.output && <><dt>Output</dt><dd><a href={t.output} target="_blank" rel="noreferrer"><code>{t.output}</code></a></dd></>}
        {t.record && <><dt>Record</dt><dd><code>{JSON.stringify(t.record)}</code></dd></>}
        {t.note && <><dt>Note</dt><dd>{t.note}</dd></>}
      </dl>
      {t.evidence.length > 0 && <ul className="notes">{t.evidence.map((e, i) => <li key={i} className="small">{e}</li>)}</ul>}
    </div>
  );
}
