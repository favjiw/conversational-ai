import type { FaceDriver } from './FaceDriver';
import type { BlendshapeWeights } from './arkit';
import type { Viseme } from '../lipsync/IndonesianVisemes';
import type { EmotionType } from '../expression/ExpressionDriver';

export interface GlbFaceAnimatorConfig {
  /** How far the jaw opens at full mouth level when no viseme data exists (0 - 1). */
  jawScale: number;
  blinkMinSec: number;
  blinkMaxSec: number;
  /** Fraction of the emotion kept while talking (see ExpressionConfig). */
  speakingEmotionScale?: number;
}

/** Emotion -> ARKit blendshapes. Kept moderate: realistic faces read big values as grimaces. */
const EMOTION_ARKIT: Record<EmotionType, BlendshapeWeights> = {
  neutral: {},
  happy: { mouthSmileLeft: 0.55, mouthSmileRight: 0.55, cheekSquintLeft: 0.3, cheekSquintRight: 0.3, eyeSquintLeft: 0.15, eyeSquintRight: 0.15 },
  excited: { mouthSmileLeft: 0.7, mouthSmileRight: 0.7, cheekSquintLeft: 0.35, cheekSquintRight: 0.35, browInnerUp: 0.3, browOuterUpLeft: 0.3, browOuterUpRight: 0.3, eyeWideLeft: 0.2, eyeWideRight: 0.2 },
  surprised: { browInnerUp: 0.6, browOuterUpLeft: 0.55, browOuterUpRight: 0.55, eyeWideLeft: 0.5, eyeWideRight: 0.5, jawOpen: 0.15 },
  sad: { browInnerUp: 0.5, mouthFrownLeft: 0.4, mouthFrownRight: 0.4, mouthPressLeft: 0.15, mouthPressRight: 0.15, eyeLookDownLeft: 0.15, eyeLookDownRight: 0.15 },
  thoughtful: { browDownLeft: 0.2, browInnerUp: 0.15, mouthPressLeft: 0.25, mouthPressRight: 0.25, eyeLookUpLeft: 0.25, eyeLookUpRight: 0.25, mouthRight: 0.15 },
  empathetic: { browInnerUp: 0.45, mouthSmileLeft: 0.2, mouthSmileRight: 0.2, eyeSquintLeft: 0.1, eyeSquintRight: 0.1 },
};

/** Viseme -> ARKit, for models without their own viseme morph targets. */
const VISEME_ARKIT: Record<Exclude<Viseme, 'sil'>, BlendshapeWeights> = {
  PP: { mouthClose: 0.35, mouthPressLeft: 0.45, mouthPressRight: 0.45, jawOpen: 0.05 },
  FF: { mouthRollLower: 0.5, mouthUpperUpLeft: 0.2, mouthUpperUpRight: 0.2, jawOpen: 0.1 },
  TH: { tongueOut: 0.3, jawOpen: 0.15 },
  DD: { jawOpen: 0.2, mouthStretchLeft: 0.15, mouthStretchRight: 0.15 },
  kk: { jawOpen: 0.25, mouthStretchLeft: 0.1, mouthStretchRight: 0.1 },
  CH: { mouthFunnel: 0.5, jawOpen: 0.15 },
  SS: { mouthStretchLeft: 0.35, mouthStretchRight: 0.35, jawOpen: 0.08 },
  nn: { jawOpen: 0.15, mouthClose: 0.1 },
  RR: { mouthFunnel: 0.25, jawOpen: 0.2 },
  aa: { jawOpen: 0.6 },
  E: { jawOpen: 0.35, mouthStretchLeft: 0.3, mouthStretchRight: 0.3 },
  I: { jawOpen: 0.15, mouthSmileLeft: 0.3, mouthSmileRight: 0.3, mouthStretchLeft: 0.2, mouthStretchRight: 0.2 },
  O: { jawOpen: 0.4, mouthFunnel: 0.5 },
  U: { mouthPucker: 0.7, jawOpen: 0.15 },
};

const BLINK_CLOSE_SEC = 0.07;
const BLINK_OPEN_SEC = 0.12;
const EMOTION_TRANSITION_SEC = 0.3;

/**
 * Face animation for ARKit GLB characters: viseme lip-sync (the model's own
 * viseme_* shapes when present, ARKit combinations otherwise), emotion
 * expressions toned down while talking, blinking, small eye saccades, and a
 * listening gaze toward the other presenter.
 */
export class GlbFaceAnimator {
  private face: FaceDriver;
  private config: GlbFaceAnimatorConfig;
  private readonly hasVisemeMorphs: boolean;
  /** -1 or +1: the eye-look direction (character's own left/right) toward the partner. */
  private partnerSide: number;

  private emotionTarget: BlendshapeWeights = {};
  private emotion = new Map<string, number>();
  private speakingEnvelope = 0;
  /** Set while the other presenter is talking. */
  isListening = false;

  private nextBlinkIn: number;
  private blinkT = -1;
  private gaze = { x: 0, y: 0 };
  private gazeTarget = { x: 0, y: 0 };
  private nextSaccadeIn = 0.5;
  /** Names written last frame, so shapes that stop being driven return to 0. */
  private lastWritten = new Set<string>();

  constructor(face: FaceDriver, config: GlbFaceAnimatorConfig, partnerSide: number) {
    this.face = face;
    this.config = config;
    this.partnerSide = partnerSide;
    this.hasVisemeMorphs = face.has('viseme_aa');
    this.nextBlinkIn = this.randomBlinkGap();
  }

  setConfig(config: Partial<GlbFaceAnimatorConfig>): void {
    this.config = { ...this.config, ...config };
  }

  setEmotion(emotion: EmotionType): void {
    this.emotionTarget = EMOTION_ARKIT[emotion] ?? {};
  }

  /**
   * @param mouthLevel Mouth level 0 - 1 from the amplitude envelope.
   * @param visemes Smoothed viseme weights, or null to fall back to the jaw.
   */
  update(deltaTime: number, mouthLevel: number, visemes: Map<Viseme, number> | null): void {
    if (this.face.manualOverride) return;
    const out: Record<string, number> = {};
    const add = (name: string, w: number) => {
      if (w > 0) out[name] = Math.min(1, (out[name] ?? 0) + w);
    };

    // Talking envelope: rises fast with sound, decays through short pauses
    const talking = mouthLevel > 0.06 ? 1 : 0;
    const envTau = talking > this.speakingEnvelope ? 0.08 : 0.6;
    this.speakingEnvelope += (talking - this.speakingEnvelope) * Math.min(1, deltaTime / envTau);

    // Emotion, damped while talking so the mouth shapes stay readable
    const damp = 1 - (1 - (this.config.speakingEmotionScale ?? 0.3)) * this.speakingEnvelope;
    const names = new Set([...this.emotion.keys(), ...Object.keys(this.emotionTarget)]);
    for (const name of names) {
      const target = (this.emotionTarget as Record<string, number>)[name] ?? 0;
      const cur = this.emotion.get(name) ?? 0;
      const next = cur + (target - cur) * Math.min(1, deltaTime / EMOTION_TRANSITION_SEC);
      if (next < 1e-3 && target === 0) this.emotion.delete(name);
      else this.emotion.set(name, next);
      add(name, next * damp);
    }

    // Mouth
    if (visemes) {
      for (const [v, w] of visemes) {
        if (v === 'sil' || w < 1e-3) continue;
        if (this.hasVisemeMorphs) {
          add(`viseme_${v}`, w);
        } else {
          for (const [name, k] of Object.entries(VISEME_ARKIT[v])) add(name, (k ?? 0) * w);
        }
      }
    } else {
      const jaw = mouthLevel * this.config.jawScale;
      add('jawOpen', jaw);
      add('mouthLowerDownLeft', jaw * 0.3);
      add('mouthLowerDownRight', jaw * 0.3);
    }

    // Eyes: saccades and blink (blink overrides squint/wide on the lids)
    this.updateGaze(deltaTime);
    const { x, y } = this.gaze;
    // x > 0: look toward the character's left; ARKit "In/Out" are per eye
    add('eyeLookOutLeft', Math.max(0, x));
    add('eyeLookInRight', Math.max(0, x));
    add('eyeLookInLeft', Math.max(0, -x));
    add('eyeLookOutRight', Math.max(0, -x));
    add('eyeLookUpLeft', Math.max(0, y));
    add('eyeLookUpRight', Math.max(0, y));
    add('eyeLookDownLeft', Math.max(0, -y));
    add('eyeLookDownRight', Math.max(0, -y));

    const blink = this.updateBlink(deltaTime);
    if (blink > 0) {
      out.eyeBlinkLeft = Math.max(out.eyeBlinkLeft ?? 0, blink);
      out.eyeBlinkRight = Math.max(out.eyeBlinkRight ?? 0, blink);
    }

    for (const name of this.lastWritten) {
      if (!(name in out)) this.face.set(name, 0);
    }
    this.face.setWeights(out);
    this.lastWritten = new Set(Object.keys(out));
  }

  private updateGaze(deltaTime: number): void {
    this.nextSaccadeIn -= deltaTime;
    if (this.nextSaccadeIn <= 0) {
      // Listening: mostly look toward the partner; otherwise small wandering
      const towardPartner = this.isListening && Math.random() < 0.7;
      this.gazeTarget = towardPartner
        ? { x: this.partnerSide * (0.25 + Math.random() * 0.1), y: (Math.random() - 0.5) * 0.06 }
        : { x: (Math.random() - 0.5) * 0.18, y: (Math.random() - 0.5) * 0.12 };
      this.nextSaccadeIn = 0.6 + Math.random() * (this.isListening ? 2.2 : 1.6);
    }
    // Saccades are fast (~40 ms)
    const k = Math.min(1, deltaTime / 0.04);
    this.gaze.x += (this.gazeTarget.x - this.gaze.x) * k;
    this.gaze.y += (this.gazeTarget.y - this.gaze.y) * k;
  }

  private updateBlink(deltaTime: number): number {
    if (this.blinkT < 0) {
      this.nextBlinkIn -= deltaTime;
      if (this.nextBlinkIn <= 0) this.blinkT = 0;
      return 0;
    }
    this.blinkT += deltaTime;
    if (this.blinkT < BLINK_CLOSE_SEC) return this.blinkT / BLINK_CLOSE_SEC;
    if (this.blinkT < BLINK_CLOSE_SEC + BLINK_OPEN_SEC) {
      return 1 - (this.blinkT - BLINK_CLOSE_SEC) / BLINK_OPEN_SEC;
    }
    this.blinkT = -1;
    this.nextBlinkIn = this.randomBlinkGap();
    return 0;
  }

  private randomBlinkGap(): number {
    const { blinkMinSec, blinkMaxSec } = this.config;
    return blinkMinSec + Math.random() * Math.max(0, blinkMaxSec - blinkMinSec);
  }
}
