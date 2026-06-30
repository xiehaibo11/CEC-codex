import { useTranslation } from 'react-i18next'
import { ScrollArea } from '@/components/ui/scroll-area'
import { DiagnosisCard } from './DiagnosisCard'
import { PromptSuggestionCard } from './PromptSuggestionCard'
import type { DiagnosisResult } from './types'

// Diagnosis Cards Panel Component
export function DiagnosisCardsPanel({ results }: { results: DiagnosisResult[] }) {
  const { t } = useTranslation()

  // Group results by roundIndex
  const groupedResults = results.reduce((acc, result) => {
    const round = result.roundIndex ?? 0
    if (!acc[round]) acc[round] = []
    acc[round].push(result)
    return acc
  }, {} as Record<number, DiagnosisResult[]>)

  // Get sorted round indices (newest first, so descending)
  const sortedRounds = Object.keys(groupedResults).map(Number).sort((a, b) => b - a)

  return (
    <div className="w-[55%] flex flex-col bg-muted/30">
      <div className="p-4 border-b">
        <h3 className="text-sm font-semibold">{t('attribution.aiAnalysis.diagnosisResults', 'Diagnosis Results')}</h3>
        <p className="text-xs text-muted-foreground mt-1">
          {results.length > 0
            ? t('attribution.aiAnalysis.resultsCount', '{{count}} result(s)').replace('{{count}}', results.length.toString())
            : t('attribution.aiAnalysis.resultsWillAppear', 'AI diagnosis results will appear here')}
        </p>
      </div>
      <ScrollArea className="flex-1 p-4">
        {results.length > 0 ? (
          <div className="space-y-4">
            {sortedRounds.map((roundIdx, groupIndex) => (
              <div key={roundIdx}>
                {groupIndex > 0 && (
                  <div className="flex items-center gap-2 my-4">
                    <div className="flex-1 h-px bg-border" />
                    <span className="text-xs text-muted-foreground">Round {roundIdx + 1}</span>
                    <div className="flex-1 h-px bg-border" />
                  </div>
                )}
                {groupIndex === 0 && sortedRounds.length > 1 && (
                  <div className="text-xs text-muted-foreground mb-2 font-medium">Latest</div>
                )}
                <div className="space-y-3">
                  {groupedResults[roundIdx].filter(r => r._type === 'diagnosis').map((card, idx) => (
                    <DiagnosisCard key={`diag-${roundIdx}-${idx}`} card={card} />
                  ))}
                  {groupedResults[roundIdx].filter(r => r._type === 'prompt_suggestion').map((suggestion, idx) => (
                    <PromptSuggestionCard key={`sugg-${roundIdx}-${idx}`} suggestion={suggestion} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            <div className="text-center">
              <p className="text-sm">{t('attribution.aiAnalysis.noResultsYet', 'No diagnosis results yet')}</p>
              <p className="text-xs mt-2">{t('attribution.aiAnalysis.startAnalysis', 'Start a conversation to get diagnosis')}</p>
            </div>
          </div>
        )}
      </ScrollArea>
    </div>
  )
}
