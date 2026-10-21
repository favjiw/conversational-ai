import * as THREE from 'three';
import type { VRM } from '@pixiv/three-vrm';

/** Default arm-down rotation (radians from T-pose) when a model has not been calibrated. */
const DEFAULT_ARM_DOWN = 1.18;
/** Target angle of the upper arm from vertical after calibration (degrees). */
export const DEFAULT_ARM_DOWN_DEG = 10;

// Per-model arm-down rotation found by RestPose.calibrate (models differ: red-male vs female).
const armDown = new WeakMap<VRM, number>();
const _shoulder = new THREE.Vector3();
const _elbow = new THREE.Vector3();

/**
 * Applies natural standing rest pose (arms down) to VRM normalized bone nodes.
 * Replaces default T-pose / A-pose.
 */
export class RestPose {
  /**
   * Find, once per model, how far the upper arms must rotate so they hang about
   * `targetDeg` degrees from vertical. A fixed angle left some models (female.vrm)
   * in an A-pose.
   */
  static calibrate(vrm: VRM, targetDeg = DEFAULT_ARM_DOWN_DEG): number {
    const humanoid = vrm.humanoid;
    const upper = humanoid?.getNormalizedBoneNode('leftUpperArm');
    const lower = humanoid?.getNormalizedBoneNode('leftLowerArm');
    if (!upper || !lower) return DEFAULT_ARM_DOWN;

    const zSign = vrm.meta?.metaVersion === '0' ? -1 : 1;
    const saved = upper.rotation.clone();
    const target = THREE.MathUtils.degToRad(targetDeg);
    const angleFor = (down: number): number => {
      upper.rotation.set(saved.x, saved.y, -down * zSign);
      upper.getWorldPosition(_shoulder);
      lower.getWorldPosition(_elbow);
      const dir = _elbow.sub(_shoulder).normalize();
      return Math.acos(THREE.MathUtils.clamp(-dir.y, -1, 1)); // 0 = straight down
    };

    // More rotation = arm closer to the body; binary search for the target angle.
    let lo = 0.6;
    let hi = 1.75;
    for (let i = 0; i < 16; i++) {
      const mid = (lo + hi) / 2;
      if (angleFor(mid) > target) lo = mid;
      else hi = mid;
    }
    upper.rotation.copy(saved);
    const value = Number.isFinite(lo) ? (lo + hi) / 2 : DEFAULT_ARM_DOWN;
    armDown.set(vrm, value);
    return value;
  }

  /**
   * Applies the resting arm pose to the given VRM model.
   * Handles coordinate system orientation differences between VRM 0.x and VRM 1.0 models.
   */
  static apply(vrm: VRM): void {
    const humanoid = vrm.humanoid;
    if (!humanoid) return;

    // VRM 0.x models face +Z (Unity standard), whereas VRM 1.0 models face -Z (glTF standard).
    // The normalized bone coordinate systems are rotated 180 degrees around Y: (x, y, z) -> (-x, y, -z).
    // Consequently, Euler rotation angles around X and Z axes are inverted for VRM 0.x.
    const isVRM0 = vrm.meta?.metaVersion === '0';
    const xSign = isVRM0 ? -1 : 1;
    const zSign = isVRM0 ? -1 : 1;
    const down = armDown.get(vrm) ?? DEFAULT_ARM_DOWN;

    // Left arm down: rotate around Z axis to bring arm downwards
    const leftUpperArm = humanoid.getNormalizedBoneNode('leftUpperArm');
    if (leftUpperArm) {
      leftUpperArm.rotation.set(0.12 * xSign, -0.05, -down * zSign);
    }

    // Right arm down: rotate around Z axis to bring arm downwards
    const rightUpperArm = humanoid.getNormalizedBoneNode('rightUpperArm');
    if (rightUpperArm) {
      rightUpperArm.rotation.set(0.12 * xSign, 0.05, down * zSign);
    }

    // Natural slight elbow bend (~12 degrees)
    const leftLowerArm = humanoid.getNormalizedBoneNode('leftLowerArm');
    if (leftLowerArm) {
      leftLowerArm.rotation.set(0.1 * xSign, 0, 0.2 * zSign);
    }

    const rightLowerArm = humanoid.getNormalizedBoneNode('rightLowerArm');
    if (rightLowerArm) {
      rightLowerArm.rotation.set(0.1 * xSign, 0, -0.2 * zSign);
    }

    // Natural hand relaxation
    const leftHand = humanoid.getNormalizedBoneNode('leftHand');
    if (leftHand) {
      leftHand.rotation.set(0.05 * xSign, 0, 0.05 * zSign);
    }

    const rightHand = humanoid.getNormalizedBoneNode('rightHand');
    if (rightHand) {
      rightHand.rotation.set(0.05 * xSign, 0, -0.05 * zSign);
    }
  }
}
