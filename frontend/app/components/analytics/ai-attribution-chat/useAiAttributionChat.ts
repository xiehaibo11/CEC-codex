import { useState, useEffect, useRef } from 'react'
import { toast } from 'react-hot-toast'
import { TradingAccount } from '@/lib/api'
import { pollAiStream } from '@/lib/pollAiStream'
import type {
  AnalysisEntry,
  CompressionPoint,
  Conversation,
  DiagnosisResult,
  Message,
  TokenUsage,
} from './types'

export function useAiAttributionChat(open: boolean, accounts: TradingAccount[]) {
  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [loadingConversations, setLoadingConversations] = useState(false)
  const [currentConversationId, setCurrentConversationId] = useState<number | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [compressionPoints, setCompressionPoints] = useState<CompressionPoint[]>([])
  const [tokenUsage, setTokenUsage] = useState<TokenUsage | null>(null)
  const [userInput, setUserInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [allDiagnosisResults, setAllDiagnosisResults] = useState<DiagnosisResult[]>([])
  const [currentRoundIndex, setCurrentRoundIndex] = useState(0)

  const aiAccounts = accounts.filter(acc => acc.account_type === 'AI')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages])

  useEffect(() => {
    if (open) {
      loadConversations()
      if (aiAccounts.length > 0 && !selectedAccountId) {
        setSelectedAccountId(aiAccounts[0].id)
      }
    }
  }, [open, accounts])

  useEffect(() => {
    if (currentConversationId) {
      loadMessages(currentConversationId)
    }
  }, [currentConversationId])

  // Refresh token usage when trader changes (without reloading messages)
  useEffect(() => {
    if (!currentConversationId || !selectedAccountId) return
    const params = `?account_id=${selectedAccountId}`
    fetch(`/api/analytics/ai-attribution/conversations/${currentConversationId}/messages${params}`)
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data?.token_usage !== undefined) setTokenUsage(data.token_usage) })
      .catch(() => {})
  }, [selectedAccountId])

  const loadConversations = async () => {
    setLoadingConversations(true)
    try {
      const response = await fetch('/api/analytics/ai-attribution/conversations')
      if (response.ok) {
        const data = await response.json()
        setConversations(data.conversations || [])
      }
    } catch (error) {
      console.error('Failed to load conversations:', error)
    } finally {
      setLoadingConversations(false)
    }
  }

  const loadMessages = async (conversationId: number) => {
    try {
      const params = selectedAccountId ? `?account_id=${selectedAccountId}` : ''
      const response = await fetch(`/api/analytics/ai-attribution/conversations/${conversationId}/messages${params}`)
      if (response.ok) {
        const data = await response.json()
        // Map tool_calls_log from API to analysisLog for display
        // Handle both old format {type, name, arguments, result} and new format {tool, args, result}
        const mappedMessages = (data.messages || []).map((m: any) => {
          const rawLog = m.tool_calls_log || []
          const analysisLog = rawLog
            .filter((e: any) => e.tool || e.type === 'tool_call')
            .map((e: any) => ({
              type: 'tool_call' as const,
              name: e.tool || e.name || 'unknown',
              arguments: e.args || e.arguments || {},
              result: typeof e.result === 'string' ? JSON.parse(e.result || '{}') : (e.result || {})
            }))
          return {
            ...m,
            analysisLog: analysisLog.length > 0 ? analysisLog : undefined,
            isInterrupted: m.is_complete === false,
          }
        })
        setMessages(mappedMessages)
        setCompressionPoints(data.compression_points || [])
        setTokenUsage(data.token_usage || null)
        // Assign roundIndex to each message's diagnosis results based on message order
        const results: DiagnosisResult[] = []
        let roundIdx = 0
        mappedMessages.forEach((m: Message) => {
          if (m.role === 'assistant' && m.diagnosis_results && m.diagnosis_results.length > 0) {
            // Add roundIndex to each result from this message
            const resultsWithRound = m.diagnosis_results.map((r: DiagnosisResult) => ({ ...r, roundIndex: roundIdx }))
            results.push(...resultsWithRound)
            roundIdx++
          }
        })
        // Reverse to show newest first
        setAllDiagnosisResults(results.reverse())
        setCurrentRoundIndex(roundIdx)
      }
    } catch (error) {
      console.error('Failed to load messages:', error)
    }
  }

  const sendMessage = async () => {
    if (!userInput.trim() || !selectedAccountId) return
    const userMessage = userInput.trim()
    setUserInput('')
    setLoading(true)

    const tempUserMsgId = Date.now()
    const tempAssistantMsgId = tempUserMsgId + 1
    const tempUserMsg: Message = { id: tempUserMsgId, role: 'user', content: userMessage }
    const tempAssistantMsg: Message = {
      id: tempAssistantMsgId,
      role: 'assistant',
      content: '',
      isStreaming: true,
      statusText: 'Connecting...',
    }
    setMessages(prev => [...prev, tempUserMsg, tempAssistantMsg])

    try {
      const response = await fetch('/api/analytics/ai-attribution/chat-stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          accountId: selectedAccountId,
          userMessage: userMessage,
          conversationId: currentConversationId,
        }),
      })

      if (!response.ok) throw new Error('Failed to send message')

      let finalContent = ''
      let finalDiagnosisResults: DiagnosisResult[] = []
      let finalConversationId: number | null = null

      // Check if response is JSON (background task mode) or SSE stream
      const contentType = response.headers.get('content-type') || ''
      if (contentType.includes('application/json')) {
        // Background task mode: poll for results
        const taskData = await response.json()
        const taskId = taskData.task_id

        const pollResult = await pollAiStream(taskId, {
          onChunk: (chunk) => {
            handleSSEEvent(chunk.event_type, chunk.data, tempAssistantMsgId, (updates) => {
              if (updates.content !== undefined) finalContent = updates.content
              if (updates.diagnosisResults) finalDiagnosisResults = updates.diagnosisResults
              if (updates.conversationId) finalConversationId = updates.conversationId
            })
          },
          onTaskLost: () => {
            if (finalConversationId || currentConversationId) {
              loadMessages(finalConversationId || currentConversationId!)
            }
          },
        })

        if (pollResult.status === 'lost') return
      } else {
        // SSE stream mode (legacy fallback, not recommended)
        if (!response.body) throw new Error('No response body')
        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        let currentEventType = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
            if (line.startsWith('event: ')) {
              currentEventType = line.slice(7).trim()
              continue
            }
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6))
                handleSSEEvent(currentEventType, data, tempAssistantMsgId, (updates) => {
                  if (updates.content !== undefined) finalContent = updates.content
                  if (updates.diagnosisResults) finalDiagnosisResults = updates.diagnosisResults
                  if (updates.conversationId) finalConversationId = updates.conversationId
                })
              } catch {}
              currentEventType = ''
            }
          }
        }
      }

      setMessages(prev => prev.map(m =>
        m.id === tempAssistantMsgId
          ? { ...m, content: finalContent, diagnosis_results: finalDiagnosisResults, isStreaming: false }
          : m
      ))
      if (finalDiagnosisResults.length > 0) {
        // Add roundIndex to each result and prepend to array (newest first)
        const resultsWithRound = finalDiagnosisResults.map(r => ({ ...r, roundIndex: currentRoundIndex }))
        setAllDiagnosisResults(prev => [...resultsWithRound, ...prev])
        setCurrentRoundIndex(prev => prev + 1)
      }
      if (!currentConversationId && finalConversationId) {
        setCurrentConversationId(finalConversationId)
        loadConversations()
      }
    } catch (error) {
      console.error('Error sending message:', error)
      toast.error('Failed to send message')
      setMessages(prev => prev.filter(m => m.id !== tempUserMsgId && m.id !== tempAssistantMsgId))
    } finally {
      setLoading(false)
    }
  }

  const handleSSEEvent = (
    eventType: string,
    data: Record<string, unknown>,
    msgId: number,
    onUpdate: (updates: { content?: string; diagnosisResults?: DiagnosisResult[]; conversationId?: number }) => void
  ) => {
    if (eventType === 'conversation_created') {
      onUpdate({ conversationId: data.conversation_id as number })
    } else if (eventType === 'tool_round') {
      setMessages(prev => prev.map(m =>
        m.id === msgId ? { ...m, statusText: `Round ${data.round}/${data.max_rounds}...` } : m
      ))
    } else if (eventType === 'retry') {
      toast(`Retrying... (attempt ${data.attempt}/${data.max_retries})`, { icon: '🔄' })
    } else if (eventType === 'status') {
      setMessages(prev => prev.map(m =>
        m.id === msgId ? { ...m, statusText: data.message as string } : m
      ))
    } else if (eventType === 'reasoning') {
      const entry: AnalysisEntry = { type: 'reasoning', content: data.content as string }
      setMessages(prev => prev.map(m =>
        m.id === msgId ? {
          ...m,
          statusText: `Thinking...`,
          analysisLog: [...(m.analysisLog || []), entry]
        } : m
      ))
    } else if (eventType === 'content') {
      onUpdate({ content: data.content as string })
      setMessages(prev => prev.map(m =>
        m.id === msgId ? { ...m, content: data.content as string, statusText: undefined } : m
      ))
    } else if (eventType === 'done') {
      onUpdate({
        conversationId: data.conversation_id as number,
        content: data.content as string,
        diagnosisResults: data.diagnosis_results as DiagnosisResult[],
      })
      if (data.compression_points) setCompressionPoints(data.compression_points as CompressionPoint[])
      // Convert streaming analysisLog to stored format for immediate display
      // Prefer backend done event data over local conversion
      setMessages(prev => prev.map(m => {
        if (m.id !== msgId) return m
        const backendTcLog = data.tool_calls_log as AnalysisEntry[] | null
        const backendRSnap = data.reasoning_snapshot as string | null
        if (backendTcLog || backendRSnap) {
          const analysisLog = backendTcLog
            ? backendTcLog.map((e: any) => ({ type: 'tool_call' as const, name: e.tool || e.name, arguments: e.args || e.arguments, result: e.result }))
            : (m.analysisLog || []).filter(e => e.type === 'tool_call')
          return { ...m, isStreaming: false, statusText: undefined, analysisLog: analysisLog.length > 0 ? analysisLog : undefined, reasoning_snapshot: backendRSnap || undefined }
        }
        // Fallback: convert from streaming analysisLog
        const log = m.analysisLog || []
        const toolCalls = log.filter(e => e.type === 'tool_call')
        const reasoningParts = log.filter(e => e.type === 'reasoning').map(e => e.content || '')
        return {
          ...m,
          isStreaming: false,
          statusText: undefined,
          analysisLog: toolCalls.length > 0 ? toolCalls : undefined,
          reasoning_snapshot: reasoningParts.length > 0 ? reasoningParts.join('\n\n---\n\n') : undefined,
        }
      }))
    } else if (eventType === 'error') {
      toast.error(data.message as string || 'Analysis failed')
    } else if (eventType === 'interrupted') {
      onUpdate({ conversationId: data.conversation_id as number })
      setMessages(prev => prev.map(m =>
        m.id === msgId ? {
          ...m,
          isStreaming: false,
          isInterrupted: true,
          interruptedRound: data.round as number,
          statusText: ''
        } : m
      ))
    } else if (eventType === 'tool_call') {
      const entry: AnalysisEntry = { type: 'tool_call', name: data.name as string, arguments: data.arguments as Record<string, unknown> }
      setMessages(prev => prev.map(m =>
        m.id === msgId ? {
          ...m,
          statusText: `Calling ${data.name}...`,
          analysisLog: [...(m.analysisLog || []), entry]
        } : m
      ))
    } else if (eventType === 'tool_result') {
      const entry: AnalysisEntry = { type: 'tool_result', name: data.name as string, result: data.result as Record<string, unknown> }
      setMessages(prev => prev.map(m =>
        m.id === msgId ? {
          ...m,
          statusText: `Got result from ${data.name}`,
          analysisLog: [...(m.analysisLog || []), entry]
        } : m
      ))
    }
  }

  const startNewConversation = () => {
    setCurrentConversationId(null)
    setMessages([])
    setAllDiagnosisResults([])
    setCurrentRoundIndex(0)
    setTokenUsage(null)
  }

  return {
    selectedAccountId,
    setSelectedAccountId,
    conversations,
    loadingConversations,
    currentConversationId,
    setCurrentConversationId,
    messages,
    compressionPoints,
    tokenUsage,
    userInput,
    setUserInput,
    loading,
    allDiagnosisResults,
    aiAccounts,
    messagesEndRef,
    sendMessage,
    startNewConversation,
  }
}
