import React, { useState, useEffect, useRef } from 'react';
import { Play, Pause, Square, AlertTriangle, ShieldCheck, Volume2, Clock, Zap } from 'lucide-react';

const EMOTION_MAP = {
  happy: { label: 'Senang', emoji: '😄', class: 'happy' },
  excited: { label: 'Semangat', emoji: '🔥', class: 'excited' },
  thoughtful: { label: 'Bijak', emoji: '🤔', class: 'thoughtful' },
  empathetic: { label: 'Empatis', emoji: '💙', class: 'empathetic' },
  surprised: { label: 'Kaget', emoji: '😲', class: 'surprised' },
  sad: { label: 'Sedih', emoji: '🥺', class: 'sad' },
  neutral: { label: 'Santai', emoji: '🎙️', class: 'neutral' },
};

export default function SessionConsole({
  clock,
  personas,
  turns,
  sessionStatus,
  onStart,
  onPause,
  onResume,
  onStop,
  activeSpeaker,
  condition,
  setCondition,
}) {
  const [activeAudioTurn, setActiveAudioTurn] = useState(null);
  const [temaTitle, setTemaTitle] = useState('');
  const [temaGuidance, setTemaGuidance] = useState('');
  const [temaMode, setTemaMode] = useState('improv');
  const [personaPromptA, setPersonaPromptA] = useState('');
  const [personaPromptB, setPersonaPromptB] = useState('');
  const [temaContent, setTemaContent] = useState('');
  const transcriptEndRef = useRef(null);

  // Auto-scroll transcript when new turn arrives
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [turns]);

  const personaA = personas?.persona_a || { name: 'Raka', gender: 'male' };
  const personaB = personas?.persona_b || { name: 'Sari', gender: 'female' };

  const isRunning = sessionStatus?.state === 'running';
  const isPaused = sessionStatus?.state === 'paused';

  // Last turn supervisor verdict
  const lastTurn = turns[turns.length - 1];
  const lastVerdict = lastTurn?.verdict;

  // Play audio manually
  const playTurnAudio = (audioUrl, turnNumber) => {
    if (!audioUrl) return;
    setActiveAudioTurn(turnNumber);
    const audio = new Audio(audioUrl);
    audio.onended = () => setActiveAudioTurn(null);
    audio.onerror = () => setActiveAudioTurn(null);
    audio.play().catch(() => setActiveAudioTurn(null));
  };

  return (
    <div className="console-wrapper">
      {/* ── Speakers Stage (Phase 1 Avatar Indicator) ── */}
      <section className="speakers-stage">
        {/* Persona A */}
        <div className={`speaker-card ${activeSpeaker === 'persona_a' ? 'active-speaker' : ''}`}>
          <div className="speaker-avatar-circle">
            {personaA.name?.substring(0, 2).toUpperCase() || 'RA'}
          </div>
          <div className="speaker-info">
            <div className="speaker-name-row">
              <span className="speaker-name">{personaA.name || 'Penyiar Pria'}</span>
              <span className={`speaker-status-tag ${activeSpeaker === 'persona_a' ? 'speaking' : 'listening'}`}>
                {activeSpeaker === 'persona_a' ? 'Sedang Bicara' : 'Mendengarkan'}
              </span>
            </div>
            <div className="speaker-meta">
              {personaA.speaking_style || 'Santai, ceria, gaul'}
            </div>
            {lastTurn?.persona === 'persona_a' && lastTurn?.emotion && (
              <div style={{ marginTop: '6px' }}>
                <span className={`emotion-badge ${EMOTION_MAP[lastTurn.emotion]?.class || 'neutral'}`}>
                  {EMOTION_MAP[lastTurn.emotion]?.emoji} {EMOTION_MAP[lastTurn.emotion]?.label || lastTurn.emotion}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Persona B */}
        <div className={`speaker-card female ${activeSpeaker === 'persona_b' ? 'active-speaker' : ''}`}>
          <div className="speaker-avatar-circle" style={{ borderColor: 'rgba(236, 72, 153, 0.4)', color: '#ec4899' }}>
            {personaB.name?.substring(0, 2).toUpperCase() || 'SA'}
          </div>
          <div className="speaker-info">
            <div className="speaker-name-row">
              <span className="speaker-name">{personaB.name || 'Penyiar Wanita'}</span>
              <span className={`speaker-status-tag ${activeSpeaker === 'persona_b' ? 'speaking' : 'listening'}`}>
                {activeSpeaker === 'persona_b' ? 'Sedang Bicara' : 'Mendengarkan'}
              </span>
            </div>
            <div className="speaker-meta">
              {personaB.speaking_style || 'Hangat, ramah, tertata'}
            </div>
            {lastTurn?.persona === 'persona_b' && lastTurn?.emotion && (
              <div style={{ marginTop: '6px' }}>
                <span className={`emotion-badge ${EMOTION_MAP[lastTurn.emotion]?.class || 'neutral'}`}>
                  {EMOTION_MAP[lastTurn.emotion]?.emoji} {EMOTION_MAP[lastTurn.emotion]?.label || lastTurn.emotion}
                </span>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* ── Control Bar ── */}
      <div className="studio-card" style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
          {/* Condition Selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
              Kondisi Eksperimen:
            </span>
            <div style={{ display: 'flex', gap: '6px' }}>
              {[
                { id: 'A', name: 'Kondisi A (Langsung)' },
                { id: 'B', name: 'Kondisi B (Re-prompt)' },
                { id: 'C', name: 'Kondisi C (Supervisor Penuh)' },
              ].map((c) => (
                <button
                  key={c.id}
                  disabled={isRunning}
                  onClick={() => setCondition(c.id)}
                  style={{
                    padding: '6px 12px',
                    borderRadius: '6px',
                    border: condition === c.id ? '1px solid var(--accent-cyan)' : '1px solid var(--border-subtle)',
                    background: condition === c.id ? 'rgba(0, 242, 254, 0.15)' : 'var(--bg-tertiary)',
                    color: condition === c.id ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                    fontWeight: condition === c.id ? 700 : 500,
                    fontSize: '0.8rem',
                    cursor: isRunning ? 'not-allowed' : 'pointer',
                  }}
                >
                  {c.name}
                </button>
              ))}
            </div>
          </div>

          {/* Custom Persona Prompts */}
          {!isRunning && !isPaused && (
            <div style={{ flexBasis: '100%', display: 'flex', flexDirection: 'column', gap: '10px', padding: '14px', background: 'var(--bg-tertiary)', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                Prompt Persona Kustom (opsional — menimpa speaking_style/latar persona bawaan untuk sesi ini saja, tanpa menyimpan ke file):
              </span>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--accent-cyan)' }}>
                    {personaA.name || 'Persona A'} (Pria)
                  </label>
                  <textarea
                    placeholder="Mis. Gaya bicara keras kepala, selalu tidak setuju dengan lawan bicara apapun yang ia katakan. Suka kopi pahit, benci dangdut."
                    value={personaPromptA}
                    onChange={(e) => setPersonaPromptA(e.target.value)}
                    rows={4}
                    style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid var(--border-subtle)', background: 'var(--bg-primary)', color: 'var(--text-primary)', resize: 'vertical' }}
                  />
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--accent-pink)' }}>
                    {personaB.name || 'Persona B'} (Wanita)
                  </label>
                  <textarea
                    placeholder="Mis. Gaya bicara lembut tapi teguh pendirian, tidak pernah setuju dengan lawan bicara. Suka teh manis, benci rock."
                    value={personaPromptB}
                    onChange={(e) => setPersonaPromptB(e.target.value)}
                    rows={4}
                    style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid var(--border-subtle)', background: 'var(--bg-primary)', color: 'var(--text-primary)', resize: 'vertical' }}
                  />
                </div>
              </div>
            </div>
          )}

          {/* Custom Tema Input */}
          {!isRunning && !isPaused && (
            <div style={{ flexBasis: '100%', display: 'flex', flexDirection: 'column', gap: '10px', padding: '14px', background: 'var(--bg-tertiary)', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                Topik Sendiri (opsional — kosongkan untuk pakai Tema dari clock):
              </span>
              <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                <input
                  type="text"
                  placeholder="Judul topik, mis. Review Film Horor"
                  value={temaTitle}
                  onChange={(e) => setTemaTitle(e.target.value)}
                  style={{ flex: '1 1 200px', padding: '8px 12px', borderRadius: '6px', border: '1px solid var(--border-subtle)', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}
                />
                <select
                  value={temaMode}
                  onChange={(e) => setTemaMode(e.target.value)}
                  style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid var(--border-subtle)', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}
                >
                  <option value="improv">Improv (dialog bebas)</option>
                  <option value="scripted">Scripted (naskah)</option>
                  <option value="listener_content">Listener Content</option>
                </select>
              </div>
              <textarea
                placeholder="Arahan / materi topik, mis. Bahas 3 film horor Indonesia terbaru, Raka suka yang jumpscare, Sari takut tapi penasaran..."
                value={temaGuidance}
                onChange={(e) => setTemaGuidance(e.target.value)}
                rows={3}
                style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid var(--border-subtle)', background: 'var(--bg-primary)', color: 'var(--text-primary)', resize: 'vertical' }}
              />
              <textarea
                placeholder="Naskah mentah / scripted content (opsional, untuk mode scripted — dengan tanda jeda / dan //)"
                value={temaContent}
                onChange={(e) => setTemaContent(e.target.value)}
                rows={3}
                style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid var(--border-subtle)', background: 'var(--bg-primary)', color: 'var(--text-primary)', resize: 'vertical' }}
              />
            </div>
          )}

          {/* Action Buttons */}
          <div style={{ display: 'flex', gap: '10px' }}>
            {!isRunning && !isPaused && (
              <button
                className="btn btn-primary"
                onClick={() =>
                  onStart(
                    temaGuidance.trim() || temaTitle.trim() || temaContent.trim()
                      ? { title: temaTitle.trim() || 'Topik Pilihan', guidance: temaGuidance.trim(), content: temaContent.trim(), mode: temaMode }
                      : null,
                    personaPromptA.trim() || personaPromptB.trim()
                      ? { personaAStyle: personaPromptA.trim(), personaBStyle: personaPromptB.trim() }
                      : null
                  )
                }
              >
                <Play size={16} fill="currentColor" />
                Mulai Siaran Live
              </button>
            )}

            {isRunning && (
              <button className="btn btn-warning" onClick={onPause}>
                <Pause size={16} />
                Jeda Siaran
              </button>
            )}

            {isPaused && (
              <button className="btn btn-primary" onClick={onResume}>
                <Play size={16} fill="currentColor" />
                Lanjutkan Siaran
              </button>
            )}

            {(isRunning || isPaused) && (
              <button className="btn btn-danger" onClick={onStop}>
                <Square size={16} fill="currentColor" />
                Berhenti Darurat (Killswitch)
              </button>
            )}
          </div>
        </div>
      </div>

      {/* ── Main Grid: Transcript & Supervisor Inspector ── */}
      <div className="console-grid">
        {/* Left: Dialogue Transcript */}
        <div className="studio-card transcript-card">
          <div className="card-title">
            <span>Transkrip Percakapan Live</span>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 'normal' }}>
              {turns.length} Giliran Selesai
            </span>
          </div>

          <div className="transcript-stream">
            {turns.length === 0 ? (
              <div style={{ textAlign: 'center', color: 'var(--text-muted)', marginTop: '80px' }}>
                <Clock size={36} style={{ margin: '0 auto 12px', opacity: 0.5 }} />
                <p>Belum ada percakapan siaran dimulai.</p>
                <p style={{ fontSize: '0.8rem' }}>Klik tombol "Mulai Siaran Live" untuk memulai sesi.</p>
              </div>
            ) : (
              turns.map((t, idx) => {
                const isA = t.persona === 'persona_a';
                const pName = isA ? personaA.name : personaB.name;
                const emotionInfo = EMOTION_MAP[t.emotion] || EMOTION_MAP.neutral;

                // Highlight pause markers
                const renderTextWithPauses = (text) => {
                  const parts = text.split(/(\/\/|\/)/g);
                  return parts.map((part, i) => {
                    if (part === '//') return <span key={i} className="bubble-pause-marker">// (jeda 900ms)</span>;
                    if (part === '/') return <span key={i} className="bubble-pause-marker">/ (jeda 400ms)</span>;
                    return part;
                  });
                };

                return (
                  <div
                    key={idx}
                    className={`transcript-bubble ${isA ? 'persona-a' : 'persona-b'}`}
                  >
                    <div className="transcript-bubble-header">
                      <div className="bubble-sender">
                        <span style={{ color: isA ? 'var(--accent-cyan)' : 'var(--accent-pink)' }}>
                          {pName}
                        </span>
                        <span className={`emotion-badge ${emotionInfo.class}`}>
                          {emotionInfo.emoji} {emotionInfo.label}
                        </span>
                      </div>
                      <span style={{ fontFamily: 'var(--font-mono)' }}>Giliran #{t.turn}</span>
                    </div>

                    <div className="bubble-text">
                      {renderTextWithPauses(t.text)}
                    </div>

                    <div className="bubble-footer">
                      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                        {t.audio_url && (
                          <button
                            className="audio-play-btn"
                            onClick={() => playTurnAudio(t.audio_url, t.turn)}
                          >
                            <Volume2 size={12} />
                            {activeAudioTurn === t.turn ? 'Memutar...' : 'Dengarkan Audio'}
                          </button>
                        )}
                        {t.verdict?.drift_detected && (
                          <span style={{ color: 'var(--accent-rose)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <AlertTriangle size={12} /> Drift Terdeteksi ({t.verdict.drift_types?.join(', ')})
                          </span>
                        )}
                      </div>
                      <span style={{ fontFamily: 'var(--font-mono)' }}>
                        Latensi: {t.latency_ms?.total || 0}ms
                      </span>
                    </div>
                  </div>
                );
              })
            )}
            <div ref={transcriptEndRef} />
          </div>
        </div>

        {/* Right: Supervisor Inspector & Telemetry */}
        <div className="inspector-panel">
          {/* Supervisor Card */}
          <div className="studio-card">
            <div className="card-title">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <ShieldCheck size={18} color="var(--accent-cyan)" />
                <span>Supervisor Inspector (Anti-Drift)</span>
              </div>
            </div>

            {condition !== 'C' ? (
              <div style={{ padding: '16px', background: 'rgba(255, 255, 255, 0.03)', borderRadius: '8px', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                Supervisor dinonaktifkan pada <strong>Kondisi {condition}</strong>.
                Pilih Kondisi C untuk mengaktifkan pemantauan drift dan koreksi real-time.
              </div>
            ) : (
              <div>
                {/* Drift Status Banner */}
                <div className={`verdict-banner ${lastVerdict?.drift_detected ? 'drift' : 'clean'}`}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {lastVerdict?.drift_detected ? (
                      <AlertTriangle size={18} />
                    ) : (
                      <ShieldCheck size={18} />
                    )}
                    <span style={{ fontWeight: 700, fontSize: '0.9rem' }}>
                      {lastVerdict?.drift_detected ? 'DRIFT TERDETEKSI' : 'STATUS PERSONA NORMAL'}
                    </span>
                  </div>
                  <span style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)' }}>
                    Keputusan: {lastVerdict?.action?.toUpperCase() || 'FORWARD'}
                  </span>
                </div>

                {lastVerdict?.drift_detected && (
                  <div style={{ marginTop: '12px' }}>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Jenis Drift:</div>
                    <div style={{ marginTop: '4px' }}>
                      {lastVerdict.drift_types?.map((dt, i) => (
                        <span key={i} className="drift-tag">{dt}</span>
                      ))}
                    </div>
                    {lastVerdict.evidence && (
                      <div className="evidence-box">
                        "{lastVerdict.evidence}"
                      </div>
                    )}
                  </div>
                )}

                {/* Correction Memory View */}
                {lastVerdict?.correction_memory && (
                  <div style={{ marginTop: '16px' }}>
                    <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>
                      Memori Koreksi Supervisor:
                    </div>
                    <div style={{ background: 'rgba(0,0,0,0.25)', padding: '10px', borderRadius: '6px', fontSize: '0.78rem' }}>
                      {lastVerdict.correction_memory.persona_reminder && (
                        <p style={{ marginBottom: '4px' }}>
                          <strong style={{ color: 'var(--accent-amber)' }}>Pengingat:</strong> {lastVerdict.correction_memory.persona_reminder}
                        </p>
                      )}
                      {lastVerdict.correction_memory.facts_to_enforce?.length > 0 && (
                        <div>
                          <strong style={{ color: 'var(--accent-cyan)' }}>Fakta Ditegakkan:</strong>
                          <ul style={{ paddingLeft: '16px', marginTop: '2px' }}>
                            {lastVerdict.correction_memory.facts_to_enforce.map((f, i) => (
                              <li key={i}>{f}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Latency & Telemetry */}
          <div className="studio-card">
            <div className="card-title">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Zap size={18} color="var(--accent-amber)" />
                <span>Rincian Latensi Giliran Terakhir</span>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px', textAlign: 'center' }}>
              <div style={{ background: 'var(--bg-tertiary)', padding: '10px', borderRadius: '8px' }}>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Persona LLM</div>
                <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--accent-cyan)' }}>
                  {lastTurn?.latency_ms?.persona || 0} ms
                </div>
              </div>

              <div style={{ background: 'var(--bg-tertiary)', padding: '10px', borderRadius: '8px' }}>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Supervisor</div>
                <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--accent-indigo)' }}>
                  {lastTurn?.latency_ms?.supervisor || 0} ms
                </div>
              </div>

              <div style={{ background: 'var(--bg-tertiary)', padding: '10px', borderRadius: '8px' }}>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>TTS Audio</div>
                <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--accent-pink)' }}>
                  {lastTurn?.latency_ms?.tts || 0} ms
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
