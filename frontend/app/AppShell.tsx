import type { MutableRefObject } from 'react'
import Header from '@/components/layout/Header'
import Sidebar from '@/components/layout/Sidebar'
import ComprehensiveView from '@/components/portfolio/ComprehensiveView'
import SystemLogs from '@/components/layout/SystemLogs'
import PromptManager from '@/components/prompt/PromptManager'
import SignalManager from '@/components/signal/SignalManager'
import AttributionAnalysis from '@/components/analytics/AttributionAnalysis'
import BacktestTool from '@/components/backtest/BacktestTool'
import FactorLibrary from '@/components/factor/FactorLibrary'
import TraderManagement from '@/components/trader/TraderManagement'
import { HyperliquidPage } from '@/components/hyperliquid'
import HyperliquidView from '@/components/hyperliquid/HyperliquidView'
import KlinesView from '@/components/klines/KlinesView'
import CoinGlassView from '@/components/coinglass/CoinGlassView'
import MobileModelChat from '@/components/mobile/MobileModelChat'
import MobileDashboard from '@/components/mobile/MobileDashboard'
import MobilePrograms from '@/components/mobile/MobilePrograms'
import ProgramTrader from '@/components/program/ProgramTrader'
import SettingsPage from '@/components/settings/SettingsPage'
import { HyperAiPage } from '@/components/hyper-ai'
import ArenaAssets from '@/components/arena/ArenaAssets'
import type { AIDecision, UnauthorizedAccount } from '@/lib/api'
import { AgentWalletUpgradeModal, AuthorizationModal } from '@/components/hyperliquid'

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
