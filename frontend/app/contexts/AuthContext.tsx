'use client'

import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'
import {
  getCurrentUser,
  loadAuthConfig,
  loginUser,
  logoutUser,
  registerUser,
  type User,
} from '@/lib/auth'

interface AuthContextType {
  user: User | null
  loading: boolean
  authEnabled: boolean
  setUser: (user: User | null) => void
  login: (username: string, password: string) => Promise<User>
  register: (username: string, password: string) => Promise<User>
  logout: () => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [authEnabled, setAuthEnabled] = useState(false)

  useEffect(() => {
    const initAuth = async () => {
      try {
        const cfg = await loadAuthConfig()
        setAuthEnabled(!!cfg)

        if (cfg) {
          const currentUser = await getCurrentUser()
          setUser(currentUser)
        }
      } catch (error) {
        console.error('Auth initialization error:', error)
      } finally {
        setLoading(false)
      }
    }

    initAuth()
  }, [])

  const login = async (username: string, password: string): Promise<User> => {
    const loggedInUser = await loginUser(username, password)
    setUser(loggedInUser)
    return loggedInUser
  }

  const register = async (username: string, password: string): Promise<User> => {
    const newUser = await registerUser(username, password)
    setUser(newUser)
    return newUser
  }

  const logout = async () => {
    await logoutUser()
    setUser(null)
    window.location.href = '/login'
  }

  return (
    <AuthContext.Provider value={{
      user,
      loading,
      authEnabled,
      setUser,
      login,
      register,
      logout,
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
