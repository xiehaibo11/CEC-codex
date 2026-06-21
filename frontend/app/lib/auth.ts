// Authentication configuration interface
interface AuthConfig {
  authProvider: string
  authProxyProvider?: string
  clientId: string
  appName: string
  organizationName: string
  redirectPath: string
  oauthProviders?: AuthOAuthProvider[]
}

export type OAuthProviderType = 'GitHub' | 'Google'

export interface AuthOAuthProvider {
  type: OAuthProviderType
  name: string
  displayName: string
  clientId: string
}

export interface TokenResponse {
  access_token?: string
  token_type?: string
  refresh_token?: string
  id_token?: string
  expires_in?: number
  scope?: string
}

export interface ArenaSessionPayload {
  token: TokenResponse
  user: User
}

// User information interface
export interface User {
  owner: string
  name: string
  createdTime: string
  updatedTime: string
  id: string
  type: string
  displayName: string
  avatar: string
  email: string
  phone: string
  location: string
  address: string[]
  affiliation: string
  title: string
  homepage: string
  bio: string
  tag: string
  region: string
  language: string
  score: number
  isAdmin: boolean
  isGlobalAdmin: boolean
  isForbidden: boolean
  signupApplication: string
}

// Global auth configuration
let authConfig: AuthConfig | null = null

const FORCE_FRESH_AUTH_KEY = 'arena-force-fresh-oauth'
const DEFAULT_AUTH_PROMPT = 'login select_account'
const FRESH_AUTH_PROMPT = 'login consent select_account'

const DEFAULT_OAUTH_PROVIDERS: AuthOAuthProvider[] = [
  {
    type: 'GitHub',
    name: 'github_login',
    displayName: 'GitHub',
    clientId: 'Ov23liwdTwGyhQkcFrYK',
  },
  {
    type: 'Google',
    name: 'google_login',
    displayName: 'Google',
    clientId: 'GOOGLE_CLIENT_ID_REDACTED',
  },
]

// Load authentication configuration
export async function loadAuthConfig(): Promise<AuthConfig | null> {
  if (authConfig) return authConfig

  try {
    const response = await fetch('/auth-config.json')
    if (!response.ok) {
      console.log('No auth config found, authentication disabled')
      return null
    }
    authConfig = await response.json()
    return authConfig
  } catch (error) {
    console.error('Failed to load auth config:', error)
    throw error
  }
}

// Generate URL-safe random string
function generateRandomString(length: number, charset = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'): string {
  const values = new Uint8Array(length)

  if (typeof crypto !== 'undefined' && typeof crypto.getRandomValues === 'function') {
    crypto.getRandomValues(values)
  } else {
    for (let i = 0; i < length; i++) {
      values[i] = Math.floor(Math.random() * 256)
    }
  }

  let result = ''
  for (let i = 0; i < length; i++) {
    result += charset.charAt(values[i] % charset.length)
  }
  return result
}

// Pure JS SHA256 implementation for non-secure contexts (HTTP with non-localhost)
function sha256Fallback(message: string): ArrayBuffer {
  function rightRotate(value: number, amount: number): number {
    return (value >>> amount) | (value << (32 - amount))
  }

  const k = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
  ]

  let h0 = 0x6a09e667, h1 = 0xbb67ae85, h2 = 0x3c6ef372, h3 = 0xa54ff53a
  let h4 = 0x510e527f, h5 = 0x9b05688c, h6 = 0x1f83d9ab, h7 = 0x5be0cd19

  const encoder = new TextEncoder()
  const msgBytes = encoder.encode(message)
  const msgLen = msgBytes.length
  const bitLen = msgLen * 8

  const padLen = (msgLen + 9) % 64 === 0 ? 0 : 64 - ((msgLen + 9) % 64)
  const paddedLen = msgLen + 1 + padLen + 8
  const padded = new Uint8Array(paddedLen)
  padded.set(msgBytes)
  padded[msgLen] = 0x80
  const view = new DataView(padded.buffer)
  view.setUint32(paddedLen - 4, bitLen, false)

  for (let i = 0; i < paddedLen; i += 64) {
    const w = new Array(64)
    for (let j = 0; j < 16; j++) {
      w[j] = view.getUint32(i + j * 4, false)
    }
    for (let j = 16; j < 64; j++) {
      const s0 = rightRotate(w[j - 15], 7) ^ rightRotate(w[j - 15], 18) ^ (w[j - 15] >>> 3)
      const s1 = rightRotate(w[j - 2], 17) ^ rightRotate(w[j - 2], 19) ^ (w[j - 2] >>> 10)
      w[j] = (w[j - 16] + s0 + w[j - 7] + s1) >>> 0
    }

    let a = h0, b = h1, c = h2, d = h3, e = h4, f = h5, g = h6, h = h7
    for (let j = 0; j < 64; j++) {
      const S1 = rightRotate(e, 6) ^ rightRotate(e, 11) ^ rightRotate(e, 25)
      const ch = (e & f) ^ (~e & g)
      const temp1 = (h + S1 + ch + k[j] + w[j]) >>> 0
      const S0 = rightRotate(a, 2) ^ rightRotate(a, 13) ^ rightRotate(a, 22)
      const maj = (a & b) ^ (a & c) ^ (b & c)
      const temp2 = (S0 + maj) >>> 0
      h = g; g = f; f = e; e = (d + temp1) >>> 0
      d = c; c = b; b = a; a = (temp1 + temp2) >>> 0
    }
    h0 = (h0 + a) >>> 0; h1 = (h1 + b) >>> 0; h2 = (h2 + c) >>> 0; h3 = (h3 + d) >>> 0
    h4 = (h4 + e) >>> 0; h5 = (h5 + f) >>> 0; h6 = (h6 + g) >>> 0; h7 = (h7 + h) >>> 0
  }

  const result = new ArrayBuffer(32)
  const resultView = new DataView(result)
  resultView.setUint32(0, h0, false); resultView.setUint32(4, h1, false)
  resultView.setUint32(8, h2, false); resultView.setUint32(12, h3, false)
  resultView.setUint32(16, h4, false); resultView.setUint32(20, h5, false)
  resultView.setUint32(24, h6, false); resultView.setUint32(28, h7, false)
  return result
}

// Generate SHA256 hash with fallback for non-secure contexts
async function sha256(plain: string): Promise<ArrayBuffer> {
  // Try Web Crypto API first (requires secure context)
  if (crypto?.subtle?.digest) {
    try {
      const encoder = new TextEncoder()
      const data = encoder.encode(plain)
      return await crypto.subtle.digest('SHA-256', data)
    } catch (err) {
      console.warn('Web Crypto API failed, using fallback:', err)
    }
  }
  // Fallback for non-secure contexts (HTTP with non-localhost)
  return sha256Fallback(plain)
}

// Convert ArrayBuffer to base64url
function base64urlEncode(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer)
  let binary = ''
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i])
  }
  return btoa(binary)
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=/g, '')
}

// Generate PKCE parameters
async function generatePKCE() {
  const codeVerifier = generateRandomString(64)
  const codeChallenge = base64urlEncode(await sha256(codeVerifier))
  return {
    codeVerifier,
    codeChallenge,
    codeChallengeMethod: 'S256'
  }
}

interface OAuthAuthParams {
  clientId: string
  responseType: string
  redirectUri: string
  scope: string
  state: string
  nonce: string
  challengeMethod: string
  codeChallenge: string
  type: string
}

interface ProviderCallbackParams {
  authParams: OAuthAuthParams
  application: string
  provider: string
  method: string
}

function authParamsToQuery(params: OAuthAuthParams): string {
  const query = new URLSearchParams({
    clientId: params.clientId,
    responseType: params.responseType,
    redirectUri: params.redirectUri,
    type: params.type,
    scope: params.scope,
    state: params.state,
    nonce: params.nonce,
    code_challenge_method: params.challengeMethod,
    code_challenge: params.codeChallenge,
  })
  return `?${query.toString()}`
}

export function markNextLoginForFreshAuthorization(): void {
  if (typeof window === 'undefined') return
  localStorage.setItem(FORCE_FRESH_AUTH_KEY, '1')
}

function consumeFreshAuthorizationFlag(): boolean {
  if (typeof window === 'undefined') return false
  const shouldForce = localStorage.getItem(FORCE_FRESH_AUTH_KEY) === '1'
  if (shouldForce) {
    localStorage.removeItem(FORCE_FRESH_AUTH_KEY)
  }
  return shouldForce
}

function buildAuthorizeSearch(
  params: OAuthAuthParams,
  forceFreshAuthorization: boolean = false
): string {
  const query = new URLSearchParams({
    client_id: params.clientId,
    response_type: params.responseType,
    redirect_uri: params.redirectUri,
    scope: params.scope,
    state: params.state,
    code_challenge: params.codeChallenge,
    code_challenge_method: params.challengeMethod,
    prompt: forceFreshAuthorization ? FRESH_AUTH_PROMPT : DEFAULT_AUTH_PROMPT,
    max_age: '0',
  })

  if (forceFreshAuthorization) {
    // These are harmless if ignored by the auth proxy, but useful for OAuth
    // providers that support forcing consent/account selection on re-login.
    query.set('approval_prompt', 'force')
    query.set('access_type', 'offline')
  }

  return `?${query.toString()}`
}

async function createOAuthAuthParams(): Promise<OAuthAuthParams | null> {
  const config = await loadAuthConfig()
  if (!config) return null

  if (typeof window === 'undefined') return null

  try {
    // Generate PKCE parameters
    const pkce = await generatePKCE()

    // Save code_verifier to localStorage (survives cross-domain redirects)
    localStorage.setItem('pkce_code_verifier', pkce.codeVerifier)
    console.log('Generated PKCE code_verifier:', pkce.codeVerifier.substring(0, 20) + '...')
    console.log('Generated PKCE code_challenge:', pkce.codeChallenge)

    // Generate random state
    const state = generateRandomString(32)
    localStorage.setItem('oauth_state', state)

    const redirectUri = new URL(config.redirectPath || '/callback', window.location.origin).toString()
    localStorage.setItem('oauth_redirect_uri', redirectUri)

    return {
      clientId: config.clientId,
      responseType: 'code',
      redirectUri,
      scope: 'read offline_access',
      state,
      nonce: '',
      challengeMethod: pkce.codeChallengeMethod,
      codeChallenge: pkce.codeChallenge,
      type: 'code',
    }
  } catch (error) {
    console.error('Failed to generate OAuth parameters:', error)
    return null
  }
}

function getConfiguredOAuthProvider(config: AuthConfig, providerType: OAuthProviderType): AuthOAuthProvider | null {
  const providers = config.oauthProviders?.length ? config.oauthProviders : DEFAULT_OAUTH_PROVIDERS
  return providers.find((provider) => provider.type === providerType) || null
}

export async function getOAuthProviderConfig(providerType: OAuthProviderType): Promise<AuthOAuthProvider | null> {
  const config = await loadAuthConfig()
  if (!config) return null
  return getConfiguredOAuthProvider(config, providerType)
}

function decodeProviderState(state: string): ProviderCallbackParams | null {
  try {
    const decoded = atob(state)
    const params = new URLSearchParams(decoded)
    const application = params.get('application')
    const provider = params.get('provider')
    const method = params.get('method') || 'signup'

    if (!application || !provider || !method) {
      return null
    }

    return {
      application,
      provider,
      method,
      authParams: {
        clientId: params.get('client_id') || '',
        responseType: params.get('response_type') || 'code',
        redirectUri: params.get('redirect_uri') || '',
        scope: params.get('scope') || 'read offline_access',
        state: params.get('state') || '',
        nonce: params.get('nonce') || '',
        challengeMethod: params.get('code_challenge_method') || '',
        codeChallenge: params.get('code_challenge') || '',
        type: 'code',
      },
    }
  } catch {
    return null
  }
}

export async function getProviderSignInUrl(providerType: OAuthProviderType): Promise<string | null> {
  const config = await loadAuthConfig()
  if (!config || typeof window === 'undefined') return null

  const provider = getConfiguredOAuthProvider(config, providerType)
  const authParams = await createOAuthAuthParams()
  if (!provider || !authParams) return null

  const authorizeUrl = new URL('/login/oauth/authorize', config.authProvider)
  authorizeUrl.search = buildAuthorizeSearch(authParams, consumeFreshAuthorizationFlag())
  authorizeUrl.searchParams.set('provider_hint', provider.name)
  return authorizeUrl.toString()
}

// Get sign in URL
export async function getSignInUrl(): Promise<string | null> {
  if (typeof window === 'undefined') return null
  return `${window.location.origin}/login`
}

export function isProviderCallback(search: string): boolean {
  const state = new URLSearchParams(search).get('state')
  return !!state && !!decodeProviderState(state)
}

async function exchangeProviderLoginForToken(
  providerCallback: ProviderCallbackParams,
  code: string,
  providerRedirectUri: string
): Promise<TokenResponse | null> {
  const loginPayload = {
    type: providerCallback.authParams.responseType || 'code',
    application: providerCallback.application,
    provider: providerCallback.provider,
    code,
    samlRequest: '',
    state: providerCallback.application,
    redirectUri: providerRedirectUri,
    method: providerCallback.method,
  }

  try {
    const response = await fetch(`/api/login${authParamsToQuery(providerCallback.authParams)}`, {
      method: 'POST',
      credentials: 'include',
      body: JSON.stringify(loginPayload),
      headers: {
        'Content-Type': 'application/json',
      },
    })

    const data = await response.json()
    if (!response.ok || data.status !== 'ok' || !data.data) {
      console.error('Provider login exchange failed:', data)
      return null
    }

    return await exchangeCodeForToken(data.data, providerCallback.authParams.state)
  } catch (error) {
    console.error('Provider login exchange error:', error)
    return null
  }
}

export async function exchangeProviderCodeForToken(
  providerType: OAuthProviderType,
  code: string,
  providerRedirectUri: string
): Promise<TokenResponse | null> {
  const config = await loadAuthConfig()
  if (!config) return null

  const provider = getConfiguredOAuthProvider(config, providerType)
  const authParams = await createOAuthAuthParams()
  if (!provider || !authParams) return null

  return await exchangeProviderLoginForToken(
    {
      application: config.appName,
      provider: provider.name,
      method: 'signup',
      authParams,
    },
    code,
    providerRedirectUri
  )
}

export async function exchangeProviderCallbackForToken(search: string): Promise<TokenResponse | null> {
  const config = await loadAuthConfig()
  if (!config || typeof window === 'undefined') return null

  const searchParams = new URLSearchParams(search)
  const providerState = searchParams.get('state')
  if (!providerState) return null

  const providerCallback = decodeProviderState(providerState)
  if (!providerCallback) return null

  const code =
    searchParams.get('code') ||
    searchParams.get('auth_code') ||
    searchParams.get('authCode')

  if (!code) {
    console.error('No provider authorization code received')
    return null
  }

  return await exchangeProviderLoginForToken(providerCallback, code, `${window.location.origin}/callback`)
}

// Exchange authorization code for access token
export async function exchangeCodeForToken(code: string, state: string): Promise<TokenResponse | null> {
  const config = await loadAuthConfig()
  if (!config) return null

  try {
    // Verify state parameter (skip if not found due to cross-domain issues)
    const savedState = localStorage.getItem('oauth_state')
    if (savedState && state !== savedState) {
      console.error('Invalid state parameter')
      return null
    }

    // Get code_verifier (generate new one if not found due to cross-domain issues)
    let codeVerifier = localStorage.getItem('pkce_code_verifier')
    console.log('Retrieved code_verifier from localStorage:', codeVerifier ? codeVerifier.substring(0, 20) + '...' : 'null')
    if (!codeVerifier) {
      console.warn('No code verifier found, using authorization code flow without PKCE')
      codeVerifier = '' // Use empty string for non-PKCE flow
    }

    const redirectUri = localStorage.getItem('oauth_redirect_uri')

    // Clean up localStorage
    localStorage.removeItem('oauth_state')
    localStorage.removeItem('pkce_code_verifier')
    localStorage.removeItem('oauth_redirect_uri')

    // Build token request
    const tokenProvider = config.authProxyProvider || config.authProvider
    const tokenUrl = `${tokenProvider}/api/login/oauth/access_token`
    const params = new URLSearchParams({
      grant_type: 'authorization_code',
      client_id: config.clientId,
      code: code
    })

    // Add code_verifier for PKCE if available
    if (codeVerifier) {
      params.append('code_verifier', codeVerifier)
      console.log('Using PKCE flow with code_verifier')
    } else {
      console.log('Using standard flow without PKCE')
    }

    if (redirectUri) {
      params.append('redirect_uri', redirectUri)
    }

    const response = await fetch(tokenUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: params.toString(),
    })

    if (!response.ok) {
      console.error('Failed to exchange code for token:', response.status, response.statusText)
      const errorText = await response.text()
      console.error('Error response:', errorText)
      return null
    }

    const data = await response.json()
    console.log('Token exchange response:', data)

    const tokenResponse: TokenResponse = {
      access_token: data.access_token,
      refresh_token: data.refresh_token,
      token_type: data.token_type,
      expires_in: data.expires_in,
      id_token: data.id_token,
      scope: data.scope
    }

    console.log('Extracted access_token:', tokenResponse.access_token ? `${tokenResponse.access_token.substring(0, 10)}...` : 'null')
    console.log('Has refresh_token:', !!tokenResponse.refresh_token)

    // Debug: Try to decode JWT token to check its content
    if (tokenResponse.access_token) {
      try {
        const tokenParts = tokenResponse.access_token.split('.')
        if (tokenParts.length === 3) {
          // Add padding if needed for base64url decoding
          let payload = tokenParts[1]
          payload += '='.repeat((4 - payload.length % 4) % 4)
          // Replace base64url chars with base64 chars
          payload = payload.replace(/-/g, '+').replace(/_/g, '/')
          const decoded = JSON.parse(atob(payload))
          console.log('Token payload:', decoded)
          console.log('Token expires at:', new Date(decoded.exp * 1000))
          console.log('Token issued for:', decoded.aud)
        } else {
          console.log('Token format:', `${tokenParts.length} parts, not a standard JWT`)
        }
      } catch (e) {
        console.log('Token decode error:', e)
        console.log('Token length:', tokenResponse.access_token.length)
        console.log('Token starts with:', tokenResponse.access_token.substring(0, 50))
      }
    }

    return tokenResponse
  } catch (error) {
    console.error('Token exchange error:', error)
    return null
  }
}

// Helper function to decode base64url with UTF-8 support
function decodeBase64Url(input: string): string {
  // Replace base64url chars with base64 chars
  let base64 = input.replace(/-/g, '+').replace(/_/g, '/')
  // Add padding if needed
  base64 += '='.repeat((4 - base64.length % 4) % 4)

  // Decode base64 to binary string
  const binaryString = atob(base64)

  // Convert binary string to UTF-8
  // Modern browsers support TextDecoder
  if (typeof TextDecoder !== 'undefined') {
    const bytes = new Uint8Array(binaryString.length)
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i)
    }
    return new TextDecoder('utf-8').decode(bytes)
  } else {
    // Fallback for older browsers
    const bytes = []
    for (let i = 0; i < binaryString.length; i++) {
      bytes.push(binaryString.charCodeAt(i))
    }
    return decodeURIComponent(escape(String.fromCharCode(...bytes)))
  }
}

// Get user information
export async function getUserInfo(token: string): Promise<User | null> {
  console.log('Getting user info with token:', token ? `${token.substring(0, 10)}...` : 'null')

  try {
    // Decode JWT token to extract user information
    // JWT format: header.payload.signature
    const tokenParts = token.split('.')
    if (tokenParts.length !== 3) {
      console.error('Invalid JWT token format')
      return null
    }

    // Decode the payload (second part) with UTF-8 support
    const payloadString = decodeBase64Url(tokenParts[1])
    const decoded = JSON.parse(payloadString)
    console.log('[getUserInfo] Decoded token payload:', decoded)

    // Map JWT claims to User interface
    const user: User = {
      owner: decoded.owner || '',
      name: decoded.name || decoded.email || '',
      createdTime: decoded.createdTime || '',
      updatedTime: decoded.updatedTime || '',
      id: decoded.id || decoded.sub || '',
      type: decoded.type || 'normal-user',
      displayName: decoded.displayName || decoded.name || '',
      avatar: decoded.avatar || '',
      email: decoded.email || '',
      phone: decoded.phone || '',
      location: decoded.location || '',
      address: decoded.address || [],
      affiliation: decoded.affiliation || '',
      title: decoded.title || '',
      homepage: decoded.homepage || '',
      bio: decoded.bio || '',
      tag: decoded.tag || '',
      region: decoded.region || '',
      language: decoded.language || '',
      score: decoded.score || 0,
      isAdmin: decoded.isAdmin || false,
      isGlobalAdmin: decoded.isGlobalAdmin || false,
      isForbidden: decoded.isForbidden || false,
      signupApplication: decoded.signupApplication || ''
    }

    console.log('[getUserInfo] Extracted user info:', user)
    return user
  } catch (error) {
    console.error('Failed to decode user info from token:', error)
    return null
  }
}

export function decodeArenaSession(session: string): ArenaSessionPayload | null {
  try {
    const decoded = decodeBase64Url(session)
    const payload = JSON.parse(decoded)
    if (!payload?.token?.access_token || !payload?.user) {
      throw new Error('Incomplete session payload')
    }
    return payload
  } catch (error) {
    console.error('Failed to decode arena session payload:', error)
    return null
  }
}

// Get sign out URL (deprecated - use ssoLogout instead)
export async function getSignOutUrl(): Promise<string | null> {
  if (typeof window === 'undefined') return null

  return `${window.location.origin}/login`
}

// SSO Logout - Clear Casdoor session across all apps
export async function ssoLogout(token: string): Promise<boolean> {
  const config = await loadAuthConfig()
  if (!config) {
    console.warn('No auth config, skipping SSO logout')
    return false
  }

  try {
    const response = await fetch(`${config.authProvider}/api/sso-logout`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      credentials: 'include'
    })

    if (!response.ok) {
      console.error('SSO logout failed:', response.status, response.statusText)
      return false
    }

    console.log('SSO logout successful')
    return true
  } catch (error) {
    console.error('SSO logout error:', error)
    return false
  }
}

// Get token expiry time from JWT
export function getTokenExpiryTime(token: string): number | null {
  try {
    const parts = token.split('.')
    if (parts.length !== 3) return null

    const payload = decodeBase64Url(parts[1])
    const decoded = JSON.parse(payload)

    // Return expiry time in milliseconds
    return decoded.exp ? decoded.exp * 1000 : null
  } catch (error) {
    console.error('[getTokenExpiryTime] Failed to decode token:', error)
    return null
  }
}

// Check if token is expired or will expire soon
export function isTokenExpiringSoon(token: string, bufferMinutes: number = 5): boolean {
  const expiryTime = getTokenExpiryTime(token)
  if (!expiryTime) return true // Treat invalid token as expired

  const bufferMs = bufferMinutes * 60 * 1000
  const now = Date.now()

  // Return true if token expires within buffer time
  return now >= (expiryTime - bufferMs)
}

// Refresh access token using refresh token via relay server (secure - client_secret stays server-side)
export async function refreshAccessToken(refreshToken: string): Promise<TokenResponse | null> {
  const config = await loadAuthConfig()
  if (!config) return null

  try {
    console.log('[refreshAccessToken] Refreshing token via auth provider...')

    const tokenProvider = config.authProxyProvider || config.authProvider
    const refreshUrl = `${tokenProvider}/api/login/oauth/refresh_token`
    const params = new URLSearchParams({
      grant_type: 'refresh_token',
      client_id: config.clientId,
      refresh_token: refreshToken,
    })

    const response = await fetch(refreshUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: params.toString(),
    })

    if (!response.ok) {
      console.error('[refreshAccessToken] Failed to refresh token:', response.status, response.statusText)
      const errorText = await response.text()
      console.error('[refreshAccessToken] Error response:', errorText)
      return null
    }

    const data = await response.json()
    console.log('[refreshAccessToken] Token refreshed successfully')

    const tokenResponse: TokenResponse = {
      access_token: data.access_token,
      refresh_token: data.refresh_token || refreshToken, // Use new refresh token if provided, otherwise keep the old one
      token_type: data.token_type,
      expires_in: data.expires_in,
      id_token: data.id_token,
      scope: data.scope
    }

    // Log new token expiry time
    if (tokenResponse.access_token) {
      const expiryTime = getTokenExpiryTime(tokenResponse.access_token)
      if (expiryTime) {
        console.log('[refreshAccessToken] New token expires at:', new Date(expiryTime))
      }
    }

    return tokenResponse
  } catch (error) {
    console.error('[refreshAccessToken] Error:', error)
    return null
  }
}
