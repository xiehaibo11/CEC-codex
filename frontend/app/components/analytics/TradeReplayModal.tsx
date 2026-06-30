import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { getAccounts } from '@/lib/api'
import type { TradingAccount } from '@/lib/api'
import { DecisionCard } from './trade-replay/DecisionCard'
import { HoldGroupCard } from './trade-replay/HoldGroupCard'
import { ReplayAiChat } from './trade-replay/ReplayAiChat'
import { ReplayKlineChart } from './trade-replay/ReplayKlineChart'
import { fetchTradeReplayData } from './trade-replay/api'
import type { DecisionGroup, TradeReplayData, TradeReplayModalProps } from './trade-replay/types'

function groupDecisionChain(decisions: TradeReplayData['decisions_chain']): DecisionGroup[] {
  const groups: DecisionGroup[] = []
  let currentHolds: TradeReplayData['decisions_chain'] = []

  decisions.forEach((decision) => {
    if (decision.operation === 'hold') {
      currentHolds.push(decision)
    } else {
      if (currentHolds.length > 0) {
        groups.push({ type: 'hold_group', items: currentHolds })
        currentHolds = []
      }
      groups.push({ type: 'single', items: [decision] })
    }
  })

  if (currentHolds.length > 0) {
    groups.push({ type: 'hold_group', items: currentHolds })
  }

  return groups
}

export default function TradeReplayModal({
  open,
  onOpenChange,
  tradeId,
}: TradeReplayModalProps) {
  const { t } = useTranslation()
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<TradeReplayData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [period, setPeriod] = useState<string>('5m')
  const [accounts, setAccounts] = useState<TradingAccount[]>([])
  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null)

  const periods = ['5m', '15m', '1h', '4h']

  // Load AI accounts
  useEffect(() => {
    if (open) {
      getAccounts().then(accs => {
        const aiAccounts = accs.filter(a => a.account_type === 'AI')
        setAccounts(aiAccounts)
        if (aiAccounts.length > 0 && !selectedAccountId) {
          setSelectedAccountId(aiAccounts[0].id)
        }
      }).catch(console.error)
    }
  }, [open])

  useEffect(() => {
    if (open && tradeId) {
      loadReplayData(tradeId)
    }
  }, [open, tradeId])

  const loadReplayData = async (id: number) => {
    setLoading(true)
    setError(null)
    try {
      const result = await fetchTradeReplayData(id)
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-[1600px] w-[95vw] h-[90vh] flex flex-col p-0 [&>button]:hidden"
        onPointerDownOutside={(e) => e.preventDefault()}
        onInteractOutside={(e) => e.preventDefault()}
      >
        <DialogHeader className="px-6 py-4 border-b flex-shrink-0">
          <div className="flex items-center justify-between">
            <DialogTitle className="text-xl">
              {t('attribution.replay.title', 'Trade Replay')} #{tradeId} {data?.trade.symbol}
            </DialogTitle>
            <Button variant="ghost" size="icon" onClick={() => onOpenChange(false)}>
              <X className="h-5 w-5" />
            </Button>
          </div>
        </DialogHeader>

        {loading ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-muted-foreground">Loading...</div>
          </div>
        ) : error ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-red-500">{error}</div>
          </div>
        ) : data ? (
          <>
            <div className="flex-1 flex overflow-hidden">
              {/* Left Column - Decision Chain */}
              <div className="w-72 border-r flex flex-col">
                <div className="px-4 py-3 border-b font-medium bg-muted/30">
                  {t('attribution.replay.decisionChain', 'Decision Chain')}
                </div>
                <ScrollArea className="flex-1">
                  <div className="p-4 space-y-3">
                    {groupDecisionChain(data.decisions_chain).map((group, groupIndex, groups) => {
                      const isLastGroup = groupIndex === groups.length - 1
                      if (group.type === 'hold_group') {
                        return (
                          <HoldGroupCard
                            key={`hold-group-${group.items[0].id}`}
                            holds={group.items}
                            isLast={isLastGroup}
                          />
                        )
                      }

                      const decision = group.items[0]
                      const isFirst = groupIndex === 0
                      return (
                        <DecisionCard
                          key={decision.id}
                          decision={decision}
                          isFirst={isFirst}
                          isLast={isLastGroup}
                        />
                      )
                    })}
                  </div>
                </ScrollArea>
              </div>

              {/* Center Column - K-line Chart */}
              <div className="flex-1 flex flex-col">
                <div className="px-4 py-2 border-b font-medium bg-muted/30 flex items-center justify-between">
                  <span>{t('attribution.replay.priceChart', 'Price Chart')}</span>
                  <div className="flex gap-1">
                    {periods.map(p => (
                      <button
                        key={p}
                        onClick={() => setPeriod(p)}
                        className={`px-2 py-1 text-xs rounded ${period === p ? 'bg-primary text-primary-foreground' : 'bg-muted hover:bg-muted/80'}`}
                      >
                        {p}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="flex-1">
                  <ReplayKlineChart tradeId={data.trade.id} period={period} />
                </div>
              </div>

              {/* Right Column - AI Chat */}
              <div className="flex-1 border-l flex flex-col min-w-0 overflow-hidden">
                <div className="px-4 py-2 border-b font-medium bg-muted/30 flex items-center justify-between flex-shrink-0">
                  <span>{t('attribution.replay.aiAnalysis', 'AI Analysis')}</span>
                  <Select
                    value={selectedAccountId?.toString() || ''}
                    onValueChange={(v) => setSelectedAccountId(Number(v))}
                  >
                    <SelectTrigger className="w-48 h-7 text-xs">
                      <SelectValue placeholder={t('attribution.aiAnalysis.selectAiTrader', 'Select AI')} />
                    </SelectTrigger>
                    <SelectContent>
                      {accounts.map((acc) => (
                        <SelectItem key={acc.id} value={acc.id.toString()}>
                          {acc.name} ({acc.model})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex-1 overflow-hidden">
                  <ReplayAiChat tradeData={data} selectedAccountId={selectedAccountId} />
                </div>
              </div>
            </div>

            {/* Bottom Summary */}
            <div className="border-t px-6 py-4 flex-shrink-0 bg-muted/30">
              <div className="flex items-center justify-between text-sm">
                <div className="flex gap-6">
                  <div>
                    <span className="text-muted-foreground">{t('attribution.replay.entryTime', 'Entry')}:</span>{' '}
                    <span className="font-medium">{data.summary.entry_time ? new Date(data.summary.entry_time + 'Z').toLocaleString() : '-'}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">{t('attribution.replay.exitTime', 'Exit')}:</span>{' '}
                    <span className="font-medium">{data.summary.exit_time ? new Date(data.summary.exit_time + 'Z').toLocaleString() : '-'}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">{t('attribution.replay.holdDuration', 'Duration')}:</span>{' '}
                    <span className="font-medium">{data.summary.hold_duration || '-'}</span>
                  </div>
                </div>
                <div className="flex gap-6">
                  <div>
                    <span className="text-muted-foreground">{t('attribution.pnl', 'PnL')}:</span>{' '}
                    <span className={`font-bold ${data.summary.pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                      ${data.summary.pnl.toFixed(2)}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </>
        ) : null}
      </DialogContent>
    </Dialog>
  )
}
