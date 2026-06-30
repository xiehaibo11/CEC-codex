import { useState } from 'react'
import { toast } from 'react-hot-toast'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Copy, Check } from 'lucide-react'
import { SaveSuggestion } from './types'

// Code Suggestions Panel Component (Right side - 55%)
export function CodeSuggestionsPanel({
  suggestions, onSave, t
}: {
  suggestions: SaveSuggestion[]
  onSave: (suggestion: SaveSuggestion) => void
  t: (key: string, fallback?: string) => string
}) {
  const [savedCodes, setSavedCodes] = useState<Set<string>>(new Set())
  const [savingCodes, setSavingCodes] = useState<Set<string>>(new Set())

  const handleSave = async (suggestion: SaveSuggestion) => {
    const key = suggestion.name
    setSavingCodes(prev => new Set(prev).add(key))
    try {
      await onSave(suggestion)
      setSavedCodes(prev => new Set(prev).add(key))
    } finally {
      setSavingCodes(prev => {
        const next = new Set(prev)
        next.delete(key)
        return next
      })
    }
  }

  return (
    <div className="w-[55%] flex flex-col bg-muted/30">
      <div className="p-4 border-b">
        <h3 className="text-sm font-semibold">{t('program.aiChat.generatedCode')}</h3>
        <p className="text-xs text-muted-foreground mt-1">
          {suggestions.length > 0
            ? t('program.aiChat.codeCount').replace('{{count}}', suggestions.length.toString())
            : t('program.aiChat.codeWillAppear')}
        </p>
      </div>
      <ScrollArea className="flex-1 p-4">
        {suggestions.length > 0 ? (
          <div className="space-y-4">
            {/* Reverse order: newest first */}
            {[...suggestions].reverse().map((suggestion, idx) => (
              <div key={idx}>
                {/* Divider between cards (not before first) */}
                {idx > 0 && (
                  <div className="flex items-center gap-2 mb-4 -mt-2">
                    <div className="flex-1 border-t border-dashed border-muted-foreground/30" />
                    <span className="text-xs text-muted-foreground/50">
                      {t('program.aiChat.previousVersion', 'Previous')}
                    </span>
                    <div className="flex-1 border-t border-dashed border-muted-foreground/30" />
                  </div>
                )}
                <CodeCard
                  suggestion={suggestion}
                  onSave={() => handleSave(suggestion)}
                  isSaving={savingCodes.has(suggestion.name)}
                  isSaved={savedCodes.has(suggestion.name)}
                  isLatest={idx === 0}
                  t={t}
                />
              </div>
            ))}
          </div>
        ) : (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            <div className="text-center">
              <p className="text-sm">{t('program.aiChat.noCodeYet')}</p>
              <p className="text-xs mt-2">{t('program.aiChat.startConversation')}</p>
            </div>
          </div>
        )}
      </ScrollArea>
    </div>
  )
}

// Individual Code Card Component
function CodeCard({
  suggestion, onSave, isSaving, isSaved, isLatest, t
}: {
  suggestion: SaveSuggestion
  onSave: () => void
  isSaving?: boolean
  isSaved?: boolean
  isLatest?: boolean
  t: (key: string, fallback?: string) => string
}) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className={`rounded-lg border bg-card p-4 ${isLatest ? 'ring-1 ring-green-500/30' : ''}`}>
      <div className="flex items-start justify-between mb-3">
        <div>
          <h4 className="font-semibold text-sm">{suggestion.name || t('program.aiChat.unnamedProgram')}</h4>
          <p className="text-xs text-muted-foreground">{suggestion.description}</p>
        </div>
        {isLatest ? (
          <span className="text-xs bg-green-500/10 text-green-600 px-2 py-1 rounded">
            {t('program.aiChat.latest', 'Latest')}
          </span>
        ) : (
          <span className="text-xs bg-primary/10 text-primary px-2 py-1 rounded">
            {t('program.aiChat.program')}
          </span>
        )}
      </div>
      <div className="bg-muted/50 rounded p-2 mb-3">
        <div className="flex items-center justify-between mb-2">
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            {expanded ? t('program.aiChat.hideCode') : t('program.aiChat.showCode')}
          </button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              navigator.clipboard.writeText(suggestion.code)
              toast.success(t('common.copied'))
            }}
          >
            <Copy className="h-3 w-3 mr-1" />
            {t('common.copy')}
          </Button>
        </div>
        {expanded && (
          <pre className="text-xs overflow-x-auto max-h-64 whitespace-pre-wrap">
            {suggestion.code}
          </pre>
        )}
      </div>
      <div className="flex gap-2">
        {isSaved ? (
          <Button size="sm" className="flex-1" variant="secondary" disabled>
            <Check className="h-3 w-3 mr-1" />
            <span className="text-green-600">{t('program.aiChat.saved')}</span>
          </Button>
        ) : (
          <Button size="sm" className="flex-1" onClick={onSave} disabled={isSaving}>
            {isSaving ? t('program.aiChat.saving') : t('program.aiChat.confirmSave')}
          </Button>
        )}
      </div>
    </div>
  )
}
