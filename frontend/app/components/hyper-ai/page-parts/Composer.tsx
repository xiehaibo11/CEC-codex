import type { KeyboardEvent, RefObject } from 'react'
import { useTranslation } from 'react-i18next'
import { Loader2, Send } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { TokenUsage } from './types'

interface ComposerProps {
  inputValue: string
  sending: boolean
  tokenUsage: TokenUsage | null
  textareaRef: RefObject<HTMLTextAreaElement | null>
  onInputChange: (value: string) => void
  onKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void
  onSend: () => void
}

export function Composer({
  inputValue,
  sending,
  tokenUsage,
  textareaRef,
  onInputChange,
  onKeyDown,
  onSend,
}: ComposerProps) {
  const { t } = useTranslation()

  return (
    <div className="px-4 pb-4 pt-2">
      <div className="max-w-5xl mx-auto relative">
        <textarea
          ref={textareaRef}
          value={inputValue}
          onChange={e => onInputChange(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={t('hyperAi.inputPlaceholder', 'Type a message...')}
          disabled={sending}
          className="w-full min-h-[80px] max-h-[200px] rounded-xl border border-input bg-transparent px-4 py-3 pb-12 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 resize-y"
          rows={3}
        />
        <div className="absolute bottom-3 right-3 flex items-center gap-2">
          {tokenUsage?.show_warning && (
            <p className="text-xs text-amber-500">
              {t('hyperAi.contextWarning', 'Context remaining: {{percent}}% · Compressing soon', { percent: Math.max(0, Math.round((1 - tokenUsage.usage_ratio) * 100)) })}
            </p>
          )}
          <Button
            onClick={onSend}
            disabled={!inputValue.trim() || sending}
            size="icon"
            className="rounded-full h-8 w-8 shrink-0"
          >
            {sending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </Button>
        </div>
      </div>
    </div>
  )
}
