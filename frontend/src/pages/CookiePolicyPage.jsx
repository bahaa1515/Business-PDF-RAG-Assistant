import React from 'react'
import LegalPageLayout from '../components/LegalPageLayout'
import { CONSENT_VERSION } from '../legal/storage'

export default function CookiePolicyPage() {
  return (
    <LegalPageLayout>
      <article className="card p-8 space-y-5">
        <div><h1 className="text-3xl font-bold">Cookie and Storage Policy</h1><p className="text-sm text-gray-500 mt-1">Consent version {CONSENT_VERSION}</p></div>
        <p>DocuQuery AI uses necessary security cookies for authentication and CSRF protection, plus browser localStorage for legal and consent choices.</p>
        <section><h2 className="text-xl font-semibold">Necessary storage</h2><p className="mt-2 text-gray-700">The HttpOnly session cookie, CSRF cookie, legal acceptance record, and consent preference record are necessary for the current workflow and cannot be disabled through the consent manager.</p></section>
        <section><h2 className="text-xl font-semibold">Optional storage</h2><p className="mt-2 text-gray-700">Analytics and marketing storage are disabled by default. No optional analytics or marketing scripts are currently installed.</p></section>
        <section><h2 className="text-xl font-semibold">Changing your choice</h2><p className="mt-2 text-gray-700">Use Manage Cookie Preferences from the application footer at any time. Logging out clears the session cookie, and clearing browser storage clears legal and consent choices.</p></section>
      </article>
    </LegalPageLayout>
  )
}
