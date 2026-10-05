import React, { useState } from 'react';
import { BookOpen, Tag, Clock, Edit3, PlusCircle } from 'lucide-react';

export default function TemaLibrary({ clock }) {
  const talkSlots = clock?.slots?.filter((s) => s.type === 'talk') || [];
  const [selectedSlotId, setSelectedSlotId] = useState(talkSlots[0]?.id || 's03');

  const activeSlot = talkSlots.find((s) => s.id === selectedSlotId) || talkSlots[0];
  const tema = activeSlot?.tema;

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
      <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '24px' }}>
        {/* Slot / Tema List */}
        <div className="studio-card">
          <div className="card-title">
            <span>Daftar Slot Bicara (Talk)</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {talkSlots.map((slot) => {
              const isSelected = slot.id === selectedSlotId;
              const mode = slot.tema?.mode || 'improv';
              return (
                <div
                  key={slot.id}
                  onClick={() => setSelectedSlotId(slot.id)}
                  style={{
                    padding: '12px',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    background: isSelected ? 'rgba(0, 242, 254, 0.1)' : 'var(--bg-tertiary)',
                    border: isSelected ? '1px solid var(--accent-cyan)' : '1px solid var(--border-subtle)',
                    transition: 'all 0.15s ease',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span style={{ fontWeight: 600, fontSize: '0.9rem', color: isSelected ? 'var(--accent-cyan)' : 'var(--text-primary)' }}>
                      {slot.tema?.title || `Slot ${slot.id}`}
                    </span>
                    <span
                      style={{
                        fontSize: '0.65rem',
                        fontWeight: 700,
                        padding: '2px 6px',
                        borderRadius: '4px',
                        textTransform: 'uppercase',
                        background: mode === 'scripted' ? 'rgba(99, 102, 241, 0.2)' : 'rgba(16, 185, 129, 0.2)',
                        color: mode === 'scripted' ? '#818cf8' : '#34d399',
                      }}
                    >
                      {mode}
                    </span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    <span>Slot: {slot.id}</span>
                    <span>•</span>
                    <span>Durasi: {Math.round(slot.duration_sec / 60)} menit ({slot.duration_sec}s)</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Tema Details & Editor View */}
        <div className="studio-card">
          <div className="card-title">
            <span>Detail Tema: {tema?.title || 'Pilih Tema'}</span>
            <span
              style={{
                fontSize: '0.75rem',
                fontWeight: 700,
                padding: '4px 10px',
                borderRadius: '9999px',
                background: tema?.mode === 'scripted' ? 'rgba(99, 102, 241, 0.2)' : 'rgba(16, 185, 129, 0.2)',
                color: tema?.mode === 'scripted' ? '#818cf8' : '#34d399',
              }}
            >
              Mode: {tema?.mode?.toUpperCase() || 'IMPROV'}
            </span>
          </div>

          {tema ? (
            <div>
              {/* Guidance Section */}
              <div className="form-group">
                <label className="form-label">Arahan / Guidance untuk Persona</label>
                <div
                  style={{
                    background: 'var(--bg-tertiary)',
                    padding: '14px',
                    borderRadius: '8px',
                    border: '1px solid var(--border-subtle)',
                    fontSize: '0.9rem',
                    color: 'var(--text-primary)',
                    lineHeight: '1.6',
                  }}
                >
                  {tema.guidance || 'Tidak ada arahan spesifik (improvisasi bebas sesuai topik)'}
                </div>
              </div>

              {/* Script / Content Section */}
              <div className="form-group" style={{ marginTop: '20px' }}>
                <label className="form-label">
                  Naskah Percakapan (dengan Tanda Jeda)
                </label>
                <div
                  style={{
                    background: 'rgba(0, 0, 0, 0.3)',
                    padding: '16px',
                    borderRadius: '8px',
                    border: '1px solid var(--border-subtle)',
                    minHeight: '140px',
                    lineHeight: '1.7',
                    fontSize: '0.925rem',
                  }}
                >
                  {tema.content ? (
                    <div>
                      {tema.content.split('//').map((chunk, cIdx) => (
                        <p key={cIdx} style={{ marginBottom: '8px' }}>
                          {chunk.split('/').map((sub, sIdx) => (
                            <React.Fragment key={sIdx}>
                              {sub}
                              {sIdx < chunk.split('/').length - 1 && (
                                <span className="bubble-pause-marker">/</span>
                              )}
                            </React.Fragment>
                          ))}
                          {cIdx < tema.content.split('//').length - 1 && (
                            <span className="bubble-pause-marker">//</span>
                          )}
                        </p>
                      ))}
                    </div>
                  ) : (
                    <div style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>
                      Mode improv: Tidak ada teks naskah tetap. Persona berdialog langsung berdasarkan persona card dan arahan topik.
                    </div>
                  )}
                </div>
              </div>

              {/* Pause marker cheat sheet */}
              <div style={{ marginTop: '24px', padding: '12px 16px', background: 'rgba(245, 158, 11, 0.08)', borderRadius: '8px', border: '1px solid rgba(245, 158, 11, 0.2)', fontSize: '0.8rem' }}>
                <strong style={{ color: 'var(--accent-amber)' }}>Panduan Penanda Jeda Vokal (PRD FR-4):</strong>
                <ul style={{ paddingLeft: '18px', marginTop: '4px', color: 'var(--text-secondary)' }}>
                  <li><code>/</code> : Jeda pendek (400ms) untuk pemisah frasa santai.</li>
                  <li><code>//</code> : Jeda panjang (900ms) untuk jeda pergantian topik atau intonasi penekanan.</li>
                </ul>
              </div>
            </div>
          ) : (
            <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '40px' }}>
              Pilih slot di sebelah kiri untuk melihat detail tema.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
