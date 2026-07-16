import React from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { RoleProvider, useRole } from './contexts/RoleContext'
import { ConsentProvider } from './contexts/ConsentContext'
import Layout from './components/Layout'
import CookieConsentManager from './components/CookieConsentManager'
import LegalAcceptanceGate from './components/LegalAcceptanceGate'
import ChatPage from './pages/ChatPage'
import DocumentsPage from './pages/DocumentsPage'
import EvaluationPage from './pages/EvaluationPage'
import OptimizationPage from './pages/OptimizationPage'
import AISettingsPage from './pages/AISettingsPage'
import LoginPage from './pages/LoginPage'
import UnauthorizedPage from './pages/UnauthorizedPage'
import AnalyticsPage from './pages/AnalyticsPage'
import TermsPage from './pages/TermsPage'
import PrivacyPage from './pages/PrivacyPage'
import CookiePolicyPage from './pages/CookiePolicyPage'
import './index.css'

function RequireAuth({ children, adminOnly = false }) {
  const { role, loading } = useRole()

  if (loading) {
    return <div className="min-h-screen flex items-center justify-center">Loading session...</div>
  }

  if (!role) {
    return <Navigate to="/login" replace />
  }

  if (adminOnly && role !== 'admin') {
    return <UnauthorizedPage />
  }

  return <LegalAcceptanceGate>{children}</LegalAcceptanceGate>
}

export default function App() {
  return (
    <RoleProvider>
      <ConsentProvider>
        <Router>
          <CookieConsentManager />
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/terms" element={<TermsPage />} />
            <Route path="/privacy" element={<PrivacyPage />} />
            <Route path="/cookie-policy" element={<CookiePolicyPage />} />
          <Route
            path="/"
            element={
              <RequireAuth>
                <Layout>
                  <ChatPage />
                </Layout>
              </RequireAuth>
            }
          />
          <Route
            path="/chat"
            element={
              <RequireAuth>
                <Layout>
                  <ChatPage />
                </Layout>
              </RequireAuth>
            }
          />
          <Route
            path="/documents"
            element={
              <RequireAuth adminOnly>
                <Layout>
                  <DocumentsPage />
                </Layout>
              </RequireAuth>
            }
          />
          <Route
            path="/ai-settings"
            element={
              <RequireAuth adminOnly>
                <Layout>
                  <AISettingsPage />
                </Layout>
              </RequireAuth>
            }
          />
          <Route
            path="/evaluation"
            element={
              <RequireAuth adminOnly>
                <Layout>
                  <EvaluationPage />
                </Layout>
              </RequireAuth>
            }
          />
          <Route
            path="/optimization"
            element={
              <RequireAuth adminOnly>
                <Layout>
                  <OptimizationPage />
                </Layout>
              </RequireAuth>
            }
          />
          <Route
            path="/analytics"
            element={
              <RequireAuth adminOnly>
                <Layout>
                  <AnalyticsPage />
                </Layout>
              </RequireAuth>
            }
          />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Router>
      </ConsentProvider>
    </RoleProvider>
  )
}
