import React, { createContext, useContext, useEffect, useState } from 'react'
import {
  DEFAULT_CONSENT_PREFERENCES,
  getStoredConsent,
  saveConsentPreferences,
  syncOptionalScripts
} from '../legal/storage'

const ConsentContext = createContext({
  preferences: DEFAULT_CONSENT_PREFERENCES,
  hasChoice: false,
  preferencesOpen: false,
  acceptAll: () => {},
  rejectOptional: () => {},
  savePreferences: () => {},
  openPreferences: () => {},
  closePreferences: () => {}
})

export function ConsentProvider({ children }) {
  const initialConsent = getStoredConsent()
  const [preferences, setPreferences] = useState(initialConsent || DEFAULT_CONSENT_PREFERENCES)
  const [hasChoice, setHasChoice] = useState(Boolean(initialConsent))
  const [preferencesOpen, setPreferencesOpen] = useState(false)

  useEffect(() => {
    syncOptionalScripts(preferences)
  }, [preferences])

  const persist = (nextPreferences) => {
    const stored = saveConsentPreferences(nextPreferences)
    setPreferences(stored)
    setHasChoice(true)
    setPreferencesOpen(false)
  }

  return (
    <ConsentContext.Provider value={{
      preferences,
      hasChoice,
      preferencesOpen,
      acceptAll: () => persist({ analytics: true, marketing: true }),
      rejectOptional: () => persist({ analytics: false, marketing: false }),
      savePreferences: persist,
      openPreferences: () => setPreferencesOpen(true),
      closePreferences: () => setPreferencesOpen(false)
    }}>
      {children}
    </ConsentContext.Provider>
  )
}

export function useConsent() {
  return useContext(ConsentContext)
}
