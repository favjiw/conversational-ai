import { useState, useEffect, useRef } from 'react';

export function useLiveSession() {
  const [sessionStatus, setSessionStatus] = useState({ state: 'idle' });
  const [turns, setTurns] = useState([]);
  const [activeSpeaker, setActiveSpeaker] = useState(null);
  const [elapsedSec, setElapsedSec] = useState(0);
  const [wsConnected, setWsConnected] = useState(false);

  const [tema, setTema] = useState('Kemacetan pagi di Bandung');
  const [personaA, setPersonaA] = useState({ name: 'Raka', style: 'Pria ceria, lugas, santai' });
  const [personaB, setPersonaB] = useState({ name: 'Salsa', style: 'Wanita hangat, tanggap, ramah' });
  const [maxTurns, setMaxTurns] = useState(10);
  const [preset, setPreset] = useState('clock_pagi_bener');
  const [currentTheme, setCurrentTheme] = useState(null);

  // Clock Rundown Live State
  const [clockSlots, setClockSlots] = useState([]);
  const [currentSlot, setCurrentSlot] = useState(null);
  const [musicTrack, setMusicTrack] = useState(null);
  const [cueSlot, setCueSlot] = useState(null);
  const [isSkipping, setIsSkipping] = useState(false);

  const wsRef = useRef(null);
  const elapsedIntervalRef = useRef(null);
  const audioQueueRef = useRef([]);
  const isPlayingAudioRef = useRef(false);
  const currentAudioRef = useRef(null);
  const transcriptRef = useRef(null);
  const elapsedSecRef = useRef(0);
  const currentGenerationRef = useRef(0);
  const [playbackState, setPlaybackState] = useState('idle');
  const [slotElapsedSec, setSlotElapsedSec] = useState(0);
  const [playbackError, setPlaybackError] = useState(null);
  const slotAudioElapsedRef = useRef(0);
  const currentSessionRef = useRef(null);
  const slotRef = useRef(null);
  const skippingRef = useRef(false);

  const clearAudio = () => {
    const audio = currentAudioRef.current;
    currentAudioRef.current = null;
    if (audio) {
      audio.onended = audio.onerror = audio.onplaying = audio.onwaiting = audio.ontimeupdate = null;
      audio.pause();
      audio.removeAttribute('src');
      audio.load();
    }
    audioQueueRef.current = [];
    isPlayingAudioRef.current = false;
    setActiveSpeaker(null);
    setMusicTrack(null);
  };

  const feedback = (item, state, message) => {
    if (item.playback_id && wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'playback_feedback', data: {
        session_id: item.session_id, generation: item.generation,
        playback_id: item.playback_id, state, message,
      } }));
    }
  };

  useEffect(() => {
    elapsedSecRef.current = elapsedSec;
  }, [elapsedSec]);

  const fmtTime = (s) => {
    const m = Math.floor(s / 60).toString().padStart(2, '0');
    const sec = Math.floor(s % 60).toString().padStart(2, '0');
    return `${m}:${sec}`;
  };

  // Fetch Clock Rundown Slots on mount
  useEffect(() => {
    fetch(`http://${window.location.hostname}:8000/api/clock/pagi-bener`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && data.slots) setClockSlots(data.slots);
      })
      .catch((err) => console.warn('Failed loading clock slots:', err));
  }, []);

  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.hostname}:8000/ws/session`;
    wsRef.current = new WebSocket(wsUrl);

    wsRef.current.onopen = () => setWsConnected(true);
    wsRef.current.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'status') {
          setSessionStatus(msg.data);
          if (msg.data.state === 'idle') {
            setActiveSpeaker(null);
            setMusicTrack(null);
            currentSessionRef.current = null;
          } else if (msg.data.state === 'running') {
            currentSessionRef.current = msg.data.session_id;
          }
        } else if (msg.type === 'theme_change') {
          setCurrentTheme(msg.data);
        } else if (msg.type === 'turn') {
          handleTurnEvent(msg.data);
        } else if (msg.type === 'clock_slot_skipped') {
          // Immediately clear audio and UI states
          skippingRef.current = false;
          setIsSkipping(false);
          clearAudio();
          setSlotElapsedSec(0);
          slotAudioElapsedRef.current = 0;
          currentGenerationRef.current = msg.data.generation;
        } else if (msg.type === 'clock_slot_started') {
          skippingRef.current = false;
          setIsSkipping(false);
          setCurrentSlot(msg.data);
          slotRef.current = msg.data;
          setSlotElapsedSec(0);
          slotAudioElapsedRef.current = 0;
          currentGenerationRef.current = msg.data.generation;
          if (msg.data.slot_type !== 'song') {
            setMusicTrack(null);
          }
        } else if (msg.type === 'clock_music') {
          const mTrack = msg.data;
          setMusicTrack(mTrack.track);
          if (mTrack.track?.preview_url) {
            audioQueueRef.current.push({
              slot_id: mTrack.slot_id,
              type: 'music',
              audioUrl: mTrack.track.preview_url,
              generation: mTrack.generation,
              session_id: mTrack.session_id,
              playback_id: mTrack.playback_id,
            });
            if (!isPlayingAudioRef.current) playNextInQueue();
          } else {
            // No preview, auto-advance
            feedback(mTrack, 'ended');
          }
        } else if (msg.type === 'clock_cue') {
          setCueSlot(msg.data);
        }
      } catch (e) {
        console.warn('WS parse error:', e);
      }
    };
    wsRef.current.onclose = () => setWsConnected(false);

    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  const handleTurnEvent = (turnEvent) => {
    // Ignore stale turns from a previous slot revision
    if (turnEvent.generation !== undefined && turnEvent.generation !== currentGenerationRef.current) {
      return;
    }
    const currentTimestamp = fmtTime(elapsedSecRef.current);
    setTurns((prev) => {
      if (prev.some((t) => t.turn === turnEvent.turn)) return prev;
      return [...prev, { ...turnEvent, displayTime: currentTimestamp }];
    });
    if (turnEvent.audio_url) {
      audioQueueRef.current.push({
        type: 'turn',
        slot_id: turnEvent.slot_id,
        slot_index: turnEvent.slot_index,
        persona: turnEvent.persona,
        persona_name: turnEvent.persona_name,
        audioUrl: turnEvent.audio_url,
        duration_sec: turnEvent.duration_sec,
        generation: turnEvent.generation,
        session_id: turnEvent.session_id,
        playback_id: turnEvent.playback_id,
      });
      if (!isPlayingAudioRef.current) playNextInQueue();
    } else if (turnEvent.playback_id) {
      // Audio failed generation, advance immediately
      feedback(turnEvent, 'ended');
    }
  };

  useEffect(() => {
    if (transcriptRef.current) {
      transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight;
    }
  }, [turns]);

  const playNextInQueue = () => {
    const next = audioQueueRef.current.shift();
    if (!next) {
      isPlayingAudioRef.current = false;
      setActiveSpeaker(null);
      return;
    }
    if (next.playback_id && (skippingRef.current ||
        next.session_id !== currentSessionRef.current ||
        next.generation !== currentGenerationRef.current ||
        next.slot_id !== slotRef.current?.slot_id)) {
      playNextInQueue();
      return;
    }
    isPlayingAudioRef.current = true;
    setPlaybackState('loading');
    const url = /^https?:/.test(next.audioUrl) ? next.audioUrl :
      `http://${window.location.hostname}:8000${next.audioUrl}`;
    const audio = new Audio(url);
    currentAudioRef.current = audio;
    const valid = () => currentAudioRef.current === audio;
    audio.onplaying = () => {
      if (!valid()) return;
      setPlaybackState('playing');
      setActiveSpeaker(next.persona_name || next.persona || null);
      skippingRef.current = false;
      setIsSkipping(false);
    };
    audio.onwaiting = () => { if (valid()) setPlaybackState('loading'); };
    audio.ontimeupdate = () => {
      if (valid() && next.playback_id) {
        setSlotElapsedSec(slotAudioElapsedRef.current + audio.currentTime);
      }
    };
    audio.onended = () => {
      if (!valid()) return;
      slotAudioElapsedRef.current += audio.currentTime;
      setSlotElapsedSec(slotAudioElapsedRef.current);
      feedback(next, 'ended');
      currentAudioRef.current = null;
      setPlaybackState('loading');
      playNextInQueue();
    };
    const fail = (message) => {
      if (!valid()) return;
      feedback(next, 'error', message);
      clearAudio();
      setPlaybackState('error');
      setPlaybackError(message);
      skippingRef.current = false;
      setIsSkipping(false);
    };
    audio.onerror = () => fail('Audio gagal dimuat. Periksa koneksi lalu mulai ulang sesi.');
    audio.play().catch((err) => fail(`Playback gagal: ${err.message}`));
  };

  const handleSkipNext = async () => {
    if (!currentSessionRef.current || skippingRef.current) return;
    skippingRef.current = true;
    setIsSkipping(true);
    setPlaybackState('loading');
    clearAudio();
    try {
      const res = await fetch(`http://${window.location.hostname}:8000/api/clock/next`, { method: 'POST' });
      if (!res.ok) {
        const err = await res.json();
        alert(`Skip failed: ${err.detail}`);
        skippingRef.current = false;
        setIsSkipping(false);
      }
    } catch (err) {
      alert(`Connection error: ${err.message}`);
      skippingRef.current = false;
      setIsSkipping(false);
    }
  };

  useEffect(() => {
    if (sessionStatus.state === 'running') {
      elapsedIntervalRef.current = setInterval(() => setElapsedSec((p) => p + 1), 1000);
    } else {
      if (elapsedIntervalRef.current) clearInterval(elapsedIntervalRef.current);
    }
    return () => {
      if (elapsedIntervalRef.current) clearInterval(elapsedIntervalRef.current);
    };
  }, [sessionStatus.state]);

  const handleStart = async () => {
    // Unlock browser audio context for subsequent async playback
    try {
      const unlockAudio = new Audio('data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA');
      unlockAudio.play().catch(() => {});
    } catch (_) {}

    setTurns([]);
    setElapsedSec(0);
    elapsedSecRef.current = 0;
    setSlotElapsedSec(0);
    slotAudioElapsedRef.current = 0;
    setPlaybackState('idle');
    setPlaybackError(null);
    clearAudio();
    setCurrentTheme(null);

    const calculatedMaxTurns =
      preset === '1hour_aron' ? 216 :
      preset === '15min' ? 48 :
      preset === 'quick' ? 10 :
      (Number(maxTurns) || 10);

    const themeMode = (preset === '1hour_aron' || preset === '15min') ? 'aron_closeness' : 'single';

    try {
      if (preset === 'clock_pagi_bener') {
        const res = await fetch(`http://${window.location.hostname}:8000/api/clock/start`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            demo_music_sec: 30,
            talk_turns_per_slot: 2,
          }),
        });
        const data = await res.json();
        if (!res.ok) alert(`Gagal memulai Clock: ${data.detail || 'Terjadi kesalahan'}`);
      } else {
        const res = await fetch(`http://${window.location.hostname}:8000/api/session/start`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            topic: tema,
            persona_a: personaA,
            persona_b: personaB,
            preset: preset,
            theme_mode: themeMode,
            turns_per_theme: 6,
            max_turns: calculatedMaxTurns,
          }),
        });
        const data = await res.json();
        if (!res.ok) alert(`Gagal memulai: ${data.detail || 'Terjadi kesalahan'}`);
      }
    } catch (err) {
      alert(`Koneksi error: ${err.message}`);
    }
  };

  const handleStop = async () => {
    try {
      await Promise.allSettled([
        fetch(`http://${window.location.hostname}:8000/api/session/stop`, { method: 'POST' }),
        fetch(`http://${window.location.hostname}:8000/api/clock/stop`, { method: 'POST' }),
      ]);
      if (currentAudioRef.current) {
        currentAudioRef.current.pause();
        currentAudioRef.current = null;
      }
      clearAudio();
      setSlotElapsedSec(0);
      slotAudioElapsedRef.current = 0;
      setPlaybackState('idle');
      currentSessionRef.current = null;
    } catch (err) {
      console.error(err);
    }
  };

  const isRunning = sessionStatus.state === 'running';
  const isRakaSpeaking =
    activeSpeaker === personaA.name ||
    activeSpeaker === 'persona_a' ||
    (isRunning && activeSpeaker === null && turns.length % 2 === 0 && turns.length > 0);
  const isSalsaSpeaking =
    activeSpeaker === personaB.name ||
    activeSpeaker === 'persona_b' ||
    (isRunning && activeSpeaker === null && turns.length % 2 === 1);

  return {
    tema,
    setTema,
    personaA,
    setPersonaA,
    personaB,
    setPersonaB,
    maxTurns,
    setMaxTurns,
    preset,
    setPreset,
    currentTheme,
    elapsedSec,
    fmtTime,
    isRunning,
    wsConnected,
    isRakaSpeaking,
    isSalsaSpeaking,
    turns,
    transcriptRef,
    handleStart,
    handleStop,
    isSkipping,
    playbackState,
    slotElapsedSec,
    handleSkipNext,
    clockSlots,
    currentSlot,
    musicTrack,
    cueSlot,
  };
}
