import React from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useRole } from '../contexts/RoleContext'
import LegalFooter from './LegalFooter'

export default function Layout({ children }) {
  const location = useLocation()
  const navigate = useNavigate()
  const { role, logout } = useRole()
  const isActive = (path) => location.pathname === path || location.pathname.startsWith(path)

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  const linkClass = (path) => `block whitespace-nowrap px-4 py-2 rounded-lg transition-colors ${
    isActive(path) ? 'bg-blue-100 text-blue-700 font-medium' : 'text-gray-700 hover:bg-gray-100'
  }`

  return (
    <div className="min-h-screen bg-gray-50 md:flex md:h-screen">
      <nav className="bg-white shadow-sm border-b border-gray-200 flex flex-col md:w-64 md:border-b-0 md:border-r">
        <div className="p-4 border-b border-gray-200 sm:p-6">
          <h1 className="text-2xl font-bold text-blue-600">DocuQuery AI</h1>
          <p className="text-sm text-gray-600 mt-1">RAG Assistant</p>
        </div>

        <ul className="flex gap-2 overflow-x-auto p-3 md:flex-1 md:flex-col md:gap-0 md:space-y-2 md:p-4">
          <li className="shrink-0 md:shrink"><Link to="/chat" className={linkClass('/chat')}>Chat</Link></li>
          {role === 'admin' && (
            <>
              <li className="shrink-0 md:shrink"><Link to="/documents" className={linkClass('/documents')}>Documents</Link></li>
              <li className="shrink-0 md:shrink"><Link to="/ai-settings" className={linkClass('/ai-settings')}>AI Settings</Link></li>
              <li className="shrink-0 md:shrink"><Link to="/evaluation" className={linkClass('/evaluation')}>Evaluation</Link></li>
              <li className="shrink-0 md:shrink"><Link to="/optimization" className={linkClass('/optimization')}>Optimization</Link></li>
              <li className="shrink-0 md:shrink"><Link to="/analytics" className={linkClass('/analytics')}>Failed Questions</Link></li>
            </>
          )}
        </ul>

        <div className="p-4 border-t border-gray-200 text-sm text-gray-600 space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-medium">Role:</span>
            <span className="text-blue-700 font-semibold">{role}</span>
          </div>
          <button onClick={handleLogout} className="btn-secondary w-full mt-2">Logout</button>
          <div className="pt-3 border-t border-gray-200"><LegalFooter /></div>
        </div>
      </nav>
      <main className="min-w-0 flex-1 overflow-auto">{children}</main>
    </div>
  )
}
