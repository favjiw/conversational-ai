import React from 'react';
import Header from './Header';
import SessionConfig from './SessionConfig';
import SpeakerCards from './SpeakerCards';
import TranscriptCard from './TranscriptCard';
import Footer from './Footer';
import { useLiveSession } from '../hooks/useLiveSession';

export default function LiveSession() {
  const {
    tema,
    setTema,
    personaA,
    setPersonaA,
    personaB,
    setPersonaB,
    elapsedSec,
    fmtTime,
    isRunning,
    wsConnected,
    isRakaSpeaking,
    isSalsaSpeaking,
    turns,
    transcriptRef,
    handleStart,
    handleStop,
    preset,
    setPreset,
    maxTurns,
    setMaxTurns,
    currentTheme,
  } = useLiveSession();

  return (
    <div className="min-h-screen bg-[#f8f9fb] text-gray-900 font-sans flex flex-col justify-between selection:bg-gray-200">
      <div className="max-w-[1140px] w-full mx-auto px-6 py-8 flex-1">
        <Header isRunning={isRunning} wsConnected={wsConnected} />

        <main className="space-y-6">
          <SessionConfig
            tema={tema}
            setTema={setTema}
            personaA={personaA}
            setPersonaA={setPersonaA}
            personaB={personaB}
            setPersonaB={setPersonaB}
            elapsedSec={elapsedSec}
            fmtTime={fmtTime}
            isRunning={isRunning}
            handleStart={handleStart}
            handleStop={handleStop}
            preset={preset}
            setPreset={setPreset}
            maxTurns={maxTurns}
            setMaxTurns={setMaxTurns}
            currentTheme={currentTheme}
          />

          <SpeakerCards
            personaA={personaA}
            personaB={personaB}
            isRakaSpeaking={isRakaSpeaking}
            isSalsaSpeaking={isSalsaSpeaking}
          />

          <TranscriptCard
            turns={turns}
            personaA={personaA}
            personaB={personaB}
            transcriptRef={transcriptRef}
            fmtTime={fmtTime}
          />
        </main>
      </div>

      <Footer wsConnected={wsConnected} />
    </div>
  );
}
