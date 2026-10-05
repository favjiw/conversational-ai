import React from 'react';

export default function TopicBanner({
  isRunning,
  currentTheme,
  preset,
  tema,
  setTema,
  maxTurns,
  setMaxTurns,
}) {
  if (isRunning && currentTheme) {
    return (
      <div className="bg-indigo-50/70 border border-indigo-100 rounded-xl p-4 mb-4 transition-all">
        <div className="flex items-center justify-between mb-1">
          <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-indigo-700">
            <span className="w-2 h-2 rounded-full bg-indigo-500 animate-ping"></span>
            Topik Siaran Aktif ({currentTheme.theme_index || 1} / {currentTheme.total_themes || 36})
          </span>
          <span className="text-[11px] text-indigo-600 font-mono bg-white px-2 py-0.5 rounded border border-indigo-200">
            Rotasi tiap 6 turn
          </span>
        </div>
        <div className="text-sm font-bold text-gray-900">{currentTheme.title}</div>
        {currentTheme.guidance && (
          <div className="text-xs text-gray-600 mt-1 italic">
            "{currentTheme.guidance}"
          </div>
        )}
      </div>
    );
  }

  if (preset === '1hour_aron' || preset === '15min') {
    return (
      <div className="bg-gray-50 border border-gray-200 rounded-xl p-3.5 text-xs text-gray-700 flex items-center justify-between mb-4">
        <div>
          <span className="font-semibold text-gray-900">Rotasi 36 Pertanyaan Interpersonal Aaron:</span>
          <span className="text-gray-500 ml-1.5">Topik otomatis berganti tiap 6 turn (Set I, II, dan III).</span>
        </div>
        <span className="text-[11px] bg-white border border-gray-300 text-gray-700 font-medium px-2 py-0.5 rounded">
          Otomatis
        </span>
      </div>
    );
  }

  return (
    <div className="space-y-3 mb-4">
      <div>
        <label className="block text-[11px] font-bold uppercase tracking-wider text-gray-400 mb-2">
          TEMA SIARAN
        </label>
        <input
          type="text"
          value={tema}
          disabled={isRunning}
          onChange={(e) => setTema(e.target.value)}
          placeholder="Topik atau tema siaran..."
          className="w-full bg-white border border-gray-200 rounded-xl px-4 py-2.5 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:border-gray-400 transition-colors disabled:bg-gray-50 disabled:text-gray-500"
        />
      </div>
      {preset === 'custom' && (
        <div className="w-48">
          <label className="block text-[11px] font-bold uppercase tracking-wider text-gray-400 mb-1">
            JUMLAH GILIRAN
          </label>
          <input
            type="number"
            min="2"
            max="300"
            value={maxTurns}
            disabled={isRunning}
            onChange={(e) => setMaxTurns(e.target.value)}
            className="w-full bg-white border border-gray-200 rounded-lg px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:border-gray-400 disabled:bg-gray-100"
          />
        </div>
      )}
    </div>
  );
}