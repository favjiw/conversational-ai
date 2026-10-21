import React from 'react';

// Peringatan output siaran di konsol: tanpa ini, audio yang tertahan di tab stage tidak terlihat
// oleh operator (rundown hanya berhenti menunggu audio selesai).
export default function OutputWarnings({ warning }) {
  const items = [];
  if (warning?.ownerAudioBlocked) {
    items.push({
      key: 'blocked',
      title: 'Audio stage diblokir browser (autoplay).',
      body: 'Buka tab stage lalu klik sekali di halamannya. Sampai itu dilakukan, suara tidak keluar dan rundown menunggu.',
    });
  }
  if ((warning?.stageCount ?? 0) > 1) {
    items.push({
      key: 'multi',
      title: `Ada ${warning.stageCount} tab stage terbuka.`,
      body: 'Hanya tab stage yang dibuka paling awal yang memutar audio. Tutup tab stage lainnya supaya suara keluar dari tab yang ditangkap OBS/TikTok LIVE Studio.',
    });
  }
  if (items.length === 0) return null;
  return (
    <div className="mb-6 space-y-2" role="alert">
      {items.map((it) => (
        <div key={it.key} className="flex gap-3 items-start border border-amber-300 bg-amber-50 text-amber-900 rounded-xl px-4 py-3 text-sm">
          <span aria-hidden="true">⚠️</span>
          <div>
            <p className="font-semibold">{it.title}</p>
            <p className="text-amber-800/90 text-xs mt-0.5">{it.body}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
