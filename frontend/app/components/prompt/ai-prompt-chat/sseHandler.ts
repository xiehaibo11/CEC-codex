import type { Dispatch, SetStateAction } from 'react'
import type { CompressionPoint, Message, ToolCallLogEntry } from './types'

interface SSEEventHandlerDeps {
  setMessages: Dispatch<SetStateAction<Message[]>>
  setCompressionPoints: Dispatch<SetStateAction<CompressionPoint[]>>
  t: (key: string, fallback?: string) => string
}

export type SSEEventUpdate = {
  content?: string
  promptResult?: string | null
  conversationId?: number
  error?: boolean
}

export type SSEEventHandler = (
  eventType: string,
  data: Record<string, unknown>,
  msgId: number,
  onUpdate: (updates: SSEEventUpdate) => void
) => void

export function createSSEEventHandler({
  setMessages,
  setCompressionPoints,
  t,
}: SSEEventHandlerDeps): SSEEventHandler {
  return (eventType, data, msgId, onUpdate) => {

    if (eventType === 'conversation_created') {
      onUpdate({ conversationId: data.conversation_id as number })
      setMessages(prev => prev.map(m =>
        m.id === msgId ? { ...m, statusText: t('aiPrompt.thinking', 'Thinking...') } : m
      ))
    } else if (eventType === 'tool_round') {
      setMessages(prev => prev.map(m =>
        m.id === msgId ? { ...m, statusText: `${t('aiPrompt.toolRound', 'Tool round')} ${data.round}/${data.max}` } : m
      ))
    } else if (eventType === 'retry') {
      setMessages(prev => prev.map(m =>
        m.id === msgId ? { ...m, statusText: `${t('aiPrompt.retrying', 'Retrying')} (${data.attempt}/${data.max_retries})` } : m
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
          statusText: `${t('aiPrompt.calling', 'Calling')} ${data.name}...`,
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
    } else if (eventType === 'suggest_apply') {
      const promptResult = data.prompt as string
      onUpdate({ promptResult })
      setMessages(prev => prev.map(m =>
        m.id === msgId ? { ...m, promptResult } : m
      ))
    } else if (eventType === 'content') {
      const content = data.content as string
      onUpdate({ content })
      setMessages(prev => prev.map(m =>
        m.id === msgId ? { ...m, content, statusText: '' } : m
      ))
    } else if (eventType === 'done') {
      const content = data.content as string
      if (content) onUpdate({ content })
      if (data.conversation_id) onUpdate({ conversationId: data.conversation_id as number })
      if (data.prompt_result) onUpdate({ promptResult: data.prompt_result as string })
      if (data.compression_points) setCompressionPoints(data.compression_points as CompressionPoint[])
      // Convert streaming toolCalls to stored formats for immediate display after completion
      setMessages(prev => prev.map(m => {
        if (m.id !== msgId) return m
        const tcLog = data.tool_calls_log as ToolCallLogEntry[] | null
        const rSnap = data.reasoning_snapshot as string | null
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
      onUpdate({ error: true })
      setMessages(prev => prev.map(m =>
        m.id === msgId ? { ...m, content: data.content as string, isStreaming: false } : m
      ))
    } else if (eventType === 'interrupted') {
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
}
