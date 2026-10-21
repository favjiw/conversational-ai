import type { VRM } from '@pixiv/three-vrm';

/**
 * VTuber-style motion for the animation (VRM) style.
 *
 * While speaking the head looks left/right to random targets with a matching tilt (eased by a
 * critically damped spring, not a stiff sine), nods with the speech rhythm plus random emphasis
 * nods, and the torso follows part of the turn with a slight lean. While listening the head only
 * sways gently and nods now and then. Applied on top of RestPose + idle every frame (the idle layer
 * resets these bones to zero first), and switched off while the music groove plays.
 */
export interface TalkMotionConfig {
  /** Head look left/right while speaking (radians). */
  headYaw: number;
  /** Head tilt that goes with the look (radians). */
  headRoll: number;
  /** Rhythmic nod while speaking (radians) and its rate (Hz). */
  nod: number;
  nodHz: number;
  /** Emphasis nod size (radians). */
  emphasisNod: number;
  /** Share of the head turn/tilt the torso follows (0..1). */
  torsoFollow: number;
  /** Forward lean while speaking (radians). */
  lean: number;
  /** Seconds between new look targets while speaking. */
  lookMinSec: number;
  lookMaxSec: number;
  /** Listening: gentle look range (radians), nod size and seconds between nods. */
  listenYaw: number;
  listenNod: number;
  listenNodMinSec: number;
  listenNodMaxSec: number;
  /** Seconds to blend between speaking and listening. */
  blendSec: number;
  /** Spring stiffness of the head look (higher = snappier). */
  stiffness: number;
}

export const DEFAULT_TALK_MOTION: TalkMotionConfig = {
  headYaw: 0.22,
  headRoll: 0.1,
  nod: 0.035,
  nodHz: 2.5,
  emphasisNod: 0.07,
  torsoFollow: 0.35,
  lean: 0.03,
  lookMinSec: 1.5,
  lookMaxSec: 3,
  listenYaw: 0.06,
  listenNod: 0.05,
  listenNodMinSec: 3,
  listenNodMaxSec: 6,
  blendSec: 0.5,
  stiffness: 10,
};

const rand = (min: number, max: number) => min + Math.random() * (max - min);

export class TalkMotion {
  private config: TalkMotionConfig;

  /** Set by IdleManager from isSpeaking. */
  public speaking = false;
  /** False while the music groove plays. */
  public enabled = true;

  private speakW = 0;
  private enabledW = 1;

  private yaw = 0;
  private yawVel = 0;
  private roll = 0;
  private rollVel = 0;
  private targetYaw = 0;
  private targetRoll = 0;
  private lookTimer = 0;

  private nodPhase = Math.random() * Math.PI * 2;
  private pulse = 0; // emphasis / listening nod, 0..1 progress
  private pulseActive = false;
  private pulseSize = 0;
  private pulseTimer = rand(1, 3);

  constructor(config: Partial<TalkMotionConfig> = {}) {
    this.config = { ...DEFAULT_TALK_MOTION, ...config };
  }

  setConfig(config: Partial<TalkMotionConfig>): void {
    Object.assign(this.config, config);
  }

  update(deltaTime: number, vrm: VRM): void {
    const c = this.config;
    const dt = Math.min(deltaTime, 0.1);
    const blend = dt / Math.max(0.05, c.blendSec);
    this.speakW += ((this.speaking ? 1 : 0) - this.speakW) * Math.min(1, blend * 3);
    this.enabledW += ((this.enabled ? 1 : 0) - this.enabledW) * Math.min(1, blend * 3);
    const s = this.speakW;
    const g = this.enabledW;
    if (g < 0.001) return;

    const humanoid = vrm.humanoid;
    if (!humanoid) return;

    // New look target: wide while speaking, small while listening.
    this.lookTimer -= dt;
    if (this.lookTimer <= 0) {
      const range = c.listenYaw + (c.headYaw - c.listenYaw) * s;
      this.targetYaw = rand(-range, range);
      // Tilt toward the look side, varying in size (a VTuber head tilts as it turns).
      const tilt = c.headRoll * s + c.headRoll * 0.3 * (1 - s);
      this.targetRoll = Math.sign(this.targetYaw) * rand(0.3, 1) * tilt;
      this.lookTimer = this.speaking ? rand(c.lookMinSec, c.lookMaxSec) : rand(c.lookMaxSec, c.lookMaxSec * 2);
    }

    // Critically damped springs for a smooth, organic look.
    const k = c.stiffness;
    const damp = 2 * Math.sqrt(k);
    this.yawVel += (k * (this.targetYaw - this.yaw) - damp * this.yawVel) * dt;
    this.yaw += this.yawVel * dt;
    this.rollVel += (k * (this.targetRoll - this.roll) - damp * this.rollVel) * dt;
    this.roll += this.rollVel * dt;

    // Nods: rhythmic while speaking, plus emphasis (speaking) or attentive (listening) pulses.
    this.nodPhase += dt * c.nodHz * Math.PI * 2;
    const rhythm = Math.sin(this.nodPhase) * c.nod * (0.6 + 0.4 * Math.sin(this.nodPhase * 0.37)) * s;
    this.pulseTimer -= dt;
    if (!this.pulseActive && this.pulseTimer <= 0) {
      this.pulseActive = true;
      this.pulse = 0;
      this.pulseSize = this.speaking ? c.emphasisNod : c.listenNod;
    }
    let pulseNod = 0;
    if (this.pulseActive) {
      this.pulse += dt / 0.6;
      pulseNod = Math.sin(Math.min(1, this.pulse) * Math.PI) * this.pulseSize;
      if (this.pulse >= 1) {
        this.pulseActive = false;
        this.pulseTimer = this.speaking ? rand(1, 2.5) : rand(c.listenNodMinSec, c.listenNodMaxSec);
      }
    }
    const pitch = (rhythm + pulseNod) * g;
    const yaw = this.yaw * g;
    const roll = this.roll * g;

    const isVRM0 = vrm.meta?.metaVersion === '0';
    const xSign = isVRM0 ? -1 : 1;
    const zSign = isVRM0 ? -1 : 1;

    const neck = humanoid.getNormalizedBoneNode('neck');
    const head = humanoid.getNormalizedBoneNode('head');
    if (neck) {
      neck.rotation.x += pitch * 0.4 * xSign;
      neck.rotation.y += yaw * 0.4;
      neck.rotation.z += roll * 0.4 * zSign;
    }
    if (head) {
      head.rotation.x += pitch * 0.6 * xSign;
      head.rotation.y += yaw * 0.6;
      head.rotation.z += roll * 0.6 * zSign;
    }

    // Torso follows part of the turn/tilt only while speaking, with a slight forward lean.
    const t = c.torsoFollow * s * g;
    const spine = humanoid.getNormalizedBoneNode('spine');
    const chest = humanoid.getNormalizedBoneNode('chest') ?? humanoid.getNormalizedBoneNode('upperChest');
    if (spine) {
      spine.rotation.y += this.yaw * t * 0.6;
      spine.rotation.z += this.roll * t * 0.6 * zSign;
    }
    if (chest) {
      chest.rotation.y += this.yaw * t * 0.4;
      chest.rotation.z += this.roll * t * 0.4 * zSign;
      chest.rotation.x += c.lean * s * g * xSign;
    }
  }
}
