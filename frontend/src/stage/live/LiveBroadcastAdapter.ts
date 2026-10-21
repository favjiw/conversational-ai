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
  /** Per-word TTS timings (ms from audio start) for viseme lip-sync. */
  word_timings?: { offset_ms: number; duration_ms: number; text: string }[] | null;
}

export interface LiveMusicData {
  slot_id?: string;
  category?: string;
  track: {
    title: string;
    artist: string;
    preview_url?: string;
    /** Username penonton bila lagu ini request dari komentar. */
    requested_by?: string;
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
  // Pre-recorded station element (jingle, bumper, taping) currently on air.
  private stationAudio: HTMLAudioElement | null = null;
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
  public onMusicChange?: (track: { title: string; artist: string; badge?: string; requestedBy?: string } | null) => void;
  public onMusicProgress?: (percent: number) => void;
  public onCardModeChange?: (mode: 'talk' | 'song') => void;
  /** Topic of the current session theme (session mode "theme_change"). */
  public onTopicChange?: (topic: string | null) => void;
  /** A presenter is about to speak a line (text + optional word timings for lip-sync). */
  public onLineStart?: (persona: 'persona_a' | 'persona_b', text: string, wordTimings: LiveTurnData['word_timings'], emotion?: string) => void;
  /** The browser refused to play audio until the viewer interacts with the page. */
  public onAutoplayBlocked?: () => void;
  /** Output routing: whether this tab plays the audio, and how many stage tabs are open. */
  public onOutputStatus?: (isAudioOwner: boolean, stageCount: number) => void;
  private audioBlocked = false;

  // Media the browser refused to autoplay. It is held (no "ended" feedback,
  // so the rundown waits) and played on the next user interaction.
  private blockedMedia: HTMLAudioElement | null = null;

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
        this.sendAudioState();
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
        if (this.stationAudio) this.stationAudio.muted = !this.isAudioOwner;
        this.onOutputStatus?.(this.isAudioOwner, Number(msg.data?.clients?.stage ?? 0));
        break;
      }

      case 'theme_change': {
        this.onTopicChange?.(msg.data?.title ?? null);
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
            this.setMusicPlaying(false);
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

      case 'clock_audio': {
        if (msg.data?.generation !== undefined && msg.data.generation !== this.currentGeneration) {
          return;
        }
        this.handleStationAudio(msg.data);
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
    this.onLineStart?.(personaKey, data.text, data.word_timings ?? null, data.emotion);

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

  /** Station recordings play as-is: announcers listen, no subtitle, no lip-sync. */
  private handleStationAudio(data: { audio_url: string; session_id?: string; generation?: number; playback_id?: string }): void {
    if (this.isSkipping) return;
    this.onTurnChange?.(null);
    this.onCardModeChange?.('talk');
    this.setSpeaking(null);
    for (const idle of this.idleManagers.values()) {
      idle.isSpeaking = false;
    }

    this.stopStationAudio();
    const audio = new Audio(data.audio_url);
    audio.muted = !this.isAudioOwner;
    this.stationAudio = audio;
    const done = () => {
      if (this.stationAudio !== audio) return;
      this.stationAudio = null;
      this.sendFeedback(data, 'ended');
    };
    audio.onended = done;
    audio.onerror = done;
    audio.play().catch((err) => {
      if (this.holdIfAutoplayBlocked(audio, err)) return;
      console.warn('[LiveBroadcastAdapter] Station audio error:', err);
      done();
    });
  }

  /** Returns true when playback was blocked by autoplay policy and is now held. */
  private holdIfAutoplayBlocked(audio: HTMLAudioElement, err: unknown): boolean {
    if (!(err instanceof DOMException) || err.name !== 'NotAllowedError') return false;
    console.warn('[LiveBroadcastAdapter] Autoplay blocked; waiting for a click to start audio');
    this.blockedMedia = audio;
    this.onAutoplayBlocked?.();
    return true;
  }

  /** Call from a user gesture: plays media that autoplay policy held back. */
  public resumeBlockedMedia(): void {
    const audio = this.blockedMedia;
    this.blockedMedia = null;
    if (audio && (audio === this.stationAudio || audio === this.musicAudio)) {
      audio.play().catch((err) => console.warn('[LiveBroadcastAdapter] Resume failed:', err));
    }
  }

  private stopStationAudio(): void {
    if (this.stationAudio) {
      this.stationAudio.pause();
      this.stationAudio.removeAttribute('src');
      this.stationAudio = null;
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
      requestedBy: track.requested_by || undefined,
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

  private setMusicPlaying(playing: boolean): void {
    for (const idle of this.idleManagers.values()) {
      idle.setMusicPlaying(playing);
    }
  }

  private playMusicAudio(url: string, data: LiveMusicData): void {
    if (this.musicAudio) {
      this.musicAudio.pause();
      this.musicAudio.removeAttribute('src');
      this.musicAudio = null;
      this.setMusicPlaying(false);
    }

    const audio = new Audio(url);
    audio.muted = !this.isAudioOwner;
    this.musicAudio = audio;
    const maxSec = data.preview_sec || 30;

    // Penyiar berjoget hanya selama audio lagu benar-benar berputar.
    audio.onplaying = () => {
      if (this.musicAudio === audio) this.setMusicPlaying(true);
    };

    audio.ontimeupdate = () => {
      if (this.musicAudio !== audio) return;
      const progress = audio.duration
        ? (audio.currentTime / audio.duration) * 100
        : (audio.currentTime / maxSec) * 100;
      this.onMusicProgress?.(Math.min(100, Math.round(progress)));

      if (audio.currentTime >= maxSec) {
        audio.pause();
        this.musicAudio = null;
        this.setMusicPlaying(false);
        this.sendFeedback(data, 'ended');
      }
    };

    audio.onended = () => {
      if (this.musicAudio !== audio) return;
      this.musicAudio = null;
      this.setMusicPlaying(false);
      this.sendFeedback(data, 'ended');
    };

    audio.onerror = () => {
      if (this.musicAudio !== audio) return;
      this.musicAudio = null;
      this.setMusicPlaying(false);
      this.sendFeedback(data, 'ended');
    };

    audio.play().catch((err) => {
      if (this.holdIfAutoplayBlocked(audio, err)) return;
      console.warn('[LiveBroadcastAdapter] Music preview error:', err);
      this.musicAudio = null;
      this.setMusicPlaying(false);
      this.sendFeedback(data, 'ended');
    });
  }

  /** Tell the backend whether autoplay holds this tab's audio (the console shows a warning). */
  public reportAudioState(blocked: boolean): void {
    this.audioBlocked = blocked;
    this.sendAudioState();
  }

  private sendAudioState(): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action: 'audio_state', data: { blocked: this.audioBlocked } }));
    }
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
    this.stopStationAudio();
    this.blockedMedia = null;

    if (this.musicAudio) {
      this.musicAudio.pause();
      this.musicAudio.removeAttribute('src');
      this.musicAudio = null;
      this.setMusicPlaying(false);
    }

    for (const idle of this.idleManagers.values()) {
      idle.isSpeaking = false;
    }
    this.setSpeaking(null);
  }

  /** talkTurns: override demo cepat; kosong = Talk mengikuti durasi slot di rundown. */
  public async startClockBroadcast(talkTurns?: number, demoMusicSec = 30): Promise<any> {
    await this.audioManager.initialize();
    const res = await fetch(`http://${window.location.hostname}:8000/api/clock/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        demo_music_sec: demoMusicSec,
        ...(talkTurns ? { talk_turns_per_slot: talkTurns } : {}),
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
