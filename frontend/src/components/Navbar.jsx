import React from 'react';
import { Radio, Activity, Settings, BookOpen, Volume2, Cpu } from 'lucide-react';

export default function Navbar({ activeTab, setActiveTab, sessionStatus, apiHealth }) {
  const isRunning = sessionStatus?.state === 'running';
  const isPaused = sessionStatus?.state === 'paused';

  return (
    <header className="top-nav">
      <div className="brand-section">
        <div className="brand-logo">
          <Radio size={26} color="#00f2fe" />
          <div>
            <div className="brand-badge">HITS AI LIVE</div>
            <div className="brand-subtitle">Studio Penyiaran AI 103.9 FM</div>
          </div>
        </div>

        <div className={`on-air-pill ${isRunning ? 'live' : isPaused ? 'paused' : 'idle'}`}>
          <div className="pulse-dot" />
          <span>{isRunning ? 'ON AIR' : isPaused ? 'JEDA' : 'OFF AIR'}</span>
        </div>
      </div>

      <nav className="nav-tabs">
        <button
          className={`nav-tab-btn ${activeTab === 'console' ? 'active' : ''}`}
          onClick={() => setActiveTab('console')}
        >
          <Activity size={16} />
          <span>Konsol Siaran</span>
        </button>

        <button
          className={`nav-tab-btn ${activeTab === 'personas' ? 'active' : ''}`}
          onClick={() => setActiveTab('personas')}
        >
          <Settings size={16} />
          <span>Editor Persona</span>
        </button>

        <button
          className={`nav-tab-btn ${activeTab === 'temas' ? 'active' : ''}`}
          onClick={() => setActiveTab('temas')}
        >
          <BookOpen size={16} />
          <span>Tema & Rundown</span>
        </button>

        <button
          className={`nav-tab-btn ${activeTab === 'tts' ? 'active' : ''}`}
          onClick={() => setActiveTab('tts')}
        >
          <Volume2 size={16} />
          <span>Laboratorium TTS</span>
        </button>

        <button
          className={`nav-tab-btn ${activeTab === 'experiments' ? 'active' : ''}`}
          onClick={() => setActiveTab('experiments')}
        >
          <Cpu size={16} />
          <span>Runner Eksperimen</span>
        </button>
      </nav>

      <div className="system-telemetry">
        <div className="telemetry-chip">
          <span style={{ color: 'var(--text-muted)' }}>LLM:</span>
          <span style={{ color: apiHealth?.llm_mode === 'mock' ? 'var(--accent-amber)' : 'var(--accent-emerald)', fontWeight: 600 }}>
            {apiHealth?.llm_mode?.toUpperCase() || 'MOCK'}
          </span>
        </div>
        <div className="telemetry-chip">
          <span style={{ color: 'var(--text-muted)' }}>TTS:</span>
          <span style={{ color: apiHealth?.tts_mode === 'mock' ? 'var(--accent-amber)' : 'var(--accent-emerald)', fontWeight: 600 }}>
            {apiHealth?.tts_provider?.toUpperCase() || 'MOCK'}
          </span>
        </div>
      </div>
    </header>
  );
}
