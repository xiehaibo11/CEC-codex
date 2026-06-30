import { SCREEN_H } from './constants'
import { toLocalTime } from './formatters'
import type { SSENewsItem } from './types'
import { WallScreen } from './WallScreen'

interface NewsScreenProps {
  x: number
  y: number
  w: number
  newsItems: SSENewsItem[]
  newsScrollIdx: number
}

export function NewsScreen({ x, y, w, newsItems, newsScrollIdx }: NewsScreenProps) {
  return (
    <WallScreen x={x} y={y} w={w} label="新闻">
      <div style={{ height: '100%', overflow: 'hidden', position: 'relative' }}>
        <div style={{
          transition: 'transform 0.6s ease-in-out',
          transform: `translateY(-${newsScrollIdx * SCREEN_H}px)`,
        }}>
          {newsItems.length > 0 ? newsItems.slice(0, 10).map((n) => (
            <div key={n.id} style={{ height: SCREEN_H, padding: '10px 12px', boxSizing: 'border-box', position: 'relative' }}>
              <div style={{ color: '#a3e635', fontSize: 13, fontWeight: 'bold', lineHeight: 1.3, marginBottom: 8 }}>
                {n.title}
              </div>
              {n.ai_summary && (
                <div style={{ color: '#94a3b8', fontSize: 11, lineHeight: 1.5, marginBottom: 8,
                  display: '-webkit-box', WebkitLineClamp: 10, WebkitBoxOrient: 'vertical', overflow: 'hidden',
                }}>
                  {n.ai_summary}
                </div>
              )}
              <div style={{ color: '#475569', fontSize: 9, fontFamily: 'monospace', position: 'absolute', bottom: 10, left: 12 }}>
                {toLocalTime(n.published_at)}
                {n.symbols && n.symbols.length > 0 && (
                  <span style={{ marginLeft: 8 }}>{n.symbols.slice(0, 3).join(' ')}</span>
                )}
              </div>
            </div>
          )) : (
            <div style={{ height: SCREEN_H, padding: 12, color: '#475569', fontSize: 14, fontFamily: 'monospace' }}>暂无信号</div>
          )}
        </div>
      </div>
    </WallScreen>
  )
}
