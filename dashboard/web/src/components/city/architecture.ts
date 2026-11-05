import * as THREE from "three";
import { PALETTE, type Archetype } from "./palette";
import { BAY_W, FLOOR_H, TEX_COLS, TEX_ROWS, facadeTexture, worldCylinderUV } from "./textures";

// Procedural skyscraper vocabulary. Geometry is decorative; only the accent material and the
// beacon carry operational meaning, and both are driven by CityView from application records.

export interface Kit {
  facade: THREE.MeshStandardMaterial;      // warm office windows (selectable buildings)
  facadeDim: THREE.MeshStandardMaterial;   // dimmer windows (scenery, paused buildings)
  glass: THREE.MeshStandardMaterial;       // curtain wall with sparse lights
  structure: THREE.MeshStandardMaterial;   // charcoal frames, fins, crowns
  podium: THREE.MeshStandardMaterial;
  roof: THREE.MeshStandardMaterial;
  entrance: THREE.MeshStandardMaterial;    // warm lobby glow (decorative)
  aviation: THREE.MeshBasicMaterial;       // white obstruction lights (decorative, never status)
  pool: THREE.MeshBasicMaterial;           // entrance light pools (decorative)
  column: THREE.CylinderGeometry;
  textures: THREE.Texture[];
  dispose: () => void;
}

export function makeKit(maxAniso: number): Kit {
  const t1 = facadeTexture(0.42, 11, maxAniso), t2 = facadeTexture(0.2, 23, maxAniso), t3 = facadeTexture(0.16, 37, maxAniso);
  const facade = new THREE.MeshStandardMaterial({ color: PALETTE.navy, roughness: 0.55, metalness: 0.35,
    emissive: PALETTE.window, emissiveMap: t1, emissiveIntensity: 1.0 });
  const facadeDim = new THREE.MeshStandardMaterial({ color: PALETTE.navy, roughness: 0.6, metalness: 0.3,
    emissive: PALETTE.window, emissiveMap: t2, emissiveIntensity: 0.55 });
  const glass = new THREE.MeshStandardMaterial({ color: PALETTE.glass, roughness: 0.18, metalness: 0.75,
    emissive: 0xffe2b8, emissiveMap: t3, emissiveIntensity: 0.85 });
  const structure = new THREE.MeshStandardMaterial({ color: 0x2a3142, roughness: 0.6, metalness: 0.45 });
  const podium = new THREE.MeshStandardMaterial({ color: 0x1f2738, roughness: 0.6, metalness: 0.3 });
  const roof = new THREE.MeshStandardMaterial({ color: 0x0f141f, roughness: 0.85, metalness: 0.2 });
  const entrance = new THREE.MeshStandardMaterial({ color: 0x1a1408, emissive: 0xffb866, emissiveIntensity: 0.7 });
  const aviation = new THREE.MeshBasicMaterial({ color: PALETTE.aviation, transparent: true, opacity: 0.9 });
  const poolCanvas = document.createElement("canvas");
  poolCanvas.width = poolCanvas.height = 64;
  const pg = poolCanvas.getContext("2d")!;
  const grad = pg.createRadialGradient(32, 32, 0, 32, 32, 32);
  grad.addColorStop(0, "rgba(255,190,110,0.9)");
  grad.addColorStop(0.45, "rgba(255,170,90,0.35)");
  grad.addColorStop(1, "rgba(255,160,80,0)");
  pg.fillStyle = grad;
  pg.fillRect(0, 0, 64, 64);
  const poolTex = new THREE.CanvasTexture(poolCanvas);
  poolTex.colorSpace = THREE.SRGBColorSpace;
  const pool = new THREE.MeshBasicMaterial({ map: poolTex, transparent: true, opacity: 0.45, blending: THREE.AdditiveBlending, depthWrite: false });
  const column = new THREE.CylinderGeometry(0.16, 0.16, 1, 8);
  const mats = [facade, facadeDim, glass, structure, podium, roof, entrance, aviation, pool];
  return { facade, facadeDim, glass, structure, podium, roof, entrance, aviation, pool, column, textures: [t1, t2, t3],
    dispose: () => { mats.forEach((m) => m.dispose()); [t1, t2, t3, poolTex].forEach((t) => t.dispose()); column.dispose(); } };
}

/** World-space UVs for any box-like geometry, computed from positions and normals (call before
 *  bending or twisting). Horizontal faces map to the dark texel so roofs show no windows. */
export function worldUV(geo: THREE.BufferGeometry, seed = 0): THREE.BufferGeometry {
  geo.computeBoundingBox();
  const minY = geo.boundingBox!.min.y;
  const pos = geo.attributes.position, nrm = geo.attributes.normal, uv = geo.attributes.uv as THREE.BufferAttribute;
  const ou = (seed * 0.37) % 1, ov = (seed * 0.61) % 1;
  const su = 1 / (TEX_COLS * BAY_W), sv = 1 / (TEX_ROWS * FLOOR_H);
  for (let i = 0; i < pos.count; i++) {
    const nx = nrm.getX(i), ny = nrm.getY(i), nz = nrm.getZ(i);
    if (Math.abs(ny) > 0.5) { uv.setXY(i, 0.5 / (TEX_COLS * 16), 0.5 / (TEX_ROWS * 16)); continue; }
    const u = Math.abs(nx) > Math.abs(nz) ? pos.getZ(i) * Math.sign(nx) : -pos.getX(i) * Math.sign(nz);
    uv.setXY(i, ou + u * su, ov + (pos.getY(i) - minY) * sv);
  }
  uv.needsUpdate = true;
  return geo;
}

export interface Built {
  group: THREE.Group;
  height: number;           // top of the architecture (label anchor)
  footprint: number;        // radius used for the halo ring and spacing
  beacon: THREE.Mesh;       // status beacon (accent material)
  aviation: THREE.Mesh[];   // decorative white lights
  hit: THREE.Object3D[];    // meshes used for picking
  dispose: () => void;
}

class Builder {
  group = new THREE.Group();
  geos: THREE.BufferGeometry[] = [];
  hit: THREE.Object3D[] = [];
  aviation: THREE.Mesh[] = [];
  constructor(public kit: Kit, public accent: THREE.MeshStandardMaterial, public seed: number) {}

  mesh(geo: THREE.BufferGeometry, mat: THREE.Material, x: number, y: number, z: number, pick = true): THREE.Mesh {
    this.geos.push(geo);
    const m = new THREE.Mesh(geo, mat);
    m.position.set(x, y, z);
    this.group.add(m);
    if (pick) this.hit.push(m);
    return m;
  }
  /** Box with its base at y0 (window UVs in world units). */
  block(w: number, h: number, d: number, mat: THREE.Material, x: number, y0: number, z: number, uvSeed = this.seed): THREE.Mesh {
    return this.mesh(worldUV(new THREE.BoxGeometry(w, h, d), uvSeed), mat, x, y0 + h / 2, z);
  }
  band(w: number, d: number, y: number, x = 0, z = 0, t = 0.16): THREE.Mesh {
    return this.mesh(new THREE.BoxGeometry(w, t, d), this.accent, x, y, z, false);
  }
  podium(w: number, d: number, h: number, columns: number) {
    this.block(w, h, d, this.kit.podium, 0, 0, 0);
    // warm light pool on the pavement in front of the entrance (decorative)
    const pool = this.mesh(new THREE.CircleGeometry(Math.min(3, w * 0.3), 24), this.kit.pool, 0, 0.09, d / 2 + 1.6, false);
    pool.rotation.x = -Math.PI / 2;
    // recessed lobby with a warm entrance and a canopy
    this.mesh(new THREE.BoxGeometry(Math.min(4, w * 0.4), h * 0.7, 0.3), this.kit.entrance, 0, h * 0.35, d / 2 + 0.05, false);
    this.mesh(new THREE.BoxGeometry(Math.min(5, w * 0.5), 0.15, 1.2), this.kit.structure, 0, h * 0.78, d / 2 + 0.6, false);
    const cols = new THREE.InstancedMesh(this.kit.column, this.kit.structure, columns * 2);
    const mtx = new THREE.Matrix4();
    for (let i = 0; i < columns; i++) {
      const x = -w / 2 + 0.5 + (i * (w - 1)) / Math.max(1, columns - 1);
      mtx.compose(new THREE.Vector3(x, h / 2, d / 2 + 0.35), new THREE.Quaternion(), new THREE.Vector3(1, h, 1));
      cols.setMatrixAt(i, mtx);
      mtx.compose(new THREE.Vector3(x, h / 2, -d / 2 - 0.35), new THREE.Quaternion(), new THREE.Vector3(1, h, 1));
      cols.setMatrixAt(columns + i, mtx);
    }
    this.group.add(cols);
  }
  equipment(w: number, d: number, y0: number, n: number) {
    for (let i = 0; i < n; i++) {
      const fx = ((i * 0.618 + this.seed * 0.13) % 1) - 0.5, fz = ((i * 0.382 + this.seed * 0.29) % 1) - 0.5;
      if (i % 3 === 0) this.mesh(new THREE.CylinderGeometry(0.45, 0.45, 0.7, 12), this.kit.structure, fx * w * 0.7, y0 + 0.35, fz * d * 0.7, false);
      else this.block(0.9 + (i % 2) * 0.6, 0.6 + (i % 2) * 0.4, 0.8, this.kit.roof, fx * w * 0.7, y0, fz * d * 0.7);
    }
  }
  antenna(x: number, y0: number, z: number, h: number) {
    this.mesh(new THREE.CylinderGeometry(0.06, 0.1, h, 6), this.kit.structure, x, y0 + h / 2, z, false);
    const light = this.mesh(new THREE.SphereGeometry(0.12, 8, 6), this.kit.aviation, x, y0 + h, z, false);
    this.aviation.push(light);
  }
  beacon(y: number, x = 0, z = 0): THREE.Mesh {
    return this.mesh(new THREE.OctahedronGeometry(0.42), this.accent, x, y, z, false);
  }
  done(height: number, footprint: number, beacon: THREE.Mesh): Built {
    const geos = this.geos;
    return { group: this.group, height, footprint, beacon, aviation: this.aviation, hit: this.hit,
      dispose: () => geos.forEach((g) => g.dispose()) };
  }
}

function terraced(b: Builder): Built {
  b.podium(10, 10, 2.2, 6);
  const tiers: [number, number][] = [[7.4, 9], [6, 7], [4.6, 5.5]];
  let y = 2.2;
  for (const [w, h] of tiers) {
    b.block(w, h, w, b.kit.facade, 0, y, 0);
    y += h;
    b.band(w + 0.35, w + 0.35, y + 0.08);                 // illuminated setback ledge
    b.block(w - 0.2, 0.25, w - 0.2, b.kit.roof, 0, y, 0);
  }
  b.block(3.2, 2.2, 3.2, b.kit.structure, 0, y, 0);       // crown
  b.band(3.5, 3.5, y + 1.6, 0, 0, 0.22);
  b.antenna(0, y + 2.2, 0, 4);
  return b.done(y + 2.2, 6, b.beacon(y + 2.8));
}

function finned(b: Builder): Built {
  b.podium(9, 9, 2, 5);
  const rb = 4.2, rt = 2.8, h = 21, y0 = 2;
  const geo = worldCylinderUV(new THREE.CylinderGeometry(rt, rb, h, 4, 1), (rb + rt) / 2, h, b.seed);
  const tower = b.mesh(geo, b.kit.glass, 0, y0 + h / 2, 0);
  tower.rotation.y = Math.PI / 4;
  // vertical fins on each face, following the taper; the centre fin carries the accent
  const ab = rb * Math.SQRT1_2, at = rt * Math.SQRT1_2;
  for (let f = 0; f < 4; f++) {
    const ang = (f * Math.PI) / 2;
    for (const s of [-0.6, 0, 0.6]) {
      const bot = new THREE.Vector3(s * ab, y0, ab + 0.12), top = new THREE.Vector3(s * at, y0 + h, at + 0.12);
      bot.applyAxisAngle(new THREE.Vector3(0, 1, 0), ang);
      top.applyAxisAngle(new THREE.Vector3(0, 1, 0), ang);
      const len = bot.distanceTo(top);
      const fin = b.mesh(new THREE.BoxGeometry(0.14, len, 0.4), s === 0 ? b.accent : b.kit.structure,
        (bot.x + top.x) / 2, (bot.y + top.y) / 2, (bot.z + top.z) / 2, false);
      fin.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), top.clone().sub(bot).normalize());
    }
  }
  const yt = y0 + h;
  for (const [x, z] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) b.block(0.2, 2.6, 0.2, b.kit.structure, x * at * 0.7, yt, z * at * 0.7);
  b.band(at * 1.6, at * 1.6, yt + 2.6, 0, 0, 0.2);
  b.antenna(0, yt, 0, 5.5);
  return b.done(yt + 2.8, 5.5, b.beacon(yt + 3.4));
}

function paired(b: Builder): Built {
  b.podium(13, 8, 2.2, 7);
  const towers: [number, number][] = [[-3.4, 19], [3.4, 15.5]];
  for (const [x, h] of towers) {
    b.block(4.4, h, 4.4, b.kit.facade, x, 2.2, 0, b.seed + x);
    b.block(4.0, 0.3, 4.0, b.kit.roof, x, 2.2 + h, 0);
    b.equipment(3.6, 3.6, 2.5 + h, 3);
  }
  // skybridge with an accent underline
  b.block(2.6, 1.4, 2.2, b.kit.glass, 0, 11.4, 0);
  b.band(2.6, 2.3, 11.3, 0, 0, 0.14);
  b.antenna(-3.4, 21.2, 0, 3.5);
  return b.done(21.5, 7, b.beacon(23.4, -3.4));
}

function twisted(b: Builder): Built {
  b.podium(9, 9, 2, 5);
  const h = 22, w = 5.2, twist = 0.7;
  const geo = worldUV(new THREE.BoxGeometry(w, h, w, 1, 22, 1), b.seed);
  const p = geo.attributes.position;
  for (let i = 0; i < p.count; i++) {
    const a = ((p.getY(i) + h / 2) / h) * twist, x = p.getX(i), z = p.getZ(i);
    p.setXYZ(i, x * Math.cos(a) - z * Math.sin(a), p.getY(i), x * Math.sin(a) + z * Math.cos(a));
  }
  geo.computeVertexNormals();
  b.mesh(geo, b.kit.facade, 0, 2 + h / 2, 0);
  const crown = b.band(w + 0.4, w + 0.4, 2 + h + 0.1, 0, 0, 0.25);
  crown.rotation.y = twist;
  const cap = b.block(w * 0.7, 1.6, w * 0.7, b.kit.structure, 0, 2 + h, 0);
  cap.rotation.y = twist;
  b.antenna(0, 3.6 + h, 0, 3.5);
  return b.done(3.6 + h, 5.5, b.beacon(4.2 + h));
}

function operations(b: Builder): Built {
  b.podium(15, 11, 2.5, 8);
  b.block(13, 9, 7.5, b.kit.facade, 0, 2.5, 0);
  b.band(13.3, 7.8, 5.6, 0, 0, 0.14);
  b.band(13.3, 7.8, 8.6, 0, 0, 0.14);
  b.block(12.6, 0.4, 7.1, b.kit.roof, 0, 11.5, 0);
  b.equipment(11, 6, 11.9, 7);
  // communications mast with a dish
  b.mesh(new THREE.CylinderGeometry(0.15, 0.2, 5, 8), b.kit.structure, 4.5, 14.4, -2, false);
  const dish = b.mesh(new THREE.SphereGeometry(1.1, 16, 8, 0, Math.PI * 2, 0, Math.PI / 3.2), b.kit.structure, 4.5, 15.6, -1.4, false);
  dish.rotation.x = -Math.PI / 2.6;
  b.antenna(-4.5, 11.9, 2, 4);
  return b.done(14, 8, b.beacon(13.2, -1.5, 0));
}

function command(b: Builder): Built {
  // drum podium with a colonnade, tapering cylindrical tower, ring crown
  const drum = worldCylinderUV(new THREE.CylinderGeometry(7, 7.4, 3.2, 40, 1), 7.2, 3.2, b.seed);
  b.mesh(drum, b.kit.podium, 0, 1.6, 0);
  const cols = new THREE.InstancedMesh(b.kit.column, b.kit.structure, 20);
  const m = new THREE.Matrix4();
  for (let i = 0; i < 20; i++) {
    const a = (i / 20) * Math.PI * 2;
    m.compose(new THREE.Vector3(Math.cos(a) * 7.8, 1.6, Math.sin(a) * 7.8), new THREE.Quaternion(), new THREE.Vector3(1, 3.2, 1));
    cols.setMatrixAt(i, m);
  }
  b.group.add(cols);
  b.mesh(new THREE.CylinderGeometry(8.3, 8.3, 0.3, 40), b.kit.structure, 0, 3.35, 0, false);
  b.mesh(new THREE.BoxGeometry(3.4, 2.2, 0.3), b.kit.entrance, 0, 1.1, 7.35, false);
  const h = 17;
  const tower = worldCylinderUV(new THREE.CylinderGeometry(2.8, 3.8, h, 32, 1), 3.3, h, b.seed);
  b.mesh(tower, b.kit.facade, 0, 3.5 + h / 2, 0);
  for (const y of [9, 15]) {
    const ring = b.mesh(new THREE.TorusGeometry(3.6 - (y / h) * 0.9, 0.12, 8, 48), b.accent, 0, y, 0, false);
    ring.rotation.x = Math.PI / 2;
  }
  const halo = b.mesh(new THREE.TorusGeometry(3.5, 0.2, 10, 64), b.accent, 0, 3.5 + h + 1.4, 0, false);
  halo.rotation.x = Math.PI / 2;
  for (let i = 0; i < 6; i++) {
    const a = (i / 6) * Math.PI * 2;
    b.block(0.18, 1.6, 0.18, b.kit.structure, Math.cos(a) * 2.7, 3.5 + h, Math.sin(a) * 2.7);
  }
  b.antenna(0, 3.5 + h, 0, 7);
  return b.done(3.5 + h + 1.8, 8.5, b.beacon(3.5 + h + 2.6));
}

function construction(b: Builder): Built {
  b.podium(9, 9, 2, 5);
  b.block(6, 7, 6, b.kit.facadeDim, 0, 2, 0);
  b.band(6.3, 6.3, 9.1, 0, 0, 0.2);                         // paused marker at the last finished floor
  // unfinished frame: slabs and corner columns, no facade
  for (let i = 0; i < 4; i++) b.block(6, 0.18, 6, b.kit.structure, 0, 9.2 + i * 2.1, 0);
  for (const [x, z] of [[-2.8, -2.8], [2.8, -2.8], [-2.8, 2.8], [2.8, 2.8]]) b.block(0.25, 8.4, 0.25, b.kit.structure, x, 9.2, z);
  // tower crane (idle)
  b.block(0.5, 21, 0.5, b.kit.structure, 4.2, 0, -3.6);
  b.block(11, 0.4, 0.45, b.kit.structure, 1.2, 21, -3.6);
  b.block(1.2, 1, 1, b.kit.roof, -3.4, 20.4, -3.6);
  b.antenna(4.2, 21.4, -3.6, 1.2);
  return b.done(17.6, 6, b.beacon(18.4));
}

const BUILDERS: Record<Archetype, (b: Builder) => Built> = { terraced, finned, paired, twisted, operations, command, construction };

export function buildArchetype(arch: Archetype, kit: Kit, accent: THREE.MeshStandardMaterial, seed: number): Built {
  return BUILDERS[arch](new Builder(kit, accent, seed));
}
