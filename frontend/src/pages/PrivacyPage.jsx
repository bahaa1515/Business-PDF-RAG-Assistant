import React from 'react'
import LegalPageLayout from '../components/LegalPageLayout'
import { PRIVACY_VERSION } from '../legal/storage'

export default function PrivacyPage() {
  return (
    <LegalPageLayout>
      <article className="card p-8 space-y-5">
        <div><h1 className="text-3xl font-bold">Privacy Policy</h1><p className="text-sm text-gray-500 mt-1">Version {PRIVACY_VERSION}</p></div>
        <p>This portfolio policy explains the data flows currently implemented by DocuQuery AI. It requires legal review before a real public deployment.</p>
        <section><h2 className="text-xl font-semibold">Data processed</h2><p className="mt-2 text-gray-700">The app processes uploaded documents, questions, generated answers, citations, evaluation results, feedback, session identifiers, and legal/storage preferences.</p></section>
        <section><h2 className="text-xl font-semibold">Service providers</h2><p className="mt-2 text-gray-700">Document chunks and questions may be sent to the configured AI API provider for embeddings and answer generation.</p></section>
        <section><h2 className="text-xl font-semibold">Demo storage</h2><p className="mt-2 text-gray-700">Legal acceptance and consent preferences are stored in this browser for demo mode. Production requires server-side user-level acceptance records and an appropriate retention policy.</p></section>
      </article>
    </LegalPageLayout>
  )
}
