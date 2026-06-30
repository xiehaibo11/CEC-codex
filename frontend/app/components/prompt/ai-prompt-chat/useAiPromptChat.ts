import { useState, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'react-hot-toast'
import { pollAiStream } from '@/lib/pollAiStream'
import { TradingAccount } from '@/lib/api'
import { createSSEEventHandler } from './sseHandler'
import type {
  CompressionPoint,
  Conversation,
  ExtractedPrompt,
  Message,
  TokenUsage,
  ToolCallLogEntry,
} from './types'

interface UseAiPromptChatParams {
  open: boolean
  onOpenChange: (open: boolean) => void
  accounts: TradingAccount[]
  onApplyPrompt: (promptText: string) => void
  promptId?: number | null
}

export function useAiPromptChat({
  open,
  onOpenChange,
  accounts,
  onApplyPrompt,
  promptId,
}: UseAiPromptChatParams) {
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
  const [extractedPrompts, setExtractedPrompts] = useState<ExtractedPrompt[]>([])
  const [selectedPromptIndex, setSelectedPromptIndex] = useState<number>(0)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const chatContainerRef = useRef<HTMLDivElement>(null)

  const handleSSEEvent = createSSEEventHandler({ setMessages, setCompressionPoints, t })

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages])

  // Load conversations when modal opens
  useEffect(() => {
    if (open) {
      loadConversations()
      // Select first AI account by default
      const aiAccounts = accounts.filter(acc => acc.account_type === 'AI')
      if (aiAccounts.length > 0 && !selectedAccountId) {
        setSelectedAccountId(aiAccounts[0].id)
      }
    }
  }, [open, accounts])

  // Load messages when conversation changes
  useEffect(() => {
    if (currentConversationId) {
      loadMessages(currentConversationId)
    }
  }, [currentConversationId])

  // Refresh token usage when trader changes (without reloading messages)
  useEffect(() => {
    if (!currentConversationId || !selectedAccountId) return
    const params = `?account_id=${selectedAccountId}`
    fetch(`/api/prompts/ai-conversations/${currentConversationId}/messages${params}`)
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data?.token_usage !== undefined) setTokenUsage(data.token_usage) })
      .catch(() => {})
  }, [selectedAccountId])

  const loadConversations = async () => {
    setLoadingConversations(true)
    try {
      const response = await fetch('/api/prompts/ai-conversations')
      if (response.ok) {
        const data = await response.json()
        setConversations(data.conversations || [])
      } else if (response.status === 403) {
        toast.error(t('aiPrompt.premiumOnly', 'This feature is only available for premium members'))
        onOpenChange(false)
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
      const response = await fetch(`/api/prompts/ai-conversations/${conversationId}/messages${params}`)
      if (response.ok) {
        const data = await response.json()
        // Map API fields to frontend format
        const mappedMessages = (data.messages || []).map((m: Message & { is_complete?: boolean; tool_calls_log?: ToolCallLogEntry[]; reasoning_snapshot?: string }) => ({
          ...m,
          isInterrupted: m.role === 'assistant' && m.is_complete === false,
          toolCallsLog: m.tool_calls_log || [],
          reasoningSnapshot: m.reasoning_snapshot || null
        }))
        setMessages(mappedMessages)
        setCompressionPoints(data.compression_points || [])
        setTokenUsage(data.token_usage || null)

        // Extract ALL prompts from assistant messages (for version management)
        const prompts: ExtractedPrompt[] = []
        mappedMessages
          .filter((m: Message) => m.role === 'assistant' && m.promptResult)
          .forEach((m: Message) => {
            if (m.promptResult) {
              prompts.push({ id: m.id, content: m.promptResult })
            }
          })
        setExtractedPrompts(prompts)
        if (prompts.length > 0) {
          setSelectedPromptIndex(prompts.length - 1)
        }
      }
    } catch (error) {
      console.error('Failed to load messages:', error)
    }
  }

  const sendMessage = async () => {
    if (!userInput.trim() || !selectedAccountId) return
    if (!selectedAccountId) {
      toast.error(t('aiPrompt.selectTraderFirst', 'Please select an AI Trader first'))
      return
    }

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
      statusText: t('aiPrompt.connecting', 'Connecting...'),
      toolCalls: [],
    }
    setMessages(prev => [...prev, tempUserMsg, tempAssistantMsg])

    let finalConversationId: number | null = null

    try {
      const response = await fetch('/api/prompts/ai-chat-stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          accountId: selectedAccountId,
          userMessage: userMessage,
          conversationId: currentConversationId,
          promptId: promptId || undefined,
        }),
      })

      if (!response.ok) {
        if (response.status === 403) {
          toast.error(t('aiPrompt.premiumOnly', 'This feature is only available for premium members'))
          onOpenChange(false)
          return
        }
        throw new Error('Failed to connect')
      }

      // Check if response is JSON (background task mode) or SSE stream
      const contentType = response.headers.get('content-type') || ''
      if (contentType.includes('application/json')) {
        // Background task mode: poll for results
        const taskData = await response.json()
        const taskId = taskData.task_id
        if (!taskId) throw new Error('No task_id returned')

        let finalContent = ''
        let finalPromptResult: string | null = null
        let hasError = false

        const pollResult = await pollAiStream(taskId, {
          onChunk: (chunk) => {
            handleSSEEvent(chunk.event_type, chunk.data, tempAssistantMsgId, (updates) => {
              if (updates.content !== undefined) finalContent = updates.content
              if (updates.promptResult !== undefined) finalPromptResult = updates.promptResult
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
            ? { ...m, content: finalContent, promptResult: finalPromptResult, isStreaming: false, statusText: undefined }
            : m
        ))

        // Add new prompt to version list if available
        if (finalPromptResult) {
          setExtractedPrompts(prev => {
            const newPrompts = [...prev, { id: tempAssistantMsgId, content: finalPromptResult! }]
            setSelectedPromptIndex(newPrompts.length - 1)
            return newPrompts
          })
        }

        // Set conversation ID if no error
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
        let finalPromptResult: string | null = null
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
                  if (updates.promptResult !== undefined) finalPromptResult = updates.promptResult
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
            ? { ...m, content: finalContent, promptResult: finalPromptResult, isStreaming: false, statusText: undefined }
            : m
        ))

        // Add new prompt to version list if available
        if (finalPromptResult) {
          setExtractedPrompts(prev => {
            const newPrompts = [...prev, { id: tempAssistantMsgId, content: finalPromptResult! }]
            setSelectedPromptIndex(newPrompts.length - 1)
            return newPrompts
          })
        }

        // Set conversation ID if no error
        if (!hasError && !currentConversationId && finalConversationId) {
          setCurrentConversationId(finalConversationId)
          loadConversations()
        }
      }
    } catch (error) {
      console.error('Chat error:', error)
      const convId = finalConversationId || currentConversationId
      if (convId) {
        toast.error(t('aiPrompt.connectionLost', 'Connection lost, reloading messages...'))
        await loadMessages(convId)
        if (!currentConversationId && finalConversationId) {
          setCurrentConversationId(finalConversationId)
          loadConversations()
        }
      } else {
        toast.error(t('aiPrompt.sendFailed', 'Failed to send message'))
        setMessages(prev => prev.filter(m => m.id !== tempUserMsgId && m.id !== tempAssistantMsgId))
      }
    } finally {
      setLoading(false)
    }
  }

  const handleApplyPrompt = (index?: number) => {
    const idx = index !== undefined ? index : selectedPromptIndex
    const prompt = extractedPrompts[idx]
    if (prompt) {
      onApplyPrompt(prompt.content)
      toast.success(t('aiPrompt.promptApplied', 'Prompt applied to editor'))
      onOpenChange(false)
    }
  }

  const startNewConversation = () => {
    setCurrentConversationId(null)
    setMessages([])
    setExtractedPrompts([])
    setSelectedPromptIndex(0)
    setTokenUsage(null)
  }

  const continueConversation = () => {
    setUserInput(t('aiPrompt.continueMessage', 'Please continue'))
    setTimeout(() => sendMessage(), 100)
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
    extractedPrompts,
    selectedPromptIndex,
    setSelectedPromptIndex,
    messagesEndRef,
    chatContainerRef,
    sendMessage,
    handleApplyPrompt,
    startNewConversation,
    continueConversation,
  }
}
