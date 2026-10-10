import React from 'react';

export default function NowPlayingMusic({ musicTrack, playbackState, slotElapsedSec }) {
  if (!musicTrack) return null;

  const { title, artist, cover_url, image_url, preview_url, category } = musicTrack;
  const artwork = cover_url || image_url;

  return (
    <div className="bg-gradient-to-r from-emerald-900 via-teal-900 to-slate-900 text-white rounded-2xl p-5 shadow-md border border-emerald-500/30 flex flex-wrap items-center justify-between gap-4 animate-fade-in">
      <div className="flex items-center gap-4">
        {/* Album Artwork or Vinyl Disc */}
        <div className="relative w-16 h-16 rounded-xl overflow-hidden bg-black/40 flex-shrink-0 border border-white/20 shadow-inner flex items-center justify-center">
          {artwork ? (
            <img src={artwork} alt={title} className="w-full h-full object-cover" />
          ) : (
            <div className="w-10 h-10 rounded-full border-2 border-dashed border-emerald-400 flex items-center justify-center animate-spin-slow">
              <span className="text-emerald-300 text-sm">🎵</span>
            </div>
          )}
          <span className="absolute bottom-1 right-1 px-1 py-0.5 text-[8px] font-mono bg-black/70 rounded text-emerald-300">
            30s
          </span>
        </div>

        {/* Track Metadata */}
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-emerald-500/30 text-emerald-300 border border-emerald-500/40">
              Now Playing Music ({category || 'Hits'})
            </span>
            <span className="text-[10px] text-gray-400 font-mono">Deezer Preview</span>
          </div>
          <h4 className="text-base font-bold text-white tracking-tight mt-1 line-clamp-1">
            {title || 'Judul Lagu'}
          </h4>
          <p className="text-xs text-emerald-200/80 mt-0.5">
            {artist || 'Artis'}
          </p>
        </div>
      </div>

      {/* Audio Visualizer Waves & Status */}
      <div className="flex items-center gap-4">
        <div className="flex items-end gap-1 h-6">
          <span className="w-1 bg-emerald-400 rounded-full animate-bounce h-4"></span>
          <span className="w-1 bg-emerald-300 rounded-full animate-bounce h-6 delay-75"></span>
          <span className="w-1 bg-emerald-500 rounded-full animate-bounce h-3 delay-150"></span>
          <span className="w-1 bg-teal-400 rounded-full animate-bounce h-5 delay-100"></span>
          <span className="w-1 bg-emerald-400 rounded-full animate-bounce h-2 delay-200"></span>
        </div>

        {preview_url ? (
          <span className={`text-xs font-mono ${playbackState === 'loading' ? 'text-amber-300 animate-pulse' : 'text-emerald-300'}`}>
            {playbackState === 'loading' ? 'LOADING...' : `${Math.floor(slotElapsedSec || 0)}s / 30s`}
          </span>
        ) : (
          <span className="text-xs text-gray-400 italic">Preview simulasi</span>
        )}
      </div>
    </div>
  );
}
