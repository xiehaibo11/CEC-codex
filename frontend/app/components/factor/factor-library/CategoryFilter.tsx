import { Badge } from '@/components/ui/badge'
import type { FactorLibraryController } from './useFactorLibrary'

export default function CategoryFilter({ ctrl }: { ctrl: FactorLibraryController }) {
  const { t, categoryFilter, setCategoryFilter, categories, getCatLabel, customFactors } = ctrl

  return (
    <div className="flex gap-1.5 flex-wrap">
      <Badge variant={categoryFilter === 'all' ? 'default' : 'outline'} className="cursor-pointer text-xs"
        onClick={() => setCategoryFilter('all')}>全部</Badge>
      {categories.map(c => (
        <Badge key={c} variant={categoryFilter === c ? 'default' : 'outline'}
          className="cursor-pointer text-xs" onClick={() => setCategoryFilter(c)}>
          {getCatLabel(c)}
        </Badge>
      ))}
      {customFactors.length > 0 && (
        <Badge
          variant={categoryFilter === 'custom' ? 'default' : 'outline'}
          className={`cursor-pointer text-xs ${categoryFilter !== 'custom' ? 'bg-purple-500/10 text-purple-400 border-purple-500/30 hover:bg-purple-500/20' : 'bg-purple-600'}`}
          onClick={() => setCategoryFilter('custom')}>
          {t('factors.customTag')} ({customFactors.length})
        </Badge>
      )}
    </div>
  )
}
