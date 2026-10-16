import { useEffect, useRef, useState } from 'react';
import Stats from 'stats.js';
import { SceneManager, type CharacterSpec } from './scene/SceneManager';
import { GlbFaceAnimator } from './face/GlbFaceAnimator';
import { GlbBodyIdle } from './face/GlbRig';
import { VisemeLipSync, DEFAULT_VISEME_CONFIG, type VisemeLipSyncConfig } from './lipsync/VisemeLipSync';
import { AudioManager } from './audio/AudioManager';
import { LipSyncLevel1, type LipSyncConfig } from './lipsync/LipSyncLevel1';
import { ExpressionDriver, type EmotionType, type ExpressionConfig } from './expression/ExpressionDriver';
import { IdleManager, type IdleConfig } from './idle/IdleManager';
import { ScenarioPlayer, type ScenarioData, type ScenarioTurn, type PlayerState } from './scenario/ScenarioPlayer';
import { DebugPanel, type DebugConfig } from './debug/DebugPanel';
import { StageBroadcastHUD } from './components/StageBroadcastHUD';
import { DebugToolbar } from './components/DebugToolbar';
import { LiveBroadcastAdapter, type LiveSlotData } from './live/LiveBroadcastAdapter';
import './StageApp.css';

const SCENARIOS = [
  { id: 'dialog-netral-01', label: '1. Dialog Netral Pendek', path: '/scenarios/scenario_neutral.json' },
  { id: 'emosi-tajam-01', label: '2. Perubahan Emosi Tajam', path: '/scenarios/scenario_emotions.json' },
  { id: 'stabilitas-panjang-01', label: '3. Uji Stabilitas Panjang', path: '/scenarios/scenario_stability.json' },
];

/** Presenter models used when avatar.config.json has no "characters" entry. */
const DEFAULT_CHARACTERS: Record<'persona_a' | 'persona_b', CharacterSpec> = {
  persona_a: { name: 'Raka', kind: 'vrm', url: '/models/red-male.vrm' },
  persona_b: { name: 'Salsa', kind: 'vrm', url: '/models/female.vrm' },
};

interface AvatarConfigFile {
  characters?: Partial<Record<'persona_a' | 'persona_b', CharacterSpec>>;
  lipsync?: Partial<LipSyncConfig>;
  expression?: Partial<ExpressionConfig>;
  idle?: Partial<IdleConfig>;
  glbFace?: { jawScale?: number };
  viseme?: Partial<VisemeLipSyncConfig>;
}

/** avatar.config.json is optional: a missing or broken file falls back to defaults. */
async function loadAvatarConfig(): Promise<AvatarConfigFile> {
  try {
    const res = await fetch('/avatar.config.json', { cache: 'no-store' });
    return res.ok ? await res.json() : {};
  } catch {
    return {};
  }
}

export interface MusicTrackData {
  title: string;
  artist: string;
  badge?: string;
}

const DEFAULT_DEMO_TRACK: MusicTrackData = {
  title: 'Hati-Hati di Jalan',
  artist: 'Tulus',
  badge: 'NOW PLAYING • INDO HITS',
};

function formatWibTime(date: Date = new Date()): string {
  const utc = date.getTime() + (date.getTimezoneOffset() * 60000);
  const wibDate = new Date(utc + (3600000 * 7));
  const hh = String(wibDate.getHours()).padStart(2, '0');
  const mm = String(wibDate.getMinutes()).padStart(2, '0');
  return `${hh}.${mm} WIB`;
}

export function StageApp() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Check ?mode=debug parameter
  const [isDebug] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    return new URLSearchParams(window.location.search).get('mode') === 'debug';
  });

  // Stage Layout & Visual Controls (Phase 2 FR-9)
  const [aspectRatio, setAspectRatio] = useState<'16:9' | 'full' | '9:16'>(() => {
    if (typeof window === 'undefined') return '16:9';
    const param = new URLSearchParams(window.location.search).get('aspect');
    if (param === '9:16' || param === 'full' || param === '16:9') return param;
    return '16:9';
  });
  const [showSafeZones, setShowSafeZones] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    const params = new URLSearchParams(window.location.search);
    if (params.has('safezones')) return params.get('safezones') === 'true';
    return params.get('mode') === 'debug';
  });
  const [displayCardMode, setDisplayCardMode] = useState<'auto' | 'talk' | 'song'>('auto');
  const [activeSpeaker, setActiveSpeaker] = useState<'persona_a' | 'persona_b' | null>(null);
  const [currentTime, setCurrentTime] = useState<string>(formatWibTime);
  const [songProgress, setSongProgress] = useState(45);
  const [audioUnlocked, setAudioUnlocked] = useState(false);

  const [sourceMode, setSourceMode] = useState<'scenario' | 'live'>(() => {
    if (typeof window === 'undefined') return 'scenario';
    return new URLSearchParams(window.location.search).get('source') === 'live' ? 'live' : 'scenario';
  });
  const [wsConnected, setWsConnected] = useState(false);
  const [liveSessionState, setLiveSessionState] = useState<'idle' | 'running' | 'paused'>('idle');
  const [currentSlot, setCurrentSlot] = useState<LiveSlotData | null>(null);

  const [selectedScenarioId, setSelectedScenarioId] = useState(SCENARIOS[0].id);
  const [currentTurn, setCurrentTurn] = useState<ScenarioTurn | null>(null);
  const [turnIndex, setTurnIndex] = useState(0);
  const [playerState, setPlayerState] = useState<PlayerState>('idle');
  const [musicTrack, setMusicTrack] = useState<MusicTrackData | null>(null);

  const sceneManagerRef = useRef<SceneManager | null>(null);
  const audioManagerRef = useRef<AudioManager | null>(null);
  const lipSyncManagersRef = useRef<Map<string, LipSyncLevel1>>(new Map());
  const expressionDriversRef = useRef<Map<string, ExpressionDriver>>(new Map());
  const idleManagersRef = useRef<Map<string, IdleManager>>(new Map());
  const glbFaceAnimatorsRef = useRef<Map<string, GlbFaceAnimator>>(new Map());
  const glbBodyIdlesRef = useRef<Map<string, GlbBodyIdle>>(new Map());
  const visemeLipSyncsRef = useRef<Map<string, VisemeLipSync>>(new Map());
  const lipSyncMethodRef = useRef<VisemeLipSyncConfig['method']>('viseme');
  const scenarioPlayerRef = useRef<ScenarioPlayer | null>(null);
  const liveAdapterRef = useRef<LiveBroadcastAdapter | null>(null);
  const [scenariosData, setScenariosData] = useState<Map<string, ScenarioData>>(() => new Map());
  const debugPanelRef = useRef<DebugPanel | null>(null);
  const statsRef = useRef<Stats | null>(null);
  const animationFrameRef = useRef<number | null>(null);

  // Auto-updating real-time WIB clock
  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(formatWibTime());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Song progress simulation ticker (debug demo card only; live progress comes from the adapter)
  useEffect(() => {
    const isDemoSong = displayCardMode === 'song' && !musicTrack;
    if (!isDemoSong) return;
    const progTimer = setInterval(() => {
      setSongProgress(prev => (prev >= 100 ? 5 : prev + 1));
    }, 1000);
    return () => clearInterval(progTimer);
  }, [displayCardMode, musicTrack]);
  useEffect(() => {
    if (!containerRef.current) return;

    let mounted = true;

    const init = async () => {
      try {
        if (isDebug && containerRef.current) {
          const stats = new Stats();
          stats.showPanel(0);
          stats.dom.style.position = 'absolute';
          stats.dom.style.left = '0';
          stats.dom.style.top = '0';
          stats.dom.style.zIndex = '50';
          containerRef.current.appendChild(stats.dom);
          statsRef.current = stats;
        }

        const sceneManager = new SceneManager(containerRef.current!);
        sceneManagerRef.current = sceneManager;

        const audioManager = new AudioManager();
        audioManagerRef.current = audioManager;
        // Debug only: lets devtools read live blendshape values while tuning.
        if (isDebug) (window as any).__stage = { sceneManager, audioManager, expressionDrivers: expressionDriversRef.current };

        const avatarConfig = await loadAvatarConfig();

        audioManager.onSpeakingChange = (personaId) => {
          if (mounted) setActiveSpeaker((personaId as any) || null);
        };

        const debugConfig: DebugConfig = {
          quality: 'medium',
          lipsync: { gain: 4.5, gate: 0.02, attackMs: 40, releaseMs: 120, ...avatarConfig.lipsync },
          expression: {
            transitionMs: 300, maxCombinedWeight: 1.0, speakingEmotionScale: 0.3,
            ...avatarConfig.expression,
            personaAEmotion: 'neutral', personaBEmotion: 'neutral',
          },
          idle: { blinkMinSec: 2, blinkMaxSec: 6, headSway: 0.3, breath: 0.4, ...avatarConfig.idle },
          viseme: { ...DEFAULT_VISEME_CONFIG, ...avatarConfig.viseme },
          showPanel: isDebug,
        };
        lipSyncMethodRef.current = debugConfig.viseme.method;

        if (isDebug) {
          const debugPanel = new DebugPanel(debugConfig);
          debugPanelRef.current = debugPanel;

          debugPanel.on('quality', (q: 'low' | 'medium' | 'high') => sceneManager.setQuality(q));
          debugPanel.on('lipsync', (c: LipSyncConfig) => {
            lipSyncManagersRef.current.forEach(ls => ls.updateConfig(c));
          });
          debugPanel.on('emotion_a', (em: EmotionType) => {
            expressionDriversRef.current.get('persona_a')?.setEmotion(em);
            glbFaceAnimatorsRef.current.get('persona_a')?.setEmotion(em);
          });
          debugPanel.on('emotion_b', (em: EmotionType) => {
            expressionDriversRef.current.get('persona_b')?.setEmotion(em);
            glbFaceAnimatorsRef.current.get('persona_b')?.setEmotion(em);
          });
          debugPanel.on('expression_config', (cfg: ExpressionConfig) => {
            expressionDriversRef.current.forEach(ed => ed.setConfig(cfg));
            glbFaceAnimatorsRef.current.forEach(fa => fa.setConfig({ speakingEmotionScale: cfg.speakingEmotionScale }));
          });
          debugPanel.on('viseme', (cfg: VisemeLipSyncConfig) => {
            visemeLipSyncsRef.current.forEach(vl => vl.setConfig(cfg));
            lipSyncMethodRef.current = cfg.method;
          });
          debugPanel.on('idle_config', (cfg: IdleConfig) => {
            idleManagersRef.current.forEach(im => im.setConfig(cfg));
            glbFaceAnimatorsRef.current.forEach(fa => fa.setConfig(cfg));
            glbBodyIdlesRef.current.forEach(bi => bi.setConfig(cfg));
          });
        }

        // Debug only: ?avatarA=/models/x.glb&avatarB=... tries a model without editing the config
        const params = new URLSearchParams(window.location.search);
        const urlOverride = (personaId: 'persona_a' | 'persona_b'): Partial<CharacterSpec> => {
          const url = isDebug ? params.get(personaId === 'persona_a' ? 'avatarA' : 'avatarB') : null;
          return url ? { url, kind: url.toLowerCase().endsWith('.vrm') ? 'vrm' : 'glb' } : {};
        };
        await Promise.all((['persona_a', 'persona_b'] as const).map((personaId) =>
          sceneManager.loadCharacter(personaId, {
            ...DEFAULT_CHARACTERS[personaId],
            ...avatarConfig.characters?.[personaId],
            ...urlOverride(personaId),
          })
        ));
        // The driver maps are shared refs: a stale mount must not write into them.
        if (!mounted) {
          sceneManager.dispose();
          audioManager.dispose();
          return;
        }

        sceneManager.buildStudio();

        ['persona_a', 'persona_b'].forEach(personaId => {
          const char = sceneManager.characters.get(personaId);
          if (!char) return;
          char.analyserNode = audioManager.createAnalyser(personaId);
          lipSyncManagersRef.current.set(personaId, new LipSyncLevel1(debugConfig.lipsync));

          if (char.bones && !char.mixer) {
            glbBodyIdlesRef.current.set(personaId, new GlbBodyIdle(char.root, char.bones, debugConfig.idle));
          }

          if (char.face) {
            // Realistic GLB: ARKit morph targets (interim jaw + blink until viseme lip-sync)
            glbFaceAnimatorsRef.current.set(personaId, new GlbFaceAnimator(char.face, {
              jawScale: avatarConfig.glbFace?.jawScale ?? 0.7,
              blinkMinSec: debugConfig.idle.blinkMinSec,
              blinkMaxSec: debugConfig.idle.blinkMaxSec,
              speakingEmotionScale: debugConfig.expression.speakingEmotionScale,
            // The partner sits on persona_a's left (+1) and on persona_b's right (-1)
            }, personaId === 'persona_a' ? 1 : -1));
            visemeLipSyncsRef.current.set(personaId, new VisemeLipSync(debugConfig.viseme));
            debugPanelRef.current?.addFaceSliders(char.name, char.face);
          }

          if (char.vrm) {
            const ed = new ExpressionDriver(char.name, char.vrm, debugConfig.expression);
            expressionDriversRef.current.set(personaId, ed);

            const im = new IdleManager(char.vrm, ed.getAdapter(), ed, debugConfig.idle);
            idleManagersRef.current.set(personaId, im);
          }
        });

        const scnMap = new Map<string, ScenarioData>();
        for (const s of SCENARIOS) {
          try {
            const res = await fetch(s.path);
            if (res.ok) {
              const data = await res.json();
              scnMap.set(s.id, data);
            }
          } catch {
            // Silently ignore optional scenario fetch errors
          }
        }
        if (!mounted) {
          // Unmounted while loading (e.g. StrictMode double mount): the cleanup
          // already ran, so tear down here and never open a WebSocket.
          sceneManager.dispose();
          audioManager.dispose();
          return;
        }
        setScenariosData(scnMap);

        const player = new ScenarioPlayer(audioManager, expressionDriversRef.current, idleManagersRef.current);
        scenarioPlayerRef.current = player;

        player.onSpeakingChange = (personaId) => {
          if (mounted) setActiveSpeaker((personaId as any) || null);
        };

        player.onTurnChange = (turn, idx) => {
          // Scenario clips carry no word timings: visemes are estimated from the text
          visemeLipSyncsRef.current.get(turn.persona)?.setLine(turn.text, null);
          glbFaceAnimatorsRef.current.get(turn.persona)?.setEmotion(turn.emotion);
          if (mounted) {
            setCurrentTurn(turn);
            setTurnIndex(idx);
            setActiveSpeaker((turn.persona as any) || null);
            if (debugPanelRef.current) {
              if (turn.persona === 'persona_a') debugPanelRef.current.setEmotionA(turn.emotion);
              else debugPanelRef.current.setEmotionB(turn.emotion);
            }
          }
        };

        player.onStateChange = (st) => {
          if (mounted) {
            setPlayerState(st);
            if (st !== 'playing') setActiveSpeaker(null);
          }
        };

        const defaultScn = scnMap.get(SCENARIOS[0].id);
        if (defaultScn) player.loadScenario(defaultScn);

        // Initialize Live Broadcast Adapter for HITS AI Live WebSocket session
        const liveAdapter = new LiveBroadcastAdapter(
          audioManager,
          expressionDriversRef.current,
          idleManagersRef.current
        );
        liveAdapterRef.current = liveAdapter;

        liveAdapter.onConnectionChange = (connected) => {
          if (mounted) setWsConnected(connected);
        };

        liveAdapter.onStateChange = (state) => {
          if (mounted) {
            setLiveSessionState(state);
            if (state === 'idle') {
              setCurrentTurn(null);
              setMusicTrack(null);
              setCurrentSlot(null);
            }
          }
        };

        liveAdapter.onSlotChange = (slot) => {
          if (mounted) setCurrentSlot(slot);
        };

        liveAdapter.onTurnChange = (turn) => {
          if (mounted) {
            if (turn) {
              setCurrentTurn({
                persona: turn.persona,
                text: turn.text,
                emotion: (turn.emotion as EmotionType) || 'neutral',
              });
              setActiveSpeaker(turn.persona);
              if (debugPanelRef.current && turn.emotion) {
                if (turn.persona === 'persona_a') debugPanelRef.current.setEmotionA(turn.emotion as EmotionType);
                else debugPanelRef.current.setEmotionB(turn.emotion as EmotionType);
              }
            } else {
              setCurrentTurn(null);
            }
          }
        };

        liveAdapter.onSpeakingChange = (personaId) => {
          if (mounted) setActiveSpeaker(personaId);
        };

        liveAdapter.onMusicChange = (track) => {
          if (mounted) setMusicTrack(track);
        };

        liveAdapter.onMusicProgress = (prog) => {
          if (mounted) setSongProgress(prog);
        };

        liveAdapter.onCardModeChange = (mode) => {
          if (mounted) setDisplayCardMode(mode);
        };

        liveAdapter.onLineStart = (persona, text, wordTimings, emotion) => {
          visemeLipSyncsRef.current.get(persona)?.setLine(text, wordTimings ?? null);
          if (emotion) glbFaceAnimatorsRef.current.get(persona)?.setEmotion(emotion as EmotionType);
        };

        liveAdapter.onAutoplayBlocked = () => {
          if (mounted) setAudioUnlocked(false);
        };

        liveAdapter.connect();

        if (mounted) {
          setLoading(false);
          animate();
        }

        // OBS browser sources allow autoplay; a normal browser tab needs a click first.
        try {
          await audioManager.initialize();
        } catch {
          // Still suspended: the unlock banner asks for a click.
        }
        if (mounted) setAudioUnlocked(!audioManager.isAudioSuspended());
      } catch (err: any) {
        console.error('Init error:', err);
        setError(err.message || 'Gagal inisialisasi avatar');
        setLoading(false);
      }
    };

    const animate = () => {
      if (!mounted) return;
      if (!sceneManagerRef.current || !audioManagerRef.current) return;
      statsRef.current?.begin();

      const sceneManager = sceneManagerRef.current;
      const audioManager = audioManagerRef.current;
      const deltaTime = sceneManager.clock.getDelta();
      const deltaTimeMs = deltaTime * 1000;

      sceneManager.characters.forEach((char, personaId) => {
        const ls = lipSyncManagersRef.current.get(personaId);
        const ed = expressionDriversRef.current.get(personaId);
        const im = idleManagersRef.current.get(personaId);
        const audioLevel = audioManager.getLevel(personaId);

        if (ls) ls.update(char.vrm, audioLevel, deltaTimeMs);
        const mouthOpen = ls ? ls.getMouthOpen() : 0;
        if (char.vrm) {
          if (ed) ed.update(deltaTime, mouthOpen);
          if (im) im.update(deltaTime);
        }
        const speaker = audioManager.getCurrentPersona();
        const listening = speaker !== null && speaker !== personaId;
        const faceAnimator = glbFaceAnimatorsRef.current.get(personaId);
        if (faceAnimator) {
          const vls = visemeLipSyncsRef.current.get(personaId);
          const visemes = vls ? vls.update(deltaTime, audioManager.getPlayback(personaId), mouthOpen) : null;
          const useVisemes = vls?.hasLine && lipSyncMethodRef.current === 'viseme';
          faceAnimator.isListening = listening;
          // Without a line (e.g. a bare test clip) fall back to amplitude jaw motion
          faceAnimator.update(deltaTime, mouthOpen, useVisemes ? visemes : null);
        }
        const bodyIdle = glbBodyIdlesRef.current.get(personaId);
        if (bodyIdle) {
          bodyIdle.isSpeaking = speaker === personaId;
          bodyIdle.isListening = listening;
          bodyIdle.update(deltaTime);
        }
      });

      sceneManager.update(deltaTime);
      sceneManager.render();
      statsRef.current?.end();

      animationFrameRef.current = requestAnimationFrame(animate);
    };

    init();

    return () => {
      mounted = false;
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
      scenarioPlayerRef.current?.stop();
      liveAdapterRef.current?.dispose();
      sceneManagerRef.current?.dispose();
      audioManagerRef.current?.dispose();
      debugPanelRef.current?.dispose();
      if (statsRef.current?.dom.parentElement) {
        statsRef.current.dom.parentElement.removeChild(statsRef.current.dom);
      }
    };
  }, [isDebug]);

  const handleSelectScenario = (id: string) => {
    setSelectedScenarioId(id);
    const scn = scenariosData.get(id);
    if (scn && scenarioPlayerRef.current) {
      scenarioPlayerRef.current.loadScenario(scn);
      setCurrentTurn(null);
      setTurnIndex(0);
    }
  };

  const activeMusicTrack = musicTrack || (isDebug && displayCardMode === 'song' ? DEFAULT_DEMO_TRACK : null);
  const isSongMode = displayCardMode === 'song' || (displayCardMode === 'auto' && Boolean(musicTrack));
  const activeScenario = scenariosData.get(selectedScenarioId);

  const handleUserInteraction = async () => {
    // Inside the click: start anything autoplay policy held back.
    liveAdapterRef.current?.resumeBlockedMedia();
    if (!audioUnlocked && audioManagerRef.current) {
      try {
        await audioManagerRef.current.initialize();
        setAudioUnlocked(!audioManagerRef.current.isAudioSuspended());
      } catch (err: any) {
        console.warn('AudioContext resume failed:', err);
      }
    }
  };

  const handleToggleSourceMode = (mode: 'scenario' | 'live') => {
    setSourceMode(mode);
    if (mode === 'live') {
      scenarioPlayerRef.current?.stop();
    } else {
      liveAdapterRef.current?.stopCurrentMedia();
    }
  };

  const handleStartLive = async () => {
    await handleUserInteraction();
    try {
      await liveAdapterRef.current?.startClockBroadcast();
    } catch (err: any) {
      console.error('Failed to start clock broadcast:', err);
    }
  };

  const handleStopLive = async () => {
    try {
      await liveAdapterRef.current?.stopBroadcast();
    } catch (err: any) {
      console.error('Failed to stop broadcast:', err);
    }
  };

  const handleSkipLiveSlot = async () => {
    try {
      await liveAdapterRef.current?.skipNextSlot();
    } catch (err: any) {
      console.error('Failed to skip slot:', err);
    }
  };

  const handleTestSpeaker = async (persona: 'persona_a' | 'persona_b') => {
    await handleUserInteraction();
    audioManagerRef.current?.clearQueue();
    const testAudio = persona === 'persona_a' ? '/audio/scenarios/s1_t1.wav' : '/audio/scenarios/s1_t2.wav';
    audioManagerRef.current?.enqueueTurn({ personaId: persona, audioUrl: testAudio });
    const idle = idleManagersRef.current.get(persona);
    if (idle) idle.isSpeaking = true;
    setActiveSpeaker(persona);
  };

  /** Debug: speak free text through the backend TTS, with word timings driving the visemes. */
  const handleSpeakText = async (persona: 'persona_a' | 'persona_b', text: string) => {
    await handleUserInteraction();
    try {
      const res = await fetch('/api/tts/line', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, persona }),
      });
      if (!res.ok) throw new Error(`TTS ${res.status}: ${await res.text()}`);
      const line = await res.json();
      visemeLipSyncsRef.current.get(persona)?.setLine(line.text, line.word_timings ?? null);
      setCurrentTurn({ persona, text: line.text, emotion: 'neutral' });
      audioManagerRef.current?.clearQueue();
      await audioManagerRef.current?.playAudio(persona, line.audio_url);
    } catch (err: any) {
      console.error('Speak text failed:', err);
      alert(`Gagal mengucapkan teks: ${err.message}`);
    }
  };

  const handleToggleAspectRatio = () => {
    const next = aspectRatio === '16:9' ? 'full' : aspectRatio === 'full' ? '9:16' : '16:9';
    setAspectRatio(next);
    setTimeout(() => {
      if (containerRef.current && sceneManagerRef.current) {
        sceneManagerRef.current.updateLayout(containerRef.current);
      }
    }, 60);
  };

  return (
    <div className="stage-app" onClick={handleUserInteraction}>
      <div
        className={`stage-frame ${
          aspectRatio === '16:9'
            ? 'aspect-16-9'
            : aspectRatio === '9:16'
            ? 'aspect-9-16'
            : 'aspect-full'
        }`}
      >
        <div ref={containerRef} className="canvas-container" />

        {/* Stage Broadcast HUD (Light Mode Studio Matching Operator Panel) */}
        <StageBroadcastHUD
          showSafeZones={showSafeZones}
          programTitle="PAGI BENER"
          stationName="103.9 HITS Unikom Radio"
          currentTime={currentTime}
          activeSpeaker={activeSpeaker}
          isSongMode={isSongMode}
          musicTrack={activeMusicTrack}
          songProgress={songProgress}
          currentTurn={currentTurn}
        />

        {/* Non-blocking Audio Unlock Banner */}
        {!audioUnlocked && !loading && (
          <div className="audio-unlock-banner">
            <span className="audio-icon">🔊</span>
            <span>Klik di mana saja untuk mengaktifkan audio siaran</span>
          </div>
        )}

        {/* Loading Overlay */}
        {loading && (
          <div className="overlay">
            <div className="loading">
              <div className="spinner"></div>
              <p>Memuat model VRM & studio avatar...</p>
            </div>
          </div>
        )}

        {/* Error Overlay */}
        {error && (
          <div className="overlay">
            <div className="error">
              <h2>Error Inisialisasi</h2>
              <p>{error}</p>
              <div className="hint">
                <strong>Solusi:</strong>
                <p>Pastikan file model VRM berada di folder <code>public/models/</code>.</p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Debug Controls Toolbar (Active when mode=debug once stage is loaded) */}
      {isDebug && !loading && (
        <DebugToolbar
          sourceMode={sourceMode}
          onToggleSourceMode={handleToggleSourceMode}
          wsConnected={wsConnected}
          liveSessionState={liveSessionState}
          currentSlotLabel={currentSlot ? (currentSlot.label || currentSlot.title || currentSlot.slot_type) : undefined}
          onStartLive={handleStartLive}
          onStopLive={handleStopLive}
          onSkipLiveSlot={handleSkipLiveSlot}
          scenarios={SCENARIOS}
          selectedScenarioId={selectedScenarioId}
          onSelectScenario={handleSelectScenario}
          playerState={playerState}
          onPlay={async () => {
            await handleUserInteraction();
            scenarioPlayerRef.current?.play();
          }}
          onPause={() => scenarioPlayerRef.current?.pause()}
          onRestart={async () => {
            await handleUserInteraction();
            scenarioPlayerRef.current?.restart();
          }}
          turns={activeScenario?.turns || []}
          turnIndex={turnIndex}
          onJumpTurn={(idx) => scenarioPlayerRef.current?.jumpToTurn(idx)}
          onTestSpeaker={handleTestSpeaker}
          onSpeakText={handleSpeakText}
          displayCardMode={displayCardMode}
          onToggleCardMode={() => setDisplayCardMode(prev => (prev === 'song' ? 'talk' : 'song'))}
          showSafeZones={showSafeZones}
          onToggleSafeZones={() => setShowSafeZones(prev => !prev)}
          aspectRatio={aspectRatio}
          onToggleAspectRatio={handleToggleAspectRatio}
          onToggleDebugPanel={() => debugPanelRef.current?.toggle()}
        />
      )}
    </div>
  );
}

export default StageApp;

