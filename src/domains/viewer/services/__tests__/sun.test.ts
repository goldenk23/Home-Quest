import { describe, it, expect } from 'vitest';
import { computeSun, lerpColor, clamp, azimuthLabel, formatClock, dayPhase, type SunInput } from '../sun';

const base: SunInput = { timeHours: 12, directionOverride: false, azimuthDeg: 120 };

describe('computeSun', () => {
  it('noon is bright, high, near-white, and not night', () => {
    const s = computeSun({ ...base, timeHours: 12 });
    expect(s.isNight).toBe(false);
    expect(s.intensity).toBeGreaterThan(2.8);
    expect(s.position[1]).toBeGreaterThan(30); // high up
    // near-white: all RGB channels close to each other and high
    expect(s.color).toMatch(/^#[0-9a-f]{6}$/i);
  });

  it('dawn (6h) and dusk (21h) are low, warm and dim compared to noon', () => {
    const dawn = computeSun({ ...base, timeHours: 6 });
    const dusk = computeSun({ ...base, timeHours: 21 });
    const noon = computeSun({ ...base, timeHours: 12 });
    for (const edge of [dawn, dusk]) {
      expect(edge.intensity).toBeLessThan(noon.intensity);
      expect(edge.position[1]).toBeLessThan(noon.position[1]);
      // warm = more red than blue
      const [, g, b] = hexChannels(edge.color);
      expect(g).toBeGreaterThan(b);
    }
  });

  it('the evening (18–21h) still has a low, lit sun before night falls', () => {
    const evening = computeSun({ ...base, timeHours: 19 });
    const noon = computeSun({ ...base, timeHours: 12 });
    expect(evening.isNight).toBe(false);
    expect(evening.intensity).toBeGreaterThan(0);
    expect(evening.position[1]).toBeLessThan(noon.position[1]); // lower than midday
  });

  it('times outside 6..21h are night (no sun contribution)', () => {
    for (const t of [0, 3, 5.9, 21.1, 23]) {
      const s = computeSun({ ...base, timeHours: t });
      expect(s.isNight, `time ${t} should be night`).toBe(true);
      expect(s.intensity, `time ${t} intensity`).toBe(0);
    }
  });

  it('directionOverride honours the supplied azimuth while time still drives brightness', () => {
    const s = computeSun({ ...base, timeHours: 12, directionOverride: true, azimuthDeg: 90 });
    expect(s.isNight).toBe(false);
    expect(s.intensity).toBeGreaterThan(2); // noon → bright
    // azimuth 90 (N): position should lean +Z
    expect(s.position[2]).toBeGreaterThan(s.position[0]);
  });

  it('directionOverride still lets time-of-day scrub brightness (dawn dimmer than noon)', () => {
    const azimuthDeg = 90;
    const dawn = computeSun({ ...base, timeHours: 6, directionOverride: true, azimuthDeg });
    const noon = computeSun({ ...base, timeHours: 12, directionOverride: true, azimuthDeg });
    const night = computeSun({ ...base, timeHours: 22, directionOverride: true, azimuthDeg });
    expect(dawn.intensity).toBeLessThan(noon.intensity);
    expect(night.intensity).toBe(0);
    expect(night.isNight).toBe(true);
    // azimuth stays fixed regardless of time
    expect(noon.position[2]).toBeGreaterThan(noon.position[0]);
  });

  it('sun position is always at roughly the configured radius', () => {
    const s = computeSun({ ...base, timeHours: 10, radius: 40 });
    const dist = Math.hypot(s.position[0], s.position[1], s.position[2]);
    expect(dist).toBeCloseTo(40, 1);
  });

  it('sky horizon colour is warmer at dawn than at noon', () => {
    const dawn = computeSun({ ...base, timeHours: 6 }).skyHorizonColor;
    const noon = computeSun({ ...base, timeHours: 12 }).skyHorizonColor;
    const [, , bd] = hexChannels(dawn);
    const [, , bn] = hexChannels(noon);
    // dawn horizon has LESS blue (warmer) than noon horizon
    expect(bd).toBeLessThan(bn);
  });
});

describe('helpers', () => {
  it('lerpColor interpolates endpoints', () => {
    expect(lerpColor('#000000', '#ffffff', 0)).toBe('#000000');
    expect(lerpColor('#000000', '#ffffff', 1)).toBe('#ffffff');
    expect(lerpColor('#000000', '#ffffff', 0.5)).toBe('#808080');
    // clamps t
    expect(lerpColor('#ff0000', '#00ff00', 5)).toBe('#00ff00');
  });

  it('clamp bounds values', () => {
    expect(clamp(5, 0, 10)).toBe(5);
    expect(clamp(-3, 0, 10)).toBe(0);
    expect(clamp(99, 0, 10)).toBe(10);
  });

  it('azimuthLabel returns 8-point compass codes', () => {
    expect(azimuthLabel(0)).toBe('E');
    expect(azimuthLabel(90)).toBe('N');
    expect(azimuthLabel(180)).toBe('W');
    expect(azimuthLabel(270)).toBe('S');
    // 120° lies between N(90) and W(180) → NW band.
    expect(azimuthLabel(120)).toBe('NW');
  });

  it('formatClock renders H:MM', () => {
    expect(formatClock(12)).toBe('12:00');
    expect(formatClock(14.5)).toBe('14:30');
    expect(formatClock(9.25)).toBe('09:15');
  });
});

describe('dayPhase', () => {
  it('classifies the named parts of the day by their boundaries', () => {
    expect(dayPhase(2).phase).toBe('night'); // before sunrise
    expect(dayPhase(6).phase).toBe('morning'); // sunrise
    expect(dayPhase(9).phase).toBe('morning');
    expect(dayPhase(11.99).phase).toBe('morning');
    expect(dayPhase(12).phase).toBe('noon');
    expect(dayPhase(13).phase).toBe('afternoon');
    expect(dayPhase(17).phase).toBe('afternoon');
    expect(dayPhase(18).phase).toBe('evening');
    expect(dayPhase(20.5).phase).toBe('evening');
    expect(dayPhase(21).phase).toBe('night'); // sunset
    expect(dayPhase(23.5).phase).toBe('night');
  });

  it('reports isDay for morning…evening and not at night, with a label + icon', () => {
    expect(dayPhase(8).isDay).toBe(true);
    expect(dayPhase(19).isDay).toBe(true);
    expect(dayPhase(3).isDay).toBe(false);
    expect(dayPhase(8).label).toBe('Morning');
    expect(dayPhase(8).icon.length).toBeGreaterThan(0);
  });

  it('wraps hours outside 0..24 into a valid phase', () => {
    expect(dayPhase(25).phase).toBe('night'); // 25 → 1h → night
    expect(dayPhase(-2).phase).toBe('night'); // -2 → 22h → night
    expect(dayPhase(31).phase).toBe('morning'); // 31 → 7h → morning
  });

  it('computeSun exposes the matching phase fields', () => {
    const noon = computeSun({ ...base, timeHours: 12 });
    expect(noon.phase).toBe('noon');
    expect(noon.phaseLabel).toBe('Noon');
    const night = computeSun({ ...base, timeHours: 23 });
    expect(night.phase).toBe('night');
  });
});

function hexChannels(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
