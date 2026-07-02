import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Info } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import PromptBacktest from '../PromptBacktest'
import EventContractTab from './EventContractTab'
import TradesTable from './TradesTable'
import type { DimensionItem, DimensionResponse, TradeDetail } from './types'

type SymbolItem = DimensionItem & { symbol?: string }
type StrategyItem = DimensionItem & { strategy_id?: number; strategy_name?: string }
type TriggerItem = DimensionItem & { trigger_type?: string }
type OperationItem = DimensionItem & { operation?: string }
type FactorItem = DimensionItem & { factor_name?: string }
type ProgramItem = DimensionItem & { program_id?: number; program_name?: string }

interface DimensionTabsProps {
  activeTab: string
  onActiveTabChange: (value: string) => void
  accountId: string
  exchange: string
  tagFilter: string | null
  onTagFilterChange: (value: string | null) => void
  trades: TradeDetail[]
  tradesLoading: boolean
  onReplayTrade: (tradeId: number) => void
  bySymbol: DimensionResponse | null
  byStrategy: DimensionResponse | null
  byTrigger: DimensionResponse | null
  byOperation: DimensionResponse | null
  byFactor: DimensionResponse | null
  progBySymbol: DimensionResponse | null
  progByProgram: DimensionResponse | null
  progByTrigger: DimensionResponse | null
  progByOperation: DimensionResponse | null
}

export default function DimensionTabs({
  activeTab,
  onActiveTabChange,
  accountId,
  exchange,
  tagFilter,
  onTagFilterChange,
  trades,
  tradesLoading,
  onReplayTrade,
  bySymbol,
  byStrategy,
  byTrigger,
  byOperation,
  byFactor,
  progBySymbol,
  progByProgram,
  progByTrigger,
  progByOperation,
}: DimensionTabsProps) {
  const { t } = useTranslation()

  return (
    <Tabs value={activeTab} onValueChange={onActiveTabChange} className="w-full">
      <div className="flex items-center gap-4 flex-wrap">
        <TabsList className="grid w-full grid-cols-4 max-w-xl">
          <TabsTrigger value="dimensions">{t('attribution.tabs.dimensions', 'Dimension Analysis')}</TabsTrigger>
          <TabsTrigger value="trades">{t('attribution.tabs.trades', 'Trade Details')}</TabsTrigger>
          <TabsTrigger value="backtest">{t('attribution.tabs.backtest', 'Prompt Backtest')}</TabsTrigger>
          <TabsTrigger value="eventContract">{t('attribution.tabs.eventContract', 'Event Contract')}</TabsTrigger>
        </TabsList>
        {activeTab === 'backtest' && (
          <p className="text-xs text-muted-foreground">
            {t('promptBacktest.description', 'Replay historical decisions with modified prompts. Placeholders are fixed.')}
          </p>
        )}
      </div>

      <TabsContent value="dimensions" className="mt-4 space-y-6">
        <div className="space-y-4">
          <h3 className="text-lg font-semibold border-b pb-2">{t('attribution.aiDecision', 'AI Decision')}</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <MetricCard<SymbolItem>
              title={t('attribution.bySymbol', 'By Symbol')}
              labelHeader="币种"
              items={bySymbol?.items as SymbolItem[] | undefined}
              itemKey={item => item.symbol}
              renderLabel={item => item.symbol}
            />
            <MetricCard<StrategyItem>
              title={t('attribution.byStrategy', 'By Strategy')}
              labelHeader="Strategy"
              items={byStrategy?.items as StrategyItem[] | undefined}
              itemKey={item => item.strategy_id}
              renderLabel={item => item.strategy_name}
              emptyMessage={byStrategy?.items.length === 0 ? t('attribution.noStrategyData', 'No strategy attribution data') : undefined}
              unattributed={byStrategy?.unattributed}
            />
            <MetricCard<TriggerItem>
              title={t('attribution.byTriggerType', 'By Trigger Type')}
              labelHeader="Trigger"
              items={byTrigger?.items as TriggerItem[] | undefined}
              itemKey={item => item.trigger_type}
              renderLabel={item => item.trigger_type}
              labelClassName="capitalize"
            />
            <MetricCard<OperationItem>
              title={t('attribution.byOperation', 'By Operation')}
              tooltip={t('attribution.operationTooltip')}
              labelHeader="Operation"
              items={byOperation?.items as OperationItem[] | undefined}
              itemKey={item => item.operation}
              renderLabel={item => item.operation}
              labelClassName="uppercase"
            />
            {byFactor?.items && byFactor.items.length > 0 && (
              <MetricCard<FactorItem>
                title={t('attribution.byFactor', 'By Factor')}
                tooltip={t('attribution.byFactorTooltip')}
                labelHeader="Factor"
                items={byFactor.items as FactorItem[]}
                itemKey={item => item.factor_name}
                renderLabel={item => item.factor_name}
                labelClassName="font-mono"
                showWinRate
              />
            )}
          </div>
        </div>

        <div className="space-y-4">
          <h3 className="text-lg font-semibold border-b pb-2">{t('attribution.programDecision', 'Program Decision')}</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <MetricCard<SymbolItem>
              title={t('attribution.bySymbol', 'By Symbol')}
              labelHeader="币种"
              items={progBySymbol?.items as SymbolItem[] | undefined}
              itemKey={item => item.symbol}
              renderLabel={item => item.symbol}
              emptyMessage={progBySymbol?.items.length === 0 ? t('attribution.noProgramData', 'No program execution data') : undefined}
            />
            <MetricCard<ProgramItem>
              title={t('attribution.byProgram', 'By Program')}
              labelHeader="Program"
              items={progByProgram?.items as ProgramItem[] | undefined}
              itemKey={item => item.program_id}
              renderLabel={item => item.program_name}
              emptyMessage={progByProgram?.items.length === 0 ? t('attribution.noProgramData', 'No program execution data') : undefined}
              unattributed={progByProgram?.unattributed}
            />
            <MetricCard<TriggerItem>
              title={t('attribution.byTriggerType', 'By Trigger Type')}
              labelHeader="Trigger"
              items={progByTrigger?.items as TriggerItem[] | undefined}
              itemKey={item => item.trigger_type}
              renderLabel={item => item.trigger_type}
              labelClassName="capitalize"
              emptyMessage={progByTrigger?.items.length === 0 ? t('attribution.noProgramData', 'No program execution data') : undefined}
            />
            <MetricCard<OperationItem>
              title={t('attribution.byOperation', 'By Operation')}
              labelHeader="Operation"
              items={progByOperation?.items as OperationItem[] | undefined}
              itemKey={item => item.operation}
              renderLabel={item => item.operation}
              labelClassName="uppercase"
              emptyMessage={progByOperation?.items.length === 0 ? t('attribution.noProgramData', 'No program execution data') : undefined}
            />
          </div>
        </div>
      </TabsContent>

      <TabsContent value="trades" className="mt-4">
        <TradesTable
          tagFilter={tagFilter}
          onTagFilterChange={onTagFilterChange}
          trades={trades}
          tradesLoading={tradesLoading}
          onReplayTrade={onReplayTrade}
        />
      </TabsContent>

      <TabsContent value="backtest" className="mt-4">
        <PromptBacktest accountId={accountId} exchange={exchange} />
      </TabsContent>

      <TabsContent value="eventContract" className="mt-4">
        <EventContractTab />
      </TabsContent>
    </Tabs>
  )
}

interface MetricCardProps<T extends DimensionItem> {
  title: ReactNode
  tooltip?: string
  labelHeader: string
  items?: T[]
  itemKey: (item: T) => string | number | undefined
  renderLabel: (item: T) => ReactNode
  labelClassName?: string
  emptyMessage?: ReactNode
  unattributed?: DimensionResponse['unattributed']
  showWinRate?: boolean
}

function MetricCard<T extends DimensionItem>({
  title,
  tooltip,
  labelHeader,
  items,
  itemKey,
  renderLabel,
  labelClassName,
  emptyMessage,
  unattributed,
  showWinRate,
}: MetricCardProps<T>) {
  const { t } = useTranslation()

  return (
    <Card>
      <CardHeader>
        <CardTitle className={tooltip ? 'flex items-center gap-2' : undefined}>
          {title}
          {tooltip && (
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Info className="w-4 h-4 text-muted-foreground hover:text-foreground cursor-help" />
                </TooltipTrigger>
                <TooltipContent side="bottom" className="max-w-xs p-3">
                  <p className="text-sm">{tooltip}</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {emptyMessage ? (
          <div className="text-muted-foreground text-sm p-4">{emptyMessage}</div>
        ) : (
          <MetricsTable
            labelHeader={labelHeader}
            items={items}
            itemKey={itemKey}
            renderLabel={renderLabel}
            labelClassName={labelClassName}
            showWinRate={showWinRate}
          />
        )}
        {unattributed && unattributed.count > 0 && (
          <div className="p-2 border-t text-sm text-muted-foreground">
            {t('attribution.unattributed', 'Unattributed')}: {unattributed.count} trades
          </div>
        )}
      </CardContent>
    </Card>
  )
}

interface MetricsTableProps<T extends DimensionItem> {
  labelHeader: string
  items?: T[]
  itemKey: (item: T) => string | number | undefined
  renderLabel: (item: T) => ReactNode
  labelClassName?: string
  showWinRate?: boolean
}

function MetricsTable<T extends DimensionItem>({
  labelHeader,
  items,
  itemKey,
  renderLabel,
  labelClassName = '',
  showWinRate,
}: MetricsTableProps<T>) {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b text-muted-foreground">
          <th className="text-left p-2 font-medium">{labelHeader}</th>
          <th className="text-right p-2 font-medium">总盈亏</th>
          <th className="text-right p-2 font-medium">手续费</th>
          <th className="text-right p-2 font-medium">净盈亏</th>
          {showWinRate && <th className="text-right p-2 font-medium">Win Rate</th>}
          <th className="text-right p-2 font-medium">交易次数</th>
        </tr>
      </thead>
      <tbody>
        {items?.map((item, index) => (
          <tr key={itemKey(item) ?? index} className="border-b last:border-0">
            <td className={`p-2 font-medium ${labelClassName}`.trim()}>{renderLabel(item)}</td>
            <td className={`p-2 text-right ${item.metrics.total_pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
              ${item.metrics.total_pnl.toFixed(2)}
            </td>
            <td className="p-2 text-right text-orange-500">${item.metrics.total_fee.toFixed(2)}</td>
            <td className={`p-2 text-right ${item.metrics.net_pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
              ${item.metrics.net_pnl.toFixed(2)}
            </td>
            {showWinRate && <td className="p-2 text-right">{item.metrics.win_rate}</td>}
            <td className="p-2 text-right">{item.metrics.trade_count}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
