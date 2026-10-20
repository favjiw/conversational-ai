import React from 'react';
import { COVERED_ZONES, FACE_BANDS, SIDE_MARGIN, coveredBy } from '../layout/stageLayout';

export interface FaceMarker {
  name: string;
  /** Canvas fractions (0 - 1). */
  x: number;
  y: number;
}

const pct = (v: number) => `${(v * 100).toFixed(2)}%`;

const ZONE_NAMES: Record<string, string> = {
  header: 'header',
  comments: 'komentar',
  bottom: 'bar bawah',
  side: 'margin sisi',
};

/**
 * Debug overlay for composition checks: TikTok UI zones (red), side margins
 * (orange), target face bands (green), the panel divider, and live markers
 * for where each face actually projects on the canvas.
 */
export const SafeZoneOverlay: React.FC<{ faces: FaceMarker[] }> = ({ faces }) => (
  <div className="safe-zone-overlay" aria-hidden="true">
    {COVERED_ZONES.map(({ id, label, rect }) => (
      <div
        key={id}
        className="sz-covered"
        style={{ left: pct(rect.x0), top: pct(rect.y0), width: pct(rect.x1 - rect.x0), height: pct(rect.y1 - rect.y0) }}
      >
        <span>{label}</span>
      </div>
    ))}
    <div className="sz-margin" style={{ left: 0, width: pct(SIDE_MARGIN) }} />
    <div className="sz-margin" style={{ right: 0, width: pct(SIDE_MARGIN) }} />
    {Object.entries(FACE_BANDS).map(([slot, band]) => (
      <div key={slot} className="sz-face-band" style={{ top: pct(band.y0), height: pct(band.y1 - band.y0) }}>
        <span>Wajah {slot === 'top' ? 'atas' : 'bawah'} {Math.round(band.y0 * 100)}–{Math.round(band.y1 * 100)}%</span>
      </div>
    ))}
    <div className="sz-divider" />
    {faces.map((f) => {
      const covered = coveredBy(f.x, f.y);
      return (
        <div key={f.name} className={`sz-face ${covered ? 'bad' : 'ok'}`} style={{ left: pct(f.x), top: pct(f.y) }}>
          <span>
            {f.name} {Math.round(f.y * 100)}% · {covered ? `tertutup ${ZONE_NAMES[covered]}` : 'OK'}
          </span>
        </div>
      );
    })}
  </div>
);

export default SafeZoneOverlay;
