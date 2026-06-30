import { useState } from 'react'
import { ChevronDown, ChevronRight, Pause } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import type { DecisionChainItem } from './types'

interface HoldGroupCardProps {
  holds: DecisionChainItem[]
  isLast: boolean
}

export function HoldGroupCard({ holds, isLast }: HoldGroupCardProps) {
  const [expanded, setExpanded] = useState(false)

  if (holds.length === 0) return null

  const firstTime = holds[0].decision_time
  const lastTime = holds[holds.length - 1].decision_time
  const formatTime = (time: string | null) => {
    if (!time) return '-'
    return new Date(time + 'Z').toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  return (
    <div className="relative">
      {!isLast && (
        <div className="absolute left-4 top-10 w-0.5 h-full bg-border" />
      )}
      <Card className="relative cursor-pointer hover:bg-muted/50" onClick={() => setExpanded(!expanded)}>
        <CardContent className="p-3">
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-full bg-gray-400 flex items-center justify-center text-white flex-shrink-0">
              <Pause className="w-4 h-4" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-muted-foreground">
                    HOLD x{holds.length}
                  </span>
                  {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                </div>
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                {formatTime(firstTime)} - {formatTime(lastTime)}
              </div>
            </div>
          </div>
          {expanded && (
            <div className="mt-3 pl-11 space-y-2 border-t pt-3">
              {holds.map((hold) => (
                <div key={hold.id} className="text-xs">
                  <div className="text-muted-foreground">
                    {hold.decision_time ? new Date(hold.decision_time + 'Z').toLocaleString() : '-'}
                  </div>
                  {hold.reason && (
                    <div className="text-muted-foreground/80 mt-1 line-clamp-2">
                      {hold.reason}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
