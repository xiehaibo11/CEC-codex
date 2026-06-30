import type { DiagnosisResult } from './types'

// Diagnosis Card Component
export function DiagnosisCard({ card }: { card: DiagnosisResult }) {
  const severityColors: Record<string, string> = {
    high: 'border-red-500/50 bg-red-500/10',
    medium: 'border-yellow-500/50 bg-yellow-500/10',
    low: 'border-blue-500/50 bg-blue-500/10',
  }
  const colorClass = severityColors[card.severity || 'medium'] || severityColors.medium

  return (
    <div className={`rounded-lg border p-4 ${colorClass}`}>
      <div className="flex items-start justify-between mb-2">
        <h4 className="font-semibold text-sm">{card.title || 'Diagnosis'}</h4>
        {card.severity && (
          <span className={`text-xs px-2 py-0.5 rounded ${
            card.severity === 'high' ? 'bg-red-500/20 text-red-600' :
            card.severity === 'medium' ? 'bg-yellow-500/20 text-yellow-600' :
            'bg-blue-500/20 text-blue-600'
          }`}>
            {card.severity.toUpperCase()}
          </span>
        )}
      </div>
      {card.metrics && (
        <div className="flex flex-wrap gap-2 mb-2">
          {Object.entries(card.metrics).map(([key, value]) => (
            <span key={key} className="text-xs bg-background/50 px-2 py-1 rounded">
              {key}: {String(value)}
            </span>
          ))}
        </div>
      )}
      {card.description && (
        <p className="text-sm text-muted-foreground">{card.description}</p>
      )}
    </div>
  )
}
