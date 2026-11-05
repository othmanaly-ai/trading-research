import * as THREE from "three";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
import { PALETTE } from "./palette";
import { groundTexture, pavingTexture } from "./textures";
import { worldUV, type Kit } from "./architecture";

// Static district: built once per mount and never touched by status updates. Decorative
// buildings are instanced, dimmer, unlabeled and not pickable, so they never look operational.

export const PLAZA_R = 9;
export const RING_IN = 11, RING_OUT = 14.5;

function rng(seed: number) {
  let s = seed >>> 0;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
}

function skyDome(): THREE.Mesh {
  const c = document.createElement("canvas");
  c.width = 4; c.height = 256;
  const g = c.getContext("2d")!;
  const grad = g.createLinearGradient(0, 0, 0, 256);
  grad.addColorStop(0, "#03050c");
  grad.addColorStop(0.55, "#0a1022");
  grad.addColorStop(0.78, "#182444");      // faint city glow at the horizon: strengthens the skyline silhouette
  grad.addColorStop(1, "#0b1020");
  g.fillStyle = grad;
  g.fillRect(0, 0, 4, 256);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  const mat = new THREE.MeshBasicMaterial({ map: tex, side: THREE.BackSide, fog: false, depthWrite: false });
  const dome = new THREE.Mesh(new THREE.SphereGeometry(230, 32, 16, 0, Math.PI * 2, 0, Math.PI / 1.9), mat);
  dome.renderOrder = -1;
  return dome;
}

export interface Scenery { group: THREE.Group; landmarks: { x: number; z: number; w: number; h: number }[]; dispose: () => void; }

export function buildScenery(kit: Kit, quality: "high" | "low", keepClear: (x: number, z: number) => boolean): Scenery {
  const group = new THREE.Group();
  const geos: THREE.BufferGeometry[] = [];
  const mats: THREE.Material[] = [];
  const texs: THREE.Texture[] = [];
  const add = <T extends THREE.Object3D>(o: T) => { group.add(o); return o; };
  const geo = <G extends THREE.BufferGeometry>(g: G) => { geos.push(g); return g; };
  const mat = <M extends THREE.Material>(m: M) => { mats.push(m); return m; };

  add(skyDome());

  // Ground: glossy dark asphalt (specular sheen from the lights gives an inexpensive wet look).
  const gt = groundTexture(); texs.push(gt);
  const ground = add(new THREE.Mesh(geo(new THREE.CircleGeometry(200, 64)),
    mat(new THREE.MeshStandardMaterial({ map: gt, color: 0xa7b3cc, roughness: 0.5, metalness: 0.15 }))));
  ground.rotation.x = -Math.PI / 2;

  const flat = (g: THREE.BufferGeometry, color: number, y: number, rough = 0.7, map?: THREE.Texture) => {
    const m = add(new THREE.Mesh(geo(g), mat(new THREE.MeshStandardMaterial({ color, roughness: rough, metalness: 0.1, map: map ?? null }))));
    m.rotation.x = -Math.PI / 2;
    m.position.y = y;
    return m;
  };
  // Ring road, sidewalks, plaza with paving, four avenues.
  flat(new THREE.RingGeometry(RING_IN, RING_OUT, 96), PALETTE.asphalt, 0.02, 0.4);
  flat(new THREE.RingGeometry(RING_OUT, RING_OUT + 1.4, 96), PALETTE.sidewalk, 0.05);
  flat(new THREE.RingGeometry(PLAZA_R, RING_IN, 96), PALETTE.sidewalk, 0.05);
  const pv = pavingTexture(); texs.push(pv);
  flat(new THREE.CircleGeometry(PLAZA_R, 64), 0xffffff, 0.06, 0.6, pv);
  for (let i = 0; i < 4; i++) {
    const a = (i / 4) * Math.PI * 2 + Math.PI / 4;
    const road = flat(new THREE.PlaneGeometry(4, 90), PALETTE.asphalt, 0.021, 0.4);
    road.rotation.z = a;
    road.position.set(Math.cos(a) * 60, 0.021, Math.sin(a) * 60);
    road.rotation.set(-Math.PI / 2, 0, -a + Math.PI / 2);
  }
  // Lane marking on the ring (dashed, dim).
  const lanePts = Array.from({ length: 129 }, (_, i) => {
    const a = (i / 128) * Math.PI * 2;
    return new THREE.Vector3(Math.cos(a) * (RING_IN + RING_OUT) / 2, 0.04, Math.sin(a) * (RING_IN + RING_OUT) / 2);
  });
  const lane = add(new THREE.Line(geo(new THREE.BufferGeometry().setFromPoints(lanePts)),
    mat(new THREE.LineDashedMaterial({ color: 0x5b6478, dashSize: 0.8, gapSize: 1.2, transparent: true, opacity: 0.6 }))));
  lane.computeLineDistances();

  // Landscaped groves (instanced crowns and trunks) at the plaza diagonals and along avenues.
  const r = rng(91);
  const treeSpots: THREE.Vector3[] = [];
  for (let k = 0; k < 4; k++) {
    const a = (k / 4) * Math.PI * 2;
    for (let j = 0; j < 5; j++) treeSpots.push(new THREE.Vector3(Math.cos(a + (j - 2) * 0.07) * 17.5, 0, Math.sin(a + (j - 2) * 0.07) * 17.5));
  }
  for (let j = 0; j < 8; j++) {
    const a = (j / 8) * Math.PI * 2 + 0.2;
    treeSpots.push(new THREE.Vector3(Math.cos(a) * (PLAZA_R - 1.2), 0, Math.sin(a) * (PLAZA_R - 1.2)));
  }
  const crowns = add(new THREE.InstancedMesh(geo(new THREE.SphereGeometry(0.9, 10, 8)),
    mat(new THREE.MeshStandardMaterial({ color: PALETTE.tree, roughness: 0.9 })), treeSpots.length));
  const trunks = add(new THREE.InstancedMesh(geo(new THREE.CylinderGeometry(0.1, 0.14, 1.2, 6)), kit.structure, treeSpots.length));
  const m4 = new THREE.Matrix4(), q = new THREE.Quaternion();
  treeSpots.forEach((p, i) => {
    const s = 0.8 + r() * 0.5;
    m4.compose(new THREE.Vector3(p.x, 1.2 + 0.7 * s, p.z), q, new THREE.Vector3(s, s * 1.15, s));
    crowns.setMatrixAt(i, m4);
    m4.compose(new THREE.Vector3(p.x, 0.6, p.z), q, new THREE.Vector3(1, 1, 1));
    trunks.setMatrixAt(i, m4);
  });

  // Street lamps around the ring (warm, low intensity: decorative, unrelated to any status).
  const lampN = quality === "high" ? 32 : 16;
  const poles = add(new THREE.InstancedMesh(geo(new THREE.CylinderGeometry(0.05, 0.07, 2.6, 6)), kit.structure, lampN));
  const heads = add(new THREE.InstancedMesh(geo(new THREE.SphereGeometry(0.16, 8, 6)),
    mat(new THREE.MeshBasicMaterial({ color: 0xffcf8a })), lampN));
  for (let i = 0; i < lampN; i++) {
    const a = (i / lampN) * Math.PI * 2;
    const x = Math.cos(a) * (RING_OUT + 0.7), z = Math.sin(a) * (RING_OUT + 0.7);
    m4.compose(new THREE.Vector3(x, 1.3, z), q, new THREE.Vector3(1, 1, 1));
    poles.setMatrixAt(i, m4);
    m4.compose(new THREE.Vector3(x, 2.65, z), q, new THREE.Vector3(1, 1, 1));
    heads.setMatrixAt(i, m4);
  }

  // Decorative skyline: instanced presets (no scaling, so window bays keep their size).
  const presets: THREE.BufferGeometry[] = [
    [4, 11, 4], [6, 18, 6], [4.5, 25, 4.5], [5, 8, 7], [5, 32, 5], [4.5, 14, 3.5],
  ].map(([w, h, d], i) => geo(worldUV(new THREE.BoxGeometry(w, h, d), i * 3.1).translate(0, h / 2, 0)));
  const stepped = (w: number, h: number, i: number) => geo(mergeGeometries([
    worldUV(new THREE.BoxGeometry(w, h * 0.55, w), i).translate(0, h * 0.275, 0),
    worldUV(new THREE.BoxGeometry(w * 0.72, h * 0.3, w * 0.72), i + 1).translate(0, h * 0.55 + h * 0.15, 0),
    worldUV(new THREE.BoxGeometry(w * 0.45, h * 0.15, w * 0.45), i + 2).translate(0, h * 0.85 + h * 0.075, 0),
  ]));
  presets.push(stepped(7, 28, 5), stepped(6, 20, 9));
  const spots: { x: number; z: number; rot: number }[] = [];
  const target = quality === "high" ? 90 : 45;
  let tries = 0;
  while (spots.length < target && tries++ < 4000) {
    const far = spots.length > target * 0.55;
    const rad = far ? 80 + r() * 45 : 34 + r() * 46;
    const a = r() * Math.PI * 2;
    const x = Math.cos(a) * rad, z = Math.sin(a) * rad;
    if (!keepClear(x, z)) continue;
    if (Math.abs(Math.abs(Math.atan2(z, x)) % (Math.PI / 2) - Math.PI / 4) < 0.06 && rad < 95) continue;   // keep avenues open
    if (spots.some((s) => (s.x - x) ** 2 + (s.z - z) ** 2 < 81)) continue;
    spots.push({ x, z, rot: Math.floor(r() * 4) * (Math.PI / 2) + (r() - 0.5) * 0.3 });
  }
  // Hierarchy: scenery near the district stays lower than the selectable buildings (presets 0, 3, 5:
  // 9-15 units); the tall presets only form the distant skyline.
  const NEAR = [0, 3, 5], ALL = presets.map((_, i) => i);
  const buckets = presets.map(() => [] as typeof spots);
  spots.forEach((s, i) => {
    const pool = Math.hypot(s.x, s.z) < 80 ? NEAR : ALL;
    buckets[pool[(i * 7 + Math.floor(Math.abs(s.x))) % pool.length]].push(s);
  });
  // the tallest distant towers (decorative light sweeps run on these, never on selectable buildings)
  const DIMS: [number, number][] = [[4, 11], [6, 18], [4.5, 25], [5, 8], [5, 32], [4.5, 14], [7, 28], [6, 20]];
  const landmarks = buckets.flatMap((list, i) => list.map((s) => ({ x: s.x, z: s.z, w: DIMS[i][0], h: DIMS[i][1] })))
    .filter((l) => l.h >= 25 && Math.hypot(l.x, l.z) < 115 && l.z < 0).sort((a, b) => b.h - a.h).slice(0, 3);
  buckets.forEach((list, i) => {
    if (!list.length) return;
    const im = add(new THREE.InstancedMesh(presets[i], kit.facadeDim, list.length));
    list.forEach((s, j) => {
      m4.compose(new THREE.Vector3(s.x, 0, s.z), new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), s.rot), new THREE.Vector3(1, 1, 1));
      im.setMatrixAt(j, m4);
    });
  });
  // Unused presets are still tracked in geos for disposal.

  // Lighting: cool moonlight, navy sky fill, two warm plaza lights for ground sheen.
  add(new THREE.HemisphereLight(0x3a4f8c, 0x06080f, 1.6));
  const moon = add(new THREE.DirectionalLight(0xb4c4ff, 1.5));
  moon.position.set(-40, 70, 30);
  // Back rim light: separates silhouettes from the sky (no shadows, cheap).
  const rim = add(new THREE.DirectionalLight(0x5b7bd6, 0.75));
  rim.position.set(30, 40, -80);
  for (const [x, z] of [[-6, 6], [6, 6]]) {
    const p = add(new THREE.PointLight(0xffb36b, 90, 45, 2));
    p.position.set(x, 4, z);
  }

  return { group, landmarks, dispose: () => { geos.forEach((g) => g.dispose()); mats.forEach((m) => m.dispose()); texs.forEach((t) => t.dispose()); } };
}
