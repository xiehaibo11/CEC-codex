import { useState, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'react-hot-toast'
import { TradingAccount } from '@/lib/api'
import { pollAiStream } from '@/lib/pollAiStream'
import {
  SaveSuggestion,
  ToolCallLogEntry,
  Message,
  Conversation,
  CompressionPoint,
  TokenUsage,
} from './types'

interface UseAiProgramChatParams {
  open: boolean
  onSaveCode: (code: string, name: string, description: string) => Promise<boolean>
  accounts: TradingAccount[]
  programId?: number | null
  programName?: string | null
  programDescription?: string | null
  isNewProgram?: boolean
}

export function useAiProgramChat({
  open,
  onSaveCode,
  accounts,
  programId,
  programName,
  programDescription,
  isNewProgram,
}: UseAiProgramChatParams) {
  const { t } = useTranslation()
  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [loadingConversations, setLoadingConversations] = useState(false)
  const [currentConversationId, setCurrentConversationId] = useState<number | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [compressionPoints, setCompressionPoints] = useState<CompressionPoint[]>([])
  const [tokenUsage, setTokenUsage] = useState<TokenUsage | null>(null)
  const [userInput, setUserInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [allCodeSuggestions, setAllCodeSuggestions] = useState<SaveSuggestion[]>([])

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
    fetch(`/api/programs/ai-conversations/${currentConversationId}/messages${params}`)
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data?.token_usage !== undefined) setTokenUsage(data.token_usage) })
      .catch(() => {})
  }, [selectedAccountId])

  const loadConversations = async () => {
    setLoadingConversations(true)
    try {
      const url = programId
        ? `/api/programs/ai-conversations?program_id=${programId}`
        : '/api/programs/ai-conversations'
      const response = await fetch(url)
      if (response.ok) {
        const data = await response.json()
        setConversations(data || [])
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
      const response = await fetch(`/api/programs/ai-conversations/${conversationId}/messages${params}`)
      if (response.ok) {
        const data = await response.json()
        // Map API fields to frontend format
        const mappedMessages = (data.messages || data).map((m: Message & { is_complete?: boolean; tool_calls_log?: ToolCallLogEntry[]; reasoning_snapshot?: string }) => ({
          ...m,
          isInterrupted: m.role === 'assistant' && m.is_complete === false,
          toolCallsLog: m.tool_calls_log || [],
          reasoningSnapshot: m.reasoning_snapshot || null
        }))
        setMessages(mappedMessages || [])
        setCompressionPoints(data.compression_points || [])
        setTokenUsage(data.token_usage || null)
        const suggestions: SaveSuggestion[] = []
        ;(data.messages || data).forEach((m: Message) => {
          if (m.role === 'assistant' && m.saveSuggestion) {
            suggestions.push(m.saveSuggestion)
          }
        })
        setAllCodeSuggestions(suggestions)
      }
    } catch (error) {
      console.error('Failed to load messages:', error)
    }
  }

  const startNewConversation = () => {
    setCurrentConversationId(null)
    setMessages([])
    setCompressionPoints([])
    setAllCodeSuggestions([])
    setTokenUsage(null)
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
      statusText: t('program.aiChat.connecting'),
      toolCalls: [],
    }
    setMessages(prev => [...prev, tempUserMsg, tempAssistantMsg])

    // Declare outside try block so catch can access it
    let finalConversationId: number | null = null

    try {
      const response = await fetch('/api/programs/ai-chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          account_id: selectedAccountId,
          message: userMessage,
          conversation_id: currentConversationId,
          program_id: programId,
        }),
      })

      if (!response.ok) throw new Error('Failed to connect')

      // Check if response is JSON (background task mode) or SSE stream
      const contentType = response.headers.get('content-type') || ''
      if (contentType.includes('application/json')) {
        // Background task mode: poll for results
        const taskData = await response.json()
        const taskId = taskData.task_id
        if (!taskId) throw new Error('No task_id returned')

        let finalContent = ''
        let finalSuggestion: SaveSuggestion | null = null
        let hasError = false

        const pollResult = await pollAiStream(taskId, {
          onChunk: (chunk) => {
            handleSSEEvent(chunk.event_type, chunk.data, tempAssistantMsgId, (updates) => {
              if (updates.content !== undefined) finalContent = updates.content
              if (updates.suggestion) finalSuggestion = updates.suggestion
              if (updates.conversationId) finalConversationId = updates.conversationId
              if (updates.error) hasError = true
            })
          },
          onTaskLost: () => {
            if (finalConversationId || currentConversationId) {
              loadMessages(finalConversationId || currentConversationId!)
            }
          },
        })

        if (pollResult.status === 'lost') return

        // Finalize the message
        setMessages(prev => prev.map(m =>
          m.id === tempAssistantMsgId
            ? { ...m, content: finalContent, isStreaming: false, statusText: undefined }
            : m
        ))

        if (finalSuggestion) {
          setAllCodeSuggestions(prev => [...prev, finalSuggestion!])
        }

        if (!hasError && !currentConversationId && finalConversationId) {
          setCurrentConversationId(finalConversationId)
          loadConversations()
        }
      } else {
        // SSE stream mode (legacy fallback)
        const reader = response.body?.getReader()
        if (!reader) throw new Error('No reader')

        const decoder = new TextDecoder()
        let buffer = ''
        let finalContent = ''
        let finalSuggestion: SaveSuggestion | null = null
        let hasError = false
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
                handleSSEEvent(currentEventType || data.type as string, data, tempAssistantMsgId, (updates) => {
                  if (updates.content !== undefined) finalContent = updates.content
                  if (updates.suggestion) finalSuggestion = updates.suggestion
                  if (updates.conversationId) finalConversationId = updates.conversationId
                  if (updates.error) hasError = true
                })
              } catch {}
              currentEventType = ''
            }
          }
        }

        // Finalize the message
        setMessages(prev => prev.map(m =>
          m.id === tempAssistantMsgId
            ? { ...m, content: finalContent, isStreaming: false, statusText: undefined }
            : m
        ))

        if (finalSuggestion) {
          setAllCodeSuggestions(prev => [...prev, finalSuggestion!])
        }

        // Only set conversation ID if no error occurred
        if (!hasError && !currentConversationId && finalConversationId) {
          setCurrentConversationId(finalConversationId)
          loadConversations()
        }
      }
    } catch (error) {
      console.error('Chat error:', error)
      // Connection lost - reload messages from server instead of deleting
      const convId = finalConversationId || currentConversationId
      if (convId) {
        toast.error(t('program.aiChat.connectionLost'))
        // Reload saved messages from server
        await loadMessages(convId)
        if (!currentConversationId && finalConversationId) {
          setCurrentConversationId(finalConversationId)
          loadConversations()
        }
      } else {
        // No conversation created yet, remove temp messages
        toast.error(t('program.aiChat.error'))
        setMessages(prev => prev.filter(m => m.id !== tempUserMsgId && m.id !== tempAssistantMsgId))
      }
    } finally {
      setLoading(false)
    }
  }

  const handleSSEEvent = (
    eventType: string,
    data: Record<string, unknown>,
    msgId: number,
    onUpdate: (updates: { content?: string; suggestion?: SaveSuggestion; conversationId?: number; error?: boolean }) => void
  ) => {

    if (eventType === 'conversation_created') {
      // Only save the ID, don't set state yet (will be set after SSE completes)
      onUpdate({ conversationId: data.conversation_id as number })
      setMessages(prev => prev.map(m =>
        m.id === msgId ? { ...m, statusText: t('program.aiChat.thinking') } : m
      ))
    } else if (eventType === 'tool_round') {
      setMessages(prev => prev.map(m =>
        m.id === msgId ? { ...m, statusText: `${t('program.aiChat.toolRound')} ${data.round}/${data.max}` } : m
      ))
    } else if (eventType === 'retry') {
      setMessages(prev => prev.map(m =>
        m.id === msgId ? { ...m, statusText: `${t('program.aiChat.retrying')} (${data.attempt}/${data.max_retries})` } : m
      ))
    } else if (eventType === 'reasoning') {
      const reasoningText = data.content as string || ''
      setMessages(prev => prev.map(m =>
        m.id === msgId ? {
          ...m,
          statusText: `Thinking: ${reasoningText.slice(0, 80)}...`,
          toolCalls: [...(m.toolCalls || []), { type: 'reasoning', content: reasoningText }],
        } : m
      ))
    } else if (eventType === 'tool_call') {
      setMessages(prev => prev.map(m =>
        m.id === msgId ? {
          ...m,
          statusText: `${t('program.aiChat.calling')} ${data.name}...`,
          toolCalls: [...(m.toolCalls || []), {
            type: 'tool_call',
            name: data.name as string,
            args: data.args as Record<string, unknown>,
          }],
        } : m
      ))
    } else if (eventType === 'tool_result') {
      setMessages(prev => prev.map(m =>
        m.id === msgId ? {
          ...m,
          toolCalls: [...(m.toolCalls || []), {
            type: 'tool_result',
            name: data.name as string,
            result: data.result as string,
          }],
        } : m
      ))
    } else if (eventType === 'save_suggestion') {
      const suggestion = data.data as SaveSuggestion
      onUpdate({ suggestion })
      setMessages(prev => prev.map(m =>
        m.id === msgId ? { ...m, saveSuggestion: suggestion } : m
      ))
    } else if (eventType === 'content') {
      const content = data.content as string
      onUpdate({ content })
      setMessages(prev => prev.map(m =>
        m.id === msgId ? { ...m, content, statusText: '' } : m
      ))
    } else if (eventType === 'done') {
      // Final content and conversation_id come in done event
      const content = data.content as string
      if (content) onUpdate({ content })
      if (data.conversation_id) onUpdate({ conversationId: data.conversation_id as number })
      if (data.compression_points) setCompressionPoints(data.compression_points as CompressionPoint[])
      // Convert streaming toolCalls to stored formats for immediate display after completion
      setMessages(prev => prev.map(m => {
        if (m.id !== msgId) return m
        const tcLog = data.tool_calls_log as ToolCallLogEntry[] | null
        const rSnap = data.reasoning_snapshot as string | null
        // Fallback: convert streaming toolCalls if backend didn't send stored formats
        let toolCallsLog = tcLog || m.toolCallsLog
        let reasoningSnapshot = rSnap || m.reasoningSnapshot
        if (!toolCallsLog && m.toolCalls && m.toolCalls.length > 0) {
          toolCallsLog = m.toolCalls
            .filter(e => e.type === 'tool_call')
            .map(e => ({ tool: e.name || 'unknown', args: e.args || {}, result: '' }))
        }
        if (!reasoningSnapshot && m.toolCalls) {
          const parts = m.toolCalls.filter(e => e.type === 'reasoning').map(e => e.content || '')
          if (parts.length > 0) reasoningSnapshot = parts.join('\n\n---\n\n')
        }
        return { ...m, isStreaming: false, toolCallsLog, reasoningSnapshot: reasoningSnapshot || null }
      }))
    } else if (eventType === 'error') {
      // Mark as error so we don't set conversationId
      onUpdate({ error: true })
      setMessages(prev => prev.map(m =>
        m.id === msgId ? { ...m, content: data.content as string, isStreaming: false } : m
      ))
    } else if (eventType === 'interrupted') {
      // AI was interrupted but progress was saved - can be continued
      onUpdate({ conversationId: data.conversation_id as number | undefined })
      setMessages(prev => prev.map(m =>
        m.id === msgId ? {
          ...m,
          isStreaming: false,
          isInterrupted: true,
          interruptedRound: data.round as number,
          statusText: ''
        } : m
      ))
    }
  }

  const handleSaveCode = async (suggestion: SaveSuggestion) => {
    // In edit mode, use original name/description; in new mode, use AI suggestion
    const finalName = !isNewProgram && programName ? programName : suggestion.name
    const finalDescription = !isNewProgram && programDescription !== undefined ? (programDescription || '') : suggestion.description
    const success = await onSaveCode(suggestion.code, finalName, finalDescription)
    if (success) {
      toast.success(t('program.aiChat.codeSaved'))
    }
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
    allCodeSuggestions,
    aiAccounts,
    messagesEndRef,
    startNewConversation,
    sendMessage,
    handleSaveCode,
  }
}
