import React from 'react';

export default function FormatPresetSelector({ preset, setPreset, isRunning }) {
  const options = [
    {
      id: 'clock_pagi_bener',
      label: 'Clock Live HITS',
      badge: '1 Jam HITS',
      desc: '39 Slot (11 Lagu Deezer, 6 Talk, 6 Adlibs, Smash/Jingle)',
      badgeColor: 'bg-rose-100 text-rose-800 font-bold',
      featured: true,
    },
    {
      id: '1hour_aron',
      label: '1 Jam Nonstop',
      badge: '1 Jam',
      desc: '36 Topik Percakapan Aaron (216 turn)',
      badgeColor: 'bg-indigo-100 text-indigo-800',
    },
    {
      id: '15min',
      label: '15 Menit',
      badge: '15 Mnt',
      desc: '8 Topik Percakapan (48 turn)',
      badgeColor: 'bg-blue-100 text-blue-800',
    },
    {
      id: 'quick',
      label: 'Demo Cepat',
      badge: '3 Mnt',
      desc: '1 Topik (10 turn)',
      badgeColor: 'bg-emerald-100 text-emerald-800',
    },
    {
      id: 'custom',
      label: 'Kustom',
      badge: 'Manual',
      desc: 'Topik & giliran bebas',
      badgeColor: 'bg-gray-100 text-gray-700',
    },
  ];

  return (
    <div className="mb-5">
      <div className="flex items-center justify-between mb-2">
        <label className="block text-[11px] font-bold uppercase tracking-wider text-gray-500">
          FORMAT SIARAN & CLOCK RUNDOWN
        </label>
        <span className="text-[11px] text-indigo-600 font-medium">
          {preset === 'clock_pagi_bener' ? '★ Live Clock Rundown Aktif' : 'Mode Percakapan'}
        </span>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2.5">
        {options.map((opt) => (
          <button
            key={opt.id}
            type="button"
            disabled={isRunning}
            onClick={() => setPreset(opt.id)}
            className={`px-3 py-2.5 rounded-xl border text-left transition-all ${
              preset === opt.id
                ? opt.featured
                  ? 'border-rose-500 bg-rose-50/60 text-rose-950 ring-2 ring-rose-500/30 shadow-xs'
                  : 'border-indigo-600 bg-indigo-50/50 text-indigo-900 ring-2 ring-indigo-500/20'
                : 'border-gray-200 hover:border-gray-300 text-gray-700 bg-white'
            } ${isRunning ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer'}`}
          >
            <div className="font-semibold text-xs flex items-center justify-between">
              <span>{opt.label}</span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${opt.badgeColor}`}>
                {opt.badge}
              </span>
            </div>
            <div className="text-[11px] text-gray-500 mt-1 leading-tight">
              {opt.desc}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}