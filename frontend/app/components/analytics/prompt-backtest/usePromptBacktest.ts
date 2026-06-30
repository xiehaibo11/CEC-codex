import { useState, useEffect, useCallback } from 'react'
import dayjs from 'dayjs'
import { createBacktestTask, BacktestTaskItemForImport } from '@/lib/api'
import { fetchModelChatRecords, fetchModelChatSnapshots, PAGE_SIZE } from './api'
import type { ModelChatEntry, SelectedRecord } from './types'

export function usePromptBacktest(
  accountId: string,
  tradingMode: string,
  exchange: string
) {
  // State for record selection
  const [records, setRecords] = useState<ModelChatEntry[]>([])
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [loading, setLoading] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(true)

  // Filter state
  const [filterOperation, setFilterOperation] = useState<string>('all')
  const [filterSymbol, setFilterSymbol] = useState<string>('all')
  const [filterHasSnapshot, setFilterHasSnapshot] = useState(false)
  const [availableSymbols, setAvailableSymbols] = useState<string[]>([])

  // State for workspace
  const [workspace, setWorkspace] = useState<SelectedRecord[]>([])
  const [findText, setFindText] = useState('')
  const [replaceText, setReplaceText] = useState('')
  const [replaceCount, setReplaceCount] = useState<number | null>(null)
  const [loadingSnapshots, setLoadingSnapshots] = useState(false)
  const [searchMode, setSearchMode] = useState(false)  // Whether in search preview mode

  // State for editing single prompt
  const [editingRecord, setEditingRecord] = useState<SelectedRecord | null>(null)
  const [editDialogOpen, setEditDialogOpen] = useState(false)

  // State for history modal
  const [historyModalOpen, setHistoryModalOpen] = useState(false)
  const [initialTaskId, setInitialTaskId] = useState<number | undefined>(undefined)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Fetch model chat records (without snapshots for performance)
  const fetchRecords = useCallback(async (beforeTime?: string, append = false) => {
    if (accountId === 'all') return
    if (append) {
      setLoadingMore(true)
    } else {
      setLoading(true)
      setHasMore(true)
    }
    try {
      const entries = await fetchModelChatRecords({ accountId, tradingMode, exchange, beforeTime })

      if (append) {
        setRecords(prev => [...prev, ...entries])
      } else {
        setRecords(entries)
        // Extract unique symbols for filter
        const symbols = [...new Set(entries.map((e: ModelChatEntry) => e.symbol).filter(Boolean))] as string[]
        setAvailableSymbols(symbols)
      }

      setHasMore(entries.length >= PAGE_SIZE)
    } catch (error) {
      console.error('Failed to fetch records:', error)
    } finally {
      setLoading(false)
      setLoadingMore(false)
    }
  }, [accountId, tradingMode, exchange])

  // Load more records
  const loadMore = () => {
    if (records.length === 0 || loadingMore) return
    const lastRecord = records[records.length - 1]
    if (lastRecord.decision_time) {
      fetchRecords(lastRecord.decision_time, true)
    }
  }

  useEffect(() => {
    fetchRecords()
  }, [fetchRecords])

  // Toggle record selection
  const toggleSelect = (id: number) => {
    const newSelected = new Set(selectedIds)
    if (newSelected.has(id)) {
      newSelected.delete(id)
    } else {
      newSelected.add(id)
    }
    setSelectedIds(newSelected)
  }

  // Filter records based on current filters
  const filteredRecords = records.filter(r => {
    if (filterOperation !== 'all' && r.operation?.toLowerCase() !== filterOperation) return false
    if (filterSymbol !== 'all' && r.symbol !== filterSymbol) return false
    if (filterHasSnapshot && !r.has_snapshot) return false
    return true
  })

  // Select all / deselect all
  const toggleSelectAll = () => {
    if (selectedIds.size === filteredRecords.length && filteredRecords.length > 0) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(filteredRecords.map(r => r.id)))
    }
  }

  // Load selected records into workspace (fetch snapshots on demand)
  const loadToWorkspace = async () => {
    const selectedRecords = records.filter(r => selectedIds.has(r.id))
    if (selectedRecords.length === 0) return

    setLoadingSnapshots(true)
    try {
      // Fetch snapshots for selected records
      const ids = selectedRecords.map(r => r.id)
      const entriesWithSnapshots = await fetchModelChatSnapshots(accountId, ids)

      // Map snapshots to selected records
      const snapshotMap = new Map(entriesWithSnapshots.map((e: ModelChatEntry) => [e.id, e]))
      const workspaceItems = selectedRecords
        .map(r => {
          const withSnapshot = snapshotMap.get(r.id)
          if (withSnapshot?.prompt_snapshot) {
            return { ...withSnapshot, modifiedPrompt: withSnapshot.prompt_snapshot }
          }
          return null
        })
        .filter(Boolean) as SelectedRecord[]

      setWorkspace(prev => {
        const existingIds = new Set(prev.map(p => p.id))
        const newItems = workspaceItems.filter(w => !existingIds.has(w.id))
        // Sort by decision_time descending (newest first)
        return [...prev, ...newItems].sort((a, b) => {
          const timeA = a.decision_time ? new Date(a.decision_time).getTime() : 0
          const timeB = b.decision_time ? new Date(b.decision_time).getTime() : 0
          return timeB - timeA
        })
      })
      setSelectedIds(new Set())
      setReplaceCount(null)
    } catch (error) {
      console.error('Failed to load snapshots:', error)
    } finally {
      setLoadingSnapshots(false)
    }
  }

  // Remove item from workspace
  const removeFromWorkspace = (id: number) => {
    setWorkspace(prev => prev.filter(r => r.id !== id))
  }

  // Apply batch replace
  const applyReplace = () => {
    if (!findText) return
    let count = 0
    const updated = workspace.map(r => {
      // Only replace if matched and selected
      if (r.isMatched && r.isSelected !== false && r.modifiedPrompt.includes(findText)) {
        count++
        return {
          ...r,
          modifiedPrompt: r.modifiedPrompt.replaceAll(findText, replaceText),
          isModified: true,
          isMatched: false,  // Clear match state after replace
          matchContext: undefined,
        }
      }
      return r
    })
    setWorkspace(updated)
    setReplaceCount(count)
    setSearchMode(false)
  }

  // Search and preview matches
  const searchPreview = () => {
    if (!findText) {
      // Clear search mode
      setSearchMode(false)
      setWorkspace(prev => prev.map(r => ({
        ...r,
        isMatched: undefined,
        isSelected: undefined,
        matchContext: undefined,
      })))
      return
    }

    const updated = workspace.map(r => {
      const matchPos = r.modifiedPrompt.indexOf(findText)

      if (matchPos >= 0) {
        // Find line number of match position
        const textBefore = r.modifiedPrompt.substring(0, matchPos)
        const linesBefore = textBefore.split('\n')
        const matchLineNum = linesBefore.length - 1  // 0-indexed

        // Split entire text into lines
        const allLines = r.modifiedPrompt.split('\n')

        // Calculate how many lines the search text spans
        const searchLines = findText.split('\n').length

        // Extract context: 1 line before, matched lines, 1 line after
        const start = Math.max(0, matchLineNum - 1)
        const end = Math.min(allLines.length, matchLineNum + searchLines + 1)
        const contextLines = allLines.slice(start, end).map((line, i) => {
          const lineNum = start + i + 1
          const isInMatch = (start + i >= matchLineNum) && (start + i < matchLineNum + searchLines)
          return `${isInMatch ? '>' : ' '} ${lineNum}: ${line}`
        })

        return {
          ...r,
          isMatched: true,
          isSelected: true,  // Default selected
          matchContext: contextLines.join('\n'),
        }
      }

      return {
        ...r,
        isMatched: false,
        isSelected: undefined,
        matchContext: undefined,
      }
    })

    setWorkspace(updated)
    setSearchMode(true)
    setReplaceCount(null)
  }

  // Toggle selection for a workspace item
  const toggleWorkspaceSelect = (id: number) => {
    setWorkspace(prev => prev.map(r =>
      r.id === id ? { ...r, isSelected: !r.isSelected } : r
    ))
  }

  // Clear search mode
  const clearSearch = () => {
    setFindText('')
    setReplaceText('')
    setSearchMode(false)
    setReplaceCount(null)
    setWorkspace(prev => prev.map(r => ({
      ...r,
      isMatched: undefined,
      isSelected: undefined,
      matchContext: undefined,
    })))
  }

  // Import items from history task to workspace
  const handleImportFromHistory = (items: BacktestTaskItemForImport[]) => {
    const newWorkspaceItems: SelectedRecord[] = items.map(item => ({
      id: item.id,
      account_id: Number(accountId),
      account_name: '',
      operation: item.operation || '',
      symbol: item.symbol,
      reason: item.reason || '',
      executed: true,
      decision_time: item.decision_time,
      realized_pnl: item.realized_pnl,
      has_snapshot: true,
      prompt_snapshot: item.modified_prompt,
      modifiedPrompt: item.modified_prompt,
    }))

    setWorkspace(prev => {
      const existingIds = new Set(prev.map(p => p.id))
      const newItems = newWorkspaceItems.filter(w => !existingIds.has(w.id))
      // Sort by decision_time descending (newest first)
      return [...prev, ...newItems].sort((a, b) => {
        const timeA = a.decision_time ? new Date(a.decision_time).getTime() : 0
        const timeB = b.decision_time ? new Date(b.decision_time).getTime() : 0
        return timeB - timeA
      })
    })

    // Clear search state
    clearSearch()
  }

  // Save edited prompt
  const saveEditedPrompt = () => {
    if (!editingRecord) return
    setWorkspace(prev =>
      prev.map(r =>
        r.id === editingRecord.id
          ? { ...r, modifiedPrompt: editingRecord.modifiedPrompt }
          : r
      )
    )
    setEditDialogOpen(false)
    setEditingRecord(null)
  }

  // Submit backtest task
  const submitBacktest = async () => {
    if (workspace.length === 0 || accountId === 'all' || isSubmitting) return
    setIsSubmitting(true)
    try {
      const result = await createBacktestTask({
        account_id: Number(accountId),
        name: `Backtest ${dayjs().format('YYYY-MM-DD HH:mm')}`,
        items: workspace.map(r => ({
          decision_log_id: r.id,
          modified_prompt: r.modifiedPrompt,
        })),
        replace_rules: findText ? [{ find: findText, replace: replaceText }] : undefined,
      })
      // Open history modal with the new task
      setInitialTaskId(result.task_id)
      setHistoryModalOpen(true)
    } catch (error) {
      console.error('Failed to create backtest task:', error)
    } finally {
      setIsSubmitting(false)
    }
  }

  // Clear search mode when find input changes
  const handleFindTextChange = (value: string) => {
    setFindText(value)
    if (searchMode) {
      setSearchMode(false)
      setReplaceCount(null)
      setWorkspace(prev => prev.map(r => ({
        ...r,
        isMatched: undefined,
        isSelected: undefined,
        matchContext: undefined,
      })))
    }
  }

  return {
    // record selection
    selectedIds,
    loading,
    loadingMore,
    hasMore,
    filteredRecords,
    fetchRecords,
    loadMore,
    toggleSelect,
    toggleSelectAll,
    // filters
    filterOperation,
    setFilterOperation,
    filterSymbol,
    setFilterSymbol,
    availableSymbols,
    // workspace
    workspace,
    findText,
    replaceText,
    setReplaceText,
    replaceCount,
    loadingSnapshots,
    searchMode,
    loadToWorkspace,
    removeFromWorkspace,
    applyReplace,
    searchPreview,
    toggleWorkspaceSelect,
    clearSearch,
    handleImportFromHistory,
    handleFindTextChange,
    // editing
    editingRecord,
    setEditingRecord,
    editDialogOpen,
    setEditDialogOpen,
    saveEditedPrompt,
    // history modal
    historyModalOpen,
    setHistoryModalOpen,
    initialTaskId,
    setInitialTaskId,
    isSubmitting,
    submitBacktest,
  }
}
