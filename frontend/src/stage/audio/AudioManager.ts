export interface AudioTurn {
  personaId: string;
  audioUrl: string;
  emotion?: string;
}

export class AudioManager {
  private audioContext: AudioContext | null = null;
  private analysers: Map<string, AnalyserNode>;
  // analysers -> masterGain -> destination; muting keeps lip-sync analysis alive.
  private masterGain: GainNode | null = null;
  private muted = false;
  private currentSource: AudioBufferSourceNode | null = null;
  private turnQueue: AudioTurn[] = [];
  private isPlaying = false;
  private onTurnEndCallback?: () => void;
  private currentPersona: string | null = null;
  public onSpeakingChange?: (personaId: string | null) => void;
  
  constructor() {
    this.analysers = new Map();
  }
  
  // Initialize AudioContext (must be called after user interaction)
  async initialize(): Promise<void> {
    if (!this.audioContext) {
      this.audioContext = new AudioContext();
    }
    if (this.audioContext.state === 'suspended') {
      await this.audioContext.resume();
    }
    console.log('✓ AudioContext initialized, state:', this.audioContext.state);
  }
  
  // Create an analyser for a specific persona
  createAnalyser(personaId: string): AnalyserNode {
    if (!this.audioContext) {
      this.audioContext = new AudioContext();
    }
    
    if (this.analysers.has(personaId)) {
      return this.analysers.get(personaId)!;
    }
    
    const analyser = this.audioContext.createAnalyser();
    analyser.fftSize = 256;
    analyser.smoothingTimeConstant = 0.8;
    
    this.analysers.set(personaId, analyser);
    console.log(`✓ Created analyser for ${personaId}`);
    
    return analyser;
  }
  
  private getOutput(): AudioNode {
    const ctx = this.audioContext!;
    if (!this.masterGain) {
      this.masterGain = ctx.createGain();
      this.masterGain.gain.value = this.muted ? 0 : 1;
      this.masterGain.connect(ctx.destination);
    }
    return this.masterGain;
  }

  /** Mute audible output while still driving analysers (lip-sync). */
  setMuted(muted: boolean) {
    this.muted = muted;
    if (this.masterGain) this.masterGain.gain.value = muted ? 0 : 1;
  }

  isAudioSuspended(): boolean {
    return !this.audioContext || this.audioContext.state !== 'running';
  }

  getAnalyser(personaId: string): AnalyserNode | null {
    return this.analysers.get(personaId) || null;
  }
  
  // Load and play audio
  async playAudio(personaId: string, audioUrl: string, onEnded?: () => void): Promise<void> {
    if (!this.audioContext) {
      throw new Error('AudioContext not initialized');
    }
    
    if (this.audioContext.state === 'suspended') {
      await this.audioContext.resume();
    }
    
    const normalizedUrl = /^https?:\/\//i.test(audioUrl) || audioUrl.startsWith('/')
      ? audioUrl
      : `/${audioUrl}`;

    try {
      // Fetch audio with CORS enabled
      const response = await fetch(normalizedUrl, { 
        mode: 'cors',
        credentials: 'omit' 
      });
      
      if (!response.ok) {
        throw new Error(`Failed to fetch audio: ${response.statusText}`);
      }
      
      const arrayBuffer = await response.arrayBuffer();
      const audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer);
      
      // Stop current audio if any
      if (this.currentSource) {
        try {
          this.currentSource.stop();
          this.currentSource.disconnect();
        } catch {}
        this.currentSource = null;
      }
      
      // Create new source
      const source = this.audioContext.createBufferSource();
      source.buffer = audioBuffer;
      
      // Get analyser for this persona
      const analyser = this.getAnalyser(personaId);
      
      if (analyser) {
        // Connect: source -> analyser -> destination
        source.connect(analyser);
        analyser.connect(this.getOutput());
      } else {
        // Direct connection if no analyser
        source.connect(this.getOutput());
      }
      
      this.currentSource = source;
      this.currentPersona = personaId;
      this.isPlaying = true;
      this.onSpeakingChange?.(personaId);
      
      // Handle end event
      source.onended = () => {
        if (this.currentSource !== source) return;
        this.isPlaying = false;
        this.currentPersona = null;
        this.currentSource = null;
        this.onSpeakingChange?.(null);
        
        onEnded?.();

        if (this.onTurnEndCallback) {
          const cb = this.onTurnEndCallback;
          this.onTurnEndCallback = undefined;
          cb();
        }
        
        // Play next in queue
        this.playNextInQueue();
      };
      
      source.start(0);
      console.log(`▶ Playing audio for ${personaId}`);
      
    } catch (error) {
      console.error(`Failed to play audio for ${personaId}:`, error);
      this.isPlaying = false;
      this.currentPersona = null;
      this.currentSource = null;
      this.onSpeakingChange?.(null);
      throw error;
    }
  }
  
  // Queue management
  enqueueTurn(turn: AudioTurn) {
    this.turnQueue.push(turn);
    
    if (!this.isPlaying) {
      this.playNextInQueue();
    }
  }
  
  private playNextInQueue() {
    if (this.turnQueue.length === 0) return;
    
    const turn = this.turnQueue.shift()!;
    this.playAudio(turn.personaId, turn.audioUrl);
  }
  
  clearQueue() {
    this.turnQueue = [];
  }
  
  // Get current audio level (RMS) for a persona
  getLevel(personaId: string): number {
    const analyser = this.getAnalyser(personaId);
    if (!analyser) return 0;
    
    const dataArray = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteTimeDomainData(dataArray);
    
    // Calculate RMS
    let sum = 0;
    for (let i = 0; i < dataArray.length; i++) {
      const normalized = (dataArray[i] - 128) / 128;
      sum += normalized * normalized;
    }
    
    const rms = Math.sqrt(sum / dataArray.length);
    return rms;
  }
  
  getCurrentPersona(): string | null {
    return this.currentPersona;
  }
  
  setOnTurnEnd(callback: () => void) {
    this.onTurnEndCallback = callback;
  }
  
  stop() {
    if (this.currentSource) {
      try {
        this.currentSource.stop();
        this.currentSource.disconnect();
      } catch {}
      this.currentSource = null;
    }
    this.isPlaying = false;
    this.currentPersona = null;
    this.onSpeakingChange?.(null);
  }
  
  dispose() {
    this.stop();
    this.clearQueue();
    
    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }
    
    this.analysers.clear();
    this.masterGain = null;
  }
}
