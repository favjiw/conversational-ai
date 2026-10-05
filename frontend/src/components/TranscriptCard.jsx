import React from 'react';

export default function TranscriptCard({
  turns,
  personaA,
  personaB,
  transcriptRef,
  fmtTime,
}) {
  return (
    <section className="bg-white rounded-2xl border border-gray-200/90 p-7 shadow-xs">
      <div className="flex items-center justify-between pb-4 border-b border-gray-100">
        <div className="flex items-center gap-2">
          <h2 className="text-base font-bold text-gray-900">Transkrip</h2>
          <span className="bg-gray-100 text-gray-500 text-[11px] font-medium px-2 py-0.5 rounded">
            Otomatis
          </span>
        </div>
        <span className="text-xs text-gray-400 font-medium">
          {turns.length} giliran
        </span>
      </div>

      <div
        ref={transcriptRef}
        className="min-h-[200px] max-h-[380px] overflow-y-auto pt-5 space-y-5 pr-2 scroll-smooth"
      >
        {turns.length === 0 ? (
          <div className="h-[200px] flex flex-col items-center justify-center text-gray-400 gap-2 select-none">
            <svg
              className="w-7 h-7 text-gray-300"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
              />
            </svg>
            <span className="text-xs italic text-gray-400">
              Belum ada percakapan. Klik "Mulai Live".
            </span>
          </div>
        ) : (
          turns.map((t, idx) => {
            const isA = t.persona === 'persona_a' || t.persona_name === personaA.name;
            return (
              <div key={idx} className="flex items-start gap-3.5">
                <span
                  className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${
                    isA ? 'bg-[#00897b]' : 'bg-[#e11d48]'
                  }`}
                ></span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline gap-2 mb-0.5">
                    <span className="font-bold text-sm text-gray-900">
                      {t.persona_name || (isA ? personaA.name : personaB.name)}
                    </span>
                    <span className="font-mono text-xs text-gray-400">
                      {t.displayTime || fmtTime(t.turn * 5)}
                    </span>
                  </div>
                  <p className="text-sm text-gray-700 leading-relaxed break-words">
                    {t.text}
                  </p>
                </div>
              </div>
            );
          })
        )}
      </div>
    </section>
  );
}
