import { Component, Suspense, lazy, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { useLiveJson } from "../useLiveJson";
import type { TowerSpec } from "./CityView";
import ReviewPanel, { ReviewerReadiness } from "./ReviewPanel";

// Operational control panel for REAL research jobs (trading/jobs.py) over saved experiment
// artifacts. Never demo data. The browser only asks; the backend validates every request,
// deduplicates work, runs it in a background thread and owns all state.

const CityView = lazy(() => import("./CityView"));

interface Job {
  id: string; pipeline_id: string; worker: string; kind: string; experiment: string; status: string;
  attempt: number; created_utc: string; started_utc: string | null; finished_utc: string | null;
  inputs: Record<string, unknown> | null; outputs: Record<string, unknown> | null;
  evidence: Record<string, unknown> | null; error: string | null;
}
interface Pipeline {
  id: string; experiment: string; pipeline: string | null; created_utc: string; started_utc: string | null;
  finished_utc: string | null; status: string; job_ids: string[]; cancel_requested: boolean;
  cancel_requested_utc: string | null; error: string | null;
}
interface JobsData {
  mode_label: string; pipelines: Pipeline[]; jobs: Job[];
  workers: { worker: string; kind: string; version: string; depends_on: string[] }[];
  roles: { role: string; kind: string; status: string }[];
  model_policy: { credential: string; authorization: string; billing: string; proposed_limits: Record<string, number> };
}
interface Artifact { name: string; present: boolean; bytes?: number; sha256?: string }
interface Experiment {
  experiment: string; artifacts: Artifact[]; problems: string[];
  status: { experiment_id: string; state: string; closed: boolean; failed_rules: string[] | null } | null;
  active_pipeline: string | null; latest_pipeline: { id: string; status: string } | null;
}
interface Candidate {
  candidate: string; artifacts: Artifact[]; problems: string[];
  status: { title: string; state: string; status: string; is_experiment: boolean; performance_evaluated: boolean;
            downloads: string; blockers: string[]; open_uncertainties: string[]; resume_requires: string; decided_utc: string } | null;
}
interface Experiments { mode_label: string; pipelines: Record<string, string>; experiments: Experiment[]; candidates?: Candidate[] }
interface Preview {
  experiment: string; pipeline: string; description: string; active_pipeline: string | null;
  tasks: { worker: string; kind: string; version: string; depends_on: string[]; action: string }[];
}

const KIND_LABEL: Record<string, string> = { deterministic: "deterministic code", model: "OPTIONAL model review (disabled unless authorized)", unimplemented: "not implemented" };
// Status accents: teal/cyan = deterministic research software; red = failed or interrupted;
// violet = optional model review (disabled); slate = idle, cancelled or not started.
const JOB_COLORS: Record<string, number> = {
  completed: 0x14b8a6, running: 0x22d3ee, queued: 0x64748b, failed: 0xef4444, blocked: 0xef4444, cancelled: 0x64748b,
  skipped: 0x8b5cf6,
};
const JOB_LEGEND = [
  { color: 0x14b8a6, label: "Completed (deterministic job)" }, { color: 0x22d3ee, label: "Running" },
  { color: 0x64748b, label: "Queued, cancelled or not started" }, { color: 0xef4444, label: "Failed or blocked" },
  { color: 0x8b5cf6, label: "Optional model review: DISABLED (skipped)" },
];
const JOB_ARCH: Record<string, "terraced" | "finned" | "paired" | "twisted" | "operations"> = {
  model: "twisted", deterministic: "terraced", unimplemented: "finned",
};
const ACTIVE = new Set(["queued", "running"]);

async function post(path: string, body: object): Promise<{ status: number; body: Record<string, unknown> }> {
  const r = await fetch(path, {
    method: "POST", body: JSON.stringify(body),
    headers: { "Content-Type": "application/json", "X-Dashboard-Control": "1" },
  });
  return { status: r.status, body: await r.json().catch(() => ({ error: `HTTP ${r.status}` })) };
}

export function pipelineLabel(p: Pipeline): string {
  if (p.status === "running" && p.cancel_requested) return "RUNNING · CANCELLATION REQUESTED (current step finishing)";
  if (p.status === "cancelled") return "CANCELLED (completed)";
  return p.status.toUpperCase();
}

class Boundary extends Component<{ onError: (m: string) => void; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(e: Error) { this.props.onError(`3D view crashed (${e.message}). Showing the table.`); }
  render() { return this.state.failed ? null : this.props.children; }
}

export default function JobsView({ reducedMotion }: { reducedMotion: boolean }) {
  const [tick, setTick] = useState(0);
  useEffect(() => { const id = setInterval(() => setTick((t) => t + 1), 1000); return () => clearInterval(id); }, []);
  const { data, error } = useLiveJson<JobsData>("/api/jobs", tick);
  const exps = useLiveJson<Experiments>("/api/experiments", tick);

  const [experiment, setExperiment] = useState<string | null>(null);
  const [pipelineId, setPipelineId] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [view, setView] = useState<"3D" | "Table">(
    () => (new URLSearchParams(window.location.search).get("3d") === "off" ? "Table" : "3D"));
  const [cityError, setCityError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ tone: string; text: string } | null>(null);
  const [report, setReport] = useState<{ id: string; text: string } | null>(null);

  const exp = exps.data?.experiments.find((e) => e.experiment === experiment) ?? null;
  useEffect(() => {                                   // default: first allowed experiment
    if (!experiment && exps.data?.experiments.length) setExperiment(exps.data.experiments[0].experiment);
  }, [experiment, exps.data]);

  const pipelines = useMemo(() => (data?.pipelines ?? []).filter((p) => p.experiment === experiment).reverse(),
    [data, experiment]);
  // Follow the active pipeline, else the newest, unless the owner picked one explicitly.
  const current = pipelines.find((p) => p.id === pipelineId)
    ?? pipelines.find((p) => ACTIVE.has(p.status)) ?? pipelines[0] ?? null;
  const active = pipelines.find((p) => ACTIVE.has(p.status)) ?? null;

  const previewKey = `${experiment}|${current?.id}|${current?.status}`;
  const preview = useLiveJson<Preview>(experiment ? `/api/pipelines/preview?experiment=${encodeURIComponent(experiment)}` : null, previewKey);

  const byId = useMemo(() => Object.fromEntries((data?.jobs ?? []).map((j) => [j.id, j])), [data]);
  const currentJobs = (current?.job_ids ?? []).map((id) => byId[id]).filter(Boolean) as Job[];
  const job = jobId ? byId[jobId] ?? null : null;
  const reportJob = currentJobs.find((j) => j.worker === "report");

  const towers = useMemo<TowerSpec[]>(() => currentJobs.map((j, i) => ({
    id: j.id, color: JOB_COLORS[j.status] ?? 0x64748b,
    // ingest/report get the broader operations building; model review the (disabled) twisted tower
    archetype: j.kind === "model" ? "twisted" : j.worker === "ingest" ? "operations" : j.worker === "report" ? "paired"
      : (["terraced", "finned"] as const)[i % 2] ?? JOB_ARCH[j.kind],
    category: j.kind === "model" ? "OPTIONAL REVIEW" : "RESEARCH JOB",
    title: j.worker,
    status: j.kind === "model" && j.status === "skipped" ? "DISABLED · SKIPPED" : j.status.toUpperCase(),
    dim: j.kind === "model" || j.status === "cancelled" || j.status === "queued",
    // draw a link only where the job really depends on another job in this pipeline
    links: (data?.workers.find((w) => w.worker === j.worker)?.depends_on ?? [])
      .map((dep) => currentJobs.find((x) => x.worker === dep)?.id).filter((x): x is string => !!x),
    lines: [
      { cls: "tl-tag", text: "REAL JOB" },
      { cls: "tl-name", text: j.worker },
      { cls: `tl-status js-${j.status}`, text: j.status.toUpperCase() },
      { cls: "tl-inst", text: KIND_LABEL[j.kind] ?? j.kind },
      ...(current && j.pipeline_id !== current.id ? [{ cls: "tl-sim", text: "reused earlier result" }] : []),
    ],
    ariaLabel: `Job ${j.worker}: ${j.status}. Show details.`,
    pulseKey: j.status,
  // eslint-disable-next-line react-hooks/exhaustive-deps
  })), [current?.id, currentJobs.map((j) => j.id + j.status).join()]);
  const onCityFailure = useCallback((m: string) => { setCityError(m); setView("Table"); }, []);

  const start = async () => {
    if (!experiment || busy) return;
    setBusy(true);
    setNotice(null);
    try {
      const r = await post("/api/pipelines", { experiment });
      if (r.status === 201 || r.status === 200) {
        setPipelineId(r.body.pipeline_id as string);
        setNotice({ tone: r.status === 201 ? "ok" : "warn",
          text: r.status === 201 ? `Started pipeline ${r.body.pipeline_id}: queued for the background runner.`
            : `Not started again: pipeline ${r.body.pipeline_id} is already active. No new work was created.` });
      } else {
        setNotice({ tone: "danger", text: `Refused by the server (HTTP ${r.status}): ${r.body.error}` });
      }
    } catch (e) {
      setNotice({ tone: "danger", text: `Request failed: ${(e as Error).message}` });
    } finally {
      setBusy(false);
      setTick((t) => t + 1);
    }
  };

  const cancel = async (p: Pipeline) => {
    setBusy(true);
    try {
      const r = await post(`/api/pipelines/${encodeURIComponent(p.id)}/cancel`, {});
      const res = r.body.result as string | undefined;
      setNotice(r.status !== 200 ? { tone: "danger", text: `Cancel refused (HTTP ${r.status}): ${r.body.error}` }
        : res === "cancelled" ? { tone: "ok", text: "Cancelled before any step started." }
        : res === "cancel_requested" ? { tone: "warn", text: "Cancellation REQUESTED. The step now running will finish; remaining steps will not start." }
        : { tone: "warn", text: `Nothing to cancel: pipeline is ${res?.replace("already ", "")}.` });
    } finally {
      setBusy(false);
      setTick((t) => t + 1);
    }
  };

  const openReport = async (p: Pipeline) => {
    const r = await fetch(`/api/reports/${encodeURIComponent(p.id)}`);
    const b = await r.json().catch(() => ({}));
    setReport(r.ok ? { id: p.id, text: b.report_markdown } : { id: p.id, text: `Report unavailable: ${b.error ?? r.status}` });
  };

  if (error) return <p className="error panel">Could not load research jobs: {error}</p>;
  if (!data || !exps.data) return <p className="empty panel">Loading research jobs…</p>;
  const finished = currentJobs.filter((j) => !ACTIVE.has(j.status)).length;
  const runningJob = currentJobs.find((j) => j.status === "running");

  return (
    <section className="panel wide jobs" aria-label="Research job control panel">
      <div className="jobs-banner"><strong>{data.mode_label}</strong> Predefined pipeline over saved artifacts of closed experiments.
        No trading evaluation is re-run, no held-out data is fetched, no orders exist here. Separate from the DEMO city.</div>

      <h3>1 · Select a saved experiment</h3>
      <div className="seg" role="radiogroup" aria-label="Experiment">
        {exps.data.experiments.map((e) => (
          <button key={e.experiment} type="button" role="radio" aria-checked={e.experiment === experiment}
                  className={e.experiment === experiment ? "on" : ""}
                  onClick={() => { setExperiment(e.experiment); setPipelineId(null); setJobId(null); setReport(null); setNotice(null); }}>
            {e.experiment}{e.status ? ` · ${e.status.state}` : ""}
          </button>
        ))}
      </div>

      {(exps.data.candidates ?? []).map((c) => (
        <details key={c.candidate} className="candidate">
          <summary>Candidate (not an experiment) · <code>{c.candidate}</code> · <strong>{c.status?.state ?? "unknown"}</strong>
            {c.status && !c.status.performance_evaluated ? " · not evaluated on performance" : ""}</summary>
          {c.status && (<>
            <p className="small">{c.status.title}</p>
            <p className="warn">{c.status.status}</p>
            <p className="small">Downloads: {c.status.downloads}. No pipeline can run on a candidate.</p>
            <p className="small"><strong>Blockers</strong></p>
            <ul className="notes">{c.status.blockers.map((b) => <li key={b}>{b}</li>)}</ul>
            <p className="small"><strong>Open uncertainties</strong></p>
            <ul className="notes">{c.status.open_uncertainties.map((b) => <li key={b}>{b}</li>)}</ul>
            <p className="small">To resume: {c.status.resume_requires}</p>
          </>)}
          <table className="artifacts"><thead><tr><th>Record</th><th>Present</th><th>Size</th><th>SHA-256 (first 16)</th></tr></thead>
            <tbody>{c.artifacts.map((a) => (
              <tr key={a.name}><td><code>{a.name}</code></td><td className={a.present ? "tone-ok" : "tone-danger"}>{a.present ? "yes" : "MISSING"}</td>
                <td>{a.bytes ?? "—"}</td><td><code>{a.sha256 ?? "—"}</code></td></tr>))}</tbody></table>
          {c.problems.length > 0 && <p className="warn">Problems: {c.problems.join("; ")}</p>}
        </details>
      ))}

      {exp && (<>
        <h3>2 · Available artifacts (read-only)</h3>
        <p className="small">Experiment {exp.status?.experiment_id ?? "?"} · state <strong>{exp.status?.state ?? "unknown"}</strong>
          {exp.status?.closed ? " · CLOSED (no further evaluation)" : ""}
          {exp.status?.failed_rules?.length ? ` · failed rules ${exp.status.failed_rules.join(", ")}` : ""}</p>
        <table className="artifacts"><thead><tr><th>File</th><th>Present</th><th>Size</th><th>SHA-256 (first 16)</th></tr></thead>
          <tbody>{exp.artifacts.map((a) => (
            <tr key={a.name}><td><code>{a.name}</code></td><td className={a.present ? "tone-ok" : "tone-danger"}>{a.present ? "yes" : "MISSING"}</td>
              <td>{a.bytes ?? "—"}</td><td><code>{a.sha256 ?? "—"}</code></td></tr>))}</tbody></table>
        {exp.problems.length > 0 && <p className="warn">Problems: {exp.problems.join("; ")}. Ingest will fail and record why.</p>}

        <h3>3 · Preview the research task</h3>
        {preview.error && <p className="error">Preview failed: {preview.error}</p>}
        {preview.data && (<>
          <p className="small"><strong>{preview.data.pipeline}</strong>: {preview.data.description}</p>
          <table><thead><tr><th>Step</th><th>Kind</th><th>Depends on</th><th>What starting would do</th></tr></thead>
            <tbody>{preview.data.tasks.map((t) => (
              <tr key={t.worker}><td>{t.worker}</td><td>{KIND_LABEL[t.kind] ?? t.kind}</td><td>{t.depends_on.join(", ") || "—"}</td><td>{t.action}</td></tr>))}</tbody></table>
        </>)}

        <h3>4 · Start the allowed job</h3>
        <div className="row">
          <button type="button" className="primary" onClick={start} disabled={busy || !!active}
                  aria-describedby="start-help">Start {preview.data?.pipeline ?? "pipeline"} for {experiment}</button>
          <span id="start-help" className="small muted">
            {active ? `Disabled: pipeline ${active.id} is ${active.status}. The server also refuses duplicates.`
              : "The server re-validates the request and reuses completed results."}</span>
        </div>
        {notice && <p className={`notice tone-${notice.tone}`} role="status">{notice.text}</p>}
      </>)}

      <h3>5 · Progress</h3>
      {!current ? <p className="empty">No pipeline has run for this experiment yet.</p> : (<>
        <div className="row pipeline-head">
          <label>Pipeline{" "}
            <select value={current.id} onChange={(e) => { setPipelineId(e.target.value); setJobId(null); setReport(null); }}>
              {pipelines.map((p) => <option key={p.id} value={p.id}>{p.id.split("@")[1]} · {p.status}{p.cancel_requested && p.status === "running" ? " (cancel requested)" : ""}</option>)}
            </select></label>
          <span className={`js js-${current.status}`} role="status" aria-live="polite">{pipelineLabel(current)}</span>
          <span className="small">{finished} of {currentJobs.length} steps finished{runningJob ? ` · now running: ${runningJob.worker}` : ""}</span>
          {ACTIVE.has(current.status) && (
            <button type="button" onClick={() => cancel(current)} disabled={busy || current.cancel_requested}>
              {current.cancel_requested ? "Cancellation requested" : "Cancel pipeline"}</button>)}
          {reportJob?.status === "completed" && <button type="button" onClick={() => openReport(current)}>6 · Open report</button>}
        </div>
        <progress max={currentJobs.length || 1} value={finished} aria-label="Steps finished" />
        <p className="small muted">Created {current.created_utc} · started {current.started_utc ?? "—"} · finished {current.finished_utc ?? "—"}
          {current.cancel_requested_utc ? ` · cancel requested ${current.cancel_requested_utc}` : ""}</p>
        {current.error && <p className="tone-danger">Pipeline error: {current.error}</p>}

        <div className="seg" role="tablist" aria-label="Job view">
          {(["3D", "Table"] as const).map((v) => (
            <button key={v} type="button" role="tab" aria-selected={view === v} className={view === v ? "on" : ""}
                    disabled={v === "3D" && !!cityError} onClick={() => setView(v)}>{v === "3D" ? "3D towers" : "Table"}</button>))}
        </div>
        {cityError && <p className="warn" role="alert">{cityError}</p>}
        {view === "3D" && !cityError && (
          <Boundary onError={onCityFailure}>
            <Suspense fallback={<p className="empty">Loading 3D view…</p>}>
              <CityView variant="jobs" towers={towers} coreColor={JOB_COLORS[current.status] ?? 0x334155}
                        legend={JOB_LEGEND} coreLabel={`this pipeline's status (${current.status})`}
                        selectedId={jobId} onSelect={setJobId} reducedMotion={reducedMotion} onFailure={onCityFailure} />
            </Suspense>
          </Boundary>
        )}
        {view === "Table" && (
          <table className="job-table" aria-label="Jobs in this pipeline">
            <thead><tr><th>Step</th><th>Kind</th><th>Status</th><th>Record</th><th>Started</th><th>Finished</th><th>Reason</th><th></th></tr></thead>
            <tbody>{currentJobs.map((j) => (
              <tr key={j.id} className={jobId === j.id ? "sel" : ""}>
                <td>{j.worker}</td><td>{KIND_LABEL[j.kind] ?? j.kind}</td>
                <td className={`js js-${j.status}`}>{j.status.toUpperCase()}</td>
                <td>{j.pipeline_id !== current.id ? "reused earlier result" : "this pipeline"}</td>
                <td>{j.started_utc ?? "—"}</td><td>{j.finished_utc ?? "—"}</td><td>{j.error ?? ""}</td>
                <td><button type="button" aria-pressed={jobId === j.id} onClick={() => setJobId(j.id)}>Details</button></td>
              </tr>))}</tbody>
          </table>
        )}
      </>)}

      {job && (
        <div className="job-detail" aria-label={`Job ${job.id}`}>
          <h3>{job.worker} <span className={`js js-${job.status}`}>{job.status.toUpperCase()}</span>
            <button type="button" className="small" onClick={() => setJobId(null)}>Close</button></h3>
          <dl className="kv">
            <dt>Job id</dt><dd><code>{job.id}</code> (attempt {job.attempt})</dd>
            <dt>Pipeline</dt><dd><code>{job.pipeline_id}</code></dd>
            <dt>Kind</dt><dd>{KIND_LABEL[job.kind] ?? job.kind}</dd>
            <dt>Timestamps</dt><dd>created {job.created_utc}; started {job.started_utc ?? "—"}; finished {job.finished_utc ?? "—"}</dd>
            <dt>Task inputs</dt><dd><code>{JSON.stringify(job.inputs)}</code></dd>
            {job.error && (<><dt>Failure / block / cancel reason</dt><dd className="tone-danger">{job.error}</dd></>)}
          </dl>
          {job.worker === "model_review" && (job.status === "blocked" || job.status === "skipped") && job.error && (<>
            <h3>Model review: OPTIONAL / DISABLED (no model review was performed)</h3>
            <ul className="notes">{job.error.replace(/^(UNAVAILABLE|OPTIONAL \/ DISABLED):\s*(no model review was performed\.\s*)?/, "").split("; ").map((r, k) => <li key={k}>{r}</li>)}</ul>
          </>)}
          {job.worker === "model_review" && typeof job.outputs?.review_id === "string" && (<>
            <h3>Automated second review</h3>
            <ReviewPanel reviewId={job.outputs.review_id} />
          </>)}
          <h3>Output</h3>
          {job.outputs ? <pre className="json">{JSON.stringify(job.outputs, null, 2).slice(0, 6000)}</pre> : <p className="empty">No output (nothing was produced or substituted).</p>}
          <h3>Evidence</h3>
          {job.evidence ? <pre className="json">{JSON.stringify(job.evidence, null, 2).slice(0, 6000)}</pre> : <p className="empty">No evidence recorded.</p>}
        </div>
      )}

      {report && report.id === current?.id && (
        <div className="job-detail" aria-label="Pipeline report">
          <h3>Report · {report.id} <button type="button" className="small" onClick={() => setReport(null)}>Close</button></h3>
          <pre className="json report">{report.text}</pre>
        </div>
      )}

      <details>
        <summary>Cancellation and restart rules</summary>
        <ul className="notes">
          <li>Queued pipeline: cancelling stops it at once; no step runs.</li>
          <li>Running pipeline: cancelling is a <em>request</em>. The step already running finishes (each step is short and atomic), then the remaining steps are marked cancelled and the pipeline shows CANCELLED. Completed steps and their evidence are kept.</li>
          <li>Backend restart: a pipeline that was running is marked FAILED ("interrupted"), never completed; its unstarted steps are marked cancelled.</li>
        </ul>
      </details>
      <details open>
        <summary>Model reviewer: readiness, budget and records</summary>
        <ReviewerReadiness tick={tick} />
      </details>
      <details>
        <summary>Roles and model-review policy</summary>
        <table><thead><tr><th>Role / worker</th><th>Kind</th><th>Status</th></tr></thead>
          <tbody>
            {data.workers.map((w) => <tr key={w.worker}><td>{w.worker}</td><td>{KIND_LABEL[w.kind] ?? w.kind}</td>
              <td>{w.worker === "model_review" ? `OPTIONAL automated review (v${w.version}): DISABLED; paid calls revoked until the owner reauthorizes` : `active job worker (v${w.version})`}</td></tr>)}
            {data.roles.map((r) => <tr key={r.role}><td>{r.role}</td><td>{KIND_LABEL[r.kind] ?? r.kind}</td><td>{r.status}</td></tr>)}
          </tbody></table>
        <ul className="notes">
          <li>The model review is implemented but stays UNAVAILABLE until the owner chooses a provider and model, writes a budget authorization, and one owner-approved verification call succeeds. It is a second opinion: it cannot change gates, rules or results.</li>
          <li>Credential: {data.model_policy.credential}</li>
          <li>Authorization: {data.model_policy.authorization}</li>
          <li>Billing: {data.model_policy.billing}</li>
        </ul>
      </details>
    </section>
  );
}
