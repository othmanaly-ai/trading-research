import { Component, Suspense, lazy, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { useLiveJson } from "../useLiveJson";
import type { EdgeSpec, TowerSpec } from "./CityView";
import { etTime } from "./Overview";

// Read-only dependency-and-health map (trading/depmap.py via /api/depmap). It starts nothing and
// changes nothing. Declared (code/config), recorded (runtime) and proposed (unimplemented)
// connections are kept apart; Graphify static code relations are shown only as code evidence.

const CityView = lazy(() => import("./CityView"));

interface Cause { node: string; label: string; status: string; depth: number; evidence: string[] }
interface MapNode {
  id: string; label: string; group: string; mode: string; files: string[]; status: string; evidence: string[];
  last_success_utc: string | null; freshness: string | null; upstream: string[]; downstream: string[];
  why_blocked: Cause[]; upstream_issues?: Cause[]; impact: { node: string; label: string; depth: number; status: string }[]; next_action: string;
  implementation?: string;
}
interface MapEdge {
  from: string; to: string; kinds: string[];
  declared: { provenance: string } | null;
  recorded: { ts_utc: string; evidence: string; historical: boolean; event_id: string } | null;
  proposed: { provenance: string } | null;
  static_code: { relations: number | null; note?: string; source: string; built_at_commit?: string } | null;
}
interface DepMap { generated_utc: string; nodes: MapNode[]; edges: MapEdge[]; legend: Record<string, string>; no_execution_path: string }

const STATUS_COLOR: Record<string, number> = {
  OK: 0x14b8a6, IDLE: 0x64748b, CLOSED: 0x64748b, STALE: 0xfb923c, FAILED: 0xef4444, UNKNOWN: 0xeab308,
  DISABLED: 0x8b5cf6, "NOT IMPLEMENTED": 0x94a3b8,
};
const ARCH: Record<string, TowerSpec["archetype"]> = {
  external: "finned", collection: "operations", quality: "terraced", storage: "paired", research: "terraced", views: "finned", proposed: "construction",
};
// Stage layout (x, z): data flows left to right; the research pipeline is the back row.
const SLOT: Record<string, [number, number]> = {
  alpaca_iex: [-50, -6], alpaca_sip: [-50, -30], supervisor: [-34, 12], monitor_worker: [-32, -10], quality: [-16, -30],
  monitor_db: [-12, -6], daily_reports: [2, -30], view_monitor: [14, -8],
  history: [-44, -60], experiments: [-30, -60], ingest: [-16, -60], reconcile: [-2, -70], analysis: [-2, -50],
  rule_checks: [12, -60], model_review: [26, -72], report: [26, -48], view_jobs: [40, -56],
  proposed_news_analysis: [-16, -84], proposed_live_performance_monitoring: [30, 10], proposed_broker_reconciliation: [46, 10],
};
const MODE_SHORT = (m: string) => m.split(" (")[0];

class Boundary extends Component<{ onError: (m: string) => void; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(e: Error) { this.props.onError(`3D map unavailable (${e.message}). The tables below hold the same information.`); }
  render() { return this.state.failed ? null : this.props.children; }
}

export default function DependencyMap({ reducedMotion }: { reducedMotion: boolean }) {
  const [tick, setTick] = useState(0);
  useEffect(() => { const id = setInterval(() => setTick((t) => t + 1), 15000); return () => clearInterval(id); }, []);
  const { data, error } = useLiveJson<DepMap>("/api/depmap", tick);
  const [sel, setSel] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [cityError, setCityError] = useState<string | null>(() =>
    new URLSearchParams(window.location.search).get("3d") === "off" ? "3D map turned off (?3d=off)." : null);
  const onCityFailure = useCallback((m: string) => setCityError(m), []);

  const nodes = useMemo(() => Object.fromEntries((data?.nodes ?? []).map((n) => [n.id, n])), [data]);
  const node = sel ? nodes[sel] ?? null : null;
  const related = useMemo(() => new Set(node ? [...node.upstream, ...node.downstream, ...data!.edges
    .filter((e) => e.kinds.includes("proposed") && (e.from === node.id || e.to === node.id)).flatMap((e) => [e.from, e.to])] : []), [node, data]);

  const towers = useMemo<TowerSpec[]>(() => (data?.nodes ?? []).map((n) => {
    // latest *current* recorded handoff into this node, used once as an arrival event (never historical ones)
    const fresh = data!.edges.filter((e) => e.to === n.id && e.recorded && !e.recorded.historical).map((e) => e.recorded!);
    const latest = fresh.sort((a, b) => b.ts_utc.localeCompare(a.ts_utc))[0];
    return {
      id: n.id, color: STATUS_COLOR[n.status] ?? 0x64748b, slot: SLOT[n.id] ?? [0, 30],
      archetype: n.id === "model_review" ? "twisted" : n.id.startsWith("view_") ? "finned" : ARCH[n.group] ?? "terraced",
      category: `${n.group.toUpperCase()} · ${MODE_SHORT(n.mode)}`,
      title: n.label.replace(" (not implemented)", "").replace("Pipeline step · ", "step: ").replace("Alpaca market data · ", "Alpaca ").replace(" (15-min delayed)", " delayed"),
      status: n.status,
      // no selection: compact labels for all; with a selection: full labels for it and its direct
      // neighbours, others hidden (still in the Buildings list and the tables below)
      labelMode: !sel ? "compact" : n.id === sel || related.has(n.id) ? "full" : "hidden",
      dim: ["IDLE", "CLOSED", "DISABLED", "NOT IMPLEMENTED"].includes(n.status), warn: ["FAILED", "STALE"].includes(n.status),
      related: related.has(n.id) && n.id !== sel,
      event: latest ? { id: latest.event_id, kind: "arrival" as const } : undefined,
      lines: [{ cls: "tl-name", text: n.label }, { cls: "tl-status", text: n.status }, ...n.evidence.map((t) => ({ cls: "tl-inst", text: t }))],
      ariaLabel: `${n.label}: ${n.status}. Show dependencies.`, pulseKey: "",
    };
  }), [data, related, sel]);

  const edgeSpecs = useMemo<EdgeSpec[]>(() => (data?.edges ?? [])
    .filter((e) => showAll || (sel && (e.from === sel || e.to === sel)))
    .map((e) => ({ from: e.from, to: e.to,
      style: e.recorded ? "recorded" : e.kinds.includes("declared") ? "declared" : "proposed",
      color: e.recorded ? (e.recorded.historical ? 0x5eead4 : 0x22d3ee) : undefined })), [data, sel, showAll]);

  if (error) return <p className="error panel">Could not load the dependency map: {error}</p>;
  if (!data) return <p className="empty panel">Loading dependency map…</p>;
  const edgesOf = (id: string) => data.edges.filter((e) => e.from === id || e.to === id);

  return (
    <section className="panel wide depmap" aria-label="Dependency and health map">
      <h2>Dependency and health map <span className="small muted">read-only · generated {etTime(data.generated_utc)}</span></h2>
      <p className="small">Select a component to see what it depends on, what depends on it, its evidence and why it may be blocked.
        Statuses come only from runtime records; with no record a status is <strong>UNKNOWN</strong>. {data.no_execution_path}</p>
      <div className="row">
        <label><input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} /> Show all connections (overview)</label>
        <span className="small muted">Line styles: solid = recorded handoff · dashed = declared dependency · dotted = proposed (not implemented).</span>
      </div>
      <div className="district">
        {cityError ? <p className="warn">{cityError}</p> : (
          <Boundary onError={onCityFailure}>
            <Suspense fallback={<p className="empty">Loading 3D map…</p>}>
              <CityView variant="depmap" towers={towers} edges={edgeSpecs} coreColor={null} selectedId={sel} onSelect={setSel}
                        reducedMotion={reducedMotion} onFailure={onCityFailure}
                        legend={Object.entries(STATUS_COLOR).map(([k, c]) => ({ color: c, label: k }))} />
            </Suspense>
          </Boundary>
        )}
        {!node && <aside className="district-detail dep-detail"><h3>Select a component</h3>
        <p className="small">Click a building, a label, a Buildings-list entry or a row in the Components table to see its upstream and downstream
          dependencies, evidence, “Why blocked?” trace, dependency impact and next available action.</p></aside>}
      {node && (
          <aside className="district-detail dep-detail" aria-label={`Selected: ${node.label}`}>
            <h3>{node.label} <button type="button" className="small" onClick={() => setSel(null)}>Close</button></h3>
            <p><strong style={{ color: `#${(STATUS_COLOR[node.status] ?? 0x64748b).toString(16).padStart(6, "0")}` }}>{node.status}</strong>
              {" "}· {node.mode}{node.implementation ? ` · ${node.implementation}` : ""}</p>
            <p className="small">Last success: {etTime(node.last_success_utc)}{node.freshness ? ` · freshness: ${node.freshness}` : ""}</p>
            <h4 className="floor-h">Evidence</h4>
            <ul className="notes">{node.evidence.map((t, i) => <li key={i}>{t}</li>)}</ul>
            <h4 className="floor-h">Why blocked?</h4>
            {node.why_blocked.length === 0 ? (<>
              <p className="small tone-ok">Not blocked: this component's own record is {node.status}.</p>
              {(node.upstream_issues ?? []).length > 0 && (<>
                <p className="small warn">Upstream issues (a dependency has a problem; this component's own record does not show it as blocked):</p>
                <ul className="notes">{node.upstream_issues!.map((c, i) => <li key={i} style={{ marginLeft: (c.depth - 1) * 12 }}><strong>{c.label}</strong> — {c.status}: {c.evidence[0]}</li>)}</ul>
              </>)}
            </>) : (
              <ol className="notes why">{node.why_blocked.map((c, i) => (
                <li key={i} style={{ marginLeft: c.depth * 12 }}><strong>{c.label}</strong> — {c.status}{c.depth ? ` (upstream, depth ${c.depth})` : " (this component)"}
                  <ul>{c.evidence.map((t, j) => <li key={j} className="small">{t}</li>)}</ul></li>))}</ol>
            )}
            {node.impact.length > 0 && (<>
              <h4 className="floor-h">Dependency impact (not proof of failure)</h4>
              <ul className="notes">{node.impact.map((x) => <li key={x.node}>{x.label} · depth {x.depth} · its own record: {x.status}</li>)}</ul>
            </>)}
            <h4 className="floor-h">Next available action</h4>
            <p className="small">{node.next_action}</p>
            <h4 className="floor-h">Connections</h4>
            <ul className="notes conn">{edgesOf(node.id).map((e) => {
              const other = e.from === node.id ? e.to : e.from;
              return (
                <li key={e.from + e.to}>
                  <button type="button" className="cite" onClick={() => setSel(other)}>{e.from === node.id ? "→" : "←"} {nodes[other]?.label ?? other}</button>
                  {" "}<span className="small">[{e.kinds.join(" + ")}]</span>
                  <ul>
                    {e.declared && <li className="small">Declared: {e.declared.provenance}</li>}
                    {e.recorded && <li className="small">Recorded handoff: {etTime(e.recorded.ts_utc)} — {e.recorded.evidence}{e.recorded.historical ? " (historical, not current activity)" : ""}</li>}
                    {e.proposed && <li className="small">Proposed: {e.proposed.provenance}</li>}
                    {e.static_code && <li className="small muted">Static code (Graphify): {e.static_code.relations ?? "n/a"}{e.static_code.note ? ` — ${e.static_code.note}` : ""}</li>}
                  </ul>
                </li>);
            })}</ul>
          </aside>
        )}
      </div>

      <h3>Components</h3>
      <div className="scroll"><table className="q-table" aria-label="Components">
        <thead><tr><th>Component</th><th>Status</th><th>Work mode</th><th>Last success</th><th>Blocked by</th><th>Next action</th></tr></thead>
        <tbody>{data.nodes.map((n) => (
          <tr key={n.id} className={sel === n.id ? "sel" : ""}>
            <td><button type="button" className="cite" aria-pressed={sel === n.id} onClick={() => setSel(n.id)}>{n.label}</button></td>
            <td>{n.status}</td><td>{n.mode}</td><td>{etTime(n.last_success_utc)}</td>
            <td>{n.why_blocked.filter((c) => c.depth > 0).map((c) => c.label).join(", ") || "—"}</td><td className="small">{n.next_action}</td>
          </tr>))}</tbody>
      </table></div>
      <h3>Connections</h3>
      <div className="scroll"><table className="q-table" aria-label="Connections">
        <thead><tr><th>From</th><th>To</th><th>Kind</th><th>Last recorded handoff</th><th>Declared in</th><th>Static code (Graphify)</th></tr></thead>
        <tbody>{data.edges.map((e) => (
          <tr key={e.from + e.to}>
            <td>{nodes[e.from]?.label}</td><td>{nodes[e.to]?.label}</td><td>{e.kinds.join(" + ")}</td>
            <td>{e.recorded ? `${etTime(e.recorded.ts_utc)}${e.recorded.historical ? " (historical)" : ""}` : "—"}</td>
            <td className="small">{e.declared?.provenance ?? e.proposed?.provenance ?? "—"}</td>
            <td className="small">{e.static_code ? (e.static_code.relations ?? "n/a") : "graph unavailable"}</td>
          </tr>))}</tbody>
      </table></div>
      <p className="small muted">{Object.entries(data.legend).map(([k, v]) => `${k}: ${v}`).join(" · ")}</p>
    </section>
  );
}
