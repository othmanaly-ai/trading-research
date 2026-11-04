import { useEffect, useRef } from "react";
import * as THREE from "three";
import { CSS2DObject, CSS2DRenderer } from "three/addons/renderers/CSS2DRenderer.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

// One 3D scene, two uses: DEMO strategy towers (boxes, purple) and REAL research-job towers
// (cylinders, teal). Every tower is driven by a TowerSpec built from records; the label always
// spells the status out, so color is never the only signal.

export interface TowerSpec {
  id: string;
  color: number;
  lines: { cls: string; text: string }[];
  ariaLabel: string;
  pulseKey: string;            // pulses when this changes (a real event: a fill, a job state change)
}

const VARIANTS = {
  strategy: { clear: 0x0b0820, grid: [0x7c3aed, 0x312e81], shape: "box" as const, labelClass: "tower-label" },
  jobs: { clear: 0x041a1f, grid: [0x0e7490, 0x134e4a], shape: "cylinder" as const, labelClass: "tower-label job-label" },
};

const PER_ROW = 6;
const SPACING = 9.5;

interface Tower {
  mesh: THREE.Mesh;
  material: THREE.MeshStandardMaterial;
  edges: THREE.LineBasicMaterial;
  label: HTMLButtonElement;
  pulse: number;
  lastKey: string;
}

interface Props {
  towers: TowerSpec[];
  coreColor: number | null;
  selectedId: string | null;
  onSelect: (id: string) => void;
  reducedMotion: boolean;
  onFailure: (reason: string) => void;
  variant?: keyof typeof VARIANTS;
}

function fillLabel(el: HTMLButtonElement, spec: TowerSpec, selected: boolean, labelClass: string) {
  el.replaceChildren();
  for (const l of spec.lines) {
    const d = document.createElement("div");
    d.className = l.cls;
    d.textContent = l.text;
    el.appendChild(d);
  }
  el.className = `${labelClass}${selected ? " selected" : ""}`;
  el.setAttribute("aria-pressed", String(selected));
  el.setAttribute("aria-label", spec.ariaLabel);
}

export default function CityView({ towers, coreColor, selectedId, onSelect, reducedMotion, onFailure,
  variant = "strategy" }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const world = useRef<{
    scene: THREE.Scene; renderer: THREE.WebGLRenderer; core: THREE.MeshStandardMaterial;
    towers: Map<string, Tower>; render: () => void;
  } | null>(null);
  const motion = useRef(reducedMotion);
  const selectRef = useRef(onSelect);
  selectRef.current = onSelect;
  motion.current = reducedMotion;
  const v = VARIANTS[variant];

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
    renderer.setClearColor(v.clear);
    renderer.domElement.setAttribute("aria-hidden", "true");
    el.appendChild(renderer.domElement);

    const labels = new CSS2DRenderer();
    labels.domElement.className = "label-layer";
    el.appendChild(labels.domElement);

    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(v.clear, 30, 90);
    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 200);
    camera.position.set(0, 14, 30);
    scene.add(new THREE.AmbientLight(0x6d5bd0, 0.6));
    const key = new THREE.PointLight(0x8b5cf6, 400, 80);
    key.position.set(0, 20, 10);
    scene.add(key);
    scene.add(new THREE.GridHelper(90, 45, v.grid[0], v.grid[1]));

    const core = new THREE.MeshStandardMaterial({ color: 0x1e1b4b, emissive: 0x4f46e5, emissiveIntensity: 0.6 });
    const coreMesh = new THREE.Mesh(new THREE.CylinderGeometry(2.2, 2.6, 0.8, 32), core);
    coreMesh.position.set(0, 0.4, 4);
    scene.add(coreMesh);

    const controls = new OrbitControls(camera, labels.domElement);
    controls.target.set(0, 3, -6);
    controls.update();
    controls.maxPolarAngle = Math.PI / 2.2;
    controls.minDistance = 10;
    controls.maxDistance = 60;

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
    const map = new Map<string, Tower>();
    world.current = { scene, renderer, core, towers: map, render };
    resize();

    const raycaster = new THREE.Raycaster();
    const onClick = (e: MouseEvent) => {
      const r = renderer.domElement.getBoundingClientRect();
      const p = new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
      raycaster.setFromCamera(p, camera);
      const hit = raycaster.intersectObjects([...map.values()].map((t) => t.mesh))[0];
      const id = hit && (hit.object.userData.id as string);
      if (id) selectRef.current(id);
    };
    labels.domElement.addEventListener("click", onClick);

    let frame = 0;
    const loop = () => {
      frame = requestAnimationFrame(loop);
      if (motion.current) return;
      let active = false;
      for (const t of map.values()) {
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
  }, [onFailure, v]);

  useEffect(() => {
    const w = world.current;
    if (!w) return;
    const n = towers.length;
    const ids = new Set(towers.map((t) => t.id));
    for (const [id, t] of w.towers) {
      if (!ids.has(id)) {
        // Removing the mesh does not remove its CSS2D label element; do it explicitly, or stale
        // labels from a previous record set would stay on screen.
        t.label.remove();
        w.scene.remove(t.mesh);
        t.mesh.geometry.dispose();
        t.material.dispose();
        w.towers.delete(id);
      }
    }
    towers.forEach((spec, i) => {
      let t = w.towers.get(spec.id);
      const row = Math.floor(i / PER_ROW), col = i % PER_ROW;
      const inRow = Math.min(PER_ROW, n - row * PER_ROW);
      if (!t) {
        const material = new THREE.MeshStandardMaterial({ color: 0x0f0b2e, emissive: spec.color, emissiveIntensity: 0.25 });
        const geometry = v.shape === "box" ? new THREE.BoxGeometry(2, 6, 2) : new THREE.CylinderGeometry(1.2, 1.2, 6, 20);
        const mesh = new THREE.Mesh(geometry, material);
        const edges = new THREE.LineBasicMaterial({ color: spec.color });
        mesh.add(new THREE.LineSegments(new THREE.EdgesGeometry(geometry, 30), edges));
        mesh.userData.id = spec.id;
        const label = document.createElement("button");
        label.type = "button";
        // OrbitControls captures the pointer on pointerdown, which would swallow the click.
        label.addEventListener("pointerdown", (e) => e.stopPropagation());
        label.addEventListener("click", (e) => { e.stopPropagation(); selectRef.current(spec.id); });
        const obj = new CSS2DObject(label);
        obj.position.set(0, 3.4, 0);
        obj.center.set(0.5, 1);
        mesh.add(obj);
        w.scene.add(mesh);
        t = { mesh, material, edges, label, pulse: 0, lastKey: spec.pulseKey };
        w.towers.set(spec.id, t);
      }
      t.mesh.position.set((col - (inRow - 1) / 2) * SPACING, 3, -6 - row * SPACING);
      if (spec.pulseKey !== t.lastKey) {
        if (!motion.current) t.pulse = 1;          // driven by a real recorded change
        t.lastKey = spec.pulseKey;
      }
      t.material.emissive.setHex(spec.color);
      t.edges.color.setHex(spec.color);
      if (motion.current || t.pulse === 0) {
        t.mesh.scale.set(1, 1, 1);
        t.material.emissiveIntensity = spec.id === selectedId ? 0.6 : 0.25;
      }
      fillLabel(t.label, spec, spec.id === selectedId, v.labelClass);
    });
    if (coreColor !== null) w.core.emissive.setHex(coreColor);
    w.render();
  }, [towers, selectedId, coreColor, v]);

  return <div className={`city city-${variant}`} ref={host} />;
}
