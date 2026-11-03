import { Component, Suspense, lazy, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import TowerPanel from "./components/TowerPanel";
import {
  AccountPanel, ActivityFeed, Banner, Controls, Leaderboard, SessionHistory, StrategyTable,
} from "./components/Panels";
import { useReplay } from "./useReplay";

// Three.js loads in its own chunk; if it fails to load, the boundary below falls back to tables.
const CityView = lazy(() => import("./components/CityView"));

class Boundary extends Component<{ onError: (m: string) => void; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(e: Error) { this.props.onError(`3D view crashed (${e.message}). Showing the Table view.`); }
  render() { return this.state.failed ? null : this.props.children; }
}

function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export default function App() {
  const r = useReplay();
  const [view, setView] = useState("City");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [reducedMotion, setReducedMotion] = useState(prefersReducedMotion);
  // ?3d=off skips WebGL entirely (slow machines, or to check the fallback path).
  const [cityError, setCityError] = useState<string | null>(() =>
    new URLSearchParams(window.location.search).get("3d") === "off"
      ? "3D view turned off (?3d=off). Showing the Table view." : null);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const on = () => setReducedMotion(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);

  const onCityFailure = useCallback((m: string) => { setCityError(m); setView("Table"); }, []);
  const snap = r.snapshot;
  const selected = snap?.strategies.find((s) => s.id === selectedId) ?? null;
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
  if (!r.meta) return <main className="fatal"><p>Loading replay description…</p></main>;
  if (r.meta.mode !== "DEMO_REPLAY") {
    return <main className="fatal"><h1>Unexpected mode: {r.meta.mode}</h1><p>This build only supports DEMO REPLAY. Nothing is displayed.</p></main>;
  }

  const lastBar = selected ? snap?.instruments.find((i) => i.id === selected.instrument)?.last_bar_end_utc ?? null : null;

  return (
    <div className="app">
      <Banner text={r.meta.banner} />
      <Controls status={r.status} connection={r.connection} lastMessageAt={r.lastMessageAt} control={r.control}
                controlError={r.controlError} view={view} setView={setView}
                reducedMotion={reducedMotion} setReducedMotion={setReducedMotion} />
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
                    <CityView strategies={snap.strategies} accountRisk={snap.account.risk_status}
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
            {selected && <TowerPanel strategy={selected} lastBar={lastBar} onClose={() => setSelectedId(null)} />}
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
