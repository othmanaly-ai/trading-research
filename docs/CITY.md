# The city: architectural district (2026-11-05)

The 3D view in the dashboard (`dashboard/web/src/components/CityView.tsx`) is a nighttime financial
district. Screenshots: `docs/city/district-overview.png` and `docs/city/district-selected-model-review.jpg`.

**The architecture is decorative.** Only these carry meaning, and each comes from application records
passed in by the calling view:
- the accent colour
- the status label
- the halo ring
- the event pulses

## Layers

| Layer | File | Notes |
|---|---|---|
| Static architecture | `city/scenery.ts`, `city/architecture.ts`, `city/textures.ts` | Built once per mount; status updates never rebuild it (geometry count verified stable across polls) |
| State mapping | `TowerSpec` built by each view (`Overview.tsx`, `JobsView.tsx`, `MonitorView.tsx`, `App.tsx`) | Accent, label, dim state, links |
| Interaction and labels | `CityView.tsx` | Picking, hover, selection, camera moves, compact labels with leader lines, building list, legend |
| Optional effects | `CityView.tsx` | Bloom, decorative aviation lights, event pulses. Off in Low and under reduced motion. |

## Building vocabulary (procedural, no external assets)

| Building | Description |
|---|---|
| Terraced tower | Setbacks, lit ledges and a crown |
| Finned glass tower | Tapered, with vertical fins |
| Paired towers | Joined by a skybridge |
| Twisted tower | |
| Operations building | Podium, rooftop plant and a dish |
| Command building | Drum podium with a colonnade and a ring crown |
| Paused construction | Unfinished frame and an idle crane |

**Shared details:**
- Every building has a podium, a lit entrance and columns.
- Windows come from a generated texture with varied lighting, mapped in world units so window bays
  are the same size everywhere.
- Scenery towers are instanced, dimmer, unlabelled and not pickable.

## What each view maps

| View | Buildings | Colours |
|---|---|---|
| Overview district | Command = city server; operations = monitoring worker; finned = IEX feeds; terraced = research-job runner; paired = closed experiments; twisted = optional model review; construction = deferred candidate | Cyan server; amber = fresh market data; slate = closed market, idle or closed; teal = jobs; violet = review (DISABLED); grey = deferred; red = failed, refused or not running |
| Research jobs | One building per job in the pipeline | Teal completed, cyan running, red failed or blocked, violet = model review "DISABLED · SKIPPED" |
| Market monitor | Worker plus one tower per symbol | Amber only when data is fresh; slate when the market is closed |
| Demo City | Simulated strategies | "DEMO REPLAY" badge; simulated statuses |

**Links** are drawn only for real dependencies:
- server to worker (supervision)
- worker to feeds (it fetches them)
- runner to server and experiments
- review to runner
- job `depends_on` relations

A pulse travels along a link only when a recorded event changes that building's `pulseKey`.

## Effects

**Implemented:**
- emissive window patterns, a cool moon light, a back rim light and warm plaza lights
- restrained bloom (High only; labels are HTML, so text is not blurred)
- exponential fog and a horizon glow behind the skyline
- a satin ground; the reflection-like sheen is specular only
- status halo rings, with selection and hover emphasis
- pulses tied to real events
- a 0.75 s eased camera move on selection, and a Reset view button
- slow white aviation lights (decorative, High only, capped at about 30 frames/s)

**Deferred, not implemented:**
- real-time shadows
- screen-space reflections or a mirror ground
- outline post-processing (a halo ring is used instead)
- skyline variation per view

## Controls and access

- **Camera:** orbit, zoom and pan, with bounds (the camera never goes below the street, and pan stays
  inside the district).
- **Toolbar:** Reset view, Effects (High or Low, remembered in this browser), Buildings, Legend.
- **Keyboard:** labels and the Buildings list are buttons; the existing tables hold the same information.
- **Fallback:** `?3d=off`, or a failed WebGL context, shows the tables only.

## Measured performance (2026-11-05, in-app Chromium, 1213×618, pixel ratio 1)

| Measure | Value |
|---|---|
| Overview district | about 232 draw calls, 22k triangles (High); 216 draw calls (Low) |
| Frame time during interaction | 8.4 ms median, 9.6 ms 90th percentile (display refresh 240 Hz) |
| Idle rendering | about 30 frames/s with High and motion allowed; on demand only (0-2 frames/s) with Low or reduced motion |

**Limitations:**
- These were measured on one machine; other GPUs were not tested.
- The CityView chunk is about 625 kB minified (three.js plus addons).
- Draw calls are dominated by per-building meshes; merging per-building static geometry would reduce
  them, and was not done.
