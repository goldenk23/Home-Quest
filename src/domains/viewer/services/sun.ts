// src/domains/viewer/services/sun.ts
//
// A pure, GPU-free sun model. Given a wall-clock time of day (and optionally a manual
// compass direction), it produces everything the scene needs to render a believable moving
// sun: its 3D position, the light's intensity + colour, and the sky's two gradient colours.
//
// Why this is the core of the realism feature: the 3D walls already have REAL holes cut for
// every window (see extrusion.ts). So once this drives the scene's directional light, the
// sun's beam and its shadow physically stream through those openings into the rooms — and
// because the position/intensity/colour change with the time of day, "however the light
// would come in" happens automatically, at zero extra GPU cost.
//
// Azimuth convention: 0° = +X (East), measured clockwise so 90° = +Z (North), 180° = -X
// (West), 270° = -Z (South). Elevation 0° = horizon, 90° = overhead. This matches the
// right-handed XZ ground plane where +Z is "north on the plan" (plan +Y → 3D −Z).

export interface SunState {
  /** Sun position in 3D world units (meters), well outside the shadow frustum. */
  position: [number, number, number];
  /** Directional-light intensity (0 = dark, ~3 = bright noon). 0 when below horizon. */
  intensity: number;
  /** Light colour as a hex string (warm near the horizon, white overhead). */
  color: string;
  /** Sky gradient colour at the zenith. */
  skyTopColor: string;
  /** Sky gradient colour at the horizon (used for fog too). */
  skyHorizonColor: string;
  /** True when the sun is below the horizon — caller may treat this as "night". */
  isNight: boolean;
}

export interface SunInput {
  /** Wall-clock hours, 6 (dawn) .. 18 (dusk). Outside this range is clamped to night. */
  timeHours: number;
  /** When true, `azimuthDeg` overrides the time-derived compass direction. */
  directionOverride: boolean;
  /** Compass azimuth in degrees (0=E, 90=N, 180=W, 270=S). */
  azimuthDeg: number;
  /** Distance of the sun from the origin in world meters (default 40). */
  radius?: number;
}

const SUN_RADIUS = 40;

/** Clamp v into [min, max]. */
export function clamp(v: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, v));
}

/**
 * Linearly interpolate between two hex colours (`#rrggbb`). t is clamped to [0,1].
 * Returns `b` for t≥1 and `a` for t≤0.
 */
export function lerpColor(a: string, b: string, t: number): string {
  const tc = clamp(t, 0, 1);
  const pa = parseHex(a);
  const pb = parseHex(b);
  if (!pa || !pb) return b;
  const r = Math.round(pa[0] + (pb[0] - pa[0]) * tc);
  const g = Math.round(pa[1] + (pb[1] - pa[1]) * tc);
  const bl = Math.round(pa[2] + (pb[2] - pa[2]) * tc);
  return toHex(r, g, bl);
}

function parseHex(hex: string): [number, number, number] | null {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) return null;
  const n = parseInt(m[1], 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function toHex(r: number, g: number, b: number): string {
  const h = (v: number) => clamp(v, 0, 255).toString(16).padStart(2, '0');
  return `#${h(r)}${h(g)}${h(b)}`;
}

// Palette stops for the realistic arc.
const COLOR_HORIZON = '#ff9a3c'; // warm orange at dawn/dusk
const COLOR_NOON = '#fff7ec'; // near-white overhead
const SKY_DAY_TOP = '#4a90d9'; // midday blue
const SKY_DAY_HORIZON = '#bcd9f2'; // pale blue haze
const SKY_DUSK_TOP = '#2a3a66'; // deep blue at dawn/dusk
const SKY_DUSK_HORIZON = '#e8a06a'; // warm glow band
const SKY_NIGHT_TOP = '#0a1020';
const SKY_NIGHT_HORIZON = '#1a2030';

/**
 * Map a time-of-day (6..18h) to a sun elevation (0..~75°). The sun arcs from the horizon
 * at dawn (6h) up to a high point near noon (12h) and back to the horizon at dusk (18h).
 * sin gives a smooth, natural-feeling arc rather than a linear sawtooth.
 */
function elevationForTime(timeHours: number): number {
  const t = clamp((timeHours - 6) / 12, 0, 1); // 0 at dawn, 1 at dusk
  return Math.sin(t * Math.PI) * 75; // 0 → 75° → 0
}

/**
 * Map a time-of-day to a compass azimuth (degrees). The sun rises in the east (≈45°, NE→E)
 * and sets in the west (≈225°, SW→W), sweeping across the southern sky over the day.
 */
function azimuthForTime(timeHours: number): number {
  const t = clamp((timeHours - 6) / 12, 0, 1); // 0 at dawn, 1 at dusk
  return 45 + t * 180; // 45° (NE) → 225° (SW)
}

/**
 * "Dayness" 0..1 — how high the sun is. Used to blend horizon→noon colour and to scale
 * intensity. 1 at noon, 0 at the horizon.
 */
function dayness(elevationDeg: number): number {
  return clamp(elevationDeg / 75, 0, 1);
}

/**
 * Convert azimuth/elevation to a 3D position on a sphere of `radius` metres.
 * Azimuth 0 = +X (East), clockwise so +Z is North; elevation 0 = horizon, 90 = up.
 */
function sphericalToCartesian(azimuthDeg: number, elevationDeg: number, radius: number): [number, number, number] {
  const az = (azimuthDeg * Math.PI) / 180;
  const el = (elevationDeg * Math.PI) / 180;
  const ce = Math.cos(el);
  return [
    Math.cos(az) * ce * radius, // X (East)
    Math.sin(el) * radius, // Y (up)
    Math.sin(az) * ce * radius, // Z (North)
  ];
}

/**
 * Compute the full sun state for the scene.
 *
 * - In the default (time-driven) mode, azimuth AND elevation both derive from `timeHours`,
 *   so a single slider produces a believable day arc: low warm sun at the edges, high white
 *   sun at noon, dark night outside 6–18h.
 * - With `directionOverride`, the caller's `azimuthDeg` is honoured and a fixed pleasant
 *   elevation (55°) is used, so the user can aim sunlight from a chosen compass direction.
 */
export function computeSun(input: SunInput): SunState {
  const radius = input.radius ?? SUN_RADIUS;

  const elevation = input.directionOverride ? 55 : elevationForTime(input.timeHours);
  const azimuth = input.directionOverride ? input.azimuthDeg : azimuthForTime(input.timeHours);

  const position = sphericalToCartesian(azimuth, elevation, radius);
  const isNight = elevation <= 2;

  // Intensity ramps up with elevation. Near the horizon it's dim/filtered; overhead it's
  // strong. Night (below horizon) contributes nothing — the env fill handles the dark.
  const intensity = isNight ? 0 : clamp(0.6 + dayness(elevation) * 2.6, 0, 3.2);

  // Light colour: warm at the horizon (thick atmosphere), white overhead.
  const horizonness = 1 - dayness(elevation); // 1 at horizon, 0 at noon
  const color = lerpColor(COLOR_NOON, COLOR_HORIZON, horizonness * 0.85);

  // Sky gradient tracks the sun: blue at noon, warm/dusky at the edges, near-black at night.
  const skyTopColor = isNight
    ? SKY_NIGHT_TOP
    : lerpColor(SKY_DAY_TOP, SKY_DUSK_TOP, horizonness);
  const skyHorizonColor = isNight
    ? SKY_NIGHT_HORIZON
    : lerpColor(SKY_DAY_HORIZON, SKY_DUSK_HORIZON, horizonness);

  return { position, intensity, color, skyTopColor, skyHorizonColor, isNight };
}

/** Human label for the compass azimuth, e.g. 120 → 'SE'. */
export function azimuthLabel(azimuthDeg: number): string {
  const dirs = ['E', 'NE', 'N', 'NW', 'W', 'SW', 'S', 'SE'];
  const idx = Math.round(((azimuthDeg % 360) / 45)) % 8;
  return dirs[(idx + 8) % 8];
}

/** Format decimal hours as an "H:MM" clock string, 24h. */
export function formatClock(timeHours: number): string {
  const h = Math.floor(clamp(timeHours, 0, 24));
  const m = Math.round((clamp(timeHours, 0, 24) - h) * 60);
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}
