import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useRole } from '../contexts/RoleContext'
import * as api from '../api/client'

export default function LoginPage() {
  const { login } = useRole()
  const navigate = useNavigate()
  const [adminPassword, setAdminPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const signIn = async (role) => {
    setLoading(true)
    setError('')
    try {
      await login(role, role === 'admin' ? adminPassword : '')
      navigate('/chat')
    } catch (requestError) {
      setError(api.getErrorMessage(requestError, 'Login failed.'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 p-6">
      <div className="w-full max-w-md bg-white rounded-3xl border border-gray-200 shadow-sm p-8">
        <h1 className="text-3xl font-bold mb-4">Welcome to DocuQuery AI</h1>
        <p className="text-gray-600 mb-6">
          Users can ask questions. Admins can manage documents, evaluation, and optimization.
        </p>

        {error && <div className="mb-4 p-3 rounded-lg bg-red-50 text-red-700 text-sm">{error}</div>}

        <button
          onClick={() => signIn('user')}
          disabled={loading}
          className="btn-primary w-full mb-6 disabled:opacity-50"
        >
          Continue as User
        </button>

        <div className="border-t border-gray-200 pt-6">
          <label htmlFor="admin-password" className="block text-sm font-medium mb-2">Admin password</label>
          <input
            id="admin-password"
            type="password"
            value={adminPassword}
            onChange={(event) => setAdminPassword(event.target.value)}
            className="input-field mb-3"
            autoComplete="current-password"
          />
          <button
            onClick={() => signIn('admin')}
            disabled={loading || !adminPassword}
            className="btn-secondary w-full disabled:opacity-50"
          >
            Continue as Admin
          </button>
        </div>
      </div>
    </div>
  )
}
