import { lazy, Suspense } from 'react'
import type { MutableRefObject } from 'react'
import Header from '@/components/layout/Header'
import Sidebar from '@/components/layout/Sidebar'
import type { AIDecision, UnauthorizedAccount } from '@/lib/api'
// Kept eager: these two modals can appear right after login/account load,
// gated only by an `isOpen` prop, so they shouldn't wait on a lazy-chunk fetch.
import AgentWalletUpgradeModal from '@/components/hyperliquid/AgentWalletUpgradeModal'
import AuthorizationModal from '@/components/hyperliquid/AuthorizationModal'

// Every page-level view is lazy-loaded so the initial bundle only ships the
// app shell; each view (and its heavy deps like chart libs/Monaco/ethers)
// downloads on first navigation to that page instead of on first paint.
const ComprehensiveView = lazy(() => import('@/components/portfolio/ComprehensiveView'))
const SystemLogs = lazy(() => import('@/components/layout/SystemLogs'))
const PromptManager = lazy(() => import('@/components/prompt/PromptManager'))
const SignalManager = lazy(() => import('@/components/signal/SignalManager'))
const AttributionAnalysis = lazy(() => import('@/components/analytics/AttributionAnalysis'))
const BacktestTool = lazy(() => import('@/components/backtest/BacktestTool'))
const FactorLibrary = lazy(() => import('@/components/factor/FactorLibrary'))
const TraderManagement = lazy(() => import('@/components/trader/TraderManagement'))
const HyperliquidPage = lazy(() => import('@/components/hyperliquid/HyperliquidPage'))
const HyperliquidView = lazy(() => import('@/components/hyperliquid/HyperliquidView'))
const KlinesView = lazy(() => import('@/components/klines/KlinesView'))
const CoinGlassView = lazy(() => import('@/components/coinglass/CoinGlassView'))
const MobileModelChat = lazy(() => import('@/components/mobile/MobileModelChat'))
const MobileDashboard = lazy(() => import('@/components/mobile/MobileDashboard'))
const MobilePrograms = lazy(() => import('@/components/mobile/MobilePrograms'))
const ProgramTrader = lazy(() => import('@/components/program/ProgramTrader'))
const SettingsPage = lazy(() => import('@/components/settings/SettingsPage'))
const HyperAiPage = lazy(() => import('@/components/hyper-ai/HyperAiPage'))
const ArenaAssets = lazy(() => import('@/components/arena/ArenaAssets'))

function ViewLoadingFallback() {
  return (
    <div className="flex flex-1 items-center justify-center min-h-0">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-muted border-t-primary" />
    </div>
  )
}

export interface AppUser {
  id: number
  username: string
}

export interface Account {
  id: number
  user_id: number
  name: string
  account_type: string
  initial_capital: number
  current_cash: number
  frozen_cash: number
}

export interface Overview {
  account: Account
  total_assets: number
  positions_value: number
  portfolio?: {
    total_assets: number
    positions_value: number
  }
}

export interface Position {
  id: number
  account_id: number
  symbol: string
  name: string
  market: string
  quantity: number
  available_quantity: number
  avg_cost: number
  last_price?: number | null
  market_value?: number | null
}

export interface Order {
  id: number
  order_no: string
  symbol: string
  name: string
  market: string
  side: string
  order_type: string
  price?: number
  quantity: number
  filled_quantity: number
  status: string
}

export interface Trade {
  id: number
  order_id: number
  account_id: number
  symbol: string
  name: string
  market: string
  side: string
  price: number
  quantity: number
  commission: number
  trade_time: string
}

interface MainContentProps {
  currentPage: string
  tradingMode: string
  account: Account | null
  effectiveOverview: Overview | null
  positions: Position[]
  orders: Order[]
  trades: Trade[]
  aiDecisions: AIDecision[]
  allAssetCurves: any[]
  wsRef: MutableRefObject<WebSocket | null>
  hyperliquidRefreshKey: number
  accountRefreshTrigger: number
  accounts: any[]
  accountsLoading: boolean
  onSwitchUser: (username: string) => void
  onSwitchAccount: (accountId: number) => void
  onRefreshData: () => void
  onPageChange: (page: string) => void
  onAccountUpdated: () => void
}

interface AppShellProps extends MainContentProps {
  pageTitle: string
  authModalOpen: boolean
  unauthorizedAccounts: UnauthorizedAccount[]
  onAuthModalClose: () => void
  onAuthorizationComplete: () => void
  agentUpgradeModalOpen: boolean
  walletsNeedUpgrade: any[]
  onAgentUpgradeClose: () => void
  onAgentUpgradeComplete: () => void
}

function MainContent({
  currentPage,
  tradingMode,
  account,
  effectiveOverview,
  positions,
  orders,
  trades,
  aiDecisions,
  allAssetCurves,
  wsRef,
  hyperliquidRefreshKey,
  accountRefreshTrigger,
  accounts,
  accountsLoading,
  onSwitchUser,
  onSwitchAccount,
  onRefreshData,
  onPageChange,
  onAccountUpdated,
}: MainContentProps) {
  return (
    <main className={`flex-1 overflow-hidden flex flex-col min-h-0 min-w-0 ${currentPage === 'hyper-ai' ? '' : 'p-4'}`}>
      <Suspense fallback={<ViewLoadingFallback />}>
      {currentPage === 'hyper-ai' && <HyperAiPage />}

      {currentPage === 'comprehensive' && (
        tradingMode === 'paper' ? (
          <div className="flex flex-col flex-1 min-h-0 overflow-hidden pr-1">
            <ComprehensiveView
              overview={effectiveOverview}
              positions={positions}
              orders={orders}
              trades={trades}
              aiDecisions={aiDecisions}
              allAssetCurves={allAssetCurves}
              wsRef={wsRef}
              onSwitchUser={onSwitchUser}
              onSwitchAccount={onSwitchAccount}
              onRefreshData={onRefreshData}
              accountRefreshTrigger={accountRefreshTrigger}
              accounts={accounts}
              loadingAccounts={accountsLoading}
              onPageChange={onPageChange}
            />
          </div>
        ) : (
          <>
            <div className="md:hidden flex flex-col flex-1 min-h-0">
              <MobileDashboard />
            </div>
            <div className="hidden md:flex flex-col flex-1 min-h-0">
              <HyperliquidView
                wsRef={wsRef}
                refreshKey={hyperliquidRefreshKey}
                onPageChange={onPageChange}
              />
            </div>
          </>
        )
      )}

      {currentPage === 'system-logs' && <SystemLogs />}
      {currentPage === 'prompt-management' && <PromptManager />}

      {currentPage === 'program-trader' && (
        <>
          <div className="md:hidden flex flex-col flex-1 min-h-0">
            <MobilePrograms />
          </div>
          <div className="hidden md:flex flex-col flex-1 min-h-0">
            <ProgramTrader />
          </div>
        </>
      )}

      {currentPage === 'signal-management' && <SignalManager />}
      {currentPage === 'attribution' && <AttributionAnalysis />}
      {currentPage === 'backtest-tool' && <BacktestTool />}
      {currentPage === 'factor-library' && <FactorLibrary />}
      {currentPage === 'trader-management' && <TraderManagement />}
      {currentPage === 'manual-trading' && <HyperliquidPage accountId={account?.id || 1} />}
      {currentPage === 'klines' && <KlinesView onAccountUpdated={onAccountUpdated} />}
      {currentPage === 'coinglass' && <CoinGlassView />}
      {currentPage === 'model-chat' && <MobileModelChat />}
      {currentPage === 'settings' && <SettingsPage />}
      {currentPage === 'arena-assets' && <ArenaAssets />}
      </Suspense>
    </main>
  )
}

export default function AppShell({
  currentPage,
  pageTitle,
  account,
  authModalOpen,
  unauthorizedAccounts,
  onAuthModalClose,
  onAuthorizationComplete,
  agentUpgradeModalOpen,
  walletsNeedUpgrade,
  onAgentUpgradeClose,
  onAgentUpgradeComplete,
  onPageChange,
  onAccountUpdated,
  ...mainContentProps
}: AppShellProps) {
  return (
    <>
      <div className="h-screen flex overflow-hidden">
        <Sidebar
          currentPage={currentPage}
          onPageChange={onPageChange}
          onAccountUpdated={onAccountUpdated}
        />
        <div className="flex-1 flex flex-col min-w-0">
          <Header
            title={pageTitle}
            currentAccount={account}
            showAccountSelector={currentPage === 'comprehensive'}
          />
          <MainContent
            currentPage={currentPage}
            account={account}
            onPageChange={onPageChange}
            onAccountUpdated={onAccountUpdated}
            {...mainContentProps}
          />
        </div>
      </div>
      <AuthorizationModal
        isOpen={authModalOpen}
        onClose={onAuthModalClose}
        unauthorizedAccounts={unauthorizedAccounts}
        onAuthorizationComplete={onAuthorizationComplete}
      />
      <AgentWalletUpgradeModal
        isOpen={agentUpgradeModalOpen}
        onClose={onAgentUpgradeClose}
        walletsToUpgrade={walletsNeedUpgrade}
        onUpgradeComplete={onAgentUpgradeComplete}
      />
    </>
  )
}
