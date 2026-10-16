import { VRM } from '@pixiv/three-vrm';

export interface LipSyncConfig {
  gain: number;
  gate: number; // noise gate threshold
  attackMs: number;
  releaseMs: number;
}

export class LipSyncLevel1 {
  private config: LipSyncConfig;
  private currentMouthOpen = 0;
  private targetMouthOpen = 0;
  
  constructor(config: LipSyncConfig) {
    this.config = config;
  }
  
  updateConfig(config: Partial<LipSyncConfig>) {
    this.config = { ...this.config, ...config };
  }
  getMouthOpen(): number {
    return this.currentMouthOpen;
  }
  

  
  /** Pass vrm = null to only compute the mouth level (GLB characters read it via getMouthOpen). */
  update(vrm: VRM | null, audioLevel: number, deltaTimeMs: number) {
    // Apply gain
    let level = audioLevel * this.config.gain;
    
    // Apply noise gate
    if (level < this.config.gate) {
      level = 0;
    }
    
    // Clamp to [0, 1]
    level = Math.max(0, Math.min(1, level));
    
    // Set target
    this.targetMouthOpen = level;
    
    // Smooth interpolation with attack/release
    const isAttack = this.targetMouthOpen > this.currentMouthOpen;
    const timeConstant = isAttack ? this.config.attackMs : this.config.releaseMs;
    const alpha = Math.min(1, deltaTimeMs / timeConstant);
    
    this.currentMouthOpen += (this.targetMouthOpen - this.currentMouthOpen) * alpha;
    
    // Apply to VRM blendshapes
    if (vrm) this.applyToVRM(vrm);
  }
  
  private applyToVRM(vrm: VRM) {
    const expressionManager = vrm.expressionManager;
    if (!expressionManager) return;
    
    // Map to 'aa' (mouth open) and a bit of 'oh'
    const aaWeight = this.currentMouthOpen;
    const ohWeight = this.currentMouthOpen * 0.3;
    
    // Try different expression name variations for compatibility
    const aaNames = ['aa', 'a', 'mouth_a'];
    const ohNames = ['oh', 'o', 'mouth_o'];
    
    for (const name of aaNames) {
      if (expressionManager.getExpression(name)) {
        expressionManager.setValue(name, aaWeight);
        break;
      }
    }
    
    for (const name of ohNames) {
      if (expressionManager.getExpression(name)) {
        expressionManager.setValue(name, ohWeight);
        break;
      }
    }
  }
  
  reset(vrm: VRM) {
    this.currentMouthOpen = 0;
    this.targetMouthOpen = 0;
    this.applyToVRM(vrm);
  }
}
