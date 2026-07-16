import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  PRIVACY_VERSION,
  TERMS_VERSION,
  hasCurrentLegalAcceptance,
  saveLegalAcceptance
} from '../legal/storage'

export default function LegalAcceptanceGate({ children }) {
  const [accepted, setAccepted] = useState(() => hasCurrentLegalAcceptance())
  const [termsChecked, setTermsChecked] = useState(false)
  const [privacyChecked, setPrivacyChecked] = useState(false)

  if (accepted) return children

  const accept = () => {
    if (!termsChecked || !privacyChecked) return
    saveLegalAcceptance()
    setAccepted(true)
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6 flex items-center justify-center">
      <section className="card max-w-xl p-8">
        <p className="text-sm font-medium text-blue-700">Required legal acceptance</p>
        <h1 className="mt-2 text-3xl font-bold">Before you continue</h1>
        <p className="mt-3 text-gray-600">
          Review and accept the current Terms of Service and acknowledge the Privacy Policy before
          using DocuQuery AI. This applies to both users and administrators.
        </p>
        <div className="mt-6 space-y-4">
          <label className="flex gap-3">
            <input
              aria-label="I accept the Terms of Service"
              type="checkbox"
              checked={termsChecked}
              onChange={(event) => setTermsChecked(event.target.checked)}
            />
            <span>
              I accept the <Link className="text-blue-700 underline" to="/terms">Terms of Service</Link>
              <span className="block text-xs text-gray-500">Version {TERMS_VERSION}</span>
            </span>
          </label>
          <label className="flex gap-3">
            <input
              aria-label="I acknowledge the Privacy Policy"
              type="checkbox"
              checked={privacyChecked}
              onChange={(event) => setPrivacyChecked(event.target.checked)}
            />
            <span>
              I acknowledge the <Link className="text-blue-700 underline" to="/privacy">Privacy Policy</Link>
              <span className="block text-xs text-gray-500">Version {PRIVACY_VERSION}</span>
            </span>
          </label>
        </div>
        <button
          onClick={accept}
          disabled={!termsChecked || !privacyChecked}
          className="btn-primary mt-6 w-full disabled:cursor-not-allowed disabled:opacity-50"
        >
          Accept and continue
        </button>
      </section>
    </div>
  )
}
