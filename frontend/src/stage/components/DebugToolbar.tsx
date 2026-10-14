import React from 'react';
import type { ScenarioTurn } from '../scenario/ScenarioPlayer';

export interface DebugToolbarProps {
  sourceMode: 'scenario' | 'live';
  onToggleSourceMode: (mode: 'scenario' | 'live') => void;
  wsConnected?: boolean;
  liveSessionState?: 'idle' | 'running' | 'paused';
  currentSlotLabel?: string;
  onStartLive?: () => void;
  onStopLive?: () => void;
  onSkipLiveSlot?: () => void;
  scenarios: Array<{ id: string; label: string; path: string }>;
  selectedScenarioId: string;
  onSelectScenario: (id: string) => void;
  playerState: string;
  onPlay: () => void;
  onPause: () => void;
  onRestart: () => void;
  turns: ScenarioTurn[];
  turnIndex: number;
  onJumpTurn: (idx: number) => void;
  onTestSpeaker: (persona: 'persona_a' | 'persona_b') => void;
  displayCardMode: 'auto' | 'talk' | 'song';
  onToggleCardMode: () => void;
  showSafeZones: boolean;
  onToggleSafeZones: () => void;
  aspectRatio: '16:9' | 'full' | '9:16';
  onToggleAspectRatio: () => void;
  onToggleDebugPanel: () => void;
}

export const DebugToolbar: React.FC<DebugToolbarProps> = ({
  sourceMode,
  onToggleSourceMode,
  wsConnected = false,
  liveSessionState = 'idle',
  currentSlotLabel,
  onStartLive,
  onStopLive,
  onSkipLiveSlot,
  scenarios,
  selectedScenarioId,
  onSelectScenario,
  playerState,
  onPlay,
  onPause,
  onRestart,
  turns,
  turnIndex,
  onJumpTurn,
  onTestSpeaker,
  displayCardMode,
  onToggleCardMode,
  showSafeZones,
  onToggleSafeZones,
  aspectRatio,
  onToggleAspectRatio,
  onToggleDebugPanel,
}) => {
  return (
    <aside className="debug-toolbar">
      <div className="debug-controls-row">
        {/* Source Mode Toggle Switch */}
        <div className="debug-btn-group">
          <button
            className={`debug-btn ${sourceMode === 'scenario' ? 'active' : ''}`}
            onClick={() => onToggleSourceMode('scenario')}
          >
            Skenario
          </button>
          <button
            className={`debug-btn ${sourceMode === 'live' ? 'active' : ''}`}
            onClick={() => onToggleSourceMode('live')}
          >
            🔴 Live WS
          </button>
        </div>

        {sourceMode === 'live' ? (
          <>
            <span className={`debug-status-pill ${wsConnected ? 'connected' : 'disconnected'}`}>
              {wsConnected ? '● Online' : '○ Offline'}
            </span>

            {liveSessionState !== 'running' ? (
              <button className="debug-btn debug-btn-primary" onClick={onStartLive}>
                Mulai Siaran
              </button>
            ) : (
              <>
                <button className="debug-btn debug-btn-danger" onClick={onStopLive}>
                  Hentikan
                </button>
                <button className="debug-btn" onClick={onSkipLiveSlot}>
                  Lewati »
                </button>
              </>
            )}

            {currentSlotLabel && (
              <span className="debug-slot-badge" title={currentSlotLabel}>
                {currentSlotLabel}
              </span>
            )}
          </>
        ) : (
          <>
            <select
              className="debug-select"
              value={selectedScenarioId}
              onChange={e => onSelectScenario(e.target.value)}
            >
              {scenarios.map(s => (
                <option key={s.id} value={s.id}>
                  {s.label}
                </option>
              ))}
            </select>

            {playerState === 'playing' ? (
              <button className="debug-btn active" onClick={onPause}>
                Jeda
              </button>
            ) : (
              <button className="debug-btn" onClick={onPlay}>
                Putar
              </button>
            )}

            <button className="debug-btn" onClick={onRestart}>
              Ulang
            </button>

            {turns.length > 0 && (
              <select
                className="debug-select"
                value={turnIndex}
                onChange={e => onJumpTurn(Number(e.target.value))}
              >
                {turns.map((t, idx) => (
                  <option key={idx} value={idx}>
                    Turn {idx + 1}: {t.persona === 'persona_a' ? 'Raka' : 'Salsa'} ({t.emotion})
                  </option>
                ))}
              </select>
            )}

            <button className="debug-btn" onClick={() => onTestSpeaker('persona_a')}>
              Tes Raka
            </button>

            <button className="debug-btn" onClick={() => onTestSpeaker('persona_b')}>
              Tes Salsa
            </button>
          </>
        )}
      </div>

      <div className="debug-controls-row">
        <button
          className={`debug-btn ${displayCardMode === 'song' ? 'active' : ''}`}
          onClick={onToggleCardMode}
        >
          Kartu: {displayCardMode === 'song' ? 'Lagu' : 'Talk'}
        </button>

        <button
          className={`debug-btn ${showSafeZones ? 'active' : ''}`}
          onClick={onToggleSafeZones}
        >
          Zona Aman: {showSafeZones ? 'ON' : 'OFF'}
        </button>

        <button
          className={`debug-btn ${aspectRatio === '16:9' ? 'active' : ''}`}
          onClick={onToggleAspectRatio}
        >
          Rasio: {aspectRatio}
        </button>

        <button className="debug-btn" onClick={onToggleDebugPanel}>
          Panel 3D
        </button>
      </div>
    </aside>
  );
};

export default DebugToolbar;
