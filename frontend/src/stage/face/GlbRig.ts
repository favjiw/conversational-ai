import * as THREE from 'three';

/** Bone names a GLB rig needs for the rest pose and idle motion. */
export interface GlbBoneMap {
  spine: string;
  neck: string;
  head: string;
  leftUpperArm: string;
  leftForearm: string;
  leftHand: string;
  rightUpperArm: string;
  rightForearm: string;
  rightHand: string;
}

/** 3ds Max Biped names as exported by Microsoft Rocketbox (three.js turns spaces into "_"). */
export const ROCKETBOX_BONES: GlbBoneMap = {
  spine: 'Bip01_Spine2',
  neck: 'Bip01_Neck',
  head: 'Bip01_Head',
  leftUpperArm: 'Bip01_L_UpperArm',
  leftForearm: 'Bip01_L_Forearm',
  leftHand: 'Bip01_L_Hand',
  rightUpperArm: 'Bip01_R_UpperArm',
  rightForearm: 'Bip01_R_Forearm',
  rightHand: 'Bip01_R_Hand',
};

/**
 * Presenter pose directions in the character's own space (+Z = facing the
 * camera, +X = the character's left): upper arms hang down and slightly out,
 * forearms reach forward so the hands rest on the desk.
 */
const UPPER_ARM_DIR = (side: number) => new THREE.Vector3(side * 0.22, -1, 0.12).normalize();
const FOREARM_DIR = (side: number) => new THREE.Vector3(side * 0.08, -0.3, 1).normalize();

const _a = new THREE.Vector3();
const _b = new THREE.Vector3();
const _q = new THREE.Quaternion();
const _parentQ = new THREE.Quaternion();
const _boneQ = new THREE.Quaternion();
const _euler = new THREE.Euler();

/**
 * Rotate `bone` so the segment bone -> child points along `worldDir`.
 * Works on any rig regardless of how its bone axes are oriented.
 */
function aimBone(bone: THREE.Object3D, child: THREE.Object3D, worldDir: THREE.Vector3): void {
  bone.updateWorldMatrix(true, true);
  bone.getWorldPosition(_a);
  child.getWorldPosition(_b);
  const current = _b.sub(_a).normalize();
  _q.setFromUnitVectors(current, worldDir);
  bone.getWorldQuaternion(_boneQ);
  _boneQ.premultiply(_q);
  if (bone.parent) {
    bone.parent.getWorldQuaternion(_parentQ);
    _boneQ.premultiply(_parentQ.invert());
  }
  bone.quaternion.copy(_boneQ);
  bone.updateWorldMatrix(false, true);
}

function find(root: THREE.Object3D, name: string): THREE.Object3D | undefined {
  return root.getObjectByName(name);
}

/**
 * Seated-presenter rest pose for a GLB rig (arms down, hands forward on the
 * desk). Returns false when the rig lacks the needed bones.
 */
export function applyGlbRestPose(root: THREE.Object3D, bones: GlbBoneMap): boolean {
  root.updateWorldMatrix(true, true);
  const rootQ = root.getWorldQuaternion(new THREE.Quaternion());
  let ok = true;
  for (const side of [1, -1] as const) {
    const upper = find(root, side === 1 ? bones.leftUpperArm : bones.rightUpperArm);
    const fore = find(root, side === 1 ? bones.leftForearm : bones.rightForearm);
    const hand = find(root, side === 1 ? bones.leftHand : bones.rightHand);
    if (!upper || !fore || !hand) {
      ok = false;
      continue;
    }
    aimBone(upper, fore, UPPER_ARM_DIR(side).applyQuaternion(rootQ));
    aimBone(fore, hand, FOREARM_DIR(side).applyQuaternion(rootQ));
  }
  return ok;
}

export interface GlbBodyIdleConfig {
  headSway: number; // 0 - 1
  breath: number; // 0 - 1
}

/**
 * Subtle body life for GLB rigs: breathing on the upper spine and a slow,
 * layered head sway, applied as offsets on top of the rest pose. Talking adds
 * a little more head motion.
 */
export class GlbBodyIdle {
  private root: THREE.Object3D;
  private spine?: THREE.Object3D;
  private neck?: THREE.Object3D;
  private head?: THREE.Object3D;
  private base = new Map<THREE.Object3D, THREE.Quaternion>();
  private t = Math.random() * 100;
  private config: GlbBodyIdleConfig;
  /** Set while this character's audio is playing. */
  isSpeaking = false;
  /** Set while the other presenter is talking: occasional small nods. */
  isListening = false;
  private nodT = -1;
  private nextNodIn = 2;
  private speakingAmount = 0;

  constructor(root: THREE.Object3D, bones: GlbBoneMap, config: GlbBodyIdleConfig) {
    this.config = config;
    this.root = root;
    this.spine = find(root, bones.spine);
    this.neck = find(root, bones.neck);
    this.head = find(root, bones.head);
    for (const b of [this.spine, this.neck, this.head]) {
      if (b) this.base.set(b, b.quaternion.clone());
    }
  }

  setConfig(config: Partial<GlbBodyIdleConfig>): void {
    this.config = { ...this.config, ...config };
  }

  update(deltaTime: number): void {
    this.t += deltaTime;
    this.speakingAmount += ((this.isSpeaking ? 1 : 0) - this.speakingAmount) * Math.min(1, deltaTime * 3);
    const t = this.t;
    const sway = this.config.headSway * (1 + this.speakingAmount * 0.8);

    // Breathing: ~0.25 Hz pitch on the upper spine
    this.offset(this.spine, Math.sin(t * 1.6) * 0.012 * this.config.breath, 0, 0);
    // Head: layered sines read as natural drift rather than a loop
    const yaw = (Math.sin(t * 0.43) * 0.6 + Math.sin(t * 1.13) * 0.4) * 0.05 * sway;
    const pitch = (Math.sin(t * 0.61 + 1.7) * 0.6 + Math.sin(t * 2.3) * 0.25 * this.speakingAmount) * 0.035 * sway;
    const roll = Math.sin(t * 0.37 + 0.5) * 0.02 * sway;
    const nod = this.updateNod(deltaTime);
    this.offset(this.neck, pitch * 0.4, yaw * 0.4, roll * 0.4);
    this.offset(this.head, pitch * 0.6 + nod, yaw * 0.6, roll * 0.6);
  }

  /** Listening nod: a quick ~0.6 s dip of the head every few seconds. */
  private updateNod(deltaTime: number): number {
    if (this.nodT < 0) {
      if (!this.isListening) return 0;
      this.nextNodIn -= deltaTime;
      if (this.nextNodIn <= 0) this.nodT = 0;
      return 0;
    }
    this.nodT += deltaTime;
    if (this.nodT > 0.6) {
      this.nodT = -1;
      this.nextNodIn = 2.5 + Math.random() * 4;
      return 0;
    }
    return Math.sin((this.nodT / 0.6) * Math.PI) * 0.06 * this.config.headSway / 0.3;
  }

  /**
   * Apply a small rotation offset (rad) around the character's own axes
   * (x = nod, y = turn, z = tilt) on top of the bone's base pose. Rig bone
   * axes vary (Biped bones point along X), so the offset is expressed in
   * character space and converted into the bone's parent space.
   */
  private offset(bone: THREE.Object3D | undefined, x: number, y: number, z: number): void {
    if (!bone || !bone.parent) return;
    const base = this.base.get(bone)!;
    this.root.getWorldQuaternion(_boneQ);
    // Offset in world space = root * local-euler * root^-1
    _q.setFromEuler(_euler.set(x, y, z)).premultiply(_boneQ);
    _q.multiply(_boneQ.invert());
    // Into the parent's space: parent^-1 * world * parent
    bone.parent.getWorldQuaternion(_parentQ);
    _q.premultiply(_parentQ.clone().invert()).multiply(_parentQ);
    bone.quaternion.copy(_q).multiply(base);
  }
}
