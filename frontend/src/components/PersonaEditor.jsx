import React, { useState } from 'react';
import { Save, Plus, X, Volume2, CheckCircle2 } from 'lucide-react';

export default function PersonaEditor({ personas, onSavePersona, onTestVoice }) {
  const [selectedPersonaId, setSelectedPersonaId] = useState('persona_a');
  const [formData, setFormData] = useState(null);
  const [saveStatus, setSaveStatus] = useState('');
  const [newCatchphrase, setNewCatchphrase] = useState('');
  const [newFact, setNewFact] = useState('');
  const [newLimit, setNewLimit] = useState('');
  const [newDoNot, setNewDoNot] = useState('');

  // Sync formData when selection or personas change
  React.useEffect(() => {
    if (personas && personas[selectedPersonaId]) {
      setFormData(JSON.parse(JSON.stringify(personas[selectedPersonaId])));
    }
  }, [selectedPersonaId, personas]);

  if (!formData) {
    return <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '40px' }}>Memuat data persona...</div>;
  }

  const handleFieldChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleAddItem = (field, item, setter) => {
    if (!item.trim()) return;
    setFormData((prev) => ({
      ...prev,
      [field]: [...(prev[field] || []), item.trim()],
    }));
    setter('');
  };

  const handleRemoveItem = (field, index) => {
    setFormData((prev) => ({
      ...prev,
      [field]: prev[field].filter((_, i) => i !== index),
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaveStatus('Menyimpan...');
    try {
      await onSavePersona(selectedPersonaId, formData);
      setSaveStatus('Tersimpan!');
      setTimeout(() => setSaveStatus(''), 3000);
    } catch (err) {
      setSaveStatus('Gagal menyimpan');
    }
  };

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto' }}>
      {/* Persona Selector Tabs */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '24px' }}>
        {['persona_a', 'persona_b'].map((pid) => {
          const p = personas?.[pid];
          const isSelected = selectedPersonaId === pid;
          return (
            <button
              key={pid}
              onClick={() => setSelectedPersonaId(pid)}
              className="studio-card"
              style={{
                flex: 1,
                cursor: 'pointer',
                border: isSelected ? '2px solid var(--accent-cyan)' : '1px solid var(--border-subtle)',
                background: isSelected ? 'rgba(0, 242, 254, 0.08)' : 'var(--bg-card)',
                textAlign: 'left',
              }}
            >
              <div style={{ fontSize: '1.1rem', fontWeight: 700, color: isSelected ? 'var(--accent-cyan)' : 'var(--text-primary)' }}>
                {p?.name || pid}
              </div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                {p?.gender === 'male' ? 'Penyiar Pria (Persona A)' : 'Penyiar Wanita (Persona B)'}
              </div>
            </button>
          );
        })}
      </div>

      {/* Edit Form */}
      <form onSubmit={handleSubmit} className="studio-card">
        <div className="card-title">
          <span>Edit Kartu Persona: {formData.name}</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => onTestVoice(formData.speaking_style, formData.gender === 'male' ? 'male_voice' : 'female_voice')}
            >
              <Volume2 size={16} />
              Uji Suara
            </button>
            <button type="submit" className="btn btn-primary">
              <Save size={16} />
              Simpan Persona
            </button>
          </div>
        </div>

        {saveStatus && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--accent-emerald)', marginBottom: '16px', fontSize: '0.875rem' }}>
            <CheckCircle2 size={16} /> {saveStatus}
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
          <div className="form-group">
            <label className="form-label">Nama Persona</label>
            <input
              type="text"
              className="form-input"
              value={formData.name || ''}
              onChange={(e) => handleFieldChange('name', e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">Gender</label>
            <select
              className="form-select"
              value={formData.gender || 'male'}
              onChange={(e) => handleFieldChange('gender', e.target.value)}
            >
              <option value="male">Pria (Male)</option>
              <option value="female">Wanita (Female)</option>
            </select>
          </div>
        </div>

        <div className="form-group">
          <label className="form-label">Gaya Bicara & Karakteristik Vokal</label>
          <textarea
            className="form-textarea"
            style={{ minHeight: '80px' }}
            value={formData.speaking_style || ''}
            onChange={(e) => handleFieldChange('speaking_style', e.target.value)}
          />
        </div>

        {/* Catchphrases */}
        <div className="form-group">
          <label className="form-label">Catchphrases / Frasa Khas</label>
          <div style={{ display: 'flex', gap: '8px' }}>
            <input
              type="text"
              className="form-input"
              placeholder="Contoh: Mantap pisan!, Gas terus!"
              value={newCatchphrase}
              onChange={(e) => setNewCatchphrase(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), handleAddItem('catchphrases', newCatchphrase, setNewCatchphrase))}
            />
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => handleAddItem('catchphrases', newCatchphrase, setNewCatchphrase)}
            >
              <Plus size={16} />
            </button>
          </div>
          <div className="tag-container">
            {formData.catchphrases?.map((cp, idx) => (
              <span key={idx} className="tag-item">
                "{cp}"
                <X size={12} className="tag-remove" onClick={() => handleRemoveItem('catchphrases', idx)} />
              </span>
            ))}
          </div>
        </div>

        {/* Background Facts */}
        <div className="form-group">
          <label className="form-label">Fakta Latar Belakang (Bank Kebenaran Persona)</label>
          <div style={{ display: 'flex', gap: '8px' }}>
            <input
              type="text"
              className="form-input"
              placeholder="Contoh: Suka kopi hitam tanpa gula, Kuliah di Unikom"
              value={newFact}
              onChange={(e) => setNewFact(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), handleAddItem('background_facts', newFact, setNewFact))}
            />
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => handleAddItem('background_facts', newFact, setNewFact)}
            >
              <Plus size={16} />
            </button>
          </div>
          <div className="tag-container">
            {formData.background_facts?.map((fact, idx) => (
              <span key={idx} className="tag-item" style={{ background: 'rgba(0, 242, 254, 0.08)', borderColor: 'rgba(0, 242, 254, 0.2)' }}>
                {fact}
                <X size={12} className="tag-remove" onClick={() => handleRemoveItem('background_facts', idx)} />
              </span>
            ))}
          </div>
        </div>

        {/* Topic Limits & Do Nots */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
          <div className="form-group">
            <label className="form-label">Batasan Topik</label>
            <div style={{ display: 'flex', gap: '8px' }}>
              <input
                type="text"
                className="form-input"
                placeholder="Contoh: Tidak membahas politik praktis"
                value={newLimit}
                onChange={(e) => setNewLimit(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), handleAddItem('topic_limits', newLimit, setNewLimit))}
              />
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => handleAddItem('topic_limits', newLimit, setNewLimit)}
              >
                <Plus size={16} />
              </button>
            </div>
            <div className="tag-container">
              {formData.topic_limits?.map((lim, idx) => (
                <span key={idx} className="tag-item" style={{ borderColor: 'rgba(245, 158, 11, 0.3)' }}>
                  {lim}
                  <X size={12} className="tag-remove" onClick={() => handleRemoveItem('topic_limits', idx)} />
                </span>
              ))}
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Larangan (Do Not)</label>
            <div style={{ display: 'flex', gap: '8px' }}>
              <input
                type="text"
                className="form-input"
                placeholder="Contoh: Jangan mengaku sebagai manusia"
                value={newDoNot}
                onChange={(e) => setNewDoNot(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), handleAddItem('do_not', newDoNot, setNewDoNot))}
              />
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => handleAddItem('do_not', newDoNot, setNewDoNot)}
              >
                <Plus size={16} />
              </button>
            </div>
            <div className="tag-container">
              {formData.do_not?.map((dn, idx) => (
                <span key={idx} className="tag-item" style={{ borderColor: 'rgba(239, 68, 68, 0.3)' }}>
                  {dn}
                  <X size={12} className="tag-remove" onClick={() => handleRemoveItem('do_not', idx)} />
                </span>
              ))}
            </div>
          </div>
        </div>
      </form>
    </div>
  );
}
