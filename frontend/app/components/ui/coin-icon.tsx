import { useEffect, useMemo, useState } from 'react'
import { cn } from '@/lib/utils'

type Props = {
  symbol: string
  size?: number
  className?: string
}

const QUOTE_SUFFIXES = ['USDT', 'USDC', 'BUSD', 'FDUSD', 'TUSD', 'USD', 'PERP']
const ICON_ALIASES: Record<string, string[]> = {
  IOTA: ['MIOTA'],
}

let cachedLocalIcons: Record<string, string> | null = null
let localIconsPromise: Promise<Record<string, string>> | null = null

function stripPrefix(symbol: string): string {
  return symbol.replace(/^k(?=[A-Z])/, '')
}

function normalizeSymbol(symbol: string): string {
  let clean = stripPrefix(symbol || '')
    .toUpperCase()
    .replace(/[^A-Z0-9]/g, '')
  for (const suffix of QUOTE_SUFFIXES) {
    if (clean.endsWith(suffix) && clean.length > suffix.length + 1) {
      clean = clean.slice(0, -suffix.length)
      break
    }
  }
  return clean
}

function iconCandidates(symbol: string): string[] {
  const clean = normalizeSymbol(symbol)
  const candidates = [clean]
  if (clean.startsWith('1000') && clean.length > 4) {
    candidates.push(clean.slice(4))
  }
  const noNumericPrefix = clean.replace(/^\d+(?=[A-Z])/, '')
  if (noNumericPrefix && noNumericPrefix !== clean) {
    candidates.push(noNumericPrefix)
  }
  if (clean.startsWith('1M') && clean.length > 2) {
    candidates.push(clean.slice(2))
  }
  if (clean.endsWith('X') && clean.length > 2) {
    candidates.push(clean.slice(0, -1))
  }
  if (/^LUNA\d+$/.test(clean)) {
    candidates.push('LUNA')
  }
  candidates.push(...(ICON_ALIASES[clean] || []))
  return Array.from(new Set(candidates.filter(Boolean)))
}

function fallbackHue(symbol: string): number {
  let hash = 0
  for (let i = 0; i < symbol.length; i += 1) {
    hash = symbol.charCodeAt(i) + ((hash << 5) - hash)
  }
  return Math.abs(hash) % 360
}

function findLocalIconUrl(symbol: string): string | null {
  if (!cachedLocalIcons) return null
  for (const candidate of iconCandidates(symbol)) {
    const url = cachedLocalIcons[candidate]
    if (url) return url
  }
  return null
}

function loadLocalIcons() {
  if (cachedLocalIcons) return Promise.resolve(cachedLocalIcons)
  if (!localIconsPromise) {
    localIconsPromise = fetch('/crypto-icons/manifest.json', { credentials: 'same-origin' })
      .then(response => response.ok ? response.json() : { icons: {} })
      .then(data => {
        cachedLocalIcons = data.icons || {}
        return cachedLocalIcons
      })
      .catch(error => {
        console.warn('Failed to load local crypto icon manifest:', error)
        cachedLocalIcons = {}
        return cachedLocalIcons
      })
  }
  return localIconsPromise
}

export function CoinIcon({ symbol, size = 20, className }: Props) {
  const [iconUrl, setIconUrl] = useState<string | null>(() => findLocalIconUrl(symbol))
  const [imageFailed, setImageFailed] = useState(false)
  const hue = useMemo(() => fallbackHue(symbol), [symbol])
  const letter = normalizeSymbol(symbol).charAt(0) || symbol.charAt(0) || '?'

  useEffect(() => {
    let cancelled = false
    setImageFailed(false)

    const cached = findLocalIconUrl(symbol)
    if (cached) {
      setIconUrl(cached)
      return () => {
        cancelled = true
      }
    }

    setIconUrl(null)
    loadLocalIcons().then(() => {
      if (!cancelled) {
        setIconUrl(findLocalIconUrl(symbol))
      }
    })
    return () => {
      cancelled = true
    }
  }, [symbol])

  if (!iconUrl || imageFailed) {
    return (
      <span
        className={cn(
          'inline-flex shrink-0 items-center justify-center rounded-full font-semibold text-white',
          className,
        )}
        style={{
          width: size,
          height: size,
          background: `linear-gradient(135deg, hsl(${hue} 55% 45%), hsl(${(hue + 40) % 360} 50% 30%))`,
          fontSize: Math.round(size * 0.5),
        }}
        aria-label={symbol}
      >
        {letter.toUpperCase()}
      </span>
    )
  }

  return (
    <img
      className={cn('shrink-0 rounded-full', className)}
      src={iconUrl}
      alt={symbol}
      width={size}
      height={size}
      loading="lazy"
      onError={() => setImageFailed(true)}
    />
  )
}
