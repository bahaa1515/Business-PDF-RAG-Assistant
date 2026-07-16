import React, { useEffect, useState } from 'react'
import { useConsent } from '../contexts/ConsentContext'

export default function CookieConsentManager() {
  const {
    preferences,
    hasChoice,
    preferencesOpen,
    acceptAll,
    rejectOptional,
    savePreferences,
    openPreferences,
    closePreferences
  } = useConsent()
  const [draft, setDraft] = useState(preferences)

  useEffect(() => setDraft(preferences), [preferences, preferencesOpen])

  return (
    <>
      {!hasChoice && !preferencesOpen && (
        <section
          aria-label="Storage consent"
          className="fixed bottom-4 left-4 right-4 z-40 mx-auto max-w-4xl rounded-xl border border-gray-200 bg-white p-5 shadow-xl"
        >
          <h2 className="text-lg font-semibold">Cookie and storage preferences</h2>
          <p className="mt-2 text-sm text-gray-600">
            Necessary local storage keeps your session and legal choices. Optional analytics and
            marketing storage are disabled unless you choose to enable them.
          </p>
          <div className="mt-4 flex flex-wrap gap-3">
            <button className="btn-primary" onClick={acceptAll}>Accept all</button>
            <button className="btn-secondary" onClick={rejectOptional}>Reject optional</button>
            <button className="btn-secondary" onClick={openPreferences}>Manage preferences</button>
          </div>
        </section>
      )}

      {preferencesOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <section
            aria-modal="true"
            role="dialog"
            aria-labelledby="storage-preferences-title"
            className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl"
          >
            <h2 id="storage-preferences-title" className="text-xl font-semibold">Manage storage preferences</h2>
            <p className="mt-2 text-sm text-gray-600">
              Necessary storage cannot be disabled. No optional analytics or marketing scripts are
              currently installed.
            </p>
            <div className="mt-5 space-y-4">
              <Preference
                label="Necessary storage"
                checked
                disabled
                description="Authentication, legal acceptance, and consent choices."
              />
              <Preference
                label="Analytics storage"
                checked={Boolean(draft.analytics)}
                onChange={(checked) => setDraft({ ...draft, analytics: checked })}
                description="Optional product usage measurement. Disabled by default."
              />
              <Preference
                label="Marketing storage"
                checked={Boolean(draft.marketing)}
                onChange={(checked) => setDraft({ ...draft, marketing: checked })}
                description="Optional marketing personalization. Disabled by default."
              />
            </div>
            <div className="mt-6 flex flex-wrap justify-end gap-3">
              {hasChoice && <button className="btn-secondary" onClick={closePreferences}>Cancel</button>}
              <button
                className="btn-primary"
                onClick={() => savePreferences(draft)}
              >
                Save preferences
              </button>
            </div>
          </section>
        </div>
      )}
    </>
  )
}

function Preference({ label, checked, disabled = false, onChange = () => {}, description }) {
  return (
    <label className="flex items-start gap-3 rounded-lg border border-gray-200 p-4">
      <input
        aria-label={label}
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
        className="mt-1"
      />
      <span>
        <span className="block font-medium">{label}</span>
        <span className="block text-sm text-gray-600">{description}</span>
      </span>
    </label>
  )
}
