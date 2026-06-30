import { useState, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'react-hot-toast'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import PacmanLoader from '@/components/ui/pacman-loader'
import { pollAiStream } from '@/lib/pollAiStream'
import type {
  AiSignalChatModalProps,
  AnalysisEntry,
  CompressionPoint,
  Conversation,
  Message,
  SignalConfig,
  ToolCallLogEntry,
  TokenUsage,
} from './ai-signal-chat/types'
import { getMetricLabel, getOperatorLabel } from './ai-signal-chat/helpers'
import { ChatArea } from './ai-signal-chat/ChatArea'
import { SignalCardsPanel } from './ai-signal-chat/SignalCardsPanel'

// Component implementation continues below
export default function AiSignalChatModal({
  open,
  onOpenChange,
  onCreateSignal,
  onCreatePool,
  onPreviewSignal,
  accounts,
  accountsLoading,
}: AiSignalChatModalProps) {
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
  const [allSignalConfigs, setAllSignalConfigs] = useState<SignalConfig[]>([])

  // Filter AI accounts
  const aiAccounts = accounts.filter(acc => acc.account_type === 'AI')

  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages])

  // Load conversations when modal opens and select default AI account
  useEffect(() => {
    if (open) {
      loadConversations()
      // Select first AI account by default
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
    fetch(`/api/signals/ai-conversations/${currentConversationId}/messages${params}`)
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data?.token_usage !== undefined) setTokenUsage(data.token_usage) })
      .catch(() => {})
  }, [selectedAccountId])

  const loadConversations = async () => {
    setLoadingConversations(true)
    try {
      const response = await fetch('/api/signals/ai-conversations')
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
      const response = await fetch(`/api/signals/ai-conversations/${conversationId}/messages${params}`)
      if (response.ok) {
        const data = await response.json()
        const mappedMessages = (data.messages || []).map((m: any) => {
          // Handle both old format {type, name, arguments, result(object)} and new format {tool, args, result(string)}
          const rawLog = m.tool_calls_log || []
          const toolCalls = rawLog
            .filter((e: any) => e.tool || e.type === 'tool_call')
            .map((e: any) => ({
              tool: e.tool || e.name || 'unknown',
              args: e.args || e.arguments || {},
              result: typeof e.result === 'string' ? e.result : JSON.stringify(e.result || '')
            }))
          return {
            ...m,
            toolCallsLog: toolCalls,
            reasoningSnapshot: m.reasoning_snapshot || null,
            isInterrupted: m.is_complete === false,
          }
        })
        setMessages(mappedMessages)
        setCompressionPoints(data.compression_points || [])
        setTokenUsage(data.token_usage || null)
        // Collect all signal configs from messages
        const configs: SignalConfig[] = []
        ;(data.messages || []).forEach((m: Message) => {
          if (m.role === 'assistant' && m.signal_configs) {
            configs.push(...m.signal_configs)
          }
        })
        setAllSignalConfigs(configs)
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
      const response = await fetch('/api/signals/ai-chat-stream', {
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
      let finalSignalConfigs: SignalConfig[] = []
      let finalConversationId: number | null = null
      let finalMessageId: number | null = null

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
              if (updates.signalConfigs) finalSignalConfigs = updates.signalConfigs
              if (updates.conversationId) finalConversationId = updates.conversationId
              if (updates.messageId) finalMessageId = updates.messageId
            })
          },
          onTaskLost: () => {
            // Task buffer expired — reload conversation to get final result
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
                  if (updates.signalConfigs) finalSignalConfigs = updates.signalConfigs
                  if (updates.conversationId) finalConversationId = updates.conversationId
                  if (updates.messageId) finalMessageId = updates.messageId
                })
              } catch {}
              currentEventType = ''
            }
          }
        }
      }

      // Finalize the message
      setMessages(prev => prev.map(m =>
        m.id === tempAssistantMsgId
          ? { ...m, content: finalContent, signal_configs: finalSignalConfigs, isStreaming: false, statusText: undefined }
          : m
      ))
      if (finalSignalConfigs.length > 0) {
        setAllSignalConfigs(prev => [...prev, ...finalSignalConfigs])
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
    onUpdate: (updates: { content?: string; signalConfigs?: SignalConfig[]; conversationId?: number; messageId?: number }) => void
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
      const reasoning = data.content as string || ''
      const entry: AnalysisEntry = { type: 'reasoning', content: reasoning }
      setMessages(prev => prev.map(m =>
        m.id === msgId ? {
          ...m,
          statusText: `Thinking: ${reasoning.slice(0, 80)}...`,
          analysisLog: [...(m.analysisLog || []), entry]
        } : m
      ))
    } else if (eventType === 'content') {
      const content = data.content as string
      onUpdate({ content })
      setMessages(prev => prev.map(m =>
        m.id === msgId ? { ...m, content, statusText: undefined } : m
      ))
    } else if (eventType === 'signal_config') {
      const config = data.config as SignalConfig
      if (config) {
        onUpdate({ signalConfigs: [config] })
      }
    } else if (eventType === 'done') {
      const content = data.content as string
      const signalConfigs = data.signal_configs as SignalConfig[]
      onUpdate({
        conversationId: data.conversation_id as number,
        messageId: data.message_id as number,
        content: content,
        signalConfigs: signalConfigs,
      })
      if (data.compression_points) setCompressionPoints(data.compression_points as CompressionPoint[])
      // Convert streaming analysisLog to stored formats for immediate display
      // Prefer backend done event data over local conversion
      setMessages(prev => prev.map(m => {
        if (m.id !== msgId) return m
        const tcLog = data.tool_calls_log as ToolCallLogEntry[] | null
        const rSnap = data.reasoning_snapshot as string | null
        if (tcLog || rSnap) {
          return { ...m, isStreaming: false, statusText: undefined, toolCallsLog: tcLog || [], reasoningSnapshot: rSnap }
        }
        // Fallback: convert from streaming analysisLog
        const log = m.analysisLog || []
        const toolCallsLog = log
          .filter(e => e.type === 'tool_call')
          .map(e => ({
            tool: e.name || 'unknown',
            args: e.arguments || {},
            result: typeof e.result === 'string' ? e.result : JSON.stringify(e.result || '')
          }))
        const reasoningParts = log.filter(e => e.type === 'reasoning').map(e => e.content || '')
        const reasoningSnapshot = reasoningParts.length > 0 ? reasoningParts.join('\n\n---\n\n') : null
        return { ...m, isStreaming: false, statusText: undefined, toolCallsLog, reasoningSnapshot }
      }))
    } else if (eventType === 'error') {
      toast.error(data.message as string || 'AI generation failed')
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
      const entry: AnalysisEntry = {
        type: 'tool_call',
        name: data.name as string,
        arguments: data.arguments as Record<string, unknown>
      }
      setMessages(prev => prev.map(m =>
        m.id === msgId ? {
          ...m,
          statusText: `Calling ${data.name}...`,
          analysisLog: [...(m.analysisLog || []), entry]
        } : m
      ))
    } else if (eventType === 'tool_result') {
      const entry: AnalysisEntry = {
        type: 'tool_result',
        name: data.name as string,
        result: data.result as Record<string, unknown>
      }
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
    setAllSignalConfigs([])
    setTokenUsage(null)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="w-[95vw] max-w-[1400px] h-[85vh] flex flex-col p-0"
        onInteractOutside={(e) => e.preventDefault()}
      >
        <DialogHeader className="px-6 py-4 border-b">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <DialogTitle>{t('signals.aiGenerator.title', 'AI Signal Generator')}</DialogTitle>
              <span className="text-xs text-muted-foreground">
                {t('signals.aiGenerator.subtitle', '(Requires Function Call support to invoke analysis tools. Reasoning models work best.)')}
              </span>
            </div>
            {(loadingConversations || accountsLoading) && <PacmanLoader className="w-8 h-4" />}
          </div>
          <div className="flex items-center gap-4 mt-4">
            <div className="flex-1">
              <label className="text-xs text-muted-foreground mb-1 block">{t('signals.aiGenerator.aiTrader', 'AI Trader')}</label>
              <Select
                value={selectedAccountId?.toString()}
                onValueChange={(val) => setSelectedAccountId(parseInt(val))}
                disabled={accountsLoading}
              >
                <SelectTrigger>
                  <SelectValue placeholder={accountsLoading ? t('signals.aiGenerator.loading', 'Loading...') : t('signals.aiGenerator.selectAiTrader', 'Select AI Trader')} />
                </SelectTrigger>
                <SelectContent>
                  {aiAccounts.map(acc => (
                    <SelectItem key={acc.id} value={acc.id.toString()}>
                      {acc.name} ({acc.model})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex-1">
              <label className="text-xs text-muted-foreground mb-1 block">{t('signals.aiGenerator.conversation', 'Conversation')}</label>
              <div className="flex gap-2">
                <Select
                  value={currentConversationId?.toString() || 'new'}
                  onValueChange={(val) => {
                    if (val === 'new') startNewConversation()
                    else setCurrentConversationId(parseInt(val))
                  }}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t('signals.aiGenerator.newConversation', 'New Conversation')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="new">{t('signals.aiGenerator.newConversation', 'New Conversation')}</SelectItem>
                    {conversations.map(conv => (
                      <SelectItem key={conv.id} value={conv.id.toString()}>
                        {conv.title}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button variant="outline" size="sm" onClick={startNewConversation}>New</Button>
              </div>
            </div>
          </div>
        </DialogHeader>

        <div className="flex-1 flex overflow-hidden">
          {/* Left: Chat Area (45%) */}
          <ChatArea
            messages={messages}
            compressionPoints={compressionPoints}
            tokenUsage={tokenUsage}
            userInput={userInput}
            setUserInput={setUserInput}
            loading={loading}
            sendMessage={sendMessage}
            messagesEndRef={messagesEndRef}
            hasAccount={!!selectedAccountId}
            t={t}
          />

          {/* Right: Signal Cards (55%) */}
          <SignalCardsPanel
            configs={allSignalConfigs}
            onPreview={onPreviewSignal}
            onCreate={onCreateSignal}
            onCreatePool={onCreatePool}
            getMetricLabel={getMetricLabel}
            getOperatorLabel={getOperatorLabel}
            t={t}
          />
        </div>
      </DialogContent>
    </Dialog>
  )
}
