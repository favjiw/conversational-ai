import React from 'react';
import FormatPresetSelector from './FormatPresetSelector';
import TopicBanner from './TopicBanner';

export default function SessionConfig({
  tema,
  setTema,
  personaA,
  setPersonaA,
  personaB,
  setPersonaB,
  elapsedSec,
  fmtTime,
  isRunning,
  handleStart,
  handleStop,
  preset,
  setPreset,
  maxTurns,
  setMaxTurns,
  currentTheme,
}) {
  return (
    <section className="bg-white rounded-2xl border border-gray-200/90 p-7 shadow-xs">
      <FormatPresetSelector
        preset={preset}
        setPreset={setPreset}
        isRunning={isRunning}
      />

      <TopicBanner
        isRunning={isRunning}
        currentTheme={currentTheme}
        preset={preset}
        tema={tema}
        setTema={setTema}
        maxTurns={maxTurns}
        setMaxTurns={setMaxTurns}
      />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-5">
        {/* Penyiar 1 */}
        <div className="bg-[#f9fafb] border border-gray-100 rounded-xl p-4">
          <div className="flex items-center justify-between mb-3">
            <span className="bg-[#e6f4ea] text-[#137333] text-[11px] font-semibold px-2 py-0.5 rounded tracking-wide">
              PENYIAR 1
            </span>
            <span className="text-xs text-gray-400">Karakter Kiri</span>
          </div>
          <div className="flex gap-3">
            <div className="w-[110px] flex-shrink-0">
              <label className="block text-[11px] text-gray-500 font-medium mb-1">Nama</label>
              <input
                type="text"
                value={personaA.name}
                disabled={isRunning}
                onChange={(e) => setPersonaA({ ...personaA, name: e.target.value })}
                className="w-full bg-white border border-gray-200 rounded-lg px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:border-gray-400 disabled:bg-gray-100"
              />
            </div>
            <div className="flex-1 min-w-0">
              <label className="block text-[11px] text-gray-500 font-medium mb-1">Persona & Gaya Bicara</label>
              <input
                type="text"
                value={personaA.style}
                disabled={isRunning}
                onChange={(e) => setPersonaA({ ...personaA, style: e.target.value })}
                className="w-full bg-white border border-gray-200 rounded-lg px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:border-gray-400 disabled:bg-gray-100"
              />
            </div>
          </div>
        </div>

        {/* Penyiar 2 */}
        <div className="bg-[#f9fafb] border border-gray-100 rounded-xl p-4">
          <div className="flex items-center justify-between mb-3">
            <span className="bg-[#fce8e6] text-[#c5221f] text-[11px] font-semibold px-2 py-0.5 rounded tracking-wide">
              PENYIAR 2
            </span>
            <span className="text-xs text-gray-400">Karakter Kanan</span>
          </div>
          <div className="flex gap-3">
            <div className="w-[110px] flex-shrink-0">
              <label className="block text-[11px] text-gray-500 font-medium mb-1">Nama</label>
              <input
                type="text"
                value={personaB.name}
                disabled={isRunning}
                onChange={(e) => setPersonaB({ ...personaB, name: e.target.value })}
                className="w-full bg-white border border-gray-200 rounded-lg px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:border-gray-400 disabled:bg-gray-100"
              />
            </div>
            <div className="flex-1 min-w-0">
              <label className="block text-[11px] text-gray-500 font-medium mb-1">Persona & Gaya Bicara</label>
              <input
                type="text"
                value={personaB.style}
                disabled={isRunning}
                onChange={(e) => setPersonaB({ ...personaB, style: e.target.value })}
                className="w-full bg-white border border-gray-200 rounded-lg px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:border-gray-400 disabled:bg-gray-100"
              />
            </div>
          </div>
        </div>
      </div>

      <div className="mt-6 pt-1 flex items-end justify-between">
        <div>
          <label className="block text-[11px] font-bold uppercase tracking-wider text-gray-400 mb-2">
            DURASI SIARAN
          </label>
          <div className="flex items-center gap-3">
            <div className="border border-gray-200 bg-white rounded-lg px-3 py-1.5 font-mono font-bold text-sm text-gray-900 tracking-wider">
              {fmtTime(elapsedSec)}
            </div>
            <span className="text-xs text-gray-500 font-normal">
              {isRunning ? 'Berjalan' : 'Siap'}
            </span>
          </div>
        </div>

        <div>
          {isRunning ? (
            <button
              onClick={handleStop}
              className="border border-red-500 text-red-600 hover:bg-red-50 font-medium text-sm px-6 py-2 rounded-xl flex items-center gap-2 transition-colors cursor-pointer"
            >
              <span className="w-2.5 h-2.5 bg-red-600 rounded-xs inline-block"></span>
              <span>Berhenti Live</span>
            </button>
          ) : (
            <button
              onClick={handleStart}
              className="bg-black hover:bg-gray-800 text-white font-medium text-sm px-6 py-2.5 rounded-xl flex items-center gap-2 transition-colors cursor-pointer shadow-xs"
            >
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span>Mulai Live</span>
            </button>
          )}
        </div>
      </div>
    </section>
  );
}
