import type { AudioManager } from '../audio/AudioManager';
import type { ExpressionDriver, EmotionType } from '../expression/ExpressionDriver';
import type { IdleManager } from '../idle/IdleManager';

export interface LiveTurnData {
  slot_id?: string;
  turn?: number;
  persona: string;
  persona_name?: string;
  text: string;
  emotion?: string;
  audio_url?: string;
  generation?: number;
  session_id?: string;
  playback_id?: string;
}

export interface LiveMusicData {
  slot_id?: string;
  category?: string;
  track: {
    title: string;
    artist: string;
    preview_url?: string;
  };
  preview_sec?: number;
  generation?: number;
  session_id?: string;
  playback_id?: string;
}

export interface LiveSlotData {
  slot_id: string;
  slot_type: string;
  label?: string;
  title?: string;
  artist?: string;
  generation?: number;
}

export class LiveBroadcastAdapter {
  private ws: WebSocket | null = null;
  private wsConnected = false;
  private sessionState: 'idle' | 'running' | 'paused' = 'idle';
  private sessionId: string | null = null;
  private currentGeneration = 0;
  private reconnectTimer: number | null = null;
  private shouldReconnect = true;

  private audioManager: AudioManager;
  private drivers: Map<string, ExpressionDriver>;
  private idleManagers: Map<string, IdleManager>;

  private musicAudio: HTMLAudioElement | null = null;
  private isSkipping = false;

  // Turns play strictly one after another. Clock mode waits for feedback
  // anyway, but session mode (quick test, 36 themes) pushes turns as soon
  // as they are generated.
  private turnQueue: LiveTurnData[] = [];
  private turnPlaying = false;
  private turnTimer: number | null = null;

  // Only the backend-elected audio owner is audible and reports playback.
  private isAudioOwner = false;

  public onConnectionChange?: (connected: boolean) => void;
  public onStateChange?: (state: 'idle' | 'running' | 'paused') => void;
  public onTurnChange?: (turn: { persona: 'persona_a' | 'persona_b'; persona_name: string; text: string; emotion?: string } | null) => void;
  public onSpeakingChange?: (persona: 'persona_a' | 'persona_b' | null) => void;
  public onSlotChange?: (slot: LiveSlotData | null) => void;
  public onMusicChange?: (track: { title: string; artist: string; badge?: string } | null) => void;
  public onMusicProgress?: (percent: number) => void;
  public onCardModeChange?: (mode: 'talk' | 'song') => void;

  constructor(
    audioManager: AudioManager,
    drivers: Map<string, ExpressionDriver>,
    idleManagers: Map<string, IdleManager>
  ) {
    this.audioManager = audioManager;
    this.drivers = drivers;
    this.idleManagers = idleManagers;
  }

  public connect(): void {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.shouldReconnect = true;
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.hostname}:8000/ws/session?role=stage`;

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        this.wsConnected = true;
        this.onConnectionChange?.(true);
      };

      this.ws.onclose = () => {
        this.wsConnected = false;
        this.onConnectionChange?.(false);
        this.ws = null;
        if (this.shouldReconnect) {
          if (this.reconnectTimer !== null) clearTimeout(this.reconnectTimer);
          this.reconnectTimer = window.setTimeout(() => this.connect(), 3000);
        }
      };

      this.ws.onerror = (err) => {
        console.warn('[LiveBroadcastAdapter] WS Error:', err);
      };

      this.ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          this.handleMessage(msg);
        } catch (err) {
          console.warn('[LiveBroadcastAdapter] Message parse error:', err);
        }
      };
    } catch (err) {
      console.warn('[LiveBroadcastAdapter] Connection error:', err);
      if (this.shouldReconnect) {
        if (this.reconnectTimer !== null) clearTimeout(this.reconnectTimer);
        this.reconnectTimer = window.setTimeout(() => this.connect(), 3000);
      }
    }
  }

  private handleMessage(msg: { type: string; data?: any }): void {
    switch (msg.type) {
      case 'status': {
        const state = msg.data?.state || 'idle';
        this.sessionState = state;
        this.sessionId = msg.data?.session_id || null;
        this.onStateChange?.(this.sessionState);

        if (state === 'idle') {
          this.stopCurrentMedia();
          this.setSpeaking(null);
          this.onMusicChange?.(null);
          this.onTurnChange?.(null);
          this.onSlotChange?.(null);
          this.onCardModeChange?.('talk');
        }
        break;
      }

      case 'output_status': {
        this.isAudioOwner = Boolean(msg.data?.is_audio_owner);
        this.audioManager.setMuted(!this.isAudioOwner);
        if (this.musicAudio) this.musicAudio.muted = !this.isAudioOwner;
        break;
      }

      case 'clock_slot_started': {
        this.isSkipping = false;
        if (msg.data?.generation !== undefined) {
          this.currentGeneration = msg.data.generation;
        }
        this.onSlotChange?.(msg.data);

        if (msg.data?.slot_type === 'song') {
          this.onCardModeChange?.('song');
        } else {
          this.onCardModeChange?.('talk');
          this.onMusicChange?.(null);
          if (this.musicAudio) {
            this.musicAudio.pause();
            this.musicAudio.removeAttribute('src');
            this.musicAudio = null;
          }
        }
        break;
      }

      case 'clock_slot_skipped': {
        this.isSkipping = false;
        if (msg.data?.generation !== undefined) {
          this.currentGeneration = msg.data.generation;
        }
        this.stopCurrentMedia();
        this.onTurnChange?.(null);
        this.onSlotChange?.(null);
        break;
      }

      case 'turn': {
        const turnData = msg.data as LiveTurnData;
        if (turnData.generation !== undefined && turnData.generation !== this.currentGeneration) {
          return;
        }
        this.handleTurn(turnData);
        break;
      }

      case 'clock_music': {
        const musicData = msg.data as LiveMusicData;
        if (musicData.generation !== undefined && musicData.generation !== this.currentGeneration) {
          return;
        }
        this.handleMusic(musicData);
        break;
      }

      default:
        break;
    }
  }

  private handleTurn(data: LiveTurnData): void {
    if (this.isSkipping) return;
    this.turnQueue.push(data);
    if (!this.turnPlaying) this.playNextTurn();
  }

  private playNextTurn(): void {
    const data = this.turnQueue.shift();
    if (!data) {
      this.turnPlaying = false;
      return;
    }
    if (data.generation !== undefined && data.generation !== this.currentGeneration) {
      this.playNextTurn();
      return;
    }
    this.turnPlaying = true;
    void this.playTurn(data);
  }

  private async playTurn(data: LiveTurnData): Promise<void> {

    const personaKey: 'persona_a' | 'persona_b' =
      (data.persona === 'persona_b' || data.persona_name?.toLowerCase() === 'salsa')
        ? 'persona_b'
        : 'persona_a';

    const displayName = data.persona_name || (personaKey === 'persona_a' ? 'Raka' : 'Salsa');

    this.onTurnChange?.({
      persona: personaKey,
      persona_name: displayName,
      text: data.text,
      emotion: data.emotion,
    });
    this.onCardModeChange?.('talk');

    const driver = this.drivers.get(personaKey);
    if (driver && data.emotion) {
      driver.setEmotion(data.emotion as EmotionType);
    }

    const idle = this.idleManagers.get(personaKey);
    if (idle) idle.isSpeaking = true;
    const otherKey = personaKey === 'persona_a' ? 'persona_b' : 'persona_a';
    const otherIdle = this.idleManagers.get(otherKey);
    if (otherIdle) otherIdle.isSpeaking = false;

    this.setSpeaking(personaKey);

    const finish = () => {
      if (idle) idle.isSpeaking = false;
      this.setSpeaking(null);
      this.sendFeedback(data, 'ended');
      this.playNextTurn();
    };

    if (data.audio_url) {
      try {
        await this.audioManager.playAudio(personaKey, data.audio_url, finish);
      } catch (err) {
        console.error('[LiveBroadcastAdapter] Turn audio failed:', err);
        finish();
      }
    } else {
      const waitMs = Math.max(2000, (data.text?.length || 20) * 55);
      this.turnTimer = window.setTimeout(() => {
        this.turnTimer = null;
        finish();
      }, waitMs);
    }
  }

  private handleMusic(data: LiveMusicData): void {
    if (this.isSkipping) return;

    const track = data.track || { title: 'Musik Hits', artist: 'HITS Radio' };
    const category = (data.category || 'INDO HITS').toUpperCase();

    this.onMusicChange?.({
      title: track.title,
      artist: track.artist,
      badge: `NOW PLAYING • ${category}`,
    });
    this.onCardModeChange?.('song');
    this.setSpeaking(null);

    for (const idle of this.idleManagers.values()) {
      idle.isSpeaking = false;
    }

    if (track.preview_url) {
      this.playMusicAudio(track.preview_url, data);
    } else {
      this.sendFeedback(data, 'ended');
    }
  }

  private playMusicAudio(url: string, data: LiveMusicData): void {
    if (this.musicAudio) {
      this.musicAudio.pause();
      this.musicAudio.removeAttribute('src');
      this.musicAudio = null;
    }

    const audio = new Audio(url);
    audio.muted = !this.isAudioOwner;
    this.musicAudio = audio;
    const maxSec = data.preview_sec || 30;

    audio.ontimeupdate = () => {
      if (this.musicAudio !== audio) return;
      const progress = audio.duration
        ? (audio.currentTime / audio.duration) * 100
        : (audio.currentTime / maxSec) * 100;
      this.onMusicProgress?.(Math.min(100, Math.round(progress)));

      if (audio.currentTime >= maxSec) {
        audio.pause();
        this.musicAudio = null;
        this.sendFeedback(data, 'ended');
      }
    };

    audio.onended = () => {
      if (this.musicAudio !== audio) return;
      this.musicAudio = null;
      this.sendFeedback(data, 'ended');
    };

    audio.onerror = () => {
      if (this.musicAudio !== audio) return;
      this.musicAudio = null;
      this.sendFeedback(data, 'ended');
    };

    audio.play().catch((err) => {
      console.warn('[LiveBroadcastAdapter] Music preview error:', err);
      this.musicAudio = null;
      this.sendFeedback(data, 'ended');
    });
  }

  /** Update local listeners and tell muted consoles who is audible. */
  private setSpeaking(persona: 'persona_a' | 'persona_b' | null): void {
    this.onSpeakingChange?.(persona);
    if (this.isAudioOwner && this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action: 'speaking', data: { persona } }));
    }
  }

  private sendFeedback(
    item: { session_id?: string; generation?: number; playback_id?: string },
    state: 'ended' | 'error',
    message?: string
  ): void {
    if (!item.playback_id || !this.isAudioOwner) return;
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(
        JSON.stringify({
          action: 'playback_feedback',
          data: {
            session_id: item.session_id,
            generation: item.generation,
            playback_id: item.playback_id,
            state,
            message,
          },
        })
      );
    }
  }

  public stopCurrentMedia(): void {
    this.turnQueue = [];
    this.turnPlaying = false;
    if (this.turnTimer !== null) {
      clearTimeout(this.turnTimer);
      this.turnTimer = null;
    }
    this.audioManager.stop();
    this.audioManager.clearQueue();

    if (this.musicAudio) {
      this.musicAudio.pause();
      this.musicAudio.removeAttribute('src');
      this.musicAudio = null;
    }

    for (const idle of this.idleManagers.values()) {
      idle.isSpeaking = false;
    }
    this.setSpeaking(null);
  }

  public async startClockBroadcast(talkTurns = 2, demoMusicSec = 30): Promise<any> {
    await this.audioManager.initialize();
    const res = await fetch(`http://${window.location.hostname}:8000/api/clock/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        demo_music_sec: demoMusicSec,
        talk_turns_per_slot: talkTurns,
      }),
    });
    return res.json();
  }

  public async stopBroadcast(): Promise<void> {
    this.stopCurrentMedia();
    await Promise.allSettled([
      fetch(`http://${window.location.hostname}:8000/api/clock/stop`, { method: 'POST' }),
      fetch(`http://${window.location.hostname}:8000/api/session/stop`, { method: 'POST' }),
    ]);
  }

  public async skipNextSlot(): Promise<any> {
    this.isSkipping = true;
    this.stopCurrentMedia();
    const res = await fetch(`http://${window.location.hostname}:8000/api/clock/next`, {
      method: 'POST',
    });
    return res.json();
  }

  public getSessionState(): 'idle' | 'running' | 'paused' {
    return this.sessionState;
  }

  public isConnected(): boolean {
    return this.wsConnected;
  }

  public dispose(): void {
    this.shouldReconnect = false;
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.onclose = null;
      this.ws.close();
      this.ws = null;
    }
    this.stopCurrentMedia();
  }
}
