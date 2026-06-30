import React, { useCallback, useEffect, useRef, useState } from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'
import './i18n' // Initialize i18n
import AppProviders from './AppProviders'
import AppShell, {
  type Account,
  type AppUser,
  type Order,
  type Overview,
  type Position,
  type Trade,
} from './AppShell'
import { useHashRoute } from './hooks/useHashRoute'
import { useTradingWebSocket } from './hooks/useTradingWebSocket'
import { SplashScreen, HyperAiOnboarding } from '@/components/hyper-ai'
import LoginPage from '@/components/auth/LoginPage'
import {
  approveBuilder,
  checkMainnetAccounts,
  getAccounts,
  isAuthenticated,
  type AIDecision,
  type UnauthorizedAccount,
} from '@/lib/api'
import { checkWalletUpgradeNeeded } from '@/lib/hyperliquidApi'
import { useAuth } from '@/contexts/AuthContext'
import { useTradingMode } from '@/contexts/TradingModeContext'

// Global error handler for debugging
window.addEventListener('error', (event) => {
  console.error('Global error caught:', event.error)
  console.error('Error stack:', event.error?.stack)
})

window.addEventListener('unhandledrejection', (event) => {
  console.error('Unhandled promise rejection:', event.reason)
})

function App() {
  const { tradingMode } = useTradingMode()
  const { user: authUser, loading: authLoading, authEnabled } = useAuth()
  const { currentPage, handlePageChange, pageTitle } = useHashRoute('hyper-ai')
  const [user, setUser] = useState<AppUser | null>(null)
  const [account, setAccount] = useState<Account | null>(null)
  const [overview, setOverview] = useState<Overview | null>(null)
  const [positions, setPositions] = useState<Position[]>([])
  const [orders, setOrders] = useState<Order[]>([])
  const [trades, setTrades] = useState<Trade[]>([])
  const [aiDecisions, setAiDecisions] = useState<AIDecision[]>([])
  const [allAssetCurves, setAllAssetCurves] = useState<any[]>([])
  const [hyperliquidRefreshKey, setHyperliquidRefreshKey] = useState(0)

  // Hyper AI states - initialization happens during splash
  const [showSplash, setShowSplash] = useState(true)
  const [showOnboarding, setShowOnboarding] = useState(false)
  const [initComplete, setInitComplete] = useState(false)
  const initStartedRef = useRef(false)

  // Check Hyper AI configuration during splash phase
  const checkHyperAiConfig = useCallback(async () => {
    // Skip the protected profile check when not logged in (no onboarding prompt).
    if (!isAuthenticated()) return false
    try {
      const res = await fetch('/api/hyper-ai/profile')
      const data = await res.json()
      return !data.llm_configured
    } catch (e) {
      console.error('Failed to check Hyper AI config:', e)
      return false
    }
  }, [])

  // Stable callback for splash completion - does all init checks
  const handleSplashComplete = useCallback(async () => {
    if (initStartedRef.current) return
    initStartedRef.current = true

    const needsOnboarding = await checkHyperAiConfig()
    setShowOnboarding(needsOnboarding)
    setInitComplete(true)
    setShowSplash(false)
  }, [checkHyperAiConfig])

  const handleOnboardingComplete = () => {
    setShowOnboarding(false)
  }

  const handleOnboardingSkip = () => {
    setShowOnboarding(false)
  }

  const [accountRefreshTrigger, setAccountRefreshTrigger] = useState<number>(0)
  const [accounts, setAccounts] = useState<any[]>([])
  const [accountsLoading, setAccountsLoading] = useState<boolean>(true)
  const [authModalOpen, setAuthModalOpen] = useState(false)
  const [unauthorizedAccounts, setUnauthorizedAccounts] = useState<UnauthorizedAccount[]>([])
  const authCheckedRef = useRef(false)
  const [agentUpgradeModalOpen, setAgentUpgradeModalOpen] = useState(false)
  const [walletsNeedUpgrade, setWalletsNeedUpgrade] = useState<any[]>([])

  // Debug function to manually trigger authorization modal
  // Uses negative IDs to avoid conflicts with real accounts
  useEffect(() => {
    (window as any).__debugShowAuthModal = (mockData?: UnauthorizedAccount[]) => {
      const testAccounts = mockData || [{
        account_id: -999,
        account_name: 'Test Account (Debug)',
        wallet_address: '0x0000000000000000000000000000000000000000',
        max_fee: 0,
        required_fee: 30
      }]
      // Force negative IDs to prevent affecting real accounts
      const safeAccounts = testAccounts.map((acc, idx) => ({
        ...acc,
        account_id: acc.account_id > 0 ? -(idx + 900) : acc.account_id
      }))
      setUnauthorizedAccounts(safeAccounts)
      setAuthModalOpen(true)
      console.log('[Debug] Authorization modal opened with SAFE accounts (negative IDs):', safeAccounts)
      console.warn('[Debug] Note: Positive account_ids are converted to negative to prevent affecting real accounts')
    }
    return () => {
      delete (window as any).__debugShowAuthModal
    }
  }, [])

  // Centralized accounts fetcher
  const refreshAccounts = async () => {
    // Wait for AuthContext to finish initialising before checking auth state.
    if (authLoading) return
    // Skip protected API calls when not logged in; use empty local default silently.
    if (!isAuthenticated()) {
      setAccounts([])
      return
    }
    try {
      setAccountsLoading(true)
      const list = await getAccounts()
      setAccounts(list)

      // Check if user only has default account and redirect to setup
      const hasOnlyDefaultAccount = list.length === 1 &&
        list[0]?.name === "Default AI Trader" &&
        list[0]?.api_key === "default-key-please-update-in-settings"

      if (hasOnlyDefaultAccount && currentPage === 'comprehensive') {
        handlePageChange('trader-management')
      }

      // Check builder fee authorization for mainnet accounts (once per session)
      // Builder binding: approve builder fee without user interaction
      if (!authCheckedRef.current) {
        authCheckedRef.current = true
        try {
          const result = await checkMainnetAccounts()
          if (result.unauthorized_accounts && result.unauthorized_accounts.length > 0) {
            // Batch builder binding
            const authResults = await Promise.all(
              result.unauthorized_accounts.map(acc =>
                approveBuilder(acc.account_id)
                  .then(res => ({ ...acc, authResult: res }))
                  .catch(err => ({ ...acc, authResult: { success: false, error: err } }))
              )
            )

            // Collect failed bindings
            const failedAccounts = authResults.filter(
              item => !item.authResult.success || item.authResult.result?.status === 'err'
            )

            // Show modal if any binding failed
            if (failedAccounts.length > 0) {
              setUnauthorizedAccounts(failedAccounts.map(item => ({
                account_id: item.account_id,
                account_name: item.account_name,
                wallet_address: item.wallet_address,
                max_fee: item.max_fee,
                required_fee: item.required_fee
              })))
              setAuthModalOpen(true)
            }
          }
        } catch (authError) {
          console.error('Failed to check mainnet accounts:', authError)
        }
      }

      // Check agent wallet upgrade (every time accounts refresh)
      try {
        const upgradeResult = await checkWalletUpgradeNeeded()
        if (upgradeResult.count > 0) {
          setWalletsNeedUpgrade(upgradeResult.needsUpgrade)
          setAgentUpgradeModalOpen(true)
        }
      } catch (upgradeError) {
        console.error('Failed to check wallet upgrade:', upgradeError)
      }
    } catch (e) {
      console.error('Failed to fetch accounts', e)
    } finally {
      setAccountsLoading(false)
    }
  }

  const { wsRef, switchUser, switchAccount, requestSnapshot } = useTradingWebSocket({
    tradingMode,
    account,
    refreshAccounts,
    setUser,
    setAccount,
    setOverview,
    setPositions,
    setOrders,
    setTrades,
    setAiDecisions,
    setAllAssetCurves,
    setHyperliquidRefreshKey,
  })

  const handleAuthorizationComplete = () => {
    setAuthModalOpen(false)
    setUnauthorizedAccounts([])
    refreshAccounts()
  }

  const handleAuthModalClose = () => {
    setAuthModalOpen(false)
    setUnauthorizedAccounts([])
    refreshAccounts()
  }

  // Fetch accounts on mount and when settings updated
  useEffect(() => {
    refreshAccounts()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accountRefreshTrigger, authLoading])

  const handleAccountUpdated = () => {
    // Increment refresh trigger to force AccountSelector to refresh
    setAccountRefreshTrigger(prev => prev + 1)

    // Also refresh the current data snapshot
    requestSnapshot()
  }

  // For non-paper modes, create minimal state to avoid loading screen
  const effectiveOverview = overview || (tradingMode !== 'paper' ? {
    account: { id: 1, user_id: 1, name: 'Hyperliquid Account', account_type: 'AI', initial_capital: 0, current_cash: 0, frozen_cash: 0 },
    total_assets: 0,
    positions_value: 0
  } : null)

  // Data ready when user and account are loaded (or non-paper mode with effectiveOverview)
  const isDataReady = !!(user && account && (effectiveOverview || tradingMode !== 'paper'))

  if (window.location.pathname === '/login') {
    return <LoginPage />
  }

  // Global auth gate: require login before rendering any business page.
  // When auth is enabled and the user is not logged in, render the login page
  // instead of the app so no protected API calls fire (eliminates page-wide 401s).
  if (authEnabled && !authLoading && !authUser) {
    return <LoginPage />
  }

  // Show splash screen first (waits for both animation AND data ready)
  if (showSplash) {
    return <SplashScreen onComplete={handleSplashComplete} isReady={isDataReady} />
  }

  // Show onboarding if Hyper AI not configured
  if (showOnboarding) {
    return (
      <HyperAiOnboarding
        onComplete={handleOnboardingComplete}
        onSkip={handleOnboardingSkip}
      />
    )
  }

  return (
    <AppShell
      currentPage={currentPage}
      pageTitle={pageTitle}
      tradingMode={tradingMode}
      account={account}
      effectiveOverview={effectiveOverview}
      positions={positions}
      orders={orders}
      trades={trades}
      aiDecisions={aiDecisions}
      allAssetCurves={allAssetCurves}
      wsRef={wsRef}
      hyperliquidRefreshKey={hyperliquidRefreshKey}
      accountRefreshTrigger={accountRefreshTrigger}
      accounts={accounts}
      accountsLoading={accountsLoading}
      onSwitchUser={switchUser}
      onSwitchAccount={switchAccount}
      onRefreshData={requestSnapshot}
      onPageChange={handlePageChange}
      onAccountUpdated={handleAccountUpdated}
      authModalOpen={authModalOpen}
      unauthorizedAccounts={unauthorizedAccounts}
      onAuthModalClose={handleAuthModalClose}
      onAuthorizationComplete={handleAuthorizationComplete}
      agentUpgradeModalOpen={agentUpgradeModalOpen}
      walletsNeedUpgrade={walletsNeedUpgrade}
      onAgentUpgradeClose={() => setAgentUpgradeModalOpen(false)}
      onAgentUpgradeComplete={() => {
        setAgentUpgradeModalOpen(false)
        setWalletsNeedUpgrade([])
        refreshAccounts()
      }}
    />
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AppProviders>
      <App />
    </AppProviders>
  </React.StrictMode>,
)
