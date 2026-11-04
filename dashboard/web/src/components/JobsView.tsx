import { useEffect, useState } from "react";
import { useLiveJson } from "../useLiveJson";

// Real research-job records from /api/jobs (trading/jobs.py). Never demo data.

interface Job {
  id: string; pipeline_id: string; worker: string; kind: string; experiment: string; status: string;
  attempt: number; created_utc: string; started_utc: string | null; finished_utc: string | null;
  inputs: Record<string, unknown> | null; outputs: Record<string, unknown> | null;
  evidence: Record<string, unknown> | null; error: string | null;
}
interface Pipeline { id: string; experiment: string; created_utc: string; status: string; job_ids: string[] }
interface JobsData {
  mode_label: string; pipelines: Pipeline[]; jobs: Job[];
  workers: { worker: string; kind: string; version: string; depends_on: string[] }[];
  roles: { role: string; kind: string; status: string }[];
  model_policy: { credential: string; authorization: string; billing: string; proposed_limits: Record<string, number> };
}

const KIND_LABEL: Record<string, string> = { deterministic: "deterministic code", model: "model-powered agent", unimplemented: "not implemented" };

export default function JobsView() {
  const [tick, setTick] = useState(0);
  useEffect(() => { const id = setInterval(() => setTick((t) => t + 1), 3000); return () => clearInterval(id); }, []);
  const { data, error } = useLiveJson<JobsData>("/api/jobs", tick);
  const [selected, setSelected] = useState<string | null>(null);

  if (error) return <p className="error panel">Could not load research jobs: {error}</p>;
  if (!data) return <p className="empty panel">Loading research jobs…</p>;
  const byId = Object.fromEntries(data.jobs.map((j) => [j.id, j]));
  const latest = Object.values(
    data.pipelines.reduce<Record<string, Pipeline>>((acc, p) => ({ ...acc, [p.experiment]: p }), {}));
  const job = selected ? byId[selected] : null;

  return (
    <section className="panel wide jobs" aria-label="Research jobs">
      <div className="jobs-banner"><strong>{data.mode_label}</strong> Jobs over saved experiment artifacts. Separate from the DEMO city and its synthetic results.</div>
      {!latest.length && (
        <p className="empty">No research jobs have run yet. Start one with <code>.venv\Scripts\python -m trading.jobs run --experiment 002_opening_range_breakout</code>.</p>
      )}
      {latest.map((p) => (
        <div key={p.id} className="pipeline">
          <h3>{p.experiment} · pipeline {p.id.split("@")[1]} · <span className={`js js-${p.status}`}>{p.status.toUpperCase()}</span></h3>
          <div className="job-towers" role="list">
            {p.job_ids.map((id) => byId[id]).filter(Boolean).map((j) => (
              <button key={j.id} type="button" role="listitem" className={`job-tower js-${j.status} ${selected === j.id ? "sel" : ""}`}
                      onClick={() => setSelected(j.id)} aria-label={`${j.worker}: ${j.status}. Show details.`}>
                <span className="jt-bar" aria-hidden="true" />
                <span className="jt-name">{j.worker}</span>
                <span className="jt-kind">{KIND_LABEL[j.kind] ?? j.kind}</span>
                <span className="jt-status">{j.status.toUpperCase()}</span>
                {j.pipeline_id !== p.id && <span className="jt-reused">reused completed result</span>}
              </button>
            ))}
          </div>
        </div>
      ))}
      {job && (
        <div className="job-detail" aria-label={`Job ${job.id}`}>
          <h3>{job.worker} <span className={`js js-${job.status}`}>{job.status.toUpperCase()}</span></h3>
          <dl className="kv">
            <dt>Job id</dt><dd><code>{job.id}</code> (attempt {job.attempt})</dd>
            <dt>Kind</dt><dd>{KIND_LABEL[job.kind] ?? job.kind}</dd>
            <dt>Timestamps</dt><dd>created {job.created_utc}; started {job.started_utc ?? "—"}; finished {job.finished_utc ?? "—"}</dd>
            <dt>Task inputs</dt><dd><code>{JSON.stringify(job.inputs)}</code></dd>
            {job.error && (<><dt>Failure / block reason</dt><dd className="tone-danger">{job.error}</dd></>)}
          </dl>
          <h3>Output</h3>
          {job.outputs ? <pre className="json">{JSON.stringify(job.outputs, null, 2).slice(0, 6000)}</pre> : <p className="empty">No output (nothing was produced or substituted).</p>}
          <h3>Evidence</h3>
          {job.evidence ? <pre className="json">{JSON.stringify(job.evidence, null, 2).slice(0, 6000)}</pre> : <p className="empty">No evidence recorded.</p>}
        </div>
      )}
      <h3>Roles</h3>
      <table><thead><tr><th>Role / worker</th><th>Kind</th><th>Status</th></tr></thead>
        <tbody>
          {data.workers.map((w) => <tr key={w.worker}><td>{w.worker}</td><td>{KIND_LABEL[w.kind] ?? w.kind}</td><td>active job worker (v{w.version})</td></tr>)}
          {data.roles.map((r) => <tr key={r.role}><td>{r.role}</td><td>{KIND_LABEL[r.kind] ?? r.kind}</td><td>{r.status}</td></tr>)}
        </tbody></table>
      <h3>Model-powered review: requirements before any paid run</h3>
      <ul className="notes">
        <li>Credential: {data.model_policy.credential}</li>
        <li>Authorization: {data.model_policy.authorization}</li>
        <li>Billing: {data.model_policy.billing}</li>
        <li>Proposed limits: {Object.entries(data.model_policy.proposed_limits).map(([k, v]) => `${k} ${v}`).join(", ")}</li>
      </ul>
    </section>
  );
}
