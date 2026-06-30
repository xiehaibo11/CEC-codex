import Cookies from 'js-cookie'
import { getAuthRequired } from './authState'

const API_BASE_URL = process.env.NODE_ENV === 'production'
  ? '/api'
  : '/api'

export function isAuthenticated(): boolean {
  if (!getAuthRequired()) return true
  return !!Cookies.get('arena_token')
}

export async function apiRequest(
  endpoint: string,
  options: RequestInit = {},
  extras: { timeoutMs?: number } = {}
): Promise<Response> {
  const url = `${API_BASE_URL}${endpoint}`

  const headers = new Headers(options.headers || {})
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }

  const token = Cookies.get('arena_token')
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  let timeoutHandle: ReturnType<typeof setTimeout> | null = null
  let signal = options.signal
  if (extras.timeoutMs && !signal) {
    const controller = new AbortController()
    timeoutHandle = setTimeout(() => controller.abort(new Error(`Request timeout after ${extras.timeoutMs}ms`)), extras.timeoutMs)
    signal = controller.signal
  }

  const defaultOptions: RequestInit = {
    ...options,
    credentials: options.credentials ?? 'same-origin',
    headers,
    signal,
  }

  let response: Response
  try {
    response = await fetch(url, defaultOptions)
  } finally {
    if (timeoutHandle) clearTimeout(timeoutHandle)
  }

  if (!response.ok) {
    let errorMessage = `HTTP error! status: ${response.status}`
    try {
      const errorData = await response.json()
      const detail = errorData.detail || errorData.message || errorData.error
      if (Array.isArray(detail)) {
        errorMessage = detail
          .map(item => typeof item === 'string' ? item : item?.msg || JSON.stringify(item))
          .join('; ')
      } else if (detail && typeof detail === 'object') {
        errorMessage = detail.message || detail.msg || JSON.stringify(detail)
      } else if (typeof detail === 'string' && detail.trim()) {
        errorMessage = detail
      }
    } catch (e) {
      // Keep the HTTP status fallback when the response is not JSON.
    }
    throw new Error(errorMessage)
  }

  const contentType = response.headers.get('content-type')
  if (!contentType || !contentType.includes('application/json')) {
    throw new Error('Response is not JSON')
  }

  return response
}
