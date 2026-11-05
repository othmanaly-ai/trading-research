import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { CSS2DObject, CSS2DRenderer } from "three/addons/renderers/CSS2DRenderer.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { ARCHETYPES, ARCHETYPE_LABEL, PALETTE, type Archetype } from "./city/palette";
import { buildArchetype, makeKit, type Built, type Kit } from "./city/architecture";
import { buildScenery, PLAZA_R, type Scenery } from "./city/scenery";
import { buildAmbient, type Ambient, type Effects } from "./city/ambient";

// The city district. Four layers, kept separate:
//   1. static architecture (scenery + building geometry) — built once, never rebuilt on status;
//   2. application-state mapping (accent colour, beacon, halo, label text) — from TowerSpec records;
//   3. interaction and labels (picking, hover, selection, camera, compact labels with leaders);
//   4. optional effects (bloom, decorative aviation lights, event pulses) — off in Low / reduced motion.
// Every operational colour, badge and pulse comes from a TowerSpec built from real records by the
// calling view. Architecture and window lights are decorative and carry no status.

export interface TowerSpec {
  id: string;
  color: number;                         // status accent from records
  lines: { cls: string; text: string }[]; // full text (kept for the accessible table/list)
  ariaLabel: string;
  pulseKey: string;                      // changes only on a real recorded event
  archetype?: Archetype;
  category?: string;                     // short tag, e.g. "MARKET DATA"
  title?: string;
  status?: string;
  dim?: boolean;                         // disabled / deferred / idle: low accent intensity
  links?: string[];                      // ids this building really depends on (drawn, pulsed on events)
  slot?: [number, number];               // explicit x,z (district layout); otherwise arranged on the arc
  /** Latest recorded event for this building. Its id must be stable for the same record, so polling
   *  and reconnects never replay it; a new id plays its effect once. */
  event?: { id: string; kind: "arrival" | "start" | "complete" | "fail" };
  active?: boolean;                      // work in progress per the records (steady accent; gentle breathing if motion allowed)
  warn?: boolean;                        // failure or stale data per the records: persistent warning ring and ⚠
  related?: boolean;                     // upstream/downstream of the selected building (highlighted)
  labelMode?: "full" | "compact" | "hidden";   // compact = title + status; hidden = listed only (Buildings list, tables)
}

/** Explicit connections with a style per kind (used by the dependency map). When given, they replace
 *  the TowerSpec `links`. recorded = solid tube, declared = dashed line, proposed = dotted line. */
export interface EdgeSpec { from: string; to: string; style: "recorded" | "declared" | "proposed"; color?: number }

// Event ids already shown, per scene type, kept across remounts so a reconnect, a view change or
// a polling repeat never animates the same recorded event twice (bounded).
const SEEN = new Map<string, Set<string>>();
function seenSet(key: string): Set<string> {
  let set = SEEN.get(key);
  if (!set) { set = new Set(); SEEN.set(key, set); }
  if (set.size > 2000) { const keep = [...set].slice(-1000); set.clear(); keep.forEach((k) => set!.add(k)); }
  return set;
}

export interface CityMode { label: string; detail?: string; tone: "demo" | "real" }

interface Props {
  towers: TowerSpec[];
  coreColor: number | null;
  selectedId: string | null;
  onSelect: (id: string) => void;
  reducedMotion: boolean;
  onFailure: (reason: string) => void;
  variant?: "strategy" | "jobs" | "monitor" | "district" | "depmap";
  edges?: EdgeSpec[] | null;
  mode?: CityMode;
  coreLabel?: string;                    // what the plaza ring colour means (if shown)
  legend?: { color: number; label: string }[];
}

const DEFAULT_MODE: Record<string, CityMode> = {
  strategy: { label: "DEMO REPLAY", detail: "synthetic data · simulated outcomes · not trading", tone: "demo" },
  jobs: { label: "REAL RESEARCH JOBS", detail: "deterministic software over saved artifacts", tone: "real" },
  monitor: { label: "REAL MARKET MONITOR", detail: "read-only market data", tone: "real" },
  district: { label: "REAL RECORDS", detail: "read-only status of this project's components", tone: "real" },
  depmap: { label: "DEPENDENCY MAP", detail: "read-only · declared, recorded and proposed connections", tone: "real" },
};
const DEFAULT_LEGEND = [
  { color: PALETTE.amber, label: "Market-data monitoring" },
  { color: PALETTE.teal, label: "Deterministic research jobs" },
  { color: PALETTE.violet, label: "Optional model review (disabled)" },
  { color: PALETTE.red, label: "Failed or interrupted" },
  { color: PALETTE.deferred, label: "Deferred / paused" },
];

type Quality = Effects;
function savedQuality(): Quality {
  try {
    const v = localStorage.getItem("city-quality");
    return v === "low" || v === "medium" || v === "high" ? v : "medium";
  } catch { return "medium"; }
}

interface Node {
  spec: TowerSpec;
  arch: Archetype;
  built: Built;
  accent: THREE.MeshStandardMaterial;
  halo: THREE.Mesh;
  holder: HTMLDivElement;
  label: HTMLButtonElement;
  leader: HTMLDivElement;
  pulse: number;
  lastKey: string;
  warnRing: THREE.Mesh;
}

const HERO = 1.3;                       // scale of selectable buildings relative to the scenery
function hex(c: number) { return `#${c.toString(16).padStart(6, "0")}`; }
function derived(spec: TowerSpec) {
  const pick = (k: string) => spec.lines.find((l) => l.cls.includes(k))?.text;
  return {
    title: spec.title ?? pick("tl-name") ?? spec.lines[0]?.text ?? spec.id,
    status: spec.status ?? pick("tl-status") ?? "",
    category: spec.category ?? pick("tl-tag") ?? "",
  };
}

/** Arc layout in front of the plaza, facing the default camera; two rows when crowded. */
function slotFor(i: number, n: number, spec: TowerSpec): THREE.Vector3 {
  if (spec.slot) return new THREE.Vector3(spec.slot[0], 0, spec.slot[1]);
  const perRow = 6;
  const row = Math.floor(i / perRow), inRow = Math.min(perRow, n - row * perRow), k = i % perRow;
  const radius = (inRow <= 3 ? 24 : 29) + row * 17;
  const spread = inRow <= 1 ? 0 : Math.min(150, 34 * (inRow - 1)) * (Math.PI / 180);
  const a = inRow <= 1 ? 0 : -spread / 2 + (k * spread) / (inRow - 1);
  return new THREE.Vector3(Math.sin(a) * radius, 0, -Math.cos(a) * radius + 4);
}

export default function CityView(props: Props) {
  const { towers, coreColor, selectedId, onSelect, reducedMotion, onFailure, variant = "strategy" } = props;
  const host = useRef<HTMLDivElement>(null);
  const [quality, setQuality] = useState<Quality>(savedQuality);
  const [showLegend, setShowLegend] = useState(false);
  const [showList, setShowList] = useState(() => window.innerWidth > 1300);
  const [stats, setStats] = useState<{ calls: number; tris: number; fps: number } | null>(null);
  const api = useRef<{
    sync: (t: TowerSpec[], sel: string | null, core: number | null) => void;
    setEdges: (e: EdgeSpec[] | null) => void;
    focus: (id: string | null) => void;
    hover: (id: string | null) => void;
  } | null>(null);
  const selectRef = useRef(onSelect);
  selectRef.current = onSelect;
  const motion = useRef(reducedMotion);
  motion.current = reducedMotion;
  const mode = props.mode ?? DEFAULT_MODE[variant];
  const legend = props.legend ?? DEFAULT_LEGEND;

  // ------------------------------------------------------------------ 1 + 3 + 4: scene setup
  useEffect(() => {
    const el = host.current!;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: quality !== "low", powerPreference: "high-performance" });
      if (!renderer.getContext()) throw new Error("no WebGL context");
    } catch (e) {
      onFailure(`3D view unavailable (${(e as Error).message}). Use the Table view.`);
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, quality === "high" ? 1.75 : quality === "medium" ? 1.25 : 1));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.3;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.domElement.setAttribute("aria-hidden", "true");
    el.appendChild(renderer.domElement);
    const labels = new CSS2DRenderer();
    labels.domElement.className = "label-layer";
    el.appendChild(labels.domElement);

    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(PALETTE.fog, quality === "low" ? 0.011 : 0.0092);
    const camera = new THREE.PerspectiveCamera(42, 1, 0.5, 600);
    const HOME_TARGET = new THREE.Vector3(0, 5, -14);
    const HOME_DIR = new THREE.Vector3(0, 0.62, 1).normalize();     // ~32° above the street: skyline with a readable plan
    camera.position.copy(HOME_TARGET).addScaledVector(HOME_DIR, 70);

    const kit: Kit = makeKit(renderer.capabilities.getMaxAnisotropy());
    // Scenery stays clear of the plaza, the selectable arc and the camera's line of sight to it.
    const keepClear = (x: number, z: number) => {
      const r = Math.hypot(x, z);
      if (r < 22) return false;
      if (z > -2 && Math.abs(x) < 55 && r < 70) return false;             // in front: open sightlines
      if (r < 48 && z < 10) return false;                                  // the selectable arc and its gaps
      return true;
    };
    const scenery: Scenery = buildScenery(kit, quality === "low" ? "low" : "high", keepClear);
    scene.add(scenery.group);
    // Decorative ambient layer (independent of application state; see the legend).
    const ambient: Ambient = buildAmbient(quality, { landmarks: scenery.landmarks, facade: kit.textures, fountain: variant !== "district" });
    scene.add(ambient.group);

    // Plaza status ring (meaning given by coreLabel in the legend; hidden when the core is a building).
    const coreMat = new THREE.MeshBasicMaterial({ color: 0x334155, transparent: true, opacity: 0.55, blending: THREE.AdditiveBlending, depthWrite: false });
    const coreRing = new THREE.Mesh(new THREE.RingGeometry(PLAZA_R - 2.2, PLAZA_R - 1.6, 96), coreMat);
    coreRing.rotation.x = -Math.PI / 2;
    coreRing.position.y = 0.08;
    scene.add(coreRing);

    const controls = new OrbitControls(camera, labels.domElement);
    controls.target.copy(HOME_TARGET);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.minDistance = 16;
    controls.maxDistance = 150;
    controls.minPolarAngle = 0.25;
    controls.maxPolarAngle = 1.42;               // never below the street
    controls.update();

    // Optional effects: restrained bloom (labels are DOM, so text is never blurred).
    let composer: EffectComposer | null = null;
    let bloom: UnrealBloomPass | null = null;
    if (quality === "high") {
      composer = new EffectComposer(renderer);
      composer.addPass(new RenderPass(scene, camera));
      bloom = new UnrealBloomPass(new THREE.Vector2(256, 256), 0.55, 0.45, 0.82);
      composer.addPass(bloom);
      composer.addPass(new OutputPass());
    }

    const nodes = new Map<string, Node>();
    const linkGroup = new THREE.Group();
    scene.add(linkGroup);
    let linkKey = "";
    const pulses: { mesh: THREE.Mesh; curve: THREE.QuadraticBezierCurve3; t: number }[] = [];
    // expanding event rings (one shared geometry, a material per ring while it plays)
    const ringGeo = new THREE.RingGeometry(1, 1.12, 64);
    const rings: { mesh: THREE.Mesh; t: number; dur: number; r0: number }[] = [];
    const seen = seenSet(variant);
    const pulseGeo = new THREE.SphereGeometry(0.35, 12, 8);
    let selected: string | null = null, hovered: string | null = null;
    let needs = true;

    // Camera transition (skipped under reduced motion).
    let tween: { t: number; fromP: THREE.Vector3; toP: THREE.Vector3; fromT: THREE.Vector3; toT: THREE.Vector3 } | null = null;
    const moveTo = (toT: THREE.Vector3, toP: THREE.Vector3) => {
      if (motion.current) { controls.target.copy(toT); camera.position.copy(toP); controls.update(); needs = true; return; }
      tween = { t: 0, fromP: camera.position.clone(), toP, fromT: controls.target.clone(), toT };
    };
    // Frame every selectable building: horizontal extent decides the distance for the window's aspect.
    const homeTarget = () => {
      const ps = [...nodes.values()].map((n) => n.built.group.position);
      if (!ps.length) return HOME_TARGET.clone();
      const cx = (Math.min(...ps.map((p) => p.x)) + Math.max(...ps.map((p) => p.x))) / 2;
      const cz = (Math.min(...ps.map((p) => p.z)) + Math.max(...ps.map((p) => p.z))) / 2;
      return new THREE.Vector3(cx, 9, cz - 2);
    };
    const homeDistance = () => {
      const ps = [...nodes.values()].map((n) => n.built.group.position);
      const half = ps.length ? Math.max(14, ...ps.map((p) => Math.abs(p.x - homeTarget().x) + 13)) : 30;
      const depth = ps.length ? Math.max(...ps.map((p) => p.z)) - Math.min(...ps.map((p) => p.z)) : 20;
      const hf = Math.atan(Math.tan((camera.fov * Math.PI) / 360) * camera.aspect);
      // vertical fit: the tallest selectable building plus room for its label
      const tallest = Math.max(10, ...[...nodes.values()].map((n) => n.built.height * HERO));
      const vfit = ((tallest + 16) / Math.tan((camera.fov * Math.PI) / 360)) * 0.72;
      return Math.min(170, Math.max(56, half / Math.tan(hf) + depth * 0.45 + 10, vfit + depth * 0.3));
    };
    let userMoved = false;                     // until the user orbits, keep the home framing fitted to the window
    const goHome = (instant = false) => {
      const t = homeTarget(), p = t.clone().addScaledVector(HOME_DIR, homeDistance());
      if (instant) { tween = null; controls.target.copy(t); camera.position.copy(p); controls.update(); needs = true; }
      else moveTo(t, p);
      userMoved = false;
    };
    const focus = (id: string | null) => {
      const n = id ? nodes.get(id) : null;
      if (!n) return;
      const p = n.built.group.position;
      const toT = new THREE.Vector3(p.x, n.built.height * HERO * 0.45, p.z);
      const dir = camera.position.clone().sub(controls.target).setY(0).normalize();
      if (dir.z < 0.2) dir.set(Math.sign(p.x) * 0.3, 0, 1).normalize();
      const dist = Math.min(110, Math.max(55, n.built.height * HERO * 2.3 + 22));
      userMoved = true;
      moveTo(toT, toT.clone().add(dir.multiplyScalar(dist)).setY(toT.y + dist * 0.55));
    };

    // Labels: compact, with a leader line to the roof; overlapping labels are lifted (leader grows).
    const declutter = () => {
      const box = el.getBoundingClientRect();
      // Overlay panels (mode badge, tools, list, legend) are obstacles; labels never hide under them.
      const wrap = el.parentElement!;
      const obstacles = [...wrap.querySelectorAll(".city-mode, .city-tools, .city-list:not(.collapsed), .city-legend")]
        .map((o) => o.getBoundingClientRect()).filter((r) => r.width > 0);
      const topLimit = box.top + 4 + Math.max(0, ...obstacles.filter((o) => o.top < box.top + 60 && o.height < 70).map((o) => o.bottom - box.top));
      const rightLimit = Math.min(box.right - 4, ...obstacles.filter((o) => o.top < box.top + 70 && o.height > 80).map((o) => o.left - 4));
      const items = [...nodes.values()].map((n) => {
        n.leader.style.height = "16px";
        n.label.style.transform = "";
        n.holder.style.visibility = "";
        return { n, r: n.label.getBoundingClientRect() };
      }).filter((x) => x.r.width > 0 && !x.n.holder.classList.contains("lm-hidden"))
        // the selected label is placed first, so it is never the one that gives way
        .sort((a, b) => (a.n.spec.id === selected ? -1 : b.n.spec.id === selected ? 1 : a.r.left - b.r.left));
      const placed: { l: number; r: number; t: number; b: number }[] = [];
      const clash = (l: number, r: number, t: number, b: number) =>
        placed.find((p) => l < p.r + 4 && r > p.l - 4 && t < p.b + 4 && b > p.t - 4)
        ?? obstacles.find((o) => l < o.right + 2 && r > o.left - 2 && t < o.bottom + 2 && b > o.top - 2);
      for (const { n, r } of items) {
        let dx = 0;
        if (r.width < rightLimit - box.left - 8) {
          if (r.left < box.left + 4) dx = box.left + 4 - r.left;
          else if (r.right > rightLimit) dx = rightLimit - r.right;
        }
        const l = r.left + dx, rr = r.right + dx;
        let lift = 0, down = 0;
        for (let guard = 0; guard < 12; guard++) {
          const t = r.top - lift, b = r.bottom - lift;
          const hit = clash(l, rr, t, b);
          if (!hit) break;
          const hb = "bottom" in hit ? hit.bottom : hit.b, ht = "top" in hit ? hit.top : hit.t;
          if (t - (b - ht + 6) < topLimit) { down = Math.max(0, hb + 6 - r.top); lift = 0; break; }   // no room above: slide down
          lift += b - ht + 6;
        }
        if (r.top - lift < topLimit && !down) { down = topLimit - r.top; lift = 0; }
        if (down) {                                   // a slid-down label must also land on a free spot
          for (let guard = 0; guard < 12; guard++) {
            const hit = clash(l, rr, r.top + down, r.bottom + down);
            if (!hit) break;
            down = ("bottom" in hit ? hit.bottom : hit.b) + 6 - r.top;
          }
        }
        const t = r.top - lift + down;
        if (n.spec.id !== selected && clash(l, rr, t, t + r.height)) {
          n.holder.style.visibility = "hidden";       // no free spot (close-up views): still listed in Buildings
          continue;
        }
        placed.push({ l, r: rr, t, b: t + r.height });
        n.leader.style.height = down ? "0px" : `${16 + Math.round(lift)}px`;
        if (dx || down) n.label.style.transform = `translate(${Math.round(dx)}px, ${Math.round(down)}px)`;
      }
    };

    let drawInfo = { calls: 0, tris: 0 };
    renderer.info.autoReset = false;
    const render = () => {
      renderer.info.reset();
      if (composer) composer.render(); else renderer.render(scene, camera);
      drawInfo = { calls: renderer.info.render.calls, tris: renderer.info.render.triangles };
      labels.render(scene, camera);
      declutter();
    };

    const resize = () => {
      const w = el.clientWidth, h = el.clientHeight;
      if (!w || !h) return;
      renderer.setSize(w, h);
      labels.setSize(w, h);
      composer?.setSize(w, h);
      bloom?.setSize(w, h);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      if (!userMoved && nodes.size) goHome(true);
      needs = true;
    };
    const ro = new ResizeObserver(resize);
    ro.observe(el);
    resize();

    // ---------------------------------------------------------------- 2: state mapping (no rebuilds)
    const accentFor = (spec: TowerSpec, isSel: boolean, isHover: boolean) =>
      (spec.dim ? 0.42 : 1.15) + (isSel ? 0.5 : isHover ? 0.25 : 0);
    const restyle = (n: Node) => {
      const isSel = n.spec.id === selected, isHover = n.spec.id === hovered;
      n.accent.emissive.setHex(n.spec.color);
      const breath = n.spec.active ? (motion.current ? 0.35 : 0.2 + 0.25 * (0.5 + 0.5 * Math.sin(performance.now() / 650))) : 0;
      n.accent.emissiveIntensity = accentFor(n.spec, isSel, isHover) + breath + n.pulse * 1.6;
      n.warnRing.visible = !!n.spec.warn;
      (n.warnRing.material as THREE.MeshBasicMaterial).color.setHex(n.spec.color);
      const hm = n.halo.material as THREE.MeshBasicMaterial;
      hm.color.setHex(n.spec.color);
      hm.opacity = isSel ? 0.9 : isHover ? 0.5 : n.spec.related ? 0.55 : n.spec.dim ? 0.12 : 0.22;
      n.halo.visible = true;
      n.label.classList.toggle("selected", isSel);
      n.label.classList.toggle("hover", isHover);
      n.label.setAttribute("aria-pressed", String(isSel));
    };
    const fillLabel = (n: Node) => {
      const d = derived(n.spec);
      n.label.replaceChildren();
      n.holder.style.setProperty("--accent", hex(n.spec.color));
      const tag = document.createElement("span"); tag.className = "cl-tag"; tag.textContent = d.category;
      const title = document.createElement("span"); title.className = "cl-title"; title.textContent = d.title;
      const status = document.createElement("span"); status.className = "cl-status"; status.textContent = (n.spec.warn ? "⚠ " : "") + d.status;
      const lm = n.spec.labelMode ?? "full";
      n.holder.classList.toggle("lm-hidden", lm === "hidden");     // a class: the 2D renderer rewrites inline display
      if (d.category && lm === "full") n.label.appendChild(tag);
      n.label.appendChild(title);
      if (d.status) n.label.appendChild(status);
      n.label.setAttribute("aria-label", n.spec.ariaLabel);
      n.label.classList.toggle("dim", !!n.spec.dim);
      n.label.classList.toggle("warn", !!n.spec.warn);
      n.label.classList.toggle("active", !!n.spec.active);
      n.label.classList.toggle("related", !!n.spec.related);
    };

    let seedCounter = 1;
    const create = (spec: TowerSpec, index: number): Node => {
      const arch = spec.archetype ?? ARCHETYPES[index % ARCHETYPES.length];
      const accent = new THREE.MeshStandardMaterial({ color: 0x0a0e18, emissive: spec.color, emissiveIntensity: 1, roughness: 0.4 });
      const built = buildArchetype(arch, kit, accent, seedCounter++ * 1.7);
      built.group.userData.id = spec.id;
      built.group.scale.setScalar(HERO);       // selectable buildings stand above the scenery
      for (const h of built.hit) h.userData.id = spec.id;
      const halo = new THREE.Mesh(new THREE.RingGeometry(built.footprint, built.footprint + 0.7, 64),
        new THREE.MeshBasicMaterial({ color: spec.color, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false }));
      halo.rotation.x = -Math.PI / 2;
      halo.position.y = 0.1;
      halo.visible = false;
      built.group.add(halo);
      const warnRing = new THREE.Mesh(new THREE.RingGeometry(built.footprint + 1.0, built.footprint + 1.9, 64),
        new THREE.MeshBasicMaterial({ color: spec.color, transparent: true, opacity: 0.85, depthWrite: false }));
      warnRing.rotation.x = -Math.PI / 2;
      warnRing.position.y = 0.11;
      warnRing.visible = false;
      built.group.add(warnRing);
      const holder = document.createElement("div");
      holder.className = "city-label-holder";
      const label = document.createElement("button");
      label.type = "button";
      label.className = "city-label";
      label.addEventListener("pointerdown", (e) => e.stopPropagation());
      label.addEventListener("click", (e) => { e.stopPropagation(); selectRef.current(spec.id); });
      label.addEventListener("pointerenter", () => setHover(spec.id));
      label.addEventListener("pointerleave", () => setHover(null));
      const leader = document.createElement("div");
      leader.className = "city-leader";
      holder.append(label, leader);
      const obj = new CSS2DObject(holder);
      obj.center.set(0.5, 1);
      obj.position.set(0, built.height + 0.6, 0);
      built.group.add(obj);
      scene.add(built.group);
      const key = spec.event?.id ?? spec.pulseKey;
      seen.add(`${spec.id}|${key}`);            // what is current at creation is history: never replayed
      return { spec, arch, built, accent, halo, holder, label, leader, pulse: 0, lastKey: key, warnRing };
    };
    const destroy = (n: Node) => {
      n.holder.remove();
      scene.remove(n.built.group);
      n.built.dispose();
      n.accent.dispose();
      n.halo.geometry.dispose();
      (n.halo.material as THREE.Material).dispose();
      n.warnRing.geometry.dispose();
      (n.warnRing.material as THREE.Material).dispose();
    };

    let extEdges: EdgeSpec[] | null = null;
    const rebuildLinks = () => {
      const key = extEdges ? "E:" + extEdges.map((e) => `${e.from}>${e.to}:${e.style}:${e.color ?? ""}`).join(";") + [...nodes.values()].map((n) => n.built.group.position.x.toFixed(1)).join(",")
        : [...nodes.values()].map((n) => `${n.spec.id}>${(n.spec.links ?? []).join("|")}@${n.built.group.position.x.toFixed(1)}`).join(";");
      if (key === linkKey) return;
      linkKey = key;
      linkGroup.children.forEach((c) => { (c as THREE.Line).geometry.dispose(); ((c as THREE.Line).material as THREE.Material).dispose(); });
      linkGroup.clear();
      if (extEdges) {
        for (const e of extEdges) {
          const m = nodes.get(e.from), n = nodes.get(e.to);
          if (!m || !n) continue;
          const a = m.built.group.position.clone().setY(1.4), b = n.built.group.position.clone().setY(1.4);
          const mid = a.clone().add(b).multiplyScalar(0.5).setY(4 + a.distanceTo(b) * 0.14);
          const curve = new THREE.QuadraticBezierCurve3(a, mid, b);
          let obj: THREE.Object3D;
          if (e.style === "recorded") {
            obj = new THREE.Mesh(new THREE.TubeGeometry(curve, 48, 0.16, 6, false),
              new THREE.MeshBasicMaterial({ color: e.color ?? 0x22d3ee, transparent: true, opacity: 0.85 }));
          } else {
            const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(curve.getPoints(60)),
              new THREE.LineDashedMaterial({ color: e.color ?? (e.style === "declared" ? 0xa5b4cf : 0x64748b), transparent: true,
                opacity: e.style === "declared" ? 0.85 : 0.55, dashSize: e.style === "declared" ? 1.1 : 0.25, gapSize: e.style === "declared" ? 0.7 : 0.7 }));
            line.computeLineDistances();
            obj = line;
          }
          obj.userData = { from: e.from, to: e.to, curve };
          linkGroup.add(obj);
        }
        return;
      }
      for (const n of nodes.values()) {
        for (const dep of n.spec.links ?? []) {
          const m = nodes.get(dep);
          if (!m) continue;
          const a = m.built.group.position.clone().setY(1.2), b = n.built.group.position.clone().setY(1.2);
          const mid = a.clone().add(b).multiplyScalar(0.5).setY(4 + a.distanceTo(b) * 0.12);
          const curve = new THREE.QuadraticBezierCurve3(a, mid, b);
          const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(curve.getPoints(40)),
            new THREE.LineBasicMaterial({ color: n.spec.color, transparent: true, opacity: 0.32 }));
          line.userData = { from: dep, to: n.spec.id, curve };
          linkGroup.add(line);
        }
      }
    };

    const firePulse = (id: string, dir: "out" | "in" | "both" = "both") => {
      if (motion.current) return;
      for (const c of linkGroup.children) {
        const u = c.userData as { from: string; to: string; curve: THREE.QuadraticBezierCurve3 };
        if (!((dir !== "in" && u.from === id) || (dir !== "out" && u.to === id))) continue;
        const color = nodes.get(u.to)?.spec.color ?? 0xffffff;
        const mesh = new THREE.Mesh(pulseGeo, new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.95 }));
        scene.add(mesh);
        pulses.push({ mesh, curve: u.curve, t: 0 });
      }
    };

    const ring = (n: Node, color: number, dur: number) => {
      if (motion.current) return;
      const mesh = new THREE.Mesh(ringGeo, new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.9,
        blending: THREE.AdditiveBlending, depthWrite: false }));
      mesh.rotation.x = -Math.PI / 2;
      mesh.position.copy(n.built.group.position).setY(0.16);
      scene.add(mesh);
      rings.push({ mesh, t: 0, dur, r0: n.built.footprint * HERO });
    };
    // Effects for recorded events only. Each plays once per event id; motion-free users get the
    // same information from the label and the steady state.
    const playEvent = (n: Node, kind: string) => {
      if (motion.current) return;
      if (kind === "arrival") { n.pulse = 0.8; ring(n, n.spec.color, 1.1); firePulse(n.spec.id, "out"); }
      else if (kind === "start") { n.pulse = 0.6; firePulse(n.spec.id, "in"); }          // handoff from real dependencies
      else if (kind === "complete") { n.pulse = 1; ring(n, n.spec.color, 1.4); }
      else if (kind === "fail") { n.pulse = 0.5; ring(n, n.spec.color, 1.8); }
      else { n.pulse = 1; firePulse(n.spec.id); }                                          // legacy pulseKey change
    };

    const sync = (list: TowerSpec[], sel: string | null, core: number | null) => {
      const ids = new Set(list.map((t) => t.id));
      for (const [id, n] of nodes) if (!ids.has(id)) { destroy(n); nodes.delete(id); }
      const before = nodes.size;
      list.forEach((spec, i) => {
        let n = nodes.get(spec.id);
        const arch = spec.archetype ?? ARCHETYPES[i % ARCHETYPES.length];
        if (n && n.arch !== arch) { destroy(n); nodes.delete(spec.id); n = undefined; }
        if (!n) { n = create(spec, i); nodes.set(spec.id, n); }
        const p = slotFor(i, list.length, spec);
        n.built.group.position.copy(p);
        n.built.group.rotation.y = spec.slot ? 0 : Math.atan2(-p.x, 24 - p.z) * 0.5;   // turn gently toward the camera
        const key = spec.event?.id ?? spec.pulseKey;
        n.spec = spec;
        if (key !== n.lastKey) {
          n.lastKey = key;
          const tag = `${spec.id}|${key}`;
          if (!seen.has(tag)) { seen.add(tag); playEvent(n, spec.event?.kind ?? "pulse"); }
        }
        fillLabel(n);
      });
      selected = sel;
      for (const n of nodes.values()) restyle(n);
      const coreIsBuilding = list.some((t) => t.slot && Math.hypot(t.slot[0], t.slot[1]) < PLAZA_R);
      coreRing.visible = core !== null && !coreIsBuilding;
      if (core !== null) coreMat.color.setHex(core);
      rebuildLinks();
      if (nodes.size !== before) goHome(before === 0);
      needs = true;
    };
    const setHover = (id: string | null) => {
      if (hovered === id) return;
      hovered = id;
      for (const n of nodes.values()) restyle(n);
      el.style.cursor = id ? "pointer" : "";
      needs = true;
    };

    // Picking (hover + click) on the label layer, which also receives the orbit gestures.
    const raycaster = new THREE.Raycaster();
    const ndc = new THREE.Vector2();
    const pickAt = (e: PointerEvent | MouseEvent): string | null => {
      const r = renderer.domElement.getBoundingClientRect();
      ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
      raycaster.setFromCamera(ndc, camera);
      const targets = [...nodes.values()].flatMap((n) => n.built.hit);
      const hit = raycaster.intersectObjects(targets, false)[0];
      return (hit?.object.userData.id as string) ?? null;
    };
    let downAt: { x: number; y: number } | null = null;
    let moveQueued = false, lastMove: PointerEvent | null = null;
    const onDown = (e: PointerEvent) => { downAt = { x: e.clientX, y: e.clientY }; };
    const onUp = (e: PointerEvent) => {
      if (downAt && Math.hypot(e.clientX - downAt.x, e.clientY - downAt.y) < 5) {
        const id = pickAt(e);
        if (id) selectRef.current(id);
      }
      downAt = null;
    };
    const onMove = (e: PointerEvent) => {
      lastMove = e;
      if (moveQueued || e.buttons) return;
      moveQueued = true;
      requestAnimationFrame(() => { moveQueued = false; if (lastMove) setHover(pickAt(lastMove)); });
    };
    const ld = labels.domElement;
    ld.addEventListener("pointerdown", onDown);
    ld.addEventListener("pointerup", onUp);
    ld.addEventListener("pointermove", onMove);
    ld.addEventListener("pointerleave", () => setHover(null));
    controls.addEventListener("start", () => { userMoved = true; tween = null; });
    controls.addEventListener("change", () => {
      // pan bounds: keep the target inside the district
      const t = controls.target;
      const r = Math.hypot(t.x, t.z);
      if (r > 45) { t.x *= 45 / r; t.z *= 45 / r; }
      t.y = Math.min(24, Math.max(1, t.y));
      needs = true;
    });

    // Frame loop: renders on demand; continuous only while something real animates, or for the
    // decorative aviation lights when quality is High and reduced motion is off.
    let frame = 0, last = performance.now(), frames = 0, statT = performance.now(), lastAmbient = 0;
    const loop = (now: number) => {
      frame = requestAnimationFrame(loop);
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      let animating = false;
      if (tween) {
        tween.t = Math.min(1, tween.t + dt / 0.75);
        const k = tween.t < 0.5 ? 4 * tween.t ** 3 : 1 - (-2 * tween.t + 2) ** 3 / 2;
        camera.position.lerpVectors(tween.fromP, tween.toP, k);
        controls.target.lerpVectors(tween.fromT, tween.toT, k);
        if (tween.t >= 1) tween = null;
        animating = true;
      }
      if (controls.update()) animating = true;
      for (const n of nodes.values()) {
        if (n.pulse > 0) { n.pulse = Math.max(0, n.pulse - dt / 1.2); restyle(n); animating = true; }
      }
      for (let i = rings.length - 1; i >= 0; i--) {
        const rg = rings[i];
        rg.t += dt / rg.dur;
        if (rg.t >= 1) { scene.remove(rg.mesh); (rg.mesh.material as THREE.Material).dispose(); rings.splice(i, 1); continue; }
        rg.mesh.scale.setScalar(rg.r0 * (1 + rg.t * 1.4));
        (rg.mesh.material as THREE.MeshBasicMaterial).opacity = 0.9 * (1 - rg.t);
        animating = true;
      }
      if (!motion.current) for (const n of nodes.values()) if (n.spec.active) { restyle(n); animating = true; }
      for (let i = pulses.length - 1; i >= 0; i--) {
        const p = pulses[i];
        p.t += dt / 1.4;
        if (p.t >= 1) { scene.remove(p.mesh); (p.mesh.material as THREE.Material).dispose(); pulses.splice(i, 1); continue; }
        p.mesh.position.copy(p.curve.getPoint(p.t));
        animating = true;
      }
      // Decorative layer at most ~30 frames/s (Medium/High); real event effects render every frame.
      let ambientDue = false;
      if (now - lastAmbient > 33) {
        const adt = Math.min(0.1, (now - lastAmbient) / 1000);
        const moving = !motion.current && quality !== "low";
        if (moving) kit.aviation.opacity = 0.35 + 0.6 * (0.5 + 0.5 * Math.sin(now / 900));   // slow, decorative, white
        ambientDue = ambient.update(adt, now, moving) || moving;
        lastAmbient = now;
      }
      if (animating || needs || ambientDue) { render(); needs = false; frames++; }
      if (now - statT > 2000) {
        setStats({ calls: drawInfo.calls, tris: drawInfo.tris, fps: Math.round(frames / ((now - statT) / 1000)) });
        statT = now;
        frames = 0;
      }
    };
    frame = requestAnimationFrame(loop);
    // Pause all rendering while the tab is hidden (backend monitoring is unaffected: it runs in
    // the worker process, and the page's own polling is separate from this loop).
    const onVisibility = () => {
      if (document.hidden) { cancelAnimationFrame(frame); frame = 0; }
      else if (!frame) { last = performance.now(); needs = true; frame = requestAnimationFrame(loop); }
    };
    document.addEventListener("visibilitychange", onVisibility);

    const setEdges = (e: EdgeSpec[] | null) => { extEdges = e; rebuildLinks(); needs = true; };
    api.current = { sync, focus, hover: setHover, setEdges };
    // Inspection hook for local verification (camera pose and frame stats); read-only use.
    (el as HTMLDivElement & { __city?: unknown }).__city = { camera, controls, nodes, renderer, sync, rings, pulses, seen };
    // reset view is exposed through a DOM event from the overlay button
    const onReset = () => goHome();
    el.addEventListener("city-reset", onReset);

    return () => {
      cancelAnimationFrame(frame);
      document.removeEventListener("visibilitychange", onVisibility);
      ro.disconnect();
      el.removeEventListener("city-reset", onReset);
      ld.removeEventListener("pointerdown", onDown);
      ld.removeEventListener("pointerup", onUp);
      ld.removeEventListener("pointermove", onMove);
      for (const n of nodes.values()) destroy(n);
      nodes.clear();
      linkGroup.children.forEach((c) => { (c as THREE.Line).geometry.dispose(); ((c as THREE.Line).material as THREE.Material).dispose(); });
      pulses.forEach((p) => (p.mesh.material as THREE.Material).dispose());
      pulseGeo.dispose();
      rings.forEach((rg) => (rg.mesh.material as THREE.Material).dispose());
      ringGeo.dispose();
      ambient.dispose();
      coreRing.geometry.dispose();
      coreMat.dispose();
      scenery.dispose();
      kit.dispose();
      composer?.dispose();
      controls.dispose();
      renderer.dispose();
      el.replaceChildren();
      api.current = null;
    };
  }, [onFailure, quality, variant]);

  // ------------------------------------------------------------------ 2: push records into the scene
  useEffect(() => { api.current?.sync(towers, selectedId, coreColor); }, [towers, selectedId, coreColor, quality]);
  useEffect(() => { api.current?.setEdges(props.edges ?? null); }, [props.edges, quality, towers]);
  const prevSel = useRef<string | null>(null);
  useEffect(() => {
    if (selectedId && selectedId !== prevSel.current) api.current?.focus(selectedId);
    prevSel.current = selectedId;
  }, [selectedId]);

  const list = useMemo(() => towers.map((t) => ({ t, d: derived(t) })), [towers]);
  const archetypes = useMemo(() => [...new Set(towers.map((t, i) => t.archetype ?? ARCHETYPES[i % ARCHETYPES.length]))], [towers]);

  return (
    <div className={`city-wrap city-${variant}`}>
      <div className="city" ref={host} />
      <div className={`city-mode tone-${mode.tone}`} role="status">
        <strong>{mode.label}</strong>{mode.detail ? <span> · {mode.detail}</span> : null}
      </div>
      <div className="city-tools" role="group" aria-label="3D view controls">
        <button type="button" onClick={() => host.current?.dispatchEvent(new Event("city-reset"))}>Reset view</button>
        <label>Effects{" "}
          <select value={quality} onChange={(e) => {
            const q = e.target.value as Quality;
            try { localStorage.setItem("city-quality", q); } catch { /* storage unavailable: keep in memory */ }
            setQuality(q);
          }}>
            <option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option>
          </select>
        </label>
        <button type="button" aria-expanded={showList} onClick={() => setShowList((s) => !s)}>Buildings</button>
        <button type="button" aria-expanded={showLegend} onClick={() => setShowLegend((s) => !s)}>Legend</button>
      </div>
      <nav className={`city-list${showList ? "" : " collapsed"}`} aria-label="Buildings in this view">
        {list.map(({ t, d }) => (
          <button key={t.id} type="button" aria-pressed={t.id === selectedId} className={t.id === selectedId ? "on" : ""}
                  onClick={() => onSelect(t.id)} onMouseEnter={() => api.current?.hover(t.id)} onMouseLeave={() => api.current?.hover(null)}
                  onFocus={() => api.current?.hover(t.id)} onBlur={() => api.current?.hover(null)}>
            <span className="dot" style={{ background: hex(t.color) }} aria-hidden="true" />
            <span className="nm">{d.title}</span><span className="st">{d.status}</span>
          </button>
        ))}
      </nav>
      {showLegend && (
        <div className="city-legend" aria-label="Legend">
          <div className="lg-h">Status colours (from records)</div>
          {legend.map((l) => <div key={l.label}><span className="dot" style={{ background: hex(l.color) }} />{l.label}</div>)}
          {props.coreLabel && <div><span className="dot ring" />Plaza ring: {props.coreLabel}</div>}
          <div className="lg-h">Architecture (decorative)</div>
          <div className="small">{archetypes.map((a) => ARCHETYPE_LABEL[a]).join(" · ")}. Shape groups components; it carries no status.</div>
          <div className="lg-h">Real events (from records)</div>
          <div className="small">Expanding ring at a building: a recorded event (new market data, a job completing or failing). Dot travelling along a line: a handoff along a real dependency. Gently brightening accent: work in progress. Steady outer ring and ⚠: failure or stale data (stays until the record changes). Each event plays once.</div>
          <div className="lg-h">Decorative (no data)</div>
          <div className="small">Traffic, street and path lights, entrance light pools, fountain, signage, district clock, window-light changes, light sweeps on distant towers, white rooftop lights and unlabelled towers. They are not agents and do not indicate market activity or work.</div>
          {reducedMotion && <div className="small">Reduced motion: traffic, sweeps, pulses and camera moves are off; status is unchanged.</div>}
        </div>
      )}
      {stats && <div className="city-stats" aria-hidden="true">{stats.calls} draw calls · {Math.round(stats.tris / 1000)}k triangles · {stats.fps} rendered frames/s · effects {quality}</div>}
    </div>
  );
}
