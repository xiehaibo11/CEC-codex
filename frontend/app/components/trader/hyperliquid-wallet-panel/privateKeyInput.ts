import type { InputType } from './types'

export function detectInputType(input: string): InputType {
  const trimmed = input.trim()
  if (!trimmed) return 'empty'
  const withoutPrefix = trimmed.startsWith('0x') ? trimmed.slice(2) : trimmed
  if (!/^[0-9a-fA-F]+$/.test(withoutPrefix)) return 'invalid'
  if (withoutPrefix.length === 64) {
    return trimmed.startsWith('0x') ? 'valid_key' : 'key_no_prefix'
  }
  if (withoutPrefix.length === 40) return 'wallet_address'
  return 'invalid'
}

export function formatPrivateKey(input: string): string {
  const trimmed = input.trim()
  if (!trimmed) return ''
  const withoutPrefix = trimmed.startsWith('0x') ? trimmed.slice(2) : trimmed
  if (withoutPrefix.length === 64 && /^[0-9a-fA-F]+$/.test(withoutPrefix)) {
    return '0x' + withoutPrefix
  }
  return trimmed
}
