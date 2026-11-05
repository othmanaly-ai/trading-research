// One palette for the whole district. Architecture is navy/charcoal; warm windows are decorative;
// accent colours are reserved for operational meaning (see the legend in CityView).

export const PALETTE = {
  sky: 0x060914,
  fog: 0x0a1020,
  ground: 0x0b111c,
  asphalt: 0x0d131f,
  sidewalk: 0x1a2232,
  plaza: 0x1c2436,
  navy: 0x121a2c,
  charcoal: 0x1b212d,
  steel: 0x2a3344,
  glass: 0x0f2033,
  window: 0xffc887,          // decorative warm office light
  tree: 0x0f2a22,
  // operational accents
  amber: 0xf59e0b,           // market-data monitoring
  teal: 0x14b8a6,            // deterministic research jobs
  cyan: 0x22d3ee,
  violet: 0x8b5cf6,          // optional model review (disabled) / demo
  red: 0xef4444,             // failed or interrupted
  deferred: 0x94a3b8,        // paused / deferred
  idle: 0x475569,
  aviation: 0xe2e8f0,        // decorative obstruction lights (white, never a status colour)
};

export type Archetype = "terraced" | "finned" | "paired" | "twisted" | "operations" | "command" | "construction";
export const ARCHETYPES: Archetype[] = ["terraced", "finned", "paired", "twisted", "operations"];

export const ARCHETYPE_LABEL: Record<Archetype, string> = {
  terraced: "Terraced tower", finned: "Finned glass tower", paired: "Paired towers", twisted: "Twisted tower",
  operations: "Operations building", command: "Command building", construction: "Paused construction",
};
