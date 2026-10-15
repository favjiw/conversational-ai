import type { VRM } from '@pixiv/three-vrm';
import { ExpressionAdapter } from './ExpressionAdapter';

export type EmotionType =
  | 'neutral'
  | 'happy'
  | 'excited'
  | 'surprised'
  | 'sad'
  | 'thoughtful'
  | 'empathetic';

export interface EmotionWeights {
  happy?: number;
  sad?: number;
  surprised?: number;
  relaxed?: number;
  angry?: number;
}

export interface ExpressionConfig {
  transitionMs: number; // 200 - 400 ms
  maxCombinedWeight: number; // 0.8 - 1.2, default 1.0
  /**
   * Fraction of the emotion kept while the character is talking (0 - 1).
   * Emotion presets like "happy" carry their own open-mouth shape and, on
   * VRM 1.0 models with overrideMouth, suppress the lip-sync visemes, so
   * they are toned down while speaking and restored while listening.
   */
  speakingEmotionScale?: number;
}

const DEFAULT_SPEAKING_EMOTION_SCALE = 0.3;
/** Mouth opening (0 - 1) that counts as "talking". */
const SPEAKING_MOUTH_THRESHOLD = 0.06;
/** How fast the talking envelope rises and falls (seconds). */
const SPEAKING_ATTACK_SEC = 0.08;
const SPEAKING_RELEASE_SEC = 0.6;

/**
 * Target blendshape weights for the 7 standard emotions as defined in PRD FR-5.
 */
export const EMOTION_PRESETS: Record<EmotionType, EmotionWeights> = {
  neutral: {},
  happy: { happy: 0.7 },
  excited: { happy: 1.0, surprised: 0.15 },
  surprised: { surprised: 0.9 },
  sad: { sad: 0.6 },
  thoughtful: { relaxed: 0.4 },
  empathetic: { sad: 0.3, relaxed: 0.3 },
};

export class ExpressionDriver {
  private vrm: VRM;
  private adapter: ExpressionAdapter;
  private config: ExpressionConfig;

  private currentEmotion: EmotionType = 'neutral';
  private targetEmotion: EmotionType = 'neutral';
  /** 0 = listening, 1 = talking; smoothed so syllable gaps do not flicker. */
  private speakingEnvelope = 0;

  // Current interpolated values
  private currentWeights: Map<string, number> = new Map([
    ['happy', 0],
    ['sad', 0],
    ['surprised', 0],
    ['relaxed', 0],
    ['angry', 0],
  ]);

  // Target values
  private targetWeights: Map<string, number> = new Map([
    ['happy', 0],
    ['sad', 0],
    ['surprised', 0],
    ['relaxed', 0],
    ['angry', 0],
  ]);

  // Head tilt / nod parameters for thoughtful and empathetic
  public headPoseOffset = {
    pitch: 0, // nodding (X rotation)
    yaw: 0,   // turning (Y rotation)
    roll: 0,  // tilting (Z rotation)
  };

  private targetHeadPose = {
    pitch: 0,
    yaw: 0,
    roll: 0,
  };

  constructor(
    characterName: string,
    vrm: VRM,
    config: ExpressionConfig = { transitionMs: 300, maxCombinedWeight: 1.0 }
  ) {
    this.vrm = vrm;
    this.config = config;
    this.adapter = new ExpressionAdapter(characterName, vrm);
  }

  getAdapter(): ExpressionAdapter {
    return this.adapter;
  }

  getEmotion(): EmotionType {
    return this.currentEmotion;
  }

  getConfig(): ExpressionConfig {
    return this.config;
  }

  setConfig(newConfig: Partial<ExpressionConfig>): void {
    Object.assign(this.config, newConfig);
  }

  /**
   * Sets new target emotion with smooth transition.
   */
  setEmotion(emotion: EmotionType): void {
    if (!EMOTION_PRESETS[emotion]) {
      console.warn(`[ExpressionDriver] Unknown emotion: ${emotion}, defaulting to neutral.`);
      emotion = 'neutral';
    }

    this.targetEmotion = emotion;
    const preset = EMOTION_PRESETS[emotion];

    // Reset all targets
    for (const key of this.targetWeights.keys()) {
      this.targetWeights.set(key, 0);
    }

    // Assign preset targets
    for (const [key, val] of Object.entries(preset)) {
      if (val !== undefined) {
        this.targetWeights.set(key, val);
      }
    }

    // Configure head pose targets for thoughtful / empathetic emotions
    if (emotion === 'thoughtful') {
      // Slight head tilt (roll), slight look up (negative pitch)
      this.targetHeadPose.pitch = -0.06;
      this.targetHeadPose.yaw = 0.04;
      this.targetHeadPose.roll = 0.08;
    } else if (emotion === 'empathetic') {
      // Gentle forward tilt
      this.targetHeadPose.pitch = 0.05;
      this.targetHeadPose.yaw = 0.0;
      this.targetHeadPose.roll = -0.03;
    } else {
      this.targetHeadPose.pitch = 0;
      this.targetHeadPose.yaw = 0;
      this.targetHeadPose.roll = 0;
    }
  }

  /**
   * Updates expression blend weights and applies them to VRM.
   * Prevents mouth distortion when speech mouthOpen weight is active.
   *
   * @param deltaTime Elapsed seconds
   * @param mouthOpen Current mouth open intensity (0 to 1) from lipsync
   */
  update(deltaTime: number, mouthOpen: number = 0): void {
    const transitionSec = Math.max(0.05, this.config.transitionMs / 1000);
    const step = deltaTime / transitionSec;

    // Smooth head pose transition
    this.headPoseOffset.pitch += (this.targetHeadPose.pitch - this.headPoseOffset.pitch) * Math.min(1, step);
    this.headPoseOffset.yaw += (this.targetHeadPose.yaw - this.headPoseOffset.yaw) * Math.min(1, step);
    this.headPoseOffset.roll += (this.targetHeadPose.roll - this.headPoseOffset.roll) * Math.min(1, step);

    // Calculate scaling factor to prevent mouth distortion when mouthOpen is high
    // If mouthOpen + emotionWeight > maxCombinedWeight, scale down facial emotion weight
    let maxWeight = 0;
    for (const key of this.targetWeights.keys()) {
      const current = this.currentWeights.get(key) || 0;
      const target = this.targetWeights.get(key) || 0;
      const next = current + (target - current) * Math.min(1, step);
      this.currentWeights.set(key, next);
      if (next > maxWeight) maxWeight = next;
    }

    // Update active currentEmotion label if close enough to target
    if (Math.abs(maxWeight - (EMOTION_PRESETS[this.targetEmotion].happy ?? 0)) < 0.05) {
      this.currentEmotion = this.targetEmotion;
    }

    // Talking envelope: rise fast on speech, fall slowly through pauses
    const talking = mouthOpen > SPEAKING_MOUTH_THRESHOLD ? 1 : 0;
    const envSec = talking > this.speakingEnvelope ? SPEAKING_ATTACK_SEC : SPEAKING_RELEASE_SEC;
    this.speakingEnvelope += (talking - this.speakingEnvelope) * Math.min(1, deltaTime / envSec);

    // Tone the emotion down while talking so the lip-sync visemes stay visible
    const speakingScale = this.config.speakingEmotionScale ?? DEFAULT_SPEAKING_EMOTION_SCALE;
    let emotionDamping = 1 - (1 - speakingScale) * this.speakingEnvelope;

    // Keep emotion + mouth within the combined budget
    const mouthBudget = Math.max(0, this.config.maxCombinedWeight - mouthOpen);
    if (maxWeight * emotionDamping > mouthBudget && maxWeight > 0) {
      emotionDamping = mouthBudget / maxWeight;
    }

    // Apply interpolated values to VRM expressions
    for (const [key, rawWeight] of this.currentWeights.entries()) {
      const finalWeight = rawWeight * emotionDamping;
      this.adapter.setValue(this.vrm, key, finalWeight);
    }
  }
}
