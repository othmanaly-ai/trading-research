import { Component, Suspense, lazy, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import TowerPanel from "./components/TowerPanel";
import JobsView from "./components/JobsView";
import MonitorView from "./components/MonitorView";
import {
  AccountPanel, ActivityFeed, Banner, Controls, Leaderboard, ModeStrip, RealBanner, ResearchView, SessionHistory, StrategyTable,
  isDemoView,
} from "./components/Panels";
import Overview from "./components/Overview";
import DependencyMap from "./components/DependencyMap";
import type { Research, StrategyView } from "./types";
import type { TowerSpec } from "./components/CityView";
import { money } from "./format";
import { useReplay } from "./useReplay";

const SUPPORTED_MODES = ["DEMO_REPLAY", "HISTORICAL_REPLAY"];

// Three.js loads in its own chunk; if it fails to load, the boundary below falls back to tables.
const CityView = lazy(() => import("./components/CityView"));

class Boundary extends Component<{ onError: (m: string) => void; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(e: Error) { this.props.onError(`3D view crashed (${e.message}). Showing the Table view.`); }
  render() { return this.state.failed ? null : this.props.children; }
}

// DEMO strategy towers: color follows the ledger's status text; the label spells it out.
const STRATEGY_COLORS: Record<string, number> = {
  long: 0x22d3ee, short: 0xe879f9, signal: 0xfbbf24, idle: 0x6366f1, skipped: 0x64748b, halted: 0xef4444,
};
function category(s: StrategyView): string {
  if (s.status.startsWith("HALTED")) return "halted";
  if (s.status === "IN POSITION LONG") return "long";
  if (s.status === "IN POSITION SHORT") return "short";
  if (s.status.startsWith("SIGNAL") || s.status === "ENTERING") return "signal";
  if (s.status === "SKIPPED") return "skipped";
  return "idle";
}
function strategyTower(s: StrategyView): TowerSpec {
  const c = category(s);
  return {
    id: s.id, color: STRATEGY_COLORS[c],
    category: "DEMO · SIMULATED", title: s.name, status: s.status, dim: c === "idle" || c === "skipped",
    lines: [
      { cls: "tl-name", text: s.name }, { cls: "tl-inst", text: s.instrument_label },
      { cls: `tl-status tone-${c}`, text: s.status },
      ...(s.feed_status === "stale" ? [{ cls: "tl-stale", text: "DATA STALE" }] : []),
      { cls: "tl-pnl", text: `Realized ${money(s.realized_pnl, true)}` },
      { cls: "tl-pnl", text: `Unrealized ${s.position ? money(s.unrealized_pnl, true) : "— (flat)"}` },
      { cls: "tl-sim", text: "simulated" },
    ],
    ariaLabel: `${s.name}, ${s.instrument_label}, ${s.status}. Open details.`,
    pulseKey: `${s.trades}:${s.position ? 1 : 0}`,      // a fill or close changed the position
  };
}
const CORE = (risk: string) => (risk === "OK" ? 0x4f46e5 : risk === "ATTENTION" ? 0xef4444 : 0x334155);

function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export default function App() {
  const r = useReplay();
  // Start on the real operational overview; the synthetic demo is one click away and labelled.
  const [view, setView] = useState(() => new URLSearchParams(window.location.search).get("view") ?? "Overview");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [reducedMotion, setReducedMotion] = useState(prefersReducedMotion);
  // ?3d=off skips WebGL entirely (slow machines, or to check the fallback path).
  const [cityError, setCityError] = useState<string | null>(() =>
    new URLSearchParams(window.location.search).get("3d") === "off"
      ? "3D view turned off (?3d=off). Showing the Table view." : null);

  const [research, setResearch] = useState<Research | null>(null);
  useEffect(() => {
    fetch("/api/research").then((x) => (x.ok ? x.json() : null)).then(setResearch).catch(() => setResearch(null));
  }, [r.meta]);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const on = () => setReducedMotion(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);

  // The tab title follows the kind of view, so a real-records page is never titled "DEMO".
  useEffect(() => {
    document.title = isDemoView(view) ? `${r.meta?.mode === "HISTORICAL_REPLAY" ? "HISTORICAL REPLAY" : "DEMO REPLAY"} · Strategy City`
      : `${view} · Real records · TradingProject`;
  }, [view, r.meta?.mode]);

  const onCityFailure = useCallback((m: string) => { setCityError(m); setView("Table"); }, []);
  const snap = r.snapshot;
  const selected = snap?.strategies.find((s) => s.id === selectedId) ?? null;
  const towers = useMemo(() => (snap?.strategies ?? []).map(strategyTower), [snap]);
  const names = useMemo(() => Object.fromEntries((snap?.strategies ?? []).map((s) => [s.id, s.name + " · " + s.instrument_label])), [snap]);

  if (r.metaError) {
    return (
      <main className="fatal">
        <Banner text="Synthetic data, simulated outcomes." />
        <h1>Backend unreachable</h1>
        <p>The dashboard could not reach the local server ({r.metaError}).</p>
        <p>Start it with <code>.venv\Scripts\python -m trading.dashboard.server</code>, then retry.</p>
        <button type="button" onClick={r.retry}>Retry</button>
      </main>
    );
  }
  const lastBar = selected ? snap?.instruments.find((i) => i.id === selected.instrument)?.last_bar_end_utc ?? null : null;
  const demo = isDemoView(view);
  const controls = (
    <Controls status={r.status} connection={r.connection} lastMessageAt={r.lastMessageAt} control={r.control}
              controlError={r.controlError} view={view} setView={setView}
              reducedMotion={reducedMotion} setReducedMotion={setReducedMotion} />
  );

  if (!demo) {
    // REAL views: no replay clock, demo controls, simulated account, demo activity or demo risk alerts.
    return (
      <div className="app app-real">
        <RealBanner />
        {controls}
        <div className="layout layout-real">
          <div className="main-area">
            {view === "Overview" && <Overview research={research} openView={setView} reducedMotion={reducedMotion} />}
            {view === "Research" && <ResearchView research={research} />}
            {view === "Research jobs" && <JobsView reducedMotion={reducedMotion} />}
            {view === "Market monitor" && <MonitorView reducedMotion={reducedMotion} />}
            {view === "Dependencies" && <DependencyMap reducedMotion={reducedMotion} />}
          </div>
        </div>
        <footer className="muted small">Real read-only records served by the local city server (127.0.0.1). The synthetic demo replay is under
          “Demo replay”; its figures are never mixed into these views.</footer>
      </div>
    );
  }

  if (!r.meta) return <main className="fatal"><p>Loading replay description…</p></main>;
  if (!SUPPORTED_MODES.includes(r.meta.mode)) {
    return <main className="fatal"><h1>Unexpected mode: {r.meta.mode}</h1><p>This build supports DEMO REPLAY and HISTORICAL REPLAY only. Nothing is displayed.</p></main>;
  }

  return (
    <div className="app">
      <Banner text={r.meta.banner} mode={r.meta.mode} />
      <ModeStrip active={r.meta.mode} research={research} />
      {controls}
      {r.connection !== "connected" && (
        <p className="warn" role="alert">Backend connection {r.connection}. Figures below are frozen at the last update.</p>
      )}
      {r.modeRejected > 0 && <p className="error" role="alert">{r.modeRejected} event(s) from another mode were rejected.</p>}
      {cityError && <p className="warn" role="alert">{cityError}</p>}
      {!snap ? <p className="empty panel">Waiting for the first snapshot…</p> : (
        <div className="layout">
          <div className="main-area">
            {view === "City" && !cityError && (
              snap.strategies.length ? (
                <Boundary onError={onCityFailure}>
                  <Suspense fallback={<p className="empty panel">Loading 3D view…</p>}>
                    <CityView towers={towers} coreColor={CORE(snap.account.risk_status)} coreLabel="simulated account risk status"
                              legend={[{ color: 0x22d3ee, label: "Simulated long" }, { color: 0xe879f9, label: "Simulated short" },
                                { color: 0xfbbf24, label: "Simulated signal" }, { color: 0x6366f1, label: "Idle" }, { color: 0xef4444, label: "Halted (simulated risk rule)" }]}
                              selectedId={selectedId} onSelect={setSelectedId}
                              reducedMotion={reducedMotion} onFailure={onCityFailure} />
                  </Suspense>
                </Boundary>
              ) : <p className="empty panel">No strategy instances configured. Add instances to dashboard/demo_config.json.</p>
            )}
            {(view === "Table" || (view === "City" && cityError)) && (
              <StrategyTable strategies={snap.strategies} selectedId={selectedId} onSelect={setSelectedId} />
            )}
            {view === "Sessions" && <SessionHistory snapshot={snap} />}
            {view === "Leaderboard" && <Leaderboard snapshot={snap} />}
          </div>
          <div className="side">
            <AccountPanel account={snap.account} snapshot={snap} instruments={snap.instruments} />
            {selected && <TowerPanel strategy={selected} lastBar={lastBar} mode={r.meta.mode} research={research}
                                     instance={r.meta.instances.find((i) => i.id === selected.id)}
                                     onClose={() => setSelectedId(null)} />}
          </div>
          <ActivityFeed events={r.events} names={names} />
        </div>
      )}
      <footer className="muted small">
        Mode {r.meta.mode} · source {r.meta.source} · feed {r.meta.feed} · cost model {r.meta.cost_model} ·
        UI duplicates ignored {r.uiDuplicatesIgnored} · {r.meta.event_count} events in replay
      </footer>
    </div>
  );
}
