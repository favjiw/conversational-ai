import { GUI } from 'lil-gui';
import type { LipSyncConfig } from '../lipsync/LipSyncLevel1';
import type { ExpressionConfig, EmotionType } from '../expression/ExpressionDriver';
import type { IdleConfig } from '../idle/IdleManager';

export interface DebugConfig {
  quality: 'low' | 'medium' | 'high';
  lipsync: LipSyncConfig;
  expression: ExpressionConfig & {
    personaAEmotion: EmotionType;
    personaBEmotion: EmotionType;
  };
  idle: IdleConfig;
  showPanel: boolean;
}

export class DebugPanel {
  private gui: GUI;
  private config: DebugConfig;
  private callbacks: Map<string, (value: any) => void>;

  constructor(initialConfig: DebugConfig) {
    this.config = initialConfig;
    this.callbacks = new Map();
    this.gui = new GUI({ title: 'Avatar Debug' });

    this.setupGUI();
  }

  private setupGUI() {
    // Quality folder
    const qualityFolder = this.gui.addFolder('Kualitas Render');
    qualityFolder.add(this.config, 'quality', ['low', 'medium', 'high'])
      .name('Kualitas')
      .onChange((value: string) => this.emit('quality', value));
    qualityFolder.close();

    // Lip-sync settings
    const lipsyncFolder = this.gui.addFolder('Lip-Sync');
    lipsyncFolder.add(this.config.lipsync, 'gain', 0.5, 3.0, 0.1)
      .name('Gain')
      .onChange(() => this.emit('lipsync', this.config.lipsync));
    lipsyncFolder.add(this.config.lipsync, 'gate', 0, 0.1, 0.001)
      .name('Noise Gate')
      .onChange(() => this.emit('lipsync', this.config.lipsync));
    lipsyncFolder.add(this.config.lipsync, 'attackMs', 10, 200, 1)
      .name('Attack (ms)')
      .onChange(() => this.emit('lipsync', this.config.lipsync));
    lipsyncFolder.add(this.config.lipsync, 'releaseMs', 50, 300, 1)
      .name('Release (ms)')
      .onChange(() => this.emit('lipsync', this.config.lipsync));
    lipsyncFolder.close();

    // FR-5 Expression folder
    const emotions: EmotionType[] = [
      'neutral',
      'happy',
      'excited',
      'surprised',
      'sad',
      'thoughtful',
      'empathetic',
    ];

    const exprFolder = this.gui.addFolder('FR-5 Ekspresi Emosi');
    exprFolder.add(this.config.expression, 'personaAEmotion', emotions)
      .name('Emosi Raka (A)')
      .onChange((val: EmotionType) => this.emit('emotion_a', val));
    exprFolder.add(this.config.expression, 'personaBEmotion', emotions)
      .name('Emosi Salsa (B)')
      .onChange((val: EmotionType) => this.emit('emotion_b', val));
    exprFolder.add(this.config.expression, 'transitionMs', 100, 800, 10)
      .name('Transisi (ms)')
      .onChange(() => this.emit('expression_config', this.config.expression));
    exprFolder.add(this.config.expression, 'maxCombinedWeight', 0.5, 1.5, 0.05)
      .name('Batas Total Bobot')
      .onChange(() => this.emit('expression_config', this.config.expression));
    exprFolder.open();

    // FR-6 Idle folder
    const idleFolder = this.gui.addFolder('FR-6 Animasi Idle');
    idleFolder.add(this.config.idle, 'blinkMinSec', 0.5, 5.0, 0.5)
      .name('Kedip Min (dtk)')
      .onChange(() => this.emit('idle_config', this.config.idle));
    idleFolder.add(this.config.idle, 'blinkMaxSec', 2.0, 10.0, 0.5)
      .name('Kedip Max (dtk)')
      .onChange(() => this.emit('idle_config', this.config.idle));
    idleFolder.add(this.config.idle, 'headSway', 0.0, 1.0, 0.05)
      .name('Gerak Kepala')
      .onChange(() => this.emit('idle_config', this.config.idle));
    idleFolder.add(this.config.idle, 'breath', 0.0, 1.0, 0.05)
      .name('Kekuatan Nafas')
      .onChange(() => this.emit('idle_config', this.config.idle));
    idleFolder.open();

    // Controls folder
    const controlsFolder = this.gui.addFolder('Kontrol');
    controlsFolder.add({ hidePanel: () => this.hide() }, 'hidePanel')
      .name('Sembunyikan Panel');
    controlsFolder.close();
  }

  setEmotionA(emotion: EmotionType) {
    this.config.expression.personaAEmotion = emotion;
    this.gui.controllersRecursive().find(c => c.property === 'personaAEmotion')?.updateDisplay();
  }

  setEmotionB(emotion: EmotionType) {
    this.config.expression.personaBEmotion = emotion;
    this.gui.controllersRecursive().find(c => c.property === 'personaBEmotion')?.updateDisplay();
  }

  on(event: string, callback: (value: any) => void) {
    this.callbacks.set(event, callback);
  }

  private emit(event: string, value: any) {
    const callback = this.callbacks.get(event);
    if (callback) {
      callback(value);
    }
  }

  show() {
    this.gui.show();
    this.config.showPanel = true;
  }

  hide() {
    this.gui.hide();
    this.config.showPanel = false;
  }

  toggle() {
    if (this.config.showPanel) {
      this.hide();
    } else {
      this.show();
    }
  }

  dispose() {
    this.gui.destroy();
  }
}

