import Cookies from 'js-cookie'
import { setAuthRequired } from './authState'

// Local username+password authentication module.
//
// The backend exposes a small same-origin auth API (proxied via Vite /api):
//   GET  /api/auth/config   -> { auth_enabled, mode }
//   POST /api/auth/register -> { access_token, token_type, user }
//   POST /api/auth/login    -> { access_token, token_type, user }
//   POST /api/auth/logout   -> clears cookie
//   GET  /api/auth/me       -> { id, username, email }
//
// The auth token lives in the `arena_token` cookie (set by the backend; also set
// client-side here for redundancy). apiRequest() reads it and sends it as a
// Bearer token.

// User information interface (local-shaped).
export interface User {
  id: number
  username: string
  email?: string | null
}

interface AuthResponse {
  access_token: string
  token_type: string
  user: User
}

// Parse an error detail out of a non-ok auth response. FastAPI returns
// { detail: string } for most errors and { detail: [{ msg, ... }] } for 422
// validation errors.
async function extractErrorMessage(response: Response, fallback: string): Promise<string> {
  try {
    const data = await response.json()
    const detail = data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => (typeof item === 'string' ? item : item?.msg))
        .filter(Boolean)
        // Pydantic v2 prefixes ValueError messages with "Value error, "
        .map((msg: string) => msg.replace(/^Value error,\s*/, ''))
      if (messages.length) return messages.join(', ')
    }
    if (typeof data?.message === 'string') return data.message
  } catch {
    // ignore JSON parse failures and fall through to the fallback
  }
  return fallback
}

// Load authentication configuration. Returns { authEnabled: true } when auth is
// required, otherwise null (so callers using `!!config` treat no-auth mode as
// disabled). Never throws.
export async function loadAuthConfig(): Promise<{ authEnabled: boolean } | null> {
  try {
    const response = await fetch('/api/auth/config')
    if (!response.ok) {
      setAuthRequired(false)
      return null
    }
    const data = await response.json()
    const authEnabled = !!data?.auth_enabled
    setAuthRequired(authEnabled)
    return authEnabled ? { authEnabled: true } : null
  } catch (error) {
    setAuthRequired(false)
    console.warn('Auth config unavailable, running in local no-auth mode:', error)
    return null
  }
}

// Register a new local user. Throws Error(detail) on failure.
export async function registerUser(username: string, password: string): Promise<User> {
  const response = await fetch('/api/auth/register', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })

  if (!response.ok) {
    throw new Error(await extractErrorMessage(response, 'Registration failed'))
  }

  const data: AuthResponse = await response.json()
  if (data.access_token) {
    Cookies.set('arena_token', data.access_token, { expires: 30 })
  }
  return data.user
}

// Log in an existing local user. Throws Error(detail) on failure.
export async function loginUser(username: string, password: string): Promise<User> {
  const response = await fetch('/api/auth/login', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })

  if (!response.ok) {
    throw new Error(await extractErrorMessage(response, 'Login failed'))
  }

  const data: AuthResponse = await response.json()
  if (data.access_token) {
    Cookies.set('arena_token', data.access_token, { expires: 30 })
  }
  return data.user
}

// Log out: clear the server-side cookie and local cookies. Ignores errors.
export async function logoutUser(): Promise<void> {
  try {
    await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' })
  } catch (error) {
    console.warn('Logout request failed:', error)
  }
  Cookies.remove('arena_token')
  Cookies.remove('arena_user')
}

// Fetch the currently authenticated user. Returns null on 401/any error.
export async function getCurrentUser(): Promise<User | null> {
  // Skip the request if there is no session cookie – avoids a 401 console
  // error when the user is simply not logged in yet.
  if (!Cookies.get('arena_token')) return null
  try {
    const response = await fetch('/api/auth/me', { credentials: 'include' })
    if (!response.ok) return null
    return (await response.json()) as User
  } catch (error) {
    console.warn('Failed to fetch current user:', error)
    return null
  }
}
