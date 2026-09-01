// Who is logged in, held in one place so every screen agrees.
//
// On page load a saved token is verified against /api/auth/me rather than
// trusted. A token that expired while the tab was closed should drop you at the
// login screen, not into a dashboard full of failed requests.

import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import * as api from './api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(api.savedUser)
  const [token, setToken] = useState(api.savedToken)
  // 'checking' until we know whether a saved token is still good.
  const [state, setState] = useState(api.savedToken() ? 'checking' : 'anonymous')

  useEffect(() => {
    const saved = api.savedToken()
    if (!saved) return
    let cancelled = false
    api
      .me(saved)
      .then((fresh) => {
        if (cancelled) return
        api.saveSession(saved, fresh)
        setUser(fresh)
        setToken(saved)
        setState('signed-in')
      })
      .catch(() => {
        if (cancelled) return
        api.clearSession()
        setUser(null)
        setToken(null)
        setState('anonymous')
      })
    return () => {
      cancelled = true
    }
  }, [])

  const signIn = useCallback(async (email, password, patientPortal = false) => {
    const result = patientPortal
      ? await api.patientLogin(email, password)
      : await api.login(email, password)
    api.saveSession(result.access_token, result.user)
    setUser(result.user)
    setToken(result.access_token)
    setState('signed-in')
    return result.user
  }, [])

  const signOut = useCallback(async () => {
    // Tell the server first so the token goes on its deny list. If that call
    // fails the local session still has to end - otherwise a network blip would
    // leave someone unable to log out.
    try {
      await api.logout()
    } catch {
      /* ignore */
    }
    api.clearSession()
    setUser(null)
    setToken(null)
    setState('anonymous')
  }, [])

  // Called when any request comes back 401: the token died mid-session.
  const expire = useCallback(() => {
    api.clearSession()
    setUser(null)
    setToken(null)
    setState('expired')
  }, [])

  const value = { user, token, state, signIn, signOut, expire }
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
