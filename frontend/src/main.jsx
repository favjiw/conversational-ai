import { StrictMode, lazy, Suspense } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

const StageApp = lazy(() => import('./stage/StageApp'))

// /stage (config default style), /stage-3d-realistic, /stage-animation
const isStageRoute = /^\/stage(-3d-realistic|-animation)?(\/|$)/.test(window.location.pathname)

createRoot(document.getElementById('root')).render(
  <StrictMode>
    {isStageRoute ? (
      <Suspense
        fallback={
          <div className="min-h-screen bg-[#0a0d12] flex items-center justify-center text-sky-400 font-sans">
            Memuat Stage Avatar...
          </div>
        }
      >
        <StageApp />
      </Suspense>
    ) : (
      <App />
    )}
  </StrictMode>,
)

