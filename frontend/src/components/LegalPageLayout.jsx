import React from 'react'
import { Link } from 'react-router-dom'
import LegalFooter from './LegalFooter'

export default function LegalPageLayout({ children }) {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
          <Link to="/" className="text-xl font-bold text-blue-700">DocuQuery AI</Link>
          <Link to="/" className="text-sm text-blue-700 hover:underline">Return to app</Link>
        </div>
      </header>
      <main className="mx-auto max-w-4xl px-6 py-10">{children}</main>
      <div className="mx-auto max-w-4xl border-t border-gray-200 px-6 py-6">
        <LegalFooter />
      </div>
    </div>
  )
}
