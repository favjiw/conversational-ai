import React from 'react';

// Jendela stage untuk streaming: popup 9:16 tanpa tab/bookmark, dibuka ulang di jendela yang sama
// (nama tetap) supaya tidak menambah tab stage. 540x960 = setengah kanvas 1080x1920.
const STAGE_URL = '/stage?clean=1';
const STAGE_WINDOW = 'hits-stage';
const STAGE_FEATURES = 'popup=yes,width=540,height=960,left=40,top=40';

function openStageWindow(event) {
  event.preventDefault();
  const win = window.open(STAGE_URL, STAGE_WINDOW, STAGE_FEATURES);
  if (win) win.focus();
  else window.open(STAGE_URL, '_blank'); // popup diblokir: tab biasa
}

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
          href={STAGE_URL}
          onClick={openStageWindow}
          title={stageConnected
            ? 'Audio diputar di layar Stage. Klik untuk membuka jendela stage 9:16.'
            : 'Stage belum dibuka, audio diputar di halaman ini. Klik untuk membuka jendela stage 9:16.'}
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

