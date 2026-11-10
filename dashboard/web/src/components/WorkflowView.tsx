import { Component, Suspense, lazy, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { useLiveJson } from "../useLiveJson";
import type { TowerSpec } from "./CityView";
import { etTime } from "./Overview";

// Coordinator research workflow (trading/coordinator.py via /api/workflows). Read-only: this view
// starts, submits and changes nothing. Every building is a recorded task; its colour, label and the
// once-only effect on a status change come from the task record. Specialist ROLES are filled by
// submitted documents (author and mode shown); no autonomous agent is running.

const CityView = lazy(() => import("./CityView"));

interface Task {
  task: string; kind: string; role: string; depends_on: string[]; completion_criteria: string; id: string; attempt: number;
  status: string; created_utc: string; started_utc: string | null; finished_utc: string | null; error: string | null;
  evidence_refs: string[]; author: string | null; mode: string | null; submission: string | null; report_path: string | null;
}
interface Workflow {
  workflow_id: string; question: string; status: string; created_utc: string; finished_utc: string | null; tasks: Task[];
  evidence_items?: { id: string; path: string; role: string; sha256?: string; present: boolean }[]; report_markdown?: string;
}
interface Data { unattended_model: { status: string; reason: string }; question: string; workflows: Workflow[] }

const COLOR: Record<string, number> = {
  completed: 0x14b8a6, running: 0x22d3ee, queued: 0x64748b, blocked: 0xeab308, failed: 0xef4444, cancelled: 0x64748b, skipped: 0x64748b,
};
const ARCH: Record<string, TowerSpec["archetype"]> = {
  evidence: "operations", strategy_analysis: "terraced", data_cost_analysis: "finned", skeptical_review: "twisted", coordinator_report: "command",
};
const SLOT: Record<string, [number, number]> = {
  coordinator_report: [0, 0], evidence: [-30, 10], strategy_analysis: [-18, -26], data_cost_analysis: [18, -26], skeptical_review: [32, 4],
};

class Boundary extends Component<{ onError: (m: string) => void; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(e: Error) { this.props.onError(`3D view unavailable (${e.message}). The task table holds the same information.`); }
  render() { return this.state.failed ? null : this.props.children; }
}

export default function WorkflowView({ reducedMotion }: { reducedMotion: boolean }) {
  const [tick, setTick] = useState(0);
  useEffect(() => { const id = setInterval(() => setTick((t) => t + 1), 10000); return () => clearInterval(id); }, []);
  const { data, error } = useLiveJson<Data>("/api/workflows", tick);
  const [sel, setSel] = useState<string | null>(null);
  const [cityError, setCityError] = useState<string | null>(() =>
    new URLSearchParams(window.location.search).get("3d") === "off" ? "3D view turned off (?3d=off)." : null);
  const onCityFailure = useCallback((m: string) => setCityError(m), []);
  const wf = data?.workflows[0] ?? null;
  const task = wf?.tasks.find((t) => t.task === sel) ?? null;
  const paths = useMemo(() => Object.fromEntries((wf?.evidence_items ?? []).map((e) => [e.id, e.path])), [wf]);

  const towers = useMemo<TowerSpec[]>(() => (wf?.tasks ?? []).map((t) => ({
    id: t.task, color: COLOR[t.status] ?? 0x64748b, slot: SLOT[t.task], archetype: ARCH[t.task] ?? "terraced",
    category: t.kind === "specialist" ? "SPECIALIST ROLE · submitted document" : "COORDINATOR CODE · deterministic",
    title: t.role, status: t.status.toUpperCase() + (t.attempt > 1 ? ` · attempt ${t.attempt}` : ""),
    dim: t.status === "blocked" || t.status === "queued", warn: t.status === "failed",
    links: t.depends_on,                                    // real task dependencies only
    // one effect per recorded status change (id = task record + status); never replayed on load
    event: t.status === "completed" ? { id: `${t.id}:completed`, kind: "complete" as const }
      : t.status === "failed" ? { id: `${t.id}:failed`, kind: "fail" as const } : undefined,
    lines: [{ cls: "tl-name", text: t.role }, { cls: "tl-status", text: t.status }],
    ariaLabel: `${t.role}: ${t.status}. Show task details.`, pulseKey: "",
  })), [wf]);

  if (error) return <p className={`panel ${error.includes("404") ? "warn" : "error"}`}>{error.includes("404")
    ? "This city server was started before the research-workflow endpoint existed. The view appears after the server's next restart (planned outside market hours). The workflow itself is recorded; see python -m trading.coordinator status."
    : `Could not load research workflows: ${error}`}</p>;
  if (!data) return <p className="empty panel">Loading research workflows…</p>;

  return (
    <section className="panel wide depmap" aria-label="Coordinator research workflow">
      <h2>Research workflow <span className="small muted">coordinator + specialist roles · read-only view</span></h2>
      <p className="small"><strong>Question:</strong> {data.question}</p>
      <p className="warn small"><strong>Unattended model connection: {data.unattended_model.status}.</strong> {data.unattended_model.reason}
        {" "}A specialist role is a task that needs a document; it is not an agent running on its own.</p>
      {!wf ? <p className="empty">No workflow yet. Start one from the command line: <code>python -m trading.coordinator start</code>.</p> : (<>
        <p className="small">Workflow <code>{wf.workflow_id}</code> · status <strong>{wf.status.toUpperCase()}</strong> · created {etTime(wf.created_utc)}
          {wf.finished_utc ? ` · finished ${etTime(wf.finished_utc)}` : ""}</p>
        <div className="district">
          {cityError ? <p className="warn">{cityError}</p> : (
            <Boundary onError={onCityFailure}>
              <Suspense fallback={<p className="empty">Loading 3D view…</p>}>
                <CityView variant="jobs" towers={towers} coreColor={null} selectedId={sel} onSelect={setSel}
                          reducedMotion={reducedMotion} onFailure={onCityFailure}
                          mode={{ label: "REAL RESEARCH WORKFLOW", tone: "real", detail: `read-only · ${wf.status} · unattended model ${data.unattended_model.status}` }}
                          legend={Object.entries(COLOR).filter(([k]) => ["completed", "running", "blocked", "failed", "queued"].includes(k))
                            .map(([k, c]) => ({ color: c, label: k === "blocked" ? "blocked (waiting for input or a document)" : k }))} />
              </Suspense>
            </Boundary>
          )}
          <aside className="district-detail dep-detail" aria-label="Task details">
            {!task ? (<><h3>Select a task</h3><p className="small">Click a building, a label or a row in the task table.</p></>) : (<>
              <h3>{task.role} <button type="button" className="small" onClick={() => setSel(null)}>Close</button></h3>
              <p><strong style={{ color: `#${(COLOR[task.status] ?? 0x64748b).toString(16).padStart(6, "0")}` }}>{task.status.toUpperCase()}</strong>
                {" "}· {task.kind === "specialist" ? "specialist role (submitted document)" : "deterministic coordinator code"} · attempt {task.attempt}</p>
              {task.author && <p className="small">Author: {task.author}<br />Mode: {task.mode}</p>}
              <p className="small">Created {etTime(task.created_utc)} · started {etTime(task.started_utc)} · finished {etTime(task.finished_utc)}</p>
              <h4 className="floor-h">Completion criteria</h4><p className="small">{task.completion_criteria}</p>
              <h4 className="floor-h">Depends on</h4><p className="small">{task.depends_on.join(", ") || "—"}</p>
              {task.error && (<><h4 className="floor-h">{task.status === "failed" ? "Errors" : "Waiting for"}</h4><p className="small warn">{task.error}</p></>)}
              <h4 className="floor-h">Evidence references</h4>
              <ul className="notes">{task.evidence_refs.map((e) => <li key={e} className="small">{e} · <code>{paths[e] ?? "?"}</code></li>)}</ul>
              {task.submission && <p className="small">Submitted document: <code>{task.submission}</code></p>}
              {task.report_path && <p className="small">Report: <code>{task.report_path}</code></p>}
            </>)}
          </aside>
        </div>
        <h3>Tasks</h3>
        <div className="scroll"><table className="q-table" aria-label="Workflow tasks">
          <thead><tr><th>Task</th><th>Kind</th><th>Status</th><th>Attempt</th><th>Finished</th><th>Evidence</th><th>Error / waiting for</th></tr></thead>
          <tbody>{wf.tasks.map((t) => (
            <tr key={t.task} className={sel === t.task ? "sel" : ""}>
              <td><button type="button" className="cite" aria-pressed={sel === t.task} onClick={() => setSel(t.task)}>{t.role}</button></td>
              <td>{t.kind}</td><td>{t.status}</td><td>{t.attempt}</td><td>{etTime(t.finished_utc)}</td>
              <td>{t.evidence_refs.length}</td><td className="small">{t.error ?? "—"}</td>
            </tr>))}</tbody>
        </table></div>
        {wf.report_markdown && (<>
          <h3>Coordinator report</h3>
          <pre className="json report-md" aria-label="Coordinator report">{wf.report_markdown}</pre>
        </>)}
      </>)}
    </section>
  );
}
