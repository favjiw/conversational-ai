import type { VRM } from '@pixiv/three-vrm';
import type * as THREE from 'three';

/**
 * Calm "groove" while a song plays (animation/VRM style): the torso sways a little left-right,
 * the head nods on the beat and follows the sway, and the hands stay low with a small
 * alternating swing. Applied on top of RestPose + idle every frame, eased in/out so the
 * presenters settle back smoothly when the song ends. Values can be overridden in
 * avatar.config.json ("groove").
 */
export interface GrooveConfig {
  /** Tempo of the movement (no beat detection: Deezer previews are not analysed). */
  bpm: number;
  /** Torso turn left-right (radians, around the vertical axis). */
  torsoYaw: number;
  /** Torso side sway (radians). */
  torsoRoll: number;
  /** Head nod on each beat (radians). */
  headNod: number;
  /** Extra head turn following the torso (radians). */
  headYaw: number;
  /** Overall arm movement (0 = arms stay down). */
  arms: number;
  /** Upper arm swing forward (radians). */
  armForward: number;
  /** Upper arm lift away from the body (radians). */
  armOut: number;
  /** Elbow bend (radians). */
  elbowBend: number;
  /** Finger curl per joint (radians): relaxed hands instead of flat palms. */
  fingerCurl: number;
  /** Alternating arm swing on the beat (radians). */
  armSwing: number;
  /** Seconds to blend in/out. */
  blendSec: number;
}

export const DEFAULT_GROOVE: GrooveConfig = {
  bpm: 92,
  torsoYaw: 0.06,
  torsoRoll: 0.03,
  headNod: 0.05,
  headYaw: 0.05,
  arms: 1,
  armForward: 0.08,
  armOut: 0,
  elbowBend: 0.25,
  fingerCurl: 0.2,
  armSwing: 0.06,
  blendSec: 0.8,
};

const FINGERS = ['Index', 'Middle', 'Ring', 'Little'] as const;
const JOINTS = ['Proximal', 'Intermediate', 'Distal'] as const;

export class MusicGroove {
  private config: GrooveConfig;
  private weight = 0;
  private phase: number;

  /** True while song audio is playing. */
  public active = false;

  constructor(config: Partial<GrooveConfig> = {}, phaseOffset = 0) {
    this.config = { ...DEFAULT_GROOVE, ...config };
    this.phase = phaseOffset;
  }

  setConfig(config: Partial<GrooveConfig>): void {
    Object.assign(this.config, config);
  }

  get isMoving(): boolean {
    return this.weight > 0.001;
  }

  /** Call after RestPose and the idle layers have written the bones for this frame. */
  update(deltaTime: number, vrm: VRM): void {
    const target = this.active ? 1 : 0;
    const step = deltaTime / Math.max(0.05, this.config.blendSec);
    this.weight = target > this.weight ? Math.min(target, this.weight + step) : Math.max(target, this.weight - step);
    if (!this.isMoving) return;

    const humanoid = vrm.humanoid;
    if (!humanoid) return;

    const beat = (this.config.bpm / 60) * Math.PI * 2; // radians per second, one cycle per beat
    this.phase += deltaTime * beat;
    // Smooth ease so the motion does not start/stop abruptly.
    const w = this.weight * this.weight * (3 - 2 * this.weight);

    const isVRM0 = vrm.meta?.metaVersion === '0';
    const xSign = isVRM0 ? -1 : 1;
    const zSign = isVRM0 ? -1 : 1;

    // Torso: turn left-right once every two beats, with a slight side sway.
    const turn = Math.sin(this.phase / 2);
    const bounce = Math.abs(Math.sin(this.phase)); // 0..1 on every beat
    const spine = humanoid.getNormalizedBoneNode('spine');
    const chest = humanoid.getNormalizedBoneNode('chest') ?? humanoid.getNormalizedBoneNode('upperChest');
    if (spine) {
      spine.rotation.y += turn * this.config.torsoYaw * 0.6 * w;
      spine.rotation.z += turn * this.config.torsoRoll * zSign * w;
    }
    if (chest) {
      chest.rotation.y += turn * this.config.torsoYaw * 0.4 * w;
      chest.rotation.x += bounce * 0.02 * xSign * w;
    }

    // Head: nod on the beat and look a little further into the turn.
    const head = humanoid.getNormalizedBoneNode('head');
    const neck = humanoid.getNormalizedBoneNode('neck');
    const nod = (bounce - 0.5) * this.config.headNod;
    if (neck) {
      neck.rotation.x += nod * 0.4 * xSign * w;
      neck.rotation.y += turn * this.config.headYaw * 0.4 * w;
    }
    if (head) {
      head.rotation.x += nod * 0.6 * xSign * w;
      head.rotation.y += turn * this.config.headYaw * 0.6 * w;
      head.rotation.z += -turn * 0.03 * zSign * w;
    }

    // Arms: hands stay low, slightly forward with a small alternating swing on the beat.
    // Upper arm forward is -x * xSign (measured on both VRM versions; opposite of RestPose's x).
    const c = this.config;
    const a = c.arms * w;
    if (a <= 0) return;
    const pumpL = Math.sin(this.phase);
    const pumpR = Math.sin(this.phase + Math.PI);
    const leftUpper = humanoid.getNormalizedBoneNode('leftUpperArm');
    const rightUpper = humanoid.getNormalizedBoneNode('rightUpperArm');
    const leftLower = humanoid.getNormalizedBoneNode('leftLowerArm');
    const rightLower = humanoid.getNormalizedBoneNode('rightLowerArm');
    const leftHand = humanoid.getNormalizedBoneNode('leftHand');
    const rightHand = humanoid.getNormalizedBoneNode('rightHand');
    if (leftUpper) {
      leftUpper.rotation.x += -(c.armForward + pumpL * c.armSwing) * xSign * a; // forward
      leftUpper.rotation.z += c.armOut * zSign * a; // away from the body
    }
    if (rightUpper) {
      rightUpper.rotation.x += -(c.armForward + pumpR * c.armSwing) * xSign * a;
      rightUpper.rotation.z += -c.armOut * zSign * a;
    }
    // Elbow flexion forward: left -y, right +y on both VRM 0.x and 1.0 normalized bones
    // (measured: forearm moves toward the camera).
    if (leftLower) leftLower.rotation.y += -(c.elbowBend + pumpL * c.armSwing * 2) * a;
    if (rightLower) rightLower.rotation.y += (c.elbowBend + pumpR * c.armSwing * 2) * a;
    if (leftHand) leftHand.rotation.z += pumpL * c.armSwing * zSign * a;
    if (rightHand) rightHand.rotation.z += -pumpR * c.armSwing * zSign * a;

    // Relaxed fingers: curl the four fingers (tip toward the palm). Left -z, right +z (zSign for VRM 0.x).
    const curl = c.fingerCurl * a;
    if (curl > 0) {
      for (const finger of FINGERS) {
        for (const joint of JOINTS) {
          const l = humanoid.getNormalizedBoneNode(`left${finger}${joint}` as never) as THREE.Object3D | null;
          const r = humanoid.getNormalizedBoneNode(`right${finger}${joint}` as never) as THREE.Object3D | null;
          if (l) l.rotation.z = -curl * zSign;
          if (r) r.rotation.z = curl * zSign;
        }
      }
    }
  }
}
