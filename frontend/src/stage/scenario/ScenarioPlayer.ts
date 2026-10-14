import type { AudioManager } from '../audio/AudioManager';
import type { ExpressionDriver, EmotionType } from '../expression/ExpressionDriver';
import type { IdleManager } from '../idle/IdleManager';

export interface ScenarioTurn {
  persona: string;
  text: string;
  emotion: EmotionType;
  audio?: string;
}

export interface ScenarioData {
  id: string;
  title: string;
  characters: Record<string, { name: string; model: string; voice?: string }>;
  turns: ScenarioTurn[];
}

export type PlayerState = 'idle' | 'playing' | 'paused' | 'ended';

export class ScenarioPlayer {
  private audioManager: AudioManager;
  private drivers: Map<string, ExpressionDriver>;
  private idleManagers: Map<string, IdleManager>;

  private currentScenario: ScenarioData | null = null;
  private currentTurnIndex = 0;
  private state: PlayerState = 'idle';
  private timerId: number | null = null;

  public onTurnChange?: (turn: ScenarioTurn, index: number, total: number) => void;
  public onStateChange?: (state: PlayerState) => void;
  public onSpeakingChange?: (persona: string | null) => void;

  constructor(
    audioManager: AudioManager,
    drivers: Map<string, ExpressionDriver>,
    idleManagers: Map<string, IdleManager>
  ) {
    this.audioManager = audioManager;
    this.drivers = drivers;
    this.idleManagers = idleManagers;
  }

  loadScenario(scenario: ScenarioData): void {
    this.stop();
    this.currentScenario = scenario;
    this.currentTurnIndex = 0;
    this.setState('idle');
  }

  getScenario(): ScenarioData | null {
    return this.currentScenario;
  }

  getState(): PlayerState {
    return this.state;
  }

  getCurrentTurnIndex(): number {
    return this.currentTurnIndex;
  }

  getTotalTurns(): number {
    return this.currentScenario?.turns.length ?? 0;
  }

  private setState(newState: PlayerState): void {
    this.state = newState;
    this.onStateChange?.(newState);
  }

  async play(): Promise<void> {
    if (!this.currentScenario || this.currentScenario.turns.length === 0) return;

    if (this.state === 'ended') {
      this.currentTurnIndex = 0;
    }

    this.setState('playing');
    await this.executeTurn(this.currentTurnIndex);
  }

  pause(): void {
    if (this.state !== 'playing') return;
    this.clearTimer();
    this.audioManager.stop();
    for (const idle of this.idleManagers.values()) {
      idle.isSpeaking = false;
    }
    this.onSpeakingChange?.(null);
    this.setState('paused');
  }

  restart(): void {
    this.stop();
    this.currentTurnIndex = 0;
    this.play();
  }

  stop(): void {
    this.clearTimer();
    this.audioManager.stop();
    for (const idle of this.idleManagers.values()) {
      idle.isSpeaking = false;
    }
    this.onSpeakingChange?.(null);
    this.setState('idle');
  }

  jumpToTurn(turnIndex: number): void {
    if (!this.currentScenario) return;
    if (turnIndex < 0 || turnIndex >= this.currentScenario.turns.length) return;

    const wasPlaying = this.state === 'playing';
    this.stop();
    this.currentTurnIndex = turnIndex;

    if (wasPlaying) {
      this.play();
    } else {
      const turn = this.currentScenario.turns[turnIndex];
      this.onTurnChange?.(turn, turnIndex, this.currentScenario.turns.length);
    }
  }

  private clearTimer(): void {
    if (this.timerId !== null) {
      window.clearTimeout(this.timerId);
      this.timerId = null;
    }
  }

  private async executeTurn(index: number): Promise<void> {
    if (!this.currentScenario || this.state !== 'playing') return;

    if (index >= this.currentScenario.turns.length) {
      this.setState('ended');
      for (const idle of this.idleManagers.values()) {
        idle.isSpeaking = false;
      }
      return;
    }

    const turn = this.currentScenario.turns[index];
    this.currentTurnIndex = index;
    this.onTurnChange?.(turn, index, this.currentScenario.turns.length);

    // Set persona emotion
    const driver = this.drivers.get(turn.persona);
    if (driver) {
      driver.setEmotion(turn.emotion);
    }

    // Update speaking flag for idle micro-movements
    for (const [persona, idle] of this.idleManagers.entries()) {
      idle.isSpeaking = persona === turn.persona;
    }
    this.onSpeakingChange?.(turn.persona);

    if (turn.audio) {
      try {
        const audioUrl = turn.audio.startsWith('/') ? turn.audio : `/${turn.audio}`;
        this.audioManager.setOnTurnEnd(() => {
          if (this.state === 'playing' && this.currentTurnIndex === index) {
            const idle = this.idleManagers.get(turn.persona);
            if (idle) idle.isSpeaking = false;
            this.onSpeakingChange?.(null);

            this.clearTimer();
            this.timerId = window.setTimeout(() => {
              if (this.state === 'playing') {
                this.executeTurn(index + 1);
              }
            }, 350);
          }
        });

        await this.audioManager.playAudio(turn.persona, audioUrl);
      } catch (err) {
        console.error(`[ScenarioPlayer] Failed to play turn audio: ${turn.audio}`, err);
        const duration = Math.max(2000, turn.text.length * 60);
        this.clearTimer();
        this.timerId = window.setTimeout(() => {
          if (this.state === 'playing' && this.currentTurnIndex === index) {
            this.onSpeakingChange?.(null);
            this.executeTurn(index + 1);
          }
        }, duration);
      }
    } else {
      const duration = Math.max(2000, turn.text.length * 60);
      this.clearTimer();
      this.timerId = window.setTimeout(() => {
        if (this.state === 'playing' && this.currentTurnIndex === index) {
          this.onSpeakingChange?.(null);
          this.executeTurn(index + 1);
        }
      }, duration);
    }
  }
}

