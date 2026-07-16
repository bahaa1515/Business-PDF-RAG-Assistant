import React from 'react'
import { Link } from 'react-router-dom'

export default function UnauthorizedPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 p-6">
      <div className="w-full max-w-xl bg-white rounded-3xl border border-gray-200 shadow-sm p-8 text-center">
        <h1 className="text-3xl font-bold mb-4">Unauthorized</h1>
        <p className="text-gray-600 mb-6">
          You do not have permission to view this page. Contact an administrator or switch to a different role.
        </p>
        <Link to="/chat" className="btn-primary inline-block">
          Go to Chat
        </Link>
      </div>
    </div>
  )
}
