import { useTranslation } from 'react-i18next'
import { Button } from '../../ui/button'

interface ReasoningDisplayProps {
  prompt?: string
  showPrompt: boolean
  onTogglePrompt: () => void
}

export function ReasoningDisplay({ prompt, showPrompt, onTogglePrompt }: ReasoningDisplayProps) {
  const { t } = useTranslation()

  if (!prompt) return null

  return (
    <div className="rounded-md border bg-muted/50 p-3">
      <div className="flex items-center justify-between">
        <div className="text-xs font-semibold text-muted-foreground">{t('kline.analysis.userPrompt', 'User Prompt')}</div>
        <Button
          variant="ghost"
          size="sm"
          className="text-xs"
          onClick={onTogglePrompt}
        >
          {showPrompt ? t('kline.analysis.hidePrompt', 'Hide') : t('kline.analysis.showPrompt', 'Show')} {t('kline.analysis.prompt', 'Prompt')}
        </Button>
      </div>
      {showPrompt && (
        <div className="mt-2 max-h-60 overflow-auto rounded border bg-background p-2">
          <pre className="whitespace-pre-wrap text-[11px] text-foreground break-words">{prompt}</pre>
        </div>
      )}
    </div>
  )
}
