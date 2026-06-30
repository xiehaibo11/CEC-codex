import { useTranslation } from 'react-i18next'
import { Send, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { TokenUsage } from './types'

interface ComposerProps {
  userInput: string
  setUserInput: (value: string) => void
  loading: boolean
  selectedAccountId: number | null
  tokenUsage: TokenUsage | null
  onSend: () => void
}

export function Composer({
  userInput,
  setUserInput,
  loading,
  selectedAccountId,
  tokenUsage,
  onSend,
}: ComposerProps) {
  const { t } = useTranslation()

  return (
    <div className="px-4 pb-4 pt-2">
      <div className="relative">
        <textarea
          placeholder={t('aiPrompt.inputPlaceholder', 'Describe your strategy or ask for modifications...')}
          value={userInput}
          onChange={(e) => setUserInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
              e.preventDefault()
              onSend()
            }
          }}
          disabled={loading || !selectedAccountId}
          className="w-full min-h-[80px] max-h-[200px] rounded-xl border border-input bg-transparent px-4 py-3 pb-12 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 resize-y"
          rows={3}
        />
        <div className="absolute bottom-3 right-3 flex items-center gap-2">
          {tokenUsage?.show_warning && (
            <p className="text-xs text-amber-500">
              {t('aiPrompt.contextWarning', 'Context remaining: {{percent}}% · Compressing soon', { percent: Math.max(0, Math.round((1 - tokenUsage.usage_ratio) * 100)) })}
            </p>
          )}
          <Button onClick={onSend} disabled={loading || !userInput.trim() || !selectedAccountId} size="icon" className="rounded-full h-8 w-8 shrink-0">
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </Button>
        </div>
      </div>
    </div>
  )
}
