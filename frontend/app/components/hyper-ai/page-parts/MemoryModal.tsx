import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Brain, Loader2, X } from 'lucide-react'

import { Button } from '@/components/ui/button'

// Memory category icons and colors
const MEMORY_CATEGORY_STYLES: Record<string, { icon: string; color: string }> = {
  preference: { icon: '🎯', color: 'text-blue-500' },
  decision: { icon: '⚡', color: 'text-amber-500' },
  lesson: { icon: '📖', color: 'text-green-500' },
  insight: { icon: '💡', color: 'text-purple-500' },
  context: { icon: '📌', color: 'text-gray-500' },
}

export function MemoryModal({
  open,
  onClose
}: {
  open: boolean
  onClose: () => void
}) {
  const { t } = useTranslation()
  const [memories, setMemories] = useState<any[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (open) {
      setLoading(true)
      fetch('/api/hyper-ai/memories?limit=50')
        .then(res => res.json())
        .then(data => setMemories(data.memories || []))
        .catch(() => setMemories([]))
        .finally(() => setLoading(false))
    }
  }, [open])

  if (!open) return null

  // Group memories by category
  const grouped: Record<string, any[]> = {}
  for (const m of memories) {
    const cat = m.category || 'context'
    if (!grouped[cat]) grouped[cat] = []
    grouped[cat].push(m)
  }

  const categoryOrder = ['preference', 'decision', 'lesson', 'insight', 'context']

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="w-full max-w-3xl bg-background rounded-lg shadow-xl flex flex-col"
           style={{ height: '600px' }}>
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b shrink-0">
          <div className="flex items-center gap-2">
            <Brain className="w-5 h-5 text-primary" />
            <h2 className="text-lg font-semibold">
              {t('hyperAi.memory.title', 'What Hyper AI Remembered')}
            </h2>
            {memories.length > 0 && (
              <span className="text-xs text-muted-foreground ml-2">
                {t('hyperAi.memory.items', '{{count}} memories', { count: memories.length })}
              </span>
            )}
          </div>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="w-4 h-4" />
          </Button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {loading ? (
            <div className="flex items-center justify-center h-full">
              <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
            </div>
          ) : memories.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <Brain className="w-12 h-12 text-muted-foreground/30 mb-3" />
              <p className="text-sm text-muted-foreground max-w-sm">
                {t('hyperAi.memory.empty')}
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {categoryOrder.map(cat => {
                const items = grouped[cat]
                if (!items || items.length === 0) return null
                const style = MEMORY_CATEGORY_STYLES[cat] || MEMORY_CATEGORY_STYLES.context
                const label = t(`hyperAi.memory.category.${cat}`, cat)
                return (
                  <div key={cat}>
                    <div className="flex items-center gap-2 mb-2">
                      <span>{style.icon}</span>
                      <span className={`text-sm font-medium ${style.color}`}>{label}</span>
                      <span className="text-xs text-muted-foreground">({items.length})</span>
                    </div>
                    <div className="space-y-2 ml-6">
                      {items.map((m: any) => (
                        <MemoryItem key={m.id} memory={m} />
                      ))}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function MemoryItem({ memory }: { memory: any }) {
  const importance = memory.importance || 0.5
  const stars = Math.round(importance * 5)
  const date = memory.created_at
    ? new Date(memory.created_at).toLocaleDateString()
    : ''

  return (
    <div className="rounded-md border bg-muted/30 px-3 py-2 text-sm">
      <p className="leading-relaxed">{memory.content}</p>
      <div className="flex items-center gap-3 mt-1.5 text-xs text-muted-foreground">
        <span>{'★'.repeat(stars)}{'☆'.repeat(5 - stars)}</span>
        {date && <span>{date}</span>}
        {memory.source && <span className="capitalize">{memory.source}</span>}
      </div>
    </div>
  )
}
