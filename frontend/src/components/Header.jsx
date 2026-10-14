import React from 'react';

export default function Header({ isRunning, wsConnected, stageConnected }) {
  return (
    <header className="flex items-center justify-between mb-8">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-black text-white flex items-center justify-center font-bold text-lg select-none shadow-xs">
          H
        </div>
        <div className="flex items-baseline gap-1.5">
          <span className="font-bold text-xl tracking-tight text-gray-900">HITS AI</span>
          <span className="text-xl font-normal text-gray-400">Live</span>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <a
          href="/stage"
          target="_blank"
          rel="noreferrer"
          title={stageConnected ? 'Audio diputar di layar Stage' : 'Stage belum dibuka, audio diputar di halaman ini'}
          className="flex items-center gap-2 border border-gray-200 bg-white rounded-full px-4 py-1.5 text-xs font-medium text-gray-700 shadow-xs hover:bg-gray-50"
        >
          <span className={`w-2 h-2 rounded-full ${stageConnected ? 'bg-sky-500' : 'bg-gray-300'}`}></span>
          <span>{stageConnected ? 'Output: Stage' : 'Output: Console · Buka Stage'}</span>
        </a>
        <div className="flex items-center gap-2 border border-gray-200 bg-white rounded-full px-4 py-1.5 text-xs font-medium text-gray-700 shadow-xs">
          <span
            className={`w-2 h-2 rounded-full ${
              isRunning ? 'bg-red-500 animate-pulse' : 'bg-emerald-500'
            }`}
          ></span>
          <span>{isRunning ? 'Sedang live' : wsConnected ? 'Siap siaran' : 'Offline'}</span>
        </div>
      </div>
    </header>
  );
}

