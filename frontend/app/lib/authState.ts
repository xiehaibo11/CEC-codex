// Shared, synchronous auth-mode flag.
//
// Open-source default is local no-auth mode: no auth-config.json is served, so
// `authRequired` stays false and the app treats every request as authenticated
// (the backend serves a single shared local user). When auth-config.json IS
// present (OAuth/Casdoor enabled), loadAuthConfig() flips this to true and the
// app requires a real login token.
//
// Kept in its own tiny module so both api.ts and auth.ts can use it without a
// circular import.

let authRequired = false

export function setAuthRequired(value: boolean): void {
  authRequired = value
}

export function getAuthRequired(): boolean {
  return authRequired
}
