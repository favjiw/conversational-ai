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
  const [preset, setPreset] = useState('1hour_aron');
  const [currentTheme, setCurrentTheme] = useState(null);

  const wsRef = useRef(null);
  const elapsedIntervalRef = useRef(null);
  const audioQueueRef = useRef([]);
  const isPlayingAudioRef = useRef(false);
  const currentAudioRef = useRef(null);
  const transcriptRef = useRef(null);
  const elapsedSecRef = useRef(0);

  useEffect(() => {
    elapsedSecRef.current = elapsedSec;
  }, [elapsedSec]);

  const fmtTime = (s) => {
    const m = Math.floor(s / 60).toString().padStart(2, '0');
    const sec = Math.floor(s % 60).toString().padStart(2, '0');
    return `${m}:${sec}`;
  };

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
          if (msg.data.state === 'idle') setActiveSpeaker(null);
        } else if (msg.type === 'theme_change') {
          setCurrentTheme(msg.data);
        } else if (msg.type === 'turn') {
          handleTurnEvent(msg.data);
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
    const currentTimestamp = fmtTime(elapsedSecRef.current);
    setTurns((prev) => {
      if (prev.some((t) => t.turn === turnEvent.turn)) return prev;
      return [...prev, { ...turnEvent, displayTime: currentTimestamp }];
    });
    if (turnEvent.audio_url) {
      audioQueueRef.current.push({
        persona: turnEvent.persona,
        persona_name: turnEvent.persona_name,
        audioUrl: turnEvent.audio_url,
      });
      if (!isPlayingAudioRef.current) playNextInQueue();
    }
  };

  useEffect(() => {
    if (transcriptRef.current) {
      transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight;
    }
  }, [turns]);

  const playNextInQueue = () => {
    if (audioQueueRef.current.length === 0) {
      isPlayingAudioRef.current = false;
      setActiveSpeaker(null);
      return;
    }
    isPlayingAudioRef.current = true;
    const next = audioQueueRef.current.shift();
    setActiveSpeaker(next.persona_name || next.persona);
    const audioUrl = `http://${window.location.hostname}:8000${next.audioUrl}`;
    const audio = new Audio(audioUrl);
    currentAudioRef.current = audio;
    audio.onended = () => playNextInQueue();
    audio.onerror = () => playNextInQueue();
    audio.play().catch(() => playNextInQueue());
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
    audioQueueRef.current = [];
    isPlayingAudioRef.current = false;
    setCurrentTheme(null);

    const calculatedMaxTurns =
      preset === '1hour_aron' ? 216 :
      preset === '15min' ? 48 :
      preset === 'quick' ? 10 :
      (Number(maxTurns) || 10);

    const themeMode = (preset === '1hour_aron' || preset === '15min') ? 'aron_closeness' : 'single';

    try {
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
    } catch (err) {
      alert(`Koneksi error: ${err.message}`);
    }
  };

  const handleStop = async () => {
    try {
      await fetch(`http://${window.location.hostname}:8000/api/session/stop`, { method: 'POST' });
      if (currentAudioRef.current) {
        currentAudioRef.current.pause();
        currentAudioRef.current = null;
      }
      audioQueueRef.current = [];
      isPlayingAudioRef.current = false;
      setActiveSpeaker(null);
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
  };
}
