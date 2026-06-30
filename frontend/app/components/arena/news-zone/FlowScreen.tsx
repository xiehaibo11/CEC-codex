import { formatFlow, toLocalTime } from './formatters'
import type { SSEFlowSummary } from './types'
import { WallScreen } from './WallScreen'

interface FlowScreenProps {
  x: number
  y: number
  w: number
  flowItems: SSEFlowSummary[]
}

export function FlowScreen({ x, y, w, flowItems }: FlowScreenProps) {
  return (
    <WallScreen x={x} y={y} w={w} label="巨鲸动向">
      <div style={{ padding: '6px 10px', overflow: 'hidden', height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'space-evenly' }}>
        {flowItems.length > 0 ? flowItems.map((f) => {
          const lbc = f.large_buy_count || 0
          const lsc = f.large_sell_count || 0
          const oiPct = f.open_interest_change_pct ?? 0
          const frPct = f.funding_rate_pct ?? 0
          return (
            <div key={f.symbol} style={{ paddingBottom: 4, borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                <span style={{ color: '#38bdf8', fontSize: 15, fontWeight: 'bold' }}>🐋 {f.symbol}</span>
                <span style={{
                  color: f.large_order_net >= 0 ? '#4ade80' : '#f87171',
                  fontSize: 20, fontWeight: 'bold',
                }}>
                  {formatFlow(f.large_order_net)}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#94a3b8', marginTop: 3 }}>
                <span>
                  <span style={{ color: '#4ade80' }}>▲{lbc}</span>
                  {' / '}
                  <span style={{ color: '#f87171' }}>▼{lsc}</span>
                  {'笔交易'}
                </span>
                <span>
                  OI <span style={{ color: oiPct >= 0 ? '#4ade80' : '#f87171' }}>{oiPct >= 0 ? '+' : ''}{oiPct.toFixed(2)}%</span>
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: '#64748b', marginTop: 2 }}>
                <span>FR: {(frPct * 100).toFixed(4)}%</span>
                <span>{toLocalTime(f.latest_trade_timestamp)}</span>
              </div>
            </div>
          )
        }) : (
          <div style={{ color: '#475569', fontSize: 14, fontFamily: 'monospace' }}>暂无数据</div>
        )}
      </div>
    </WallScreen>
  )
}
