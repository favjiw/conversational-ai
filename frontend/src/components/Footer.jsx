import React from 'react';

export default function Footer({ wsConnected }) {
  return (
    <footer className="w-full border-t border-gray-100 bg-[#f8f9fb] py-5 mt-8">
      <div className="max-w-[1140px] mx-auto px-6 flex items-center justify-between text-xs text-gray-400">
        <span>HITS AI Audio Engine v2.4</span>
        <div className="flex items-center gap-6">
          <span>
            Koneksi WebSocket:{' '}
            {wsConnected ? (
              <span className="text-gray-500">Aktif (24ms)</span>
            ) : (
              <span className="text-amber-500">Terputus</span>
            )}
          </span>
          <span>Bitrate: 128 kbps stereo</span>
        </div>
      </div>
    </footer>
  );
}
