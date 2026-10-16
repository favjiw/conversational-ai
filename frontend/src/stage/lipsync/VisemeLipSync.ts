import { buildVisemeTimeline, OCULUS_VISEMES, type Viseme, type VisemeSegment, type WordTiming } from './IndonesianVisemes';

/**
 * Lip-sync method for realistic characters, switchable at runtime to compare
 * them (stage R3 adds "audio2face" once a capable NVIDIA GPU is available).
 */
export type LipSyncMethod = 'viseme' | 'amplitude';

export interface VisemeLipSyncConfig {
  /** Which method drives the mouth. */
  method: LipSyncMethod;
  /** Overall viseme strength (0 - 1). */
  gain: number;
  /** Smoothing time constant when a shape grows (s). */
  attackSec: number;
  /** Smoothing time constant when a shape fades (s). */
  releaseSec: number;
  /** Fraction of the next viseme blended in at the end of a segment (coarticulation). */
  anticipation: number;
}

export const DEFAULT_VISEME_CONFIG: VisemeLipSyncConfig = {
  method: 'viseme',
  gain: 0.9,
  attackSec: 0.045,
  releaseSec: 0.07,
  anticipation: 0.35,
};

/** Audio level (0 - 1) below which the mouth is treated as silent. */
const SILENCE_LEVEL = 0.03;
/** How long the audio must stay silent before forcing the mouth closed (s). */
const SILENCE_HOLD_SEC = 0.09;

/**
 * Turns a line's viseme timeline into smoothed per-frame viseme weights,
 * synced to the audio playback clock. The audio level only gates silence (so
 * timing drift never leaves the mouth moving in a pause); the shapes
 * themselves come from the text.
 */
export class VisemeLipSync {
  private config: VisemeLipSyncConfig;
  private text = '';
  private timings: WordTiming[] | null = null;
  private timeline: VisemeSegment[] = [];
  private builtForDuration = 0;
  private cursor = 0;
  private silentFor = 0;
  private wasPlaying = false;
  /** True once the current line's audio has been seen playing. */
  private lineStarted = false;
  private weights = new Map<Viseme, number>(OCULUS_VISEMES.map((v) => [v, 0]));

  constructor(config: Partial<VisemeLipSyncConfig> = {}) {
    this.config = { ...DEFAULT_VISEME_CONFIG, ...config };
  }

  setConfig(config: Partial<VisemeLipSyncConfig>): void {
    this.config = { ...this.config, ...config };
  }

  /** Prepare the next line; the timeline is built once the audio length is known. */
  setLine(text: string, timings: WordTiming[] | null): void {
    this.text = text;
    this.timings = timings && timings.length ? timings : null;
    this.timeline = this.timings ? buildVisemeTimeline(text, this.timings) : [];
    this.builtForDuration = this.timings ? -1 : 0;
    this.cursor = 0;
    this.lineStarted = false;
  }

  /** True while a line is set (until its audio has played). */
  get hasLine(): boolean {
    return this.text !== '';
  }

  /** True when the current line came with TTS word timings. */
  get hasTimings(): boolean {
    return this.timings !== null;
  }

  /**
   * @param playback Elapsed/duration of this character's audio, or null when not speaking.
   * @param level Audio level 0 - 1 (from the amplitude lip-sync envelope).
   * @returns Weights per viseme (0 - 1); "sil" is never returned.
   */
  update(deltaTime: number, playback: { elapsed: number; duration: number } | null, level: number): Map<Viseme, number> {
    const targets = new Map<Viseme, number>();

    // A line belongs to one clip: forget it once that clip has finished. A
    // line set while the previous clip was ending has not started yet, so keep it.
    if (this.wasPlaying && !playback && this.lineStarted) this.setLine('', null);
    this.wasPlaying = playback !== null;
    if (playback && this.text) this.lineStarted = true;

    if (playback && this.text) {
      if (!this.timings && this.builtForDuration !== playback.duration) {
        this.timeline = buildVisemeTimeline(this.text, null, playback.duration);
        this.builtForDuration = playback.duration;
        this.cursor = 0;
      }
      this.silentFor = level < SILENCE_LEVEL ? this.silentFor + deltaTime : 0;
      if (this.silentFor < SILENCE_HOLD_SEC) this.collectTargets(playback.elapsed, targets);
    } else {
      this.silentFor = 0;
    }

    const { attackSec, releaseSec, gain } = this.config;
    for (const v of OCULUS_VISEMES) {
      const target = v === 'sil' ? 0 : (targets.get(v) ?? 0) * gain;
      const current = this.weights.get(v)!;
      const tau = target > current ? attackSec : releaseSec;
      this.weights.set(v, current + (target - current) * Math.min(1, deltaTime / tau));
    }
    return this.weights;
  }

  private collectTargets(t: number, targets: Map<Viseme, number>): void {
    const tl = this.timeline;
    if (!tl.length) return;
    if (this.cursor >= tl.length || tl[this.cursor].start > t) this.cursor = 0;
    while (this.cursor < tl.length - 1 && tl[this.cursor].end <= t) this.cursor++;
    const seg = tl[this.cursor];
    if (t < seg.start || t > seg.end) return; // between words

    targets.set(seg.viseme, 1);
    // Coarticulation: start shaping the next sound near the end of this one
    const next = tl[this.cursor + 1];
    const progress = (t - seg.start) / Math.max(1e-3, seg.end - seg.start);
    if (next && progress > 0.6 && next.start - seg.end < 0.05) {
      const blend = ((progress - 0.6) / 0.4) * this.config.anticipation;
      targets.set(next.viseme, Math.max(targets.get(next.viseme) ?? 0, blend));
      targets.set(seg.viseme, 1 - blend * 0.5);
    }
  }
}
