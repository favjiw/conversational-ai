import type { VRM } from '@pixiv/three-vrm';

/**
 * Expression name synonyms mapping across VRM 0.x and VRM 1.0 specifications.
 */
const EXPRESSION_ALIASES: Record<string, string[]> = {
  // Emotions
  happy: ['happy', 'joy'],
  sad: ['sad', 'sorrow'],
  angry: ['angry'],
  relaxed: ['relaxed', 'fun'],
  surprised: ['surprised'],
  neutral: ['neutral'],

  // Vowels (Lip-Sync)
  aa: ['aa', 'a', 'mouth_a'],
  ih: ['ih', 'i', 'mouth_i'],
  ou: ['ou', 'u', 'mouth_u'],
  ee: ['ee', 'e', 'mouth_e'],
  oh: ['oh', 'o', 'mouth_o'],

  // Blinks
  blink: ['blink'],
  blinkLeft: ['blinkLeft', 'blink_l', 'blinkLeftEye'],
  blinkRight: ['blinkRight', 'blink_r', 'blinkRightEye'],

  // Gaze
  lookUp: ['lookUp', 'lookup'],
  lookDown: ['lookDown', 'lookdown'],
  lookLeft: ['lookLeft', 'lookleft'],
  lookRight: ['lookRight', 'lookright'],
};

export class ExpressionAdapter {
  private characterName: string;
  private supportedExpressions: Set<string> = new Set();
  private aliasResolutionMap: Map<string, string> = new Map();

  constructor(characterName: string, vrm: VRM) {
    this.characterName = characterName;
    this.inspectAndRegister(vrm);
  }

  /**
   * Inspects and logs all expressions present on the VRM model.
   * Resolves canonical names to model-supported names.
   */
  private inspectAndRegister(vrm: VRM): void {
    const manager = vrm.expressionManager;
    if (!manager) {
      console.warn(`[ExpressionAdapter] Karakter "${this.characterName}" tidak memiliki ExpressionManager!`);
      return;
    }

    // Inspect all available expression names
    const names: string[] = [];
    for (const expr of manager.expressions) {
      names.push(expr.expressionName);
      this.supportedExpressions.add(expr.expressionName);
    }

    console.log(
      `[ExpressionAdapter] Karakter "${this.characterName}" mendukung ${names.length} ekspresi:`,
      names
    );

    // Build alias resolution map
    for (const [canonicalName, aliases] of Object.entries(EXPRESSION_ALIASES)) {
      for (const alias of aliases) {
        if (this.supportedExpressions.has(alias)) {
          this.aliasResolutionMap.set(canonicalName, alias);
          break;
        }
      }
    }
  }

  /**
   * Returns the actual expression name registered in the model for the given canonical name, or null.
   */
  resolveExpressionName(canonicalName: string): string | null {
    if (this.aliasResolutionMap.has(canonicalName)) {
      return this.aliasResolutionMap.get(canonicalName)!;
    }
    if (this.supportedExpressions.has(canonicalName)) {
      return canonicalName;
    }
    return null;
  }

  /**
   * Sets the expression weight safely using resolved name and clamp [0, 1].
   */
  setValue(vrm: VRM, canonicalName: string, weight: number): boolean {
    const manager = vrm.expressionManager;
    if (!manager) return false;

    const actualName = this.resolveExpressionName(canonicalName);
    if (!actualName) return false;

    manager.setValue(actualName, Math.max(0, Math.min(1, weight)));
    return true;
  }

  /**
   * Gets the expression weight safely.
   */
  getValue(vrm: VRM, canonicalName: string): number {
    const manager = vrm.expressionManager;
    if (!manager) return 0;

    const actualName = this.resolveExpressionName(canonicalName);
    if (!actualName) return 0;

    return manager.getValue(actualName) ?? 0;
  }
}
