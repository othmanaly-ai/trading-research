import { useEffect, useRef } from "react";
import * as THREE from "three";
import { CSS2DObject, CSS2DRenderer } from "three/addons/renderers/CSS2DRenderer.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { money } from "../format";
import type { StrategyView } from "../types";

// Tower color follows the ledger's status text; the label always spells the status out.
const COLORS: Record<string, number> = {
  long: 0x22d3ee, short: 0xe879f9, signal: 0xfbbf24, idle: 0x6366f1, skipped: 0x64748b, halted: 0xef4444,
};

const PER_ROW = 5;
const SPACING = 9.5;

function category(s: StrategyView): string {
  if (s.status.startsWith("HALTED")) return "halted";
  if (s.status === "IN POSITION LONG") return "long";
  if (s.status === "IN POSITION SHORT") return "short";
  if (s.status.startsWith("SIGNAL") || s.status === "ENTERING") return "signal";
  if (s.status === "SKIPPED") return "skipped";
  return "idle";
}

interface Tower {
  mesh: THREE.Mesh;
  material: THREE.MeshStandardMaterial;
  edges: THREE.LineBasicMaterial;
  label: HTMLButtonElement;
  pulse: number;          // 0..1, set when a fill or close event changed the position
  lastTrades: number;
  lastInPosition: boolean;
}

interface Props {
  strategies: StrategyView[];
  accountRisk: string;
  selectedId: string | null;
  onSelect: (id: string) => void;
  reducedMotion: boolean;
  onFailure: (reason: string) => void;
}

function fillLabel(el: HTMLButtonElement, s: StrategyView, selected: boolean) {
  el.replaceChildren();
  const line = (cls: string, text: string) => {
    const d = document.createElement("div");
    d.className = cls;
    d.textContent = text;
    el.appendChild(d);
  };
  line("tl-name", s.name);
  line("tl-inst", s.instrument_label);
  line(`tl-status tone-${category(s)}`, s.status);
  if (s.feed_status === "stale") line("tl-stale", "DATA STALE");
  line("tl-pnl", `Realized ${money(s.realized_pnl, true)}`);
  line("tl-pnl", `Unrealized ${s.position ? money(s.unrealized_pnl, true) : "— (flat)"}`);
  line("tl-sim", "simulated");
  el.className = `tower-label${selected ? " selected" : ""}`;
  el.setAttribute("aria-pressed", String(selected));
  el.setAttribute("aria-label", `${s.name}, ${s.instrument_label}, ${s.status}. Open details.`);
}

export default function CityView({ strategies, accountRisk, selectedId, onSelect, reducedMotion, onFailure }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const world = useRef<{
    scene: THREE.Scene; camera: THREE.PerspectiveCamera; renderer: THREE.WebGLRenderer;
    labels: CSS2DRenderer; controls: OrbitControls; core: THREE.MeshStandardMaterial;
    towers: Map<string, Tower>; render: () => void;
  } | null>(null);
  const motion = useRef(reducedMotion);
  const selectRef = useRef(onSelect);
  selectRef.current = onSelect;
  motion.current = reducedMotion;

  useEffect(() => {
    const el = host.current!;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true });
      if (!renderer.getContext()) throw new Error("no WebGL context");
    } catch (e) {
      onFailure(`3D view unavailable (${(e as Error).message}). Use the Table view.`);
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x0b0820);
    renderer.domElement.setAttribute("aria-hidden", "true");
    el.appendChild(renderer.domElement);

    const labels = new CSS2DRenderer();
    labels.domElement.className = "label-layer";
    el.appendChild(labels.domElement);

    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0x0b0820, 30, 80);
    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 200);
    camera.position.set(0, 14, 28);
    scene.add(new THREE.AmbientLight(0x6d5bd0, 0.6));
    const key = new THREE.PointLight(0x8b5cf6, 400, 80);
    key.position.set(0, 20, 10);
    scene.add(key);
    const grid = new THREE.GridHelper(80, 40, 0x7c3aed, 0x312e81);
    scene.add(grid);

    const core = new THREE.MeshStandardMaterial({ color: 0x1e1b4b, emissive: 0x4f46e5, emissiveIntensity: 0.6 });
    // Account core: its color follows the account risk status from the ledger.
    const coreMesh = new THREE.Mesh(new THREE.CylinderGeometry(2.2, 2.6, 0.8, 32), core);
    coreMesh.position.set(0, 0.4, 4);
    scene.add(coreMesh);

    const controls = new OrbitControls(camera, labels.domElement);
    controls.target.set(0, 3, -6);
    controls.update();
    controls.maxPolarAngle = Math.PI / 2.2;
    controls.minDistance = 10;
    controls.maxDistance = 50;

    const render = () => {
      renderer.render(scene, camera);
      labels.render(scene, camera);
    };
    controls.addEventListener("change", render);

    const resize = () => {
      const w = el.clientWidth, h = el.clientHeight;
      if (!w || !h) return;
      renderer.setSize(w, h);
      labels.setSize(w, h);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      render();
    };
    const ro = new ResizeObserver(resize);
    ro.observe(el);

    const towers = new Map<string, Tower>();
    world.current = { scene, camera, renderer, labels, controls, core, towers, render };
    resize();

    const raycaster = new THREE.Raycaster();
    const onClick = (e: MouseEvent) => {
      const r = renderer.domElement.getBoundingClientRect();
      const p = new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
      raycaster.setFromCamera(p, camera);
      const hit = raycaster.intersectObjects([...towers.values()].map((t) => t.mesh))[0];
      const id = hit && (hit.object.userData.id as string);
      if (id) selectRef.current(id);
    };
    labels.domElement.addEventListener("click", onClick);

    let frame = 0;
    const loop = () => {
      frame = requestAnimationFrame(loop);
      if (motion.current) return;
      let active = false;
      for (const t of towers.values()) {
        if (t.pulse > 0) {
          t.pulse = Math.max(0, t.pulse - 0.02);
          t.mesh.scale.set(1 + t.pulse * 0.25, 1, 1 + t.pulse * 0.25);
          t.material.emissiveIntensity = 0.25 + t.pulse * 1.2;
          active = true;
        }
      }
      if (active) render();
    };
    loop();

    return () => {
      cancelAnimationFrame(frame);
      ro.disconnect();
      labels.domElement.removeEventListener("click", onClick);
      controls.dispose();
      renderer.dispose();
      el.replaceChildren();
      world.current = null;
    };
  }, [onFailure]);

  useEffect(() => {
    const w = world.current;
    if (!w) return;
    const n = strategies.length;
    const ids = new Set(strategies.map((s) => s.id));
    for (const [id, t] of w.towers) {
      if (!ids.has(id)) {
        w.scene.remove(t.mesh);
        w.towers.delete(id);
      }
    }
    strategies.forEach((s, i) => {
      let t = w.towers.get(s.id);
      if (!t) {
        const material = new THREE.MeshStandardMaterial({ color: 0x0f0b2e, emissive: COLORS.idle, emissiveIntensity: 0.25 });
        const geometry = new THREE.BoxGeometry(2, 6, 2);
        const mesh = new THREE.Mesh(geometry, material);
        const edges = new THREE.LineBasicMaterial({ color: COLORS.idle });
        mesh.add(new THREE.LineSegments(new THREE.EdgesGeometry(geometry), edges));
        mesh.userData.id = s.id;
        // Evenly spaced rows of up to PER_ROW towers, far enough apart that labels don't overlap.
        const row = Math.floor(i / PER_ROW), col = i % PER_ROW;
        const inRow = Math.min(PER_ROW, n - row * PER_ROW);
        mesh.position.set((col - (inRow - 1) / 2) * SPACING, 3, -6 - row * SPACING);
        const label = document.createElement("button");
        label.type = "button";
        // OrbitControls captures the pointer on pointerdown, which would swallow the click.
        label.addEventListener("pointerdown", (e) => e.stopPropagation());
        label.addEventListener("click", (e) => { e.stopPropagation(); selectRef.current(s.id); });
        const obj = new CSS2DObject(label);
        obj.position.set(0, 3.4, 0);
        obj.center.set(0.5, 1);
        mesh.add(obj);
        w.scene.add(mesh);
        t = { mesh, material, edges, label, pulse: 0, lastTrades: s.trades, lastInPosition: !!s.position };
        w.towers.set(s.id, t);
      }
      const inPosition = !!s.position;
      if (s.trades !== t.lastTrades || inPosition !== t.lastInPosition) {
        // A fill opened or closed a position: that event drives the pulse.
        if (!motion.current) t.pulse = 1;
        t.lastTrades = s.trades;
        t.lastInPosition = inPosition;
      }
      t.material.emissive.setHex(COLORS[category(s)]);
      t.edges.color.setHex(COLORS[category(s)]);
      if (motion.current || t.pulse === 0) {
        t.mesh.scale.set(1, 1, 1);
        t.material.emissiveIntensity = s.id === selectedId ? 0.6 : 0.25;
      }
      fillLabel(t.label, s, s.id === selectedId);
    });
    w.core.emissive.setHex(accountRisk === "OK" ? 0x4f46e5 : accountRisk === "ATTENTION" ? 0xef4444 : 0x334155);
    w.render();
  }, [strategies, selectedId, accountRisk]);

  return <div className="city" ref={host} />;
}
