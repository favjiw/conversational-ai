import React, { useEffect, useRef } from 'react';

export default function ClockRundownTimeline({ slots, currentSlot, isRunning, isSkipping, playbackState, slotElapsedSec, handleSkipNext }) {
  const activeCardRef = useRef(null);
  const currentIdx = currentSlot ? currentSlot.slot_index : -1;
  const slotCount = slots?.length || 0;
  const progressPct = slotCount > 0 ? Math.round(((currentIdx + 1) / slotCount) * 100) : 0;
  // Quarter = number of time markers already reached (rundown has markers at 15/30/45).
  const currentQuarter = currentIdx < 0 ? -1 : (slots || [])
    .slice(0, currentIdx + 1)
    .filter((s) => s.type === 'time_marker').length;

  // Auto-scroll timeline to keep active slot centered in view
  useEffect(() => {
    if (activeCardRef.current) {
      activeCardRef.current.scrollIntoView({
        behavior: 'smooth',
        inline: 'center',
        block: 'nearest',
      });
    }
  }, [currentIdx]);

  if (!slots || slots.length === 0) return null;

  const countOf = (pred) => slots.filter(pred).length;
  const songCount = countOf((s) => s.type === 'song');
  const talkCount = countOf((s) => s.source === 'llm_conversation');
  const adlibCount = countOf((s) => s.type === 'spot_adlibs');

  const getBadge = (type, category) => {
    if (type === 'song') return { icon: '🎵', label: category ? category.toUpperCase() : 'SONG', color: 'bg-emerald-50 text-emerald-700 border-emerald-200' };
    if (type === 'talk') return { icon: '🎙️', label: 'TALK', color: 'bg-indigo-50 text-indigo-700 border-indigo-200' };
    if (type === 'spot_adlibs') return { icon: '📢', label: 'ADLIBS', color: 'bg-amber-50 text-amber-700 border-amber-200' };
    if (type === 'bumper') return { icon: '📻', label: 'BUMPER', color: 'bg-sky-50 text-sky-700 border-sky-200' };
    if (type === 'taping') return { icon: '📼', label: 'TAPING', color: 'bg-sky-50 text-sky-700 border-sky-200' };
    if (type === 'time_marker') return { icon: '⏱️', label: 'MARKER', color: 'bg-purple-50 text-purple-700 border-purple-200' };
    return { icon: '⚡', label: type.toUpperCase(), color: 'bg-rose-50 text-rose-700 border-rose-200' };
  };

  const quarters = [
    { label: 'Q1: 00.00 - 00.15', desc: 'Ice Breaking, Opening, Say Hi' },
    { label: 'Q2: 00.15 - 00.30', desc: 'Teaser 3M' },
    { label: 'Q3: 00.30 - 00.45', desc: 'Segmen 3M' },
    { label: 'Q4: 00.45 - 01.00', desc: 'SKEMA & Closing' },
  ];

  return (
    <div className="bg-white rounded-2xl border border-gray-200/80 shadow-xs p-5 transition-all">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-rose-500 animate-pulse"></span>
            <h3 className="text-sm font-bold tracking-tight text-gray-900 uppercase">
              Clock Rundown: Pagi Bener 1 Jam (HITS 103.9 FM)
            </h3>
            <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-rose-100 text-rose-800 font-semibold">
              {slotCount} Slot Rundown
            </span>
          </div>
          <p className="text-xs text-gray-500 mt-0.5">
            Format siaran radio aktual: {songCount} Lagu Deezer, {talkCount} Segmen Talk AI, {adlibCount} Adlibs, Jingle & Bumper
          </p>
        </div>

        <div className="flex items-center gap-4">
          {/* Action Controls */}
          {isRunning && (
            <button
              onClick={handleSkipNext}
              disabled={isSkipping || currentIdx >= slotCount - 1}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all shadow-xs border ${
                isSkipping || currentIdx >= slotCount - 1
                  ? 'bg-gray-100 text-gray-400 border-gray-200 cursor-not-allowed'
                  : 'bg-white hover:bg-rose-50 text-rose-700 border-rose-200 hover:border-rose-300'
              }`}
            >
              {isSkipping ? (
                <>
                  <span className="w-3 h-3 rounded-full border-2 border-rose-300 border-t-rose-600 animate-spin"></span>
                  Skipping...
                </>
              ) : (
                <>
                  <span>⏭️</span> Next Segmen
                </>
              )}
            </button>
          )}

          <div className="flex items-center gap-3 border-l border-gray-200 pl-4">
            <div className="text-right">
              <div className="text-xs font-semibold text-gray-700">
                {currentIdx >= 0 ? `Slot ${currentIdx + 1} / ${slots.length}` : 'Standby'}
              </div>
              <div className="text-[10px] text-gray-400 font-mono">
                {isRunning ? `${progressPct}% Selesai` : 'Siap siaran'}
              </div>
            </div>
            <div className="w-24 bg-gray-100 rounded-full h-2 overflow-hidden border border-gray-200">
              <div className="bg-rose-500 h-2 rounded-full transition-all duration-500" style={{ width: `${progressPct}%` }}></div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-4 text-center">
        {quarters.map((q, idx) => {
          const isCurrentQuarter = currentQuarter === idx;
          return (
            <div
              key={idx}
              className={`p-2 rounded-xl border text-xs transition-all ${
                isCurrentQuarter
                  ? 'bg-rose-50 border-rose-300 font-semibold text-rose-900 shadow-xs'
                  : 'bg-gray-50/60 border-gray-200/60 text-gray-500'
              }`}
            >
              <div className="font-bold">{q.label}</div>
              <div className="text-[10px] opacity-75 mt-0.5">{q.desc}</div>
            </div>
          );
        })}
      </div>

      <div className="relative">
        <div className="flex gap-2 overflow-x-auto pb-3 pt-1 scrollbar-thin scrollbar-thumb-gray-300">
          {slots.map((slot, idx) => {
            const badge = getBadge(slot.type, slot.category);
            const isActive = currentIdx === idx;
            const isDone = currentIdx > idx;

            return (
              <div
                key={slot.id || idx}
                ref={isActive ? activeCardRef : null}
                className={`flex-shrink-0 w-36 p-2.5 rounded-xl border transition-all text-left relative ${
                  isActive
                    ? 'border-rose-500 bg-rose-50/90 ring-2 ring-rose-500/40 shadow-sm scale-102 z-10'
                    : isDone
                    ? 'border-gray-200 bg-gray-50/70 text-gray-400 opacity-70'
                    : 'border-gray-200/80 bg-white hover:border-gray-300'
                }`}
              >
                <div className="flex items-center justify-between gap-1 mb-1">
                  <span className="text-[10px] font-mono font-bold text-gray-400">#{idx + 1}</span>
                  <span className={`text-[9px] px-1.5 py-0.5 rounded border font-semibold ${badge.color}`}>
                    {badge.icon} {badge.label}
                  </span>
                </div>
                <div
                  className={`text-xs font-semibold truncate ${
                    isActive ? 'text-rose-900 font-bold' : isDone ? 'text-gray-400' : 'text-gray-800'
                  }`}
                  title={slot.label || slot.id}
                >
                  {slot.label || slot.id}
                </div>
                <div className="flex items-center justify-between mt-1 text-[10px] text-gray-400 font-mono">
                  {isActive ? (
                    <span className={playbackState === 'loading' ? 'text-amber-500 font-bold animate-pulse' : 'text-gray-600'}>
                      {playbackState === 'loading' ? 'LOADING...' : `${Math.floor(slotElapsedSec)}s / ${slot.nominal_sec || slot.duration_sec || 0}s`}
                    </span>
                  ) : (
                    <span>{slot.nominal_sec || slot.duration_sec || 0}s</span>
                  )}
                  {isActive && playbackState !== 'loading' && <span className="text-rose-600 font-bold animate-pulse text-[9px]">LIVE NOW</span>}
                  {isDone && <span className="text-emerald-500 font-bold text-[10px]">✓</span>}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
