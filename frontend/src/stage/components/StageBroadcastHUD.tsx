import React from 'react';

export interface StageBroadcastHUDProps {
  showSafeZones: boolean;
  programTitle?: string;
  stationName?: string;
  currentTime: string;
  activeSpeaker: 'persona_a' | 'persona_b' | null;
  isSongMode: boolean;
  musicTrack?: {
    title: string;
    artist: string;
    badge?: string;
  } | null;
  songProgress?: number;
  currentTurn?: {
    persona: string;
    text: string;
    emotion?: string;
  } | null;
}

const SPEAKERS = [
  { id: 'persona_a', name: 'Raka', role: 'Penyiar 1', side: 'left' },
  { id: 'persona_b', name: 'Salsa', role: 'Penyiar 2', side: 'right' },
] as const;

/** Strip pause markers (/ and //), bracketed cues and written laughter for display. */
function toSubtitle(text: string): string {
  return text
    .replace(/\[.*?\]|\(.*?\)/g, '')
    .replace(/(^|\s)\/{1,2}(?=\s|$)/g, ' ')
    .replace(/\b(?:ha){2,}h?\b|\b(?:he){2,}h?\b|\bwk(?:wk)*\b/gi, '')
    .replace(/[*#~`"]+/g, '')
    .replace(/[\p{Extended_Pictographic}\u{FE0F}\u{200D}]/gu, '')
    .replace(/\s+([,.!?])/g, '$1')
    .replace(/\s+/g, ' ')
    .trim();
}

/**
 * Overlay for the live output: split-screen halves (one per announcer),
 * a small program/time header, and one bottom card for the subtitle or
 * the song now playing. Nothing is shown when there is nothing to say.
 */
export const StageBroadcastHUD: React.FC<StageBroadcastHUDProps> = ({
  showSafeZones,
  programTitle = 'PAGI BENER',
  stationName = '103.9 HITS Unikom Radio',
  currentTime,
  activeSpeaker,
  isSongMode,
  musicTrack,
  songProgress = 0,
  currentTurn,
}) => {
  const subtitleSpeaker = SPEAKERS.find((s) => s.id === currentTurn?.persona);
  const subtitle = currentTurn?.text ? toSubtitle(currentTurn.text) : '';

  return (
    <div className="stage-hud">
      {SPEAKERS.map((s) => (
        <div
          key={s.id}
          className={`split-half split-${s.side} ${s.id} ${activeSpeaker === s.id ? 'active' : ''}`}
        >
          <div className="name-tag">
            <span className="name-tag-dot" />
            <span className="name-tag-name">{s.name}</span>
            <span className="name-tag-role">{s.role}</span>
          </div>
        </div>
      ))}
      <div className="split-divider" />

      <header className="stage-header">
        <div className="program">
          <span className="program-title">{programTitle}</span>
          <span className="program-station">{stationName}</span>
        </div>
        <div className="time-pill">{currentTime}</div>
      </header>

      {isSongMode && musicTrack ? (
        <div className="bottom-card song-card">
          <span className="song-icon" aria-hidden="true">♪</span>
          <div className="song-details">
            <span className="song-badge">{musicTrack.badge || 'NOW PLAYING'}</span>
            <span className="song-title">{musicTrack.title}</span>
            <span className="song-artist">{musicTrack.artist}</span>
            <div className="song-progress">
              <div className="song-progress-fill" style={{ width: `${songProgress}%` }} />
            </div>
          </div>
        </div>
      ) : (
        subtitle && (
          <div className={`bottom-card subtitle-card ${subtitleSpeaker?.id ?? ''}`}>
            {subtitleSpeaker && <span className="subtitle-name">{subtitleSpeaker.name}</span>}
            <p className="subtitle-text">{subtitle}</p>
          </div>
        )
      )}

      {showSafeZones && (
        <>
          <div className="safe-zone safe-zone-top"><span>Zona aman atas</span></div>
          <div className="safe-zone safe-zone-bottom"><span>Zona aman bawah</span></div>
        </>
      )}
    </div>
  );
};

export default StageBroadcastHUD;
