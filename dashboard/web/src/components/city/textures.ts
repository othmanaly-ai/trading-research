import * as THREE from "three";

// Locally generated textures (no downloaded assets). One facade texture is shared by every
// building: UVs are scaled to world size, so a window bay is the same size everywhere.

export const BAY_W = 1.1;          // world units per window bay (horizontal)
export const FLOOR_H = 0.9;        // world units per floor
export const TEX_COLS = 16, TEX_ROWS = 32;

function rng(seed: number) {
  let s = seed >>> 0;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
}

/** Window grid: dark mullions, mostly dark glass, a varied minority of warm lit windows.
 *  `litShare` controls density; bottom-left texel is always dark (used for roofs). */
export function facadeTexture(litShare: number, seed: number, maxAniso: number): THREE.CanvasTexture {
  const cw = 16, ch = 16;
  const c = document.createElement("canvas");
  c.width = TEX_COLS * cw;
  c.height = TEX_ROWS * ch;
  const g = c.getContext("2d")!;
  g.fillStyle = "#000000";
  g.fillRect(0, 0, c.width, c.height);
  const r = rng(seed);
  for (let row = 0; row < TEX_ROWS; row++) {
    // whole floors are sometimes dark (unoccupied), which reads as believable variation
    const floorLit = r() < 0.82;
    for (let col = 0; col < TEX_COLS; col++) {
      if (row === TEX_ROWS - 1 && col === 0) continue;
      const lit = floorLit && r() < litShare;
      const x = col * cw + 3, y = row * ch + 3, w = cw - 6, h = ch - 5;
      if (lit) {
        const warm = 0.55 + r() * 0.45;
        const tint = r();
        const R = Math.round(255 * warm), G = Math.round((175 + 50 * tint) * warm), B = Math.round((95 + 70 * tint) * warm);
        g.fillStyle = `rgb(${R},${G},${B})`;
      } else {
        const v = Math.round(10 + r() * 14);
        g.fillStyle = `rgb(${v},${v + 4},${v + 12})`;
      }
      g.fillRect(x, y, w, h);
    }
  }
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = maxAniso;
  t.needsUpdate = true;
  return t;
}

/** Ground: dark asphalt with faint noise; a gloss map is not needed (roughness is uniform). */
export function groundTexture(): THREE.CanvasTexture {
  const c = document.createElement("canvas");
  c.width = c.height = 256;
  const g = c.getContext("2d")!;
  const img = g.createImageData(256, 256);
  const r = rng(7);
  for (let i = 0; i < img.data.length; i += 4) {
    const v = 22 + r() * 10;
    img.data[i] = v; img.data[i + 1] = v + 3; img.data[i + 2] = v + 9; img.data[i + 3] = 255;
  }
  g.putImageData(img, 0, 0);
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(24, 24);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

/** Plaza paving: subtle square grid. */
export function pavingTexture(): THREE.CanvasTexture {
  const c = document.createElement("canvas");
  c.width = c.height = 128;
  const g = c.getContext("2d")!;
  g.fillStyle = "#1d2537";
  g.fillRect(0, 0, 128, 128);
  g.strokeStyle = "#2a344a";
  g.lineWidth = 2;
  for (let i = 0; i <= 128; i += 32) {
    g.beginPath(); g.moveTo(i, 0); g.lineTo(i, 128); g.stroke();
    g.beginPath(); g.moveTo(0, i); g.lineTo(128, i); g.stroke();
  }
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(8, 8);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

/** Box UVs in world units (window bays), with a per-building offset. Top and bottom faces map to
 *  the always-dark texel so roofs never show windows. */
export function worldBoxUV(geo: THREE.BoxGeometry, w: number, h: number, d: number, seed = 0): THREE.BoxGeometry {
  const uv = geo.attributes.uv as THREE.BufferAttribute;
  const ou = (seed * 0.37) % 1, ov = (seed * 0.61) % 1;
  const su = 1 / (TEX_COLS * BAY_W), sv = 1 / (TEX_ROWS * FLOOR_H);
  // BoxGeometry face order: +x, -x, +y, -y, +z, -z; 4 vertices each (with 1x1 segments).
  const faceW = [d, d, w, w, w, w];
  for (let f = 0; f < 6; f++) {
    for (let k = 0; k < 4; k++) {
      const i = f * 4 + k;
      if (f === 2 || f === 3) { uv.setXY(i, 0.5 / (TEX_COLS * 16), 0.5 / (TEX_ROWS * 16)); continue; }
      const u0 = uv.getX(i), v0 = uv.getY(i);
      uv.setXY(i, ou + u0 * faceW[f] * su, ov + v0 * h * sv);
    }
  }
  uv.needsUpdate = true;
  return geo;
}

/** Side UVs for a cylinder/frustum in world units (u = around the perimeter, v = height). */
export function worldCylinderUV(geo: THREE.CylinderGeometry, radius: number, h: number, seed = 0): THREE.CylinderGeometry {
  const uv = geo.attributes.uv as THREE.BufferAttribute;
  const perimeter = 2 * Math.PI * radius;
  const ou = (seed * 0.37) % 1, ov = (seed * 0.61) % 1;
  const p = geo.parameters;
  const sideCount = (p.radialSegments + 1) * (p.heightSegments + 1);
  for (let i = 0; i < uv.count; i++) {
    if (i >= sideCount) { uv.setXY(i, 0.5 / (TEX_COLS * 16), 0.5 / (TEX_ROWS * 16)); continue; }
    uv.setXY(i, ou + uv.getX(i) * perimeter / (TEX_COLS * BAY_W), ov + uv.getY(i) * h / (TEX_ROWS * FLOOR_H));
  }
  uv.needsUpdate = true;
  return geo;
}
