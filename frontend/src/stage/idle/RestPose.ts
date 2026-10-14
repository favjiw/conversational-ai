import type { VRM } from '@pixiv/three-vrm';

/**
 * Applies natural standing rest pose (arms down) to VRM normalized bone nodes.
 * Replaces default T-pose / A-pose.
 */
export class RestPose {
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

    // Left arm down: rotate around Z axis to bring arm downwards
    const leftUpperArm = humanoid.getNormalizedBoneNode('leftUpperArm');
    if (leftUpperArm) {
      leftUpperArm.rotation.set(0.12 * xSign, -0.05, -1.18 * zSign);
    }

    // Right arm down: rotate around Z axis to bring arm downwards
    const rightUpperArm = humanoid.getNormalizedBoneNode('rightUpperArm');
    if (rightUpperArm) {
      rightUpperArm.rotation.set(0.12 * xSign, 0.05, 1.18 * zSign);
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

