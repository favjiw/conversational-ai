/**
 * Portrait 9:16 layout of the live output, modelled on the real HITS TikTok
 * live: two stacked camera panels (one presenter each) on a fixed 1080x1920
 * canvas, composed around the TikTok UI that covers parts of the screen.
 *
 * All zones are fractions of the canvas (0 - 1) so the overlay, the camera
 * framing and the HUD read the same numbers.
 */

export const CANVAS_WIDTH = 1080;
export const CANVAS_HEIGHT = 1920;

export interface Rect {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

/** Areas the TikTok app draws over (keep faces and important text out). */
export const COVERED_ZONES: Array<{ id: string; label: string; rect: Rect }> = [
  { id: 'header', label: 'Header TikTok (akun, Follow, ranking)', rect: { x0: 0, y0: 0, x1: 1, y1: 0.10 } },
  { id: 'comments', label: 'Daftar komentar', rect: { x0: 0, y0: 0.65, x1: 0.70, y1: 0.91 } },
  { id: 'bottom', label: 'Bar input & hadiah', rect: { x0: 0, y0: 0.93, x1: 1, y1: 1 } },
];

/** Side margin cropped on phones taller than 9:16 (fraction of width). */
export const SIDE_MARGIN = 0.05;

export type PanelSlot = 'top' | 'bottom';

/** Camera framing of one panel. */
export interface PanelFraming {
  persona: 'persona_a' | 'persona_b';
  /** Target face height on the canvas (fraction of canvas height). */
  faceAt: number;
  /** Camera distance from the presenter (m); smaller = closer shot. */
  distance: number;
  /** Vertical field of view (deg). */
  fov: number;
}

export interface StageLayoutConfig {
  /** Top panel first, bottom panel second. */
  panels: [PanelFraming, PanelFraming];
}

/** Where each face must land (bands drawn green in the debug overlay). */
export const FACE_BANDS: Record<PanelSlot, { y0: number; y1: number }> = {
  top: { y0: 0.22, y1: 0.28 },
  // Raised from the panel centre so the comment list does not cover it
  bottom: { y0: 0.55, y1: 0.60 },
};

export const DEFAULT_LAYOUT: StageLayoutConfig = {
  panels: [
    { persona: 'persona_a', faceAt: 0.25, distance: 1.6, fov: 30 },
    // Closer than the top panel: the face must stay high (comment list below), so a 1.75 m
    // shot showed the presenter standing once the 3D desk gave way to the studio photo.
    { persona: 'persona_b', faceAt: 0.59, distance: 1.35, fov: 30 },
  ],
};

/** Merge a partial layout from avatar.config.json over the defaults. */
export function resolveLayout(partial?: { panels?: Partial<PanelFraming>[] }): StageLayoutConfig {
  const panels = DEFAULT_LAYOUT.panels.map((def, i) => ({ ...def, ...(partial?.panels?.[i] ?? {}) }));
  // A swapped order must still keep each slot's face band
  panels[0].faceAt = partial?.panels?.[0]?.faceAt ?? DEFAULT_LAYOUT.panels[0].faceAt;
  panels[1].faceAt = partial?.panels?.[1]?.faceAt ?? DEFAULT_LAYOUT.panels[1].faceAt;
  return { panels: [panels[0], panels[1]] };
}

/** True when a point (canvas fractions) lies inside a covered zone or the side margin. */
export function coveredBy(x: number, y: number): string | null {
  if (x < SIDE_MARGIN || x > 1 - SIDE_MARGIN) return 'side';
  const zone = COVERED_ZONES.find(({ rect: r }) => x >= r.x0 && x <= r.x1 && y >= r.y0 && y <= r.y1);
  return zone?.id ?? null;
}
