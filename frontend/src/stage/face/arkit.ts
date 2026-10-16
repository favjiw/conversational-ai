/**
 * The 52 ARKit face blendshape names, exactly as Apple spells them
 * (case-sensitive). Realistic GLB characters must expose morph targets with
 * these names for FaceDriver to animate them.
 */
export const ARKIT_BLENDSHAPES = [
  // Brows
  'browInnerUp', 'browDownLeft', 'browDownRight', 'browOuterUpLeft', 'browOuterUpRight',
  // Eyes
  'eyeLookUpLeft', 'eyeLookUpRight', 'eyeLookDownLeft', 'eyeLookDownRight',
  'eyeLookInLeft', 'eyeLookInRight', 'eyeLookOutLeft', 'eyeLookOutRight',
  'eyeBlinkLeft', 'eyeBlinkRight', 'eyeSquintLeft', 'eyeSquintRight', 'eyeWideLeft', 'eyeWideRight',
  // Cheeks and nose
  'cheekPuff', 'cheekSquintLeft', 'cheekSquintRight', 'noseSneerLeft', 'noseSneerRight',
  // Jaw
  'jawOpen', 'jawForward', 'jawLeft', 'jawRight',
  // Mouth
  'mouthFunnel', 'mouthPucker', 'mouthLeft', 'mouthRight',
  'mouthRollUpper', 'mouthRollLower', 'mouthShrugUpper', 'mouthShrugLower', 'mouthClose',
  'mouthSmileLeft', 'mouthSmileRight', 'mouthFrownLeft', 'mouthFrownRight',
  'mouthDimpleLeft', 'mouthDimpleRight', 'mouthUpperUpLeft', 'mouthUpperUpRight',
  'mouthLowerDownLeft', 'mouthLowerDownRight', 'mouthPressLeft', 'mouthPressRight',
  'mouthStretchLeft', 'mouthStretchRight',
  // Tongue
  'tongueOut',
] as const;

export type ArkitBlendshape = (typeof ARKIT_BLENDSHAPES)[number];

export type BlendshapeWeights = Partial<Record<ArkitBlendshape, number>>;
