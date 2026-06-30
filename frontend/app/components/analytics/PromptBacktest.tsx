import { useTranslation } from 'react-i18next'
import { Card, CardContent } from '@/components/ui/card'
import BacktestHistoryModal from './BacktestHistoryModal'
import { usePromptBacktest } from './prompt-backtest/usePromptBacktest'
import DecisionRecordsPanel from './prompt-backtest/DecisionRecordsPanel'
import WorkspacePanel from './prompt-backtest/WorkspacePanel'
import EditPromptDialog from './prompt-backtest/EditPromptDialog'
import type { PromptBacktestProps, SelectedRecord } from './prompt-backtest/types'

export default function PromptBacktest({
  accountId,
  tradingMode = 'all',
  exchange = 'all',
}: PromptBacktestProps) {
  const { t } = useTranslation()
  const pb = usePromptBacktest(accountId, tradingMode, exchange)

  if (accountId === 'all') {
    return (
      <Card>
        <CardContent className="pt-6">
          <p className="text-muted-foreground text-center">
            {t('promptBacktest.selectAccount', 'Please select a specific AI Trader to use Prompt Backtest')}
          </p>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="flex h-full min-h-0 flex-col overflow-y-auto xl:overflow-hidden">
      {/* Main Layout: Left (Records) + Right (Workspace) */}
      <div className="grid min-h-[760px] grid-cols-1 gap-4 xl:min-h-0 xl:flex-1 xl:grid-cols-2">
        {/* Left Panel: Decision Records */}
        <DecisionRecordsPanel
          filteredRecords={pb.filteredRecords}
          selectedIds={pb.selectedIds}
          loading={pb.loading}
          loadingMore={pb.loadingMore}
          hasMore={pb.hasMore}
          loadingSnapshots={pb.loadingSnapshots}
          filterOperation={pb.filterOperation}
          setFilterOperation={pb.setFilterOperation}
          filterSymbol={pb.filterSymbol}
          setFilterSymbol={pb.setFilterSymbol}
          availableSymbols={pb.availableSymbols}
          fetchRecords={pb.fetchRecords}
          loadMore={pb.loadMore}
          toggleSelect={pb.toggleSelect}
          toggleSelectAll={pb.toggleSelectAll}
          loadToWorkspace={pb.loadToWorkspace}
        />

        {/* Right Panel: Workspace */}
        <WorkspacePanel
          workspace={pb.workspace}
          findText={pb.findText}
          replaceText={pb.replaceText}
          setReplaceText={pb.setReplaceText}
          replaceCount={pb.replaceCount}
          searchMode={pb.searchMode}
          isSubmitting={pb.isSubmitting}
          handleFindTextChange={pb.handleFindTextChange}
          searchPreview={pb.searchPreview}
          applyReplace={pb.applyReplace}
          clearSearch={pb.clearSearch}
          submitBacktest={pb.submitBacktest}
          toggleWorkspaceSelect={pb.toggleWorkspaceSelect}
          removeFromWorkspace={pb.removeFromWorkspace}
          onOpenHistory={() => { pb.setInitialTaskId(undefined); pb.setHistoryModalOpen(true) }}
          onEditRecord={(record: SelectedRecord) => {
            pb.setEditingRecord(record)
            pb.setEditDialogOpen(true)
          }}
        />
      </div>

      {/* Edit Prompt Dialog */}
      <EditPromptDialog
        open={pb.editDialogOpen}
        onOpenChange={pb.setEditDialogOpen}
        editingRecord={pb.editingRecord}
        setEditingRecord={pb.setEditingRecord}
        onSave={pb.saveEditedPrompt}
      />

      {/* Backtest History Modal */}
      <BacktestHistoryModal
        open={pb.historyModalOpen}
        onOpenChange={pb.setHistoryModalOpen}
        accountId={accountId}
        initialTaskId={pb.initialTaskId}
        onImportToWorkspace={pb.handleImportFromHistory}
      />
    </div>
  )
}
