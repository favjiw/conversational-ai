import React from 'react';

export default function SpeakerCards({
  personaA,
  personaB,
  isRakaSpeaking,
  isSalsaSpeaking,
}) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* Penyiar 1 Card */}
      <div className="bg-white rounded-2xl border border-gray-200/90 p-7 flex flex-col justify-between shadow-xs min-h-[340px]">
        <div className="flex items-center justify-between mb-4">
          <span className="bg-[#e6f4ea] text-[#137333] text-[11px] font-semibold px-2 py-0.5 rounded tracking-wide">
            PENYIAR 1
          </span>
          {isRakaSpeaking ? (
            <span className="flex items-center gap-1.5 text-xs font-medium text-[#137333]">
              <span className="w-2 h-2 rounded-full bg-[#137333] animate-pulse"></span>
              Berbicara
            </span>
          ) : (
            <span className="text-xs text-gray-400">Standby</span>
          )}
        </div>

        <div className="flex flex-col items-center justify-center my-auto py-2">
          <div className="flex items-center justify-center">
            <div
              className={`w-[104px] h-[104px] rounded-full flex items-center justify-center transition-all duration-300 ${
                isRakaSpeaking
                  ? 'border-2 border-teal-300 ring-4 ring-teal-50'
                  : 'border-2 border-teal-100/70'
              }`}
            >
              <div className="w-20 h-20 rounded-full bg-[#e0f2f1] flex items-center justify-center text-[#00695c] font-bold text-3xl select-none">
                {personaA.name ? personaA.name.charAt(0).toUpperCase() : 'R'}
              </div>
            </div>
          </div>

          <h3 className="text-lg font-bold text-gray-900 mt-4 tracking-tight">
            {personaA.name || 'Raka'}
          </h3>
          <p className="text-xs text-gray-500 mt-1">
            Suara pria • Karakter ceria & lugas
          </p>
        </div>

        <div className="border-t border-gray-100 pt-4 flex flex-col items-center justify-center text-center mt-3">
          {isRakaSpeaking ? (
            <>
              <div className="flex items-center gap-1.5 text-xs font-semibold text-[#137333]">
                <span className="w-1.5 h-1.5 rounded-full bg-[#137333] inline-block animate-ping"></span>
                Berbicara
              </div>
              <span className="text-[11px] font-medium text-teal-700 mt-0.5">
                Sedang berbicara
              </span>
            </>
          ) : (
            <div className="flex items-center gap-1.5 text-xs text-gray-400">
              <span className="w-1.5 h-1.5 rounded-full bg-gray-300 inline-block"></span>
              Menunggu giliran
            </div>
          )}
        </div>
      </div>

      {/* Penyiar 2 Card */}
      <div className="bg-white rounded-2xl border border-gray-200/90 p-7 flex flex-col justify-between shadow-xs min-h-[340px]">
        <div className="flex items-center justify-between mb-4">
          <span className="bg-[#fce8e6] text-[#c5221f] text-[11px] font-semibold px-2 py-0.5 rounded tracking-wide">
            PENYIAR 2
          </span>
          {isSalsaSpeaking ? (
            <span className="flex items-center gap-1.5 text-xs font-medium text-[#c5221f]">
              <span className="w-2 h-2 rounded-full bg-[#c5221f] animate-pulse"></span>
              Berbicara
            </span>
          ) : (
            <span className="text-xs text-gray-400">Standby</span>
          )}
        </div>

        <div className="flex flex-col items-center justify-center my-auto py-2">
          <div className="flex items-center justify-center">
            <div
              className={`w-[104px] h-[104px] rounded-full flex items-center justify-center transition-all duration-300 ${
                isSalsaSpeaking
                  ? 'border-2 border-rose-300 ring-4 ring-rose-50'
                  : 'border-2 border-transparent'
              }`}
            >
              <div className="w-20 h-20 rounded-full bg-[#fce4ec] flex items-center justify-center text-[#c2185b] font-bold text-3xl select-none">
                {personaB.name ? personaB.name.charAt(0).toUpperCase() : 'S'}
              </div>
            </div>
          </div>

          <h3 className="text-lg font-bold text-gray-900 mt-4 tracking-tight">
            {personaB.name || 'Salsa'}
          </h3>
          <p className="text-xs text-gray-500 mt-1">
            Suara wanita • Karakter hangat & tanggap
          </p>
        </div>

        <div className="border-t border-gray-100 pt-4 flex flex-col items-center justify-center text-center mt-3">
          {isSalsaSpeaking ? (
            <>
              <div className="flex items-center gap-1.5 text-xs font-semibold text-[#c5221f]">
                <span className="w-1.5 h-1.5 rounded-full bg-[#c5221f] inline-block animate-ping"></span>
                Berbicara
              </div>
              <span className="text-[11px] font-medium text-rose-700 mt-0.5">
                Sedang berbicara
              </span>
            </>
          ) : (
            <div className="flex items-center gap-1.5 text-xs text-gray-400">
              <span className="w-1.5 h-1.5 rounded-full bg-gray-300 inline-block"></span>
              Menunggu giliran
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
