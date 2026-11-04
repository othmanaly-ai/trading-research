import { useEffect, useState } from "react";

// Automated second review (trading/reviewer). Displays what the backend validated and recorded;
// nothing is computed here. Deterministic checks stay the authority for pass/fail.

interface Citation { item_id: string; path: string; field: string; source: string; value_excerpt: string }
interface Gate { gate: string; deterministic_result: string; explanation: string; citations: Citation[] }
interface Finding { category: string; topic: string; statement: string; citations: Citation[] }
export interface Review {
  review_kind: string; summary: string; failed_gates: Gate[]; findings: Finding[]; limitations_of_this_review: string[];
}
interface EvidenceItem { id: string; path: string; field: string; source: string; value: unknown }
interface ReviewRecord {
  id: string; status: string; model: string; provider: string; prompt_version: string; evidence_fingerprint: string;
  started_utc: string | null; finished_utc: string | null; http_status: number | null; stop_reason: string | null;
  input_tokens: number | null; output_tokens: number | null; cost_usd: number | null; charged_usd: number | null;
  cost_basis: string | null; mock: boolean; error: string | null; validation: string[] | null;
  attempts: { attempt: number; outcome: string; http_status?: number | null; error?: string }[] | null;
  package: { items: EvidenceItem[]; untrusted_text_flags: { where: string; excerpt: string }[]; excluded: string[];
    deterministic_gates: Record<string, boolean>; redactions: number; truncations: unknown[] } | null;
}

const CAT_LABEL: Record<string, string> = { fact: "RECORDED FACT", deduction: "DEDUCTION", suggestion: "SUGGESTION (speculative)" };

export default function ReviewPanel({ reviewId }: { reviewId: string }) {
  const [rec, setRec] = useState<ReviewRecord | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  useEffect(() => {
    setRec(null); setErr(null); setOpen(null);
    fetch(`/api/reviews/${encodeURIComponent(reviewId)}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setRec).catch((e: Error) => setErr(e.message));
  }, [reviewId]);

  if (err) return <p className="error">Could not load review {reviewId}: {err}</p>;
  if (!rec) return <p className="empty">Loading review record…</p>;
  const review = (rec as unknown as { review: Review | null }).review;
  const item = open ? rec.package?.items.find((i) => i.id === open) : null;

  const cites = (cs: Citation[]) => cs.length === 0 ? <span className="muted small"> (no citation)</span> : (
    <span className="cites">{cs.map((c, k) => (
      <button key={k} type="button" className="cite" aria-pressed={open === c.item_id}
              title={`${c.path} · ${c.field}`} onClick={() => setOpen(c.item_id)}>
        {c.item_id} · {c.path.replace(/^research\//, "")} · {c.field}
      </button>))}</span>);

  return (
    <div className="review" aria-label={`Review ${rec.id}`}>
      <p className="review-banner">
        <strong>Automated second review</strong>, not proof of independent correctness. The deterministic checks
        decide arithmetic and pass/fail; a review that contradicts them is rejected.
        {rec.mock && <strong className="tone-warn"> MOCK RESPONSE (test data, not a real model).</strong>}
      </p>
      <dl className="kv">
        <dt>Record</dt><dd><code>{rec.id}</code> · status <strong>{rec.status.toUpperCase()}</strong></dd>
        <dt>Model</dt><dd>{rec.provider} / <code>{rec.model}</code> · prompt {rec.prompt_version}</dd>
        <dt>Evidence</dt><dd>fingerprint <code>{rec.evidence_fingerprint?.slice(0, 16)}</code> · {rec.package?.items.length ?? 0} items
          · {rec.package?.redactions ?? 0} redactions · {rec.package?.untrusted_text_flags.length ?? 0} instruction-like texts flagged</dd>
        <dt>Timing</dt><dd>started {rec.started_utc ?? "—"} · finished {rec.finished_utc ?? "—"} · HTTP {rec.http_status ?? "—"} · stop {rec.stop_reason ?? "—"}</dd>
        <dt>Usage / cost</dt><dd>{rec.input_tokens ?? "—"} in / {rec.output_tokens ?? "—"} out tokens · ${(rec.charged_usd ?? 0).toFixed(4)} charged ({rec.cost_basis ?? "—"})</dd>
        {rec.error && (<><dt>Error</dt><dd className="tone-danger">{rec.error}</dd></>)}
      </dl>
      {rec.validation && rec.validation.length > 0 && (
        <><h4>Validation errors (response rejected)</h4><ul className="notes">{rec.validation.map((v, k) => <li key={k}>{v}</li>)}</ul></>)}
      {review && (<>
        <h4>Summary</h4><p>{review.summary}</p>
        <h4>Failed gates</h4>
        <table><thead><tr><th>Gate</th><th>Deterministic result (authority)</th><th>Reviewer explanation</th></tr></thead>
          <tbody>{review.failed_gates.map((g) => (
            <tr key={g.gate}><td>{g.gate}</td><td className="tone-danger">{g.deterministic_result}</td>
              <td>{g.explanation}{cites(g.citations)}</td></tr>))}</tbody></table>
        <h4>Findings</h4>
        <ul className="findings">{review.findings.map((f, k) => (
          <li key={k}><span className={`badge cat-${f.category}`}>{CAT_LABEL[f.category] ?? f.category}</span>
            <span className="muted small"> {f.topic}</span> {f.statement}{cites(f.citations)}</li>))}</ul>
        <h4>Limitations of this review</h4>
        <ul className="notes">{review.limitations_of_this_review.map((l, k) => <li key={k}>{l}</li>)}</ul>
      </>)}
      {item && (
        <div className="evidence-item" role="region" aria-label={`Evidence ${item.id}`}>
          <h4>Evidence {item.id} <button type="button" className="small" onClick={() => setOpen(null)}>Close</button></h4>
          <p className="small"><code>{item.path}</code> · field <code>{item.field}</code> · {item.source === "deterministic_check" ? "deterministic check (authority)" : "saved artifact (sanitized copy)"}</p>
          <pre className="json">{typeof item.value === "string" ? item.value : JSON.stringify(item.value, null, 2)}</pre>
        </div>
      )}
      {rec.package && rec.package.untrusted_text_flags.length > 0 && (
        <details><summary>Instruction-like text found in artifacts (treated as data)</summary>
          <ul className="notes">{rec.package.untrusted_text_flags.map((f, k) => <li key={k}><code>{f.where}</code>: {f.excerpt}</li>)}</ul></details>)}
    </div>
  );
}

interface Readiness {
  available: boolean; label: string; checks: { check: string; ok: boolean; detail: string }[];
  month_spent_usd: number; prices_per_million: Record<string, [number, number]>; price_source: string;
  proposed_limits: Record<string, string | number>; hard_limits: Record<string, number>; prompt_version: string;
  authorization: Record<string, unknown> | null;
  recent: { id: string; status: string; model: string; experiment: string; charged_usd: number; mock: boolean; finished_utc: string | null }[];
}

export function ReviewerReadiness({ tick }: { tick: number }) {
  const [r, setR] = useState<Readiness | null>(null);
  useEffect(() => {
    fetch("/api/reviewer/status").then((x) => (x.ok ? x.json() : null)).then(setR).catch(() => setR(null));
  }, [Math.floor(tick / 5)]);
  if (!r) return <p className="empty">Loading reviewer status…</p>;
  return (
    <div className="readiness">
      <p className={r.available ? "tone-ok" : "tone-warn"}><strong>Model reviewer: {r.available ? "AVAILABLE" : "UNAVAILABLE"}</strong>
        {" "}({r.label}). Prompt {r.prompt_version}. Charged this month: ${r.month_spent_usd.toFixed(4)}.</p>
      <table><thead><tr><th>Gate</th><th>OK</th><th>Detail</th></tr></thead>
        <tbody>{r.checks.map((c) => <tr key={c.check}><td>{c.check}</td><td className={c.ok ? "tone-ok" : "tone-danger"}>{c.ok ? "yes" : "NO"}</td><td>{c.detail}</td></tr>)}</tbody></table>
      <p className="small">Proposed limits (not authorized): {Object.entries(r.proposed_limits).map(([k, v]) => `${k} ${v}`).join(" · ")}</p>
      <p className="small">Prices per 1M tokens, input / output ({r.price_source}): {Object.entries(r.prices_per_million).map(([m, [i, o]]) => `${m} $${i} / $${o}`).join(" · ")}</p>
      {r.recent.length > 0 && (
        <table><thead><tr><th>Review</th><th>Experiment</th><th>Model</th><th>Status</th><th>Charged</th></tr></thead>
          <tbody>{r.recent.map((x) => <tr key={x.id}><td><code>{x.id}</code>{x.mock ? " (MOCK)" : ""}</td><td>{x.experiment}</td><td>{x.model}</td><td>{x.status}</td><td>${(x.charged_usd ?? 0).toFixed(4)}</td></tr>)}</tbody></table>)}
    </div>
  );
}
