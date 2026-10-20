import React from 'react';

export interface ProgramInfo {
  title: string;
  station: string;
  /** Host's pinned "bait" question, e.g. "APA CERITA HORROR KAMU SOBAT HITS?" */
  pinnedQuestion?: string;
}

export interface PanelSpeaker {
  persona: 'persona_a' | 'persona_b';
  name: string;
  role: string;
}

/** What the right column of the bottom panel shows. */
export type InfoCard =
  | { kind: 'talk'; label: string; topic?: string; badge?: string }
  | { kind: 'song'; title: string; artist: string; badge?: string; requestedBy?: string; progress: number }
  | { kind: 'cue'; label: string }
  | null;

export interface PortraitHUDProps {
  program: ProgramInfo;
  currentTime: string;
  /** Top panel first, bottom panel second (follows the layout order). */
  panels: [PanelSpeaker, PanelSpeaker];
  activeSpeaker: 'persona_a' | 'persona_b' | null;
  info: InfoCard;
}

/**
 * Overlay of the 9:16 live output, placed around the TikTok UI (see
 * layout/stageLayout.ts): program pill on the panel divider, pinned question
 * just under the header zone, a speaker marker per panel, and the dynamic
 * talk/song card in the bottom panel's right column (clear of the comments).
 */
export const PortraitHUD: React.FC<PortraitHUDProps> = ({ program, currentTime, panels, activeSpeaker, info }) => (
  <div className="portrait-hud">
    {panels.map((p, i) => (
      <div
        key={p.persona}
        className={`ph-panel ${i === 0 ? 'top' : 'bottom'} ${p.persona} ${activeSpeaker === p.persona ? 'speaking' : ''}`}
      >
        <div className="ph-name">
          <span className="ph-dot" />
          <span className="ph-name-text">{p.name}</span>
          <span className="ph-role">{p.role}</span>
        </div>
      </div>
    ))}

    <div className="ph-program">
      <span className="ph-ai">AI</span>
      <span className="ph-title">{program.title}</span>
      <span className="ph-sep" />
      <span className="ph-station">{program.station}</span>
      <span className="ph-sep" />
      <span className="ph-time">{currentTime}</span>
    </div>

    {program.pinnedQuestion && (
      <div className="ph-pinned">
        <span className="ph-pin">📌</span>
        <span>{program.pinnedQuestion}</span>
      </div>
    )}

    {info && (
      <div className={`ph-info ${info.kind}`}>
        {info.kind === 'song' && (
          <>
            <span className="ph-info-badge">{info.badge || 'NOW PLAYING'}</span>
            <span className="ph-info-title">{info.title}</span>
            <span className="ph-info-sub">{info.artist}</span>
            {info.requestedBy && <span className="ph-info-request">Request @{info.requestedBy}</span>}
            <div className="ph-progress"><div style={{ width: `${info.progress}%` }} /></div>
          </>
        )}
        {info.kind === 'talk' && (
          <>
            <span className="ph-info-badge">{info.badge || 'SEDANG DIBAHAS'}</span>
            <span className="ph-info-title">{info.topic || info.label}</span>
            {info.topic && <span className="ph-info-sub">{info.label}</span>}
          </>
        )}
        {info.kind === 'cue' && (
          <>
            <span className="ph-info-badge">ON AIR</span>
            <span className="ph-info-title">{info.label}</span>
          </>
        )}
      </div>
    )}
  </div>
);

export default PortraitHUD;
