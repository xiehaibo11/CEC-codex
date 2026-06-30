import { useTranslation } from 'react-i18next'
import type { DiagnosisResult } from './types'

// Prompt Suggestion Card Component
export function PromptSuggestionCard({ suggestion }: { suggestion: DiagnosisResult }) {
  const { t } = useTranslation()

  return (
    <div className="rounded-lg border border-primary/50 bg-primary/5 p-4">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs bg-primary/20 text-primary px-2 py-0.5 rounded font-medium">
          {t('attribution.aiAnalysis.promptSuggestion', 'Prompt Suggestion')}
        </span>
      </div>
      <h4 className="font-semibold text-sm mb-2">{suggestion.title}</h4>
      {suggestion.current_behavior && (
        <div className="mb-2">
          <span className="text-xs text-muted-foreground">{t('attribution.aiAnalysis.currentBehavior', 'Current')}:</span>
          <p className="text-sm bg-muted/50 rounded p-2 mt-1">{suggestion.current_behavior}</p>
        </div>
      )}
      {suggestion.suggested_change && (
        <div className="mb-2">
          <span className="text-xs text-muted-foreground">{t('attribution.aiAnalysis.suggestedChange', 'Suggested')}:</span>
          <p className="text-sm bg-green-500/10 border border-green-500/30 rounded p-2 mt-1">{suggestion.suggested_change}</p>
        </div>
      )}
      {suggestion.reason && (
        <p className="text-xs text-muted-foreground mt-2">
          <strong>{t('attribution.aiAnalysis.reason', 'Reason')}:</strong> {suggestion.reason}
        </p>
      )}
    </div>
  )
}
