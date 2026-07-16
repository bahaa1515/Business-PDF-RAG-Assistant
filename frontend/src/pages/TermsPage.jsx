import React from 'react'
import LegalPageLayout from '../components/LegalPageLayout'
import { TERMS_VERSION } from '../legal/storage'

export default function TermsPage() {
  return (
    <LegalPageLayout>
      <article className="card p-8 space-y-5">
        <div><h1 className="text-3xl font-bold">Terms of Service</h1><p className="text-sm text-gray-500 mt-1">Version {TERMS_VERSION}</p></div>
        <p>These portfolio terms describe the technical demo conditions for using DocuQuery AI. They are not lawyer-approved final terms.</p>
        <section><h2 className="text-xl font-semibold">Permitted use</h2><p className="mt-2 text-gray-700">Use the service to upload authorized documents and ask questions about them. Do not upload content you lack permission to process.</p></section>
        <section><h2 className="text-xl font-semibold">AI limitations</h2><p className="mt-2 text-gray-700">Generated answers may be incomplete or incorrect. Verify important decisions against original documents and professional advice.</p></section>
        <section><h2 className="text-xl font-semibold">Availability and responsibility</h2><p className="mt-2 text-gray-700">This demo is provided without guaranteed availability. Administrators are responsible for deployment security, access control, and API costs.</p></section>
      </article>
    </LegalPageLayout>
  )
}
