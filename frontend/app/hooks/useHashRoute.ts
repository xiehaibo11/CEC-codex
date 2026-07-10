import { useCallback, useEffect, useState } from 'react'

export const PAGE_TITLES: Record<string, string> = {
  'hyper-ai': 'Hyper AI',
  comprehensive: 'Dashboard',
  'system-logs': 'System Logs',
  'prompt-management': 'Prompt Templates',
  'program-trader': 'Programs',
  'signal-management': 'Signal System',
  attribution: 'Attribution Analysis',
  'backtest-tool': 'Backtest Tool',
  'factor-library': 'Factor Library',
  'trader-management': 'AI Trader Management',
  'manual-trading': 'Manual Trading',
  klines: 'K-Line Charts',
  coinglass: 'CoinGlass',
  'model-chat': 'Model Chat',
  settings: 'Settings',
  'arena-assets': 'Arena Assets',
  'event-arrows': 'Event Arrows',
}

const normalizePageName = (pageName: string) => (
  pageName === 'hyperliquid' ? 'manual-trading' : pageName
)

const getHashPageName = () => {
  const hash = window.location.hash.slice(1)
  if (!hash) return null

  const hashParamIndex = hash.indexOf('?')
  return normalizePageName(hashParamIndex !== -1 ? hash.slice(0, hashParamIndex) : hash)
}

export function useHashRoute(defaultPage = 'hyper-ai') {
  const [currentPage, setCurrentPage] = useState<string>(defaultPage)

  /**
   * Hash routing keeps links shareable and lets Hyper AI direct users to pages.
   * Navigation should use this function instead of setting currentPage directly.
   */
  const handlePageChange = useCallback((page: string) => {
    setCurrentPage(page)
    window.location.hash = page
  }, [])

  useEffect(() => {
    const applyHashPage = () => {
      const pageName = getHashPageName()
      if (pageName && PAGE_TITLES[pageName]) {
        setCurrentPage(pageName)
      }
    }

    applyHashPage()
    window.addEventListener('hashchange', applyHashPage)
    return () => window.removeEventListener('hashchange', applyHashPage)
  }, [])

  const pageTitle = PAGE_TITLES[currentPage] ?? PAGE_TITLES.comprehensive

  return {
    currentPage,
    handlePageChange,
    pageTitle,
  }
}
