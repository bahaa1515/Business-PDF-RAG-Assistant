import React from 'react'
import { Link } from 'react-router-dom'
import { useConsent } from '../contexts/ConsentContext'

export default function LegalFooter({ onManagePreferences }) {
  const { openPreferences } = useConsent()
  const managePreferences = onManagePreferences || openPreferences

  return (
    <footer className="text-xs text-gray-500">
      <div className="flex flex-wrap gap-x-3 gap-y-2">
        <Link className="hover:text-blue-700" to="/terms">Terms of Service</Link>
        <Link className="hover:text-blue-700" to="/privacy">Privacy Policy</Link>
        <Link className="hover:text-blue-700" to="/cookie-policy">Cookie/Storage Policy</Link>
        <button className="text-left hover:text-blue-700" onClick={managePreferences}>
          Manage Cookie Preferences
        </button>
      </div>
    </footer>
  )
}
