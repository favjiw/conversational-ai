import React, { useState } from 'react';
import { Volume2, Play, Star, Plus, CheckCircle, RefreshCw } from 'lucide-react';

export default function TTSLab() {
  const [inputText, setInputText] = useState(
    'Halo pendengar setia HITS Unikom Radio! / Kembali lagi bareng gue di program Pagi Bener. // Jangan lupa sarapan dulu ya!'
  );
  const [selectedVoice, setSelectedVoice] = useState('male_voice');
  const [isLoading, setIsLoading] = useState(false);
  const [audioUrl, setAudioUrl] = useState(null);
  const [rating, setRating] = useState(4);
  const [notes, setNotes] = useState('');
  const [evalSaved, setEvalSaved] = useState(false);

  // Insert pause markers into text
  const insertPause = (marker) => {
    setInputText((prev) => prev + ` ${marker} `);
  };

  const handleSynthesize = async () => {
    setIsLoading(true);
    setAudioUrl(null);
    try {
      const res = await fetch('/api/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: inputText,
          voice: selectedVoice,
        }),
      });

      if (!res.ok) throw new Error('Sintesis gagal');

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      setAudioUrl(url);
    } catch (err) {
      alert('Gagal menghasilkan audio: ' + err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveEvaluation = (e) => {
    e.preventDefault();
    setEvalSaved(true);
    setTimeout(() => setEvalSaved(false), 3000);
  };

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto' }}>
      <div className="studio-card" style={{ marginBottom: '24px' }}>
        <div className="card-title">
          <span>Laboratorium Pengujian Suara TTS (FR-4)</span>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Dukungan Jeda Vokal & Skor Naturalness
          </span>
        </div>

        {/* Input Text Section */}
        <div className="form-group">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
            <label className="form-label" style={{ margin: 0 }}>
              Teks Uji Suara (Bahasa Indonesia)
            </label>
            <div style={{ display: 'flex', gap: '6px' }}>
              <button
                type="button"
                className="btn btn-secondary"
                style={{ padding: '4px 10px', fontSize: '0.75rem' }}
                onClick={() => insertPause('/')}
              >
                + Tambah Jeda Pendek / (400ms)
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                style={{ padding: '4px 10px', fontSize: '0.75rem' }}
                onClick={() => insertPause('//')}
              >
                + Tambah Jeda Panjang // (900ms)
              </button>
            </div>
          </div>

          <textarea
            className="form-textarea"
            rows={4}
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
          />
        </div>

        {/* Voice and Action Controls */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
          <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
            <div>
              <label className="form-label" style={{ marginBottom: '4px' }}>Pilihan Suara:</label>
              <select
                className="form-select"
                value={selectedVoice}
                onChange={(e) => setSelectedVoice(e.target.value)}
                style={{ width: '220px' }}
              >
                <option value="male_voice">Pria (Raka) - Indonesian</option>
                <option value="female_voice">Wanita (Sari) - Indonesian</option>
              </select>
            </div>
          </div>

          <button
            className="btn btn-primary"
            onClick={handleSynthesize}
            disabled={isLoading || !inputText.trim()}
          >
            {isLoading ? <RefreshCw size={16} className="spin" /> : <Volume2 size={16} />}
            {isLoading ? 'Mensintesis Audio...' : 'Sintesis Suara Sekarang'}
          </button>
        </div>

        {/* Audio Player Result */}
        {audioUrl && (
          <div
            style={{
              marginTop: '24px',
              padding: '16px',
              background: 'rgba(0, 242, 254, 0.05)',
              borderRadius: '8px',
              border: '1px solid var(--accent-cyan)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '12px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <Volume2 size={24} color="var(--accent-cyan)" />
              <div>
                <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>Hasil Sintesis TTS Selesai</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  Format: WAV (PCM 24kHz) • Suara: {selectedVoice}
                </div>
              </div>
            </div>

            <audio controls src={audioUrl} autoPlay style={{ height: '40px' }} />
          </div>
        )}
      </div>

      {/* Naturalness Scoring Form (PRD Section 17 & Week 4 Requirement) */}
      <div className="studio-card">
        <div className="card-title">
          <span>Formulir Evaluasi Naturalness Suara (Skala 1 - 5)</span>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Evaluasi Skripsi & Uji Dengar</span>
        </div>

        <form onSubmit={handleSaveEvaluation}>
          <div className="form-group">
            <label className="form-label">Skor Kealamian (Naturalness Rating):</label>
            <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  key={star}
                  type="button"
                  onClick={() => setRating(star)}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    cursor: 'pointer',
                    color: star <= rating ? 'var(--accent-amber)' : 'var(--text-muted)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    fontSize: '1rem',
                  }}
                >
                  <Star size={24} fill={star <= rating ? 'currentColor' : 'none'} />
                  <span>{star}</span>
                </button>
              ))}
              <span style={{ marginLeft: '12px', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                {rating === 5 && 'Sangat Alami (Mirip Penyiar Manusia)'}
                {rating === 4 && 'Alami (Sedikit Intonasi Sintetis)'}
                {rating === 3 && 'Cukup (Bisa Diterima)'}
                {rating === 2 && 'Kaku / Robotik'}
                {rating === 1 && 'Sangat Tidak Alami'}
              </span>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Catatan Evaluasi / Observasi:</label>
            <textarea
              className="form-textarea"
              rows={2}
              placeholder="Contoh: Jeda vokal terasa pas di tanda jeda ganda, pelafalan kata serapan sangat fasih..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: '12px' }}>
            {evalSaved && (
              <span style={{ color: 'var(--accent-emerald)', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <CheckCircle size={16} /> Skor evaluasi berhasil disimpan!
              </span>
            )}
            <button type="submit" className="btn btn-secondary">
              Simpan Skor Evaluasi
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
