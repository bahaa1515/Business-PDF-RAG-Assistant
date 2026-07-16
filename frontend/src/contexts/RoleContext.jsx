import React, { createContext, useContext, useEffect, useState } from 'react'
import * as api from '../api/client'

const RoleContext = createContext({
  role: null,
  loading: true,
  login: async () => {},
  logout: () => {}
})

export function RoleProvider({ children }) {
  const [role, setRole] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const restoreSession = async () => {
      try {
        const response = await api.getSession()
        setRole(response.data.role)
        api.setCsrfToken(response.data.csrf_token)
      } catch {
        api.setCsrfToken('')
        setRole(null)
      } finally {
        setLoading(false)
      }
    }

    restoreSession()
  }, [])

  const login = async (nextRole, password = '') => {
    const response = await api.login(nextRole, password)
    api.setCsrfToken(response.data.csrf_token)
    setRole(response.data.role)
  }

  const logout = async () => {
    try {
      await api.logout()
    } finally {
      api.setCsrfToken('')
      setRole(null)
    }
  }

  return (
    <RoleContext.Provider value={{ role, loading, login, logout }}>
      {children}
    </RoleContext.Provider>
  )
}

export function useRole() {
  return useContext(RoleContext)
}
