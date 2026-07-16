export const TERMS_VERSION = '2026-06-14'
export const PRIVACY_VERSION = '2026-06-14'
export const CONSENT_VERSION = '2026-06-14'

export const LEGAL_ACCEPTANCE_STORAGE_KEY = 'docuquery_legal_acceptance'
export const CONSENT_STORAGE_KEY = 'docuquery_storage_consent'

export const DEFAULT_CONSENT_PREFERENCES = Object.freeze({
  necessary: true,
  analytics: false,
  marketing: false
})

function readJson(key) {
  try {
    return JSON.parse(window.localStorage.getItem(key))
  } catch {
    return null
  }
}

export function hasCurrentLegalAcceptance({
  termsVersion = TERMS_VERSION,
  privacyVersion = PRIVACY_VERSION
} = {}) {
  const acceptance = readJson(LEGAL_ACCEPTANCE_STORAGE_KEY)
  return Boolean(
    acceptance?.acceptedAt &&
    acceptance.termsVersion === termsVersion &&
    acceptance.privacyVersion === privacyVersion
  )
}

export function saveLegalAcceptance() {
  const acceptance = {
    termsVersion: TERMS_VERSION,
    privacyVersion: PRIVACY_VERSION,
    acceptedAt: new Date().toISOString()
  }
  window.localStorage.setItem(LEGAL_ACCEPTANCE_STORAGE_KEY, JSON.stringify(acceptance))
  return acceptance
}

export function getStoredConsent() {
  const consent = readJson(CONSENT_STORAGE_KEY)
  if (!consent?.updatedAt || consent.version !== CONSENT_VERSION) return null
  return {
    version: CONSENT_VERSION,
    necessary: true,
    analytics: Boolean(consent.analytics),
    marketing: Boolean(consent.marketing),
    updatedAt: consent.updatedAt
  }
}

export function saveConsentPreferences(preferences) {
  const consent = {
    version: CONSENT_VERSION,
    necessary: true,
    analytics: Boolean(preferences.analytics),
    marketing: Boolean(preferences.marketing),
    updatedAt: new Date().toISOString()
  }
  window.localStorage.setItem(CONSENT_STORAGE_KEY, JSON.stringify(consent))
  return consent
}

export function syncOptionalScripts(preferences) {
  document.querySelectorAll('script[data-consent-category]').forEach((script) => {
    const category = script.dataset.consentCategory
    if (!preferences?.[category]) script.remove()
  })
}
