import * as THREE from "three";
import { RING_IN, RING_OUT, PLAZA_R } from "./scenery";

// DECORATIVE ambient layer: traffic, path lights, plaza inlays, a fountain, signage, a district
// clock, window-light variation and slow light sweeps on distant scenery towers. None of it reads
// application state, and the legend says so. Everything is instanced or emissive geometry: no
// dynamic light per vehicle or window.

export type Effects = "low" | "medium" | "high";
export interface Landmark { x: number; z: number; w: number; h: number }

export interface Ambient {
  group: THREE.Group;
  /** Advance decorative animation. Returns true when something moved (a render is needed). */
  update: (dt: number, now: number, moving: boolean) => boolean;
  dispose: () => void;
}

const VEHICLES: Record<Effects, number> = { low: 0, medium: 12, high: 26 };

interface Car { route: number; s: number; speed: number }

function rng(seed: number) {
  let s = seed >>> 0;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
}

function signTexture(lines: string[], w = 512, h = 128, color = "#f8e7c4"): THREE.CanvasTexture {
  const c = document.createElement("canvas");
  c.width = w; c.height = h;
  const g = c.getContext("2d")!;
  g.fillStyle = "#070a12";
  g.fillRect(0, 0, w, h);
  g.strokeStyle = "rgba(248,231,196,0.35)";
  g.lineWidth = 4;
  g.strokeRect(6, 6, w - 12, h - 12);
  g.fillStyle = color;
  g.textAlign = "center";
  g.textBaseline = "middle";
  lines.forEach((t, i) => {
    g.font = `${i === 0 ? 600 : 400} ${i === 0 ? 40 : 26}px system-ui, Segoe UI, sans-serif`;
    g.fillText(t, w / 2, (h / (lines.length + 1)) * (i + 1));
  });
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

export function buildAmbient(effects: Effects, opts: { landmarks: Landmark[]; facade: THREE.Texture[]; fountain: boolean }): Ambient {
  const group = new THREE.Group();
  const geos: THREE.BufferGeometry[] = [];
  const mats: THREE.Material[] = [];
  const texs: THREE.Texture[] = [];
  const G = <T extends THREE.BufferGeometry>(g: T) => { geos.push(g); return g; };
  const M = <T extends THREE.Material>(m: T) => { mats.push(m); return m; };
  const r = rng(4242);

  // ---------------------------------------------------------------- illuminated paths & plaza
  const pathMat = M(new THREE.MeshBasicMaterial({ color: 0xffd9a0, transparent: true, opacity: 0.55, depthWrite: false }));
  for (const rad of [RING_OUT + 1.38, PLAZA_R + 0.05, RING_IN - 0.05]) {
    const m = new THREE.Mesh(G(new THREE.RingGeometry(rad - 0.06, rad + 0.06, 128)), pathMat);
    m.rotation.x = -Math.PI / 2; m.position.y = 0.07;
    group.add(m);
  }
  const inlay = new THREE.InstancedMesh(G(new THREE.PlaneGeometry(0.1, PLAZA_R - 3.2)),
    M(new THREE.MeshBasicMaterial({ color: 0xcfd8ea, transparent: true, opacity: 0.28, depthWrite: false })), 12);
  const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), one = new THREE.Vector3(1, 1, 1);
  for (let i = 0; i < 12; i++) {
    const a = (i / 12) * Math.PI * 2;
    const rr = 3 + (PLAZA_R - 3.2) / 2;
    q.setFromEuler(new THREE.Euler(-Math.PI / 2, 0, -a + Math.PI / 2));
    m4.compose(new THREE.Vector3(Math.cos(a) * rr, 0.075, Math.sin(a) * rr), q, one);
    inlay.setMatrixAt(i, m4);
  }
  group.add(inlay);
  if (opts.fountain) {
    const basin = new THREE.Mesh(G(new THREE.CylinderGeometry(2.4, 2.6, 0.5, 40)),
      M(new THREE.MeshStandardMaterial({ color: 0x232b3c, roughness: 0.6 })));
    basin.position.y = 0.25;
    const water = new THREE.Mesh(G(new THREE.CircleGeometry(2.15, 40)),
      M(new THREE.MeshBasicMaterial({ color: 0xbcd3f5, transparent: true, opacity: 0.35 })));
    water.rotation.x = -Math.PI / 2; water.position.y = 0.51;
    group.add(basin, water);
  }

  // ---------------------------------------------------------------- signage and district clock
  const signTex = signTexture(["CENTRAL PLAZA", "research district · read-only"]); texs.push(signTex);
  const pylon = new THREE.Mesh(G(new THREE.BoxGeometry(3.2, 0.8, 0.12)), M(new THREE.MeshBasicMaterial({ map: signTex })));
  pylon.position.set(-6.4, 1.4, 7.6); pylon.rotation.y = 0.55;
  const post = new THREE.Mesh(G(new THREE.BoxGeometry(0.12, 1.0, 0.12)), M(new THREE.MeshStandardMaterial({ color: 0x2a3142 })));
  post.position.set(-6.4, 0.5, 7.6);
  group.add(pylon, post);
  const clockCanvas = document.createElement("canvas");
  clockCanvas.width = 256; clockCanvas.height = 96;
  const clockTex = new THREE.CanvasTexture(clockCanvas); clockTex.colorSpace = THREE.SRGBColorSpace; texs.push(clockTex);
  const clock = new THREE.Mesh(G(new THREE.BoxGeometry(2.2, 0.82, 0.12)), M(new THREE.MeshBasicMaterial({ map: clockTex })));
  clock.position.set(6.4, 1.4, 7.6); clock.rotation.y = -0.55;
  const post2 = post.clone(); post2.position.set(6.4, 0.5, 7.6);
  group.add(clock, post2);
  let clockMinute = "";
  const drawClock = () => {
    const t = new Date().toLocaleTimeString("en-US", { timeZone: "America/New_York", hour: "2-digit", minute: "2-digit", hour12: false });
    if (t === clockMinute) return false;
    clockMinute = t;
    const g = clockCanvas.getContext("2d")!;
    g.fillStyle = "#070a12"; g.fillRect(0, 0, 256, 96);
    g.fillStyle = "#f8e7c4"; g.textAlign = "center"; g.textBaseline = "middle";
    g.font = "600 40px system-ui, Segoe UI, sans-serif"; g.fillText(`${t} ET`, 128, 42);
    g.font = "400 18px system-ui, Segoe UI, sans-serif"; g.fillStyle = "#a7b0c2"; g.fillText("district clock", 128, 78);
    clockTex.needsUpdate = true;
    return true;
  };
  drawClock();
  // a slowly scrolling banner (High only): district name, no data of any kind
  let banner: THREE.Mesh | null = null, bannerTex: THREE.CanvasTexture | null = null;
  if (effects === "high") {
    bannerTex = signTexture(["TRADINGPROJECT · RESEARCH DISTRICT · READ-ONLY RECORDS · NO TRADING EXECUTION"], 1024, 64, "#e8dcc2");
    bannerTex.wrapS = THREE.RepeatWrapping;
    bannerTex.repeat.set(0.5, 1);
    texs.push(bannerTex);
    banner = new THREE.Mesh(G(new THREE.BoxGeometry(5, 0.4, 0.08)), M(new THREE.MeshBasicMaterial({ map: bannerTex })));
    banner.position.set(0, 0.55, PLAZA_R + 0.9);
    group.add(banner);
  }

  // ---------------------------------------------------------------- traffic (instanced)
  const n = VEHICLES[effects];
  const laneR = [RING_IN + 0.95, RING_OUT - 0.95];
  const avenues = [0, 1, 2, 3].map((k) => (k / 4) * Math.PI * 2 + Math.PI / 4);
  const cars: Car[] = [];
  for (let i = 0; i < n; i++) cars.push({ route: i % 10, s: r(), speed: 0.65 + r() * 0.5 });
  // routes 0-1: ring lanes (opposite directions); 2-9: avenue lanes (out/in on each avenue)
  const pose = (c: Car, out: { p: THREE.Vector3; yaw: number }) => {
    if (c.route < 2) {
      const R = laneR[c.route], dir = c.route === 0 ? 1 : -1, a = c.s * Math.PI * 2 * dir;
      out.p.set(Math.cos(a) * R, 0.3, Math.sin(a) * R);
      out.yaw = Math.atan2(-Math.cos(a) * dir, -Math.sin(a) * dir);    // heading = direction of travel
      return;
    }
    const av = avenues[(c.route - 2) >> 1], inbound = (c.route - 2) % 2 === 1;
    const d = 16 + (inbound ? 1 - c.s : c.s) * 84;
    const off = inbound ? -0.9 : 0.9;
    out.p.set(Math.cos(av) * d - Math.sin(av) * off, 0.3, Math.sin(av) * d + Math.cos(av) * off);
    out.yaw = -av + (inbound ? Math.PI : 0);
  };
  const bodies = n ? new THREE.InstancedMesh(G(new THREE.BoxGeometry(1.5, 0.5, 0.72)),
    M(new THREE.MeshStandardMaterial({ color: 0x1b2232, roughness: 0.4, metalness: 0.6 })), n) : null;
  const heads = n ? new THREE.InstancedMesh(G(new THREE.BoxGeometry(0.08, 0.13, 0.17)), M(new THREE.MeshBasicMaterial({ color: 0xf5f8ff })), n * 2) : null;
  const tails = n ? new THREE.InstancedMesh(G(new THREE.BoxGeometry(0.08, 0.11, 0.17)), M(new THREE.MeshBasicMaterial({ color: 0xff3b30 })), n * 2) : null;
  if (bodies && heads && tails) group.add(bodies, heads, tails);
  const tmp = { p: new THREE.Vector3(), yaw: 0 };
  const local = new THREE.Vector3();
  const placeCars = () => {
    if (!bodies || !heads || !tails) return;
    cars.forEach((c, i) => {
      pose(c, tmp);
      q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), tmp.yaw);
      m4.compose(tmp.p, q, one);
      bodies.setMatrixAt(i, m4);
      for (const [k, side] of [[0, -0.24], [1, 0.24]] as const) {
        local.set(0.77, 0.03, side).applyQuaternion(q).add(tmp.p);
        m4.compose(local, q, one); heads.setMatrixAt(i * 2 + k, m4);
        local.set(-0.77, 0.03, side).applyQuaternion(q).add(tmp.p);
        m4.compose(local, q, one); tails.setMatrixAt(i * 2 + k, m4);
      }
    });
    bodies.instanceMatrix.needsUpdate = heads.instanceMatrix.needsUpdate = tails.instanceMatrix.needsUpdate = true;
  };
  placeCars();

  // ---------------------------------------------------------------- light sweeps on distant scenery
  const sweeps: THREE.Mesh[] = [];
  if (effects === "high") {
    const sweepMat = M(new THREE.MeshBasicMaterial({ color: 0xe8eefc, transparent: true, opacity: 0.16, blending: THREE.AdditiveBlending, depthWrite: false }));
    for (const l of opts.landmarks.slice(0, 3)) {
      const s = new THREE.Mesh(G(new THREE.BoxGeometry(l.w + 0.25, 0.9, l.w + 0.25)), sweepMat);
      s.position.set(l.x, 0, l.z);
      s.userData = { h: l.h, phase: r() };
      sweeps.push(s);
      group.add(s);
    }
  }

  // ---------------------------------------------------------------- facade light variation
  const flicker = effects !== "low";
  let nextFlicker = 0;
  const flick = () => {
    for (const tex of opts.facade) {
      const c = tex.image as HTMLCanvasElement;
      const g = c.getContext("2d")!;
      for (let k = 0; k < 5; k++) {
        const col = Math.floor(r() * 16), row = Math.floor(r() * 32);
        if (row === 31 && col === 0) continue;
        const on = r() < 0.45;
        const w = 0.55 + r() * 0.45;
        g.fillStyle = on ? `rgb(${Math.round(255 * w)},${Math.round(200 * w)},${Math.round(120 * w)})` : "rgb(14,18,26)";
        g.fillRect(col * 16 + 3, row * 16 + 3, 10, 11);
      }
      tex.needsUpdate = true;
    }
  };

  const update = (dt: number, now: number, moving: boolean): boolean => {
    let changed = drawClock();
    if (!moving) return changed;                     // reduced motion: everything decorative stands still
    if (cars.length) {
      for (const c of cars) {
        const len = c.route < 2 ? Math.PI * 2 * laneR[c.route] : 84;
        c.s = (c.s + (c.speed * 8 * dt) / len) % 1;
      }
      placeCars();
      changed = true;
    }
    for (const s of sweeps) {
      const h = s.userData.h as number;
      s.position.y = ((now / 14000 + (s.userData.phase as number)) % 1) * h;
      changed = true;
    }
    if (bannerTex) { bannerTex.offset.x = (now / 40000) % 1; changed = true; }
    if (flicker && now > nextFlicker) { flick(); nextFlicker = now + 4500; changed = true; }
    return changed;
  };

  return { group, update, dispose: () => { geos.forEach((g) => g.dispose()); mats.forEach((m) => m.dispose()); texs.forEach((t) => t.dispose()); } };
}
