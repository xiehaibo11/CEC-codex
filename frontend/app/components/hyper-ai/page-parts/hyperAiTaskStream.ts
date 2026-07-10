import type { Dispatch, RefObject, SetStateAction } from 'react'
import { pollAiStream } from '@/lib/pollAiStream'
import type {
  CompressionPoint,
  Message,
  TokenUsage,
  ToolCallEntry,
  ToolCallLogEntry,
} from './types'

interface PollHyperAiTaskResponseArgs {
  taskId: string
  convId: number
  currentConvId: number | null
  t: any
  messagesEndRef: RefObject<HTMLDivElement | null>
  fetchMessages: (convId: number) => void | Promise<void>
  fetchConversations: () => void | Promise<void>
  setCurrentConvId: Dispatch<SetStateAction<number | null>>
  setMessages: Dispatch<SetStateAction<Message[]>>
  setStreamingContent: Dispatch<SetStateAction<string>>
  setTokenUsage: Dispatch<SetStateAction<TokenUsage | null>>
  setCompressionPoints: Dispatch<SetStateAction<CompressionPoint[]>>
  setActiveSkill: Dispatch<SetStateAction<string | null>>
  setSending: Dispatch<SetStateAction<boolean>>
}

export async function pollHyperAiTaskResponse({
  taskId,
  convId,
  currentConvId,
  t,
  messagesEndRef,
  fetchMessages,
  fetchConversations,
  setCurrentConvId,
  setMessages,
  setStreamingContent,
  setTokenUsage,
  setCompressionPoints,
  setActiveSkill,
  setSending,
}: PollHyperAiTaskResponseArgs) {
  let content = ''
  let reasoning = ''
  let activeConvId = convId
  let toolCalls: ToolCallEntry[] = []
  let doneToolCallsLog: ToolCallLogEntry[] | null = null
  let doneReasoningSnapshot: string | null = null
  let isInterrupted = false
  let interruptedRound = 0

  if (!currentConvId && convId) {
    setCurrentConvId(convId)
  }

  try {
    const pollResult = await pollAiStream(taskId, {
      interval: 300,
      onChunk: (chunk) => {
        const eventType = chunk.event_type
        const data = chunk.data

        if (eventType === 'content' && data.text) {
          content += data.text
          setStreamingContent(content)
          setMessages(prev => prev.map((m, idx) =>
            idx === prev.length - 1 && m.isStreaming
              ? { ...m, content, statusText: '' }
              : m
          ))
        } else if (eventType === 'reasoning' && data.content) {
          reasoning += data.content
          const reasoningText = data.content as string
          setMessages(prev => prev.map((m, idx) =>
            idx === prev.length - 1 && m.isStreaming
              ? {
                  ...m,
                  statusText: `Thinking: ${reasoningText.slice(0, 80)}...`,
                  toolCalls: [...(m.toolCalls || []), { type: 'reasoning', content: reasoningText }],
                }
              : m
          ))
        } else if (eventType === 'tool_call' && data.name) {
          toolCalls.push({ type: 'tool_call', name: data.name, args: data.args || {} })
          setMessages(prev => prev.map((m, idx) =>
            idx === prev.length - 1 && m.isStreaming
              ? {
                  ...m,
                  statusText: `${t('hyperAi.calling', 'Calling')} ${data.name}...`,
                  toolCalls: [...(m.toolCalls || []), { type: 'tool_call', name: data.name, args: data.args }]
                }
              : m
          ))
        } else if (eventType === 'tool_result' && data.name) {
          toolCalls.push({ type: 'tool_result', name: data.name, result: data.result })
          setMessages(prev => prev.map((m, idx) =>
            idx === prev.length - 1 && m.isStreaming
              ? {
                  ...m,
                  statusText: '',
                  toolCalls: [...(m.toolCalls || []), { type: 'tool_result', name: data.name, result: data.result }]
                }
              : m
          ))
        } else if (eventType === 'skill_loaded' && data.skill_name) {
          setActiveSkill(data.skill_name as string)
        } else if (eventType === 'conversation_rollover' && data.conversation_id) {
          // Context detection point hit: backend archived the old round and
          // continued this request in a fresh seeded conversation.
          activeConvId = data.conversation_id as number
          setCurrentConvId(activeConvId)
          fetchConversations()
          setMessages(prev => prev.map((m, idx) =>
            idx === prev.length - 1 && m.isStreaming
              ? { ...m, statusText: t('hyperAi.rollover', 'Context limit reached — continuing in a new round...') }
              : m
          ))
        } else if (eventType === 'subagent_progress') {
          const agent = data.subagent || 'Agent'
          let statusMsg = ''
          const progressEntry: any = { type: 'subagent_progress', subagent: agent, step: data.step }

          if (data.step === 'reasoning') {
            statusMsg = `${agent}: ${t('hyperAi.subagentProcessing', 'processing')}...`
            progressEntry.content = data.content || ''
          } else if (data.step === 'tool_call') {
            statusMsg = `${agent}: → ${data.tool || ''}`
            progressEntry.tool = data.tool || ''
          } else if (data.step === 'tool_result') {
            statusMsg = `${agent}: ← ${data.tool || ''}`
            progressEntry.tool = data.tool || ''
          } else if (data.step === 'tool_round') {
            const roundInfo = data.round && data.max_rounds ? ` ${data.round}/${data.max_rounds}` : (data.round ? ` ${data.round}` : '')
            statusMsg = `${agent}: ${t('hyperAi.subagentRound', 'round')}${roundInfo}...`
            progressEntry.round = data.round
            progressEntry.max_rounds = data.max_rounds
          } else {
            statusMsg = `${agent}: ${t('hyperAi.subagentProcessing', 'processing')}...`
          }

          setMessages(prev => prev.map((m, idx) =>
            idx === prev.length - 1 && m.isStreaming
              ? { ...m, statusText: statusMsg, toolCalls: [...(m.toolCalls || []), progressEntry] }
              : m
          ))
        } else if (eventType === 'retry') {
          const attempt = data.attempt || 2
          const maxRetries = data.max_retries || 3
          setMessages(prev => prev.map((m, idx) =>
            idx === prev.length - 1 && m.isStreaming
              ? { ...m, statusText: `${t('hyperAi.retrying', 'Retrying')} (${attempt}/${maxRetries})...` }
              : m
          ))
        } else if (eventType === 'confirmation_required') {
          const confirmationEntry: ToolCallEntry = {
            type: 'confirmation_required',
            taskId,
            confirmationId: data.confirmation_id,
            name: data.tool_name,
            args: data.args || {},
            description: data.description || '',
            status: 'pending',
          }
          setMessages(prev => prev.map((m, idx) =>
            idx === prev.length - 1 && m.isStreaming
              ? {
                  ...m,
                  statusText: t('hyperAi.confirmationRequired', 'Confirmation required'),
                  toolCalls: [...(m.toolCalls || []), confirmationEntry],
                }
              : m
          ))
          setTimeout(() => {
            messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
          }, 100)
        } else if (eventType === 'tool_error') {
          const errorEntry: ToolCallEntry = {
            type: 'tool_error',
            name: data.name,
            message: data.message || data.code || '',
            severity: data.severity || data.status,
          }
          setMessages(prev => prev.map((m, idx) =>
            idx === prev.length - 1 && m.isStreaming
              ? {
                  ...m,
                  statusText: data.message || t('hyperAi.toolWarning', 'Tool warning'),
                  toolCalls: [...(m.toolCalls || []), errorEntry],
                }
              : m
          ))
        } else if (eventType === 'interrupted') {
          isInterrupted = true
          interruptedRound = data.round || 0
          if (data.conversation_id) {
            setCurrentConvId(data.conversation_id)
          }
        } else if (eventType === 'error') {
          console.error('Stream error:', data.message)
        } else if (eventType === 'done') {
          if (data.content) content = data.content
          if (data.conversation_id) setCurrentConvId(data.conversation_id)
          if (data.token_usage) setTokenUsage(data.token_usage)
          if (data.compression_points) setCompressionPoints(data.compression_points)
          if (data.tool_calls_log) doneToolCallsLog = data.tool_calls_log
          if (data.reasoning_snapshot) doneReasoningSnapshot = data.reasoning_snapshot
        }
      },
      onTaskLost: () => {
        if (activeConvId) {
          fetchMessages(activeConvId)
        }
      },
    })

    if (pollResult.status === 'lost') {
      setSending(false)
      return
    }

    const localToolCallsLog = toolCalls.filter(tc => tc.type === 'tool_call' || tc.type === 'tool_result')
      .reduce((acc: ToolCallLogEntry[], tc) => {
        if (tc.type === 'tool_call' && tc.name) {
          acc.push({ tool: tc.name, args: tc.args || {}, result: '' })
        } else if (tc.type === 'tool_result' && tc.name && acc.length > 0) {
          const lastCall = acc[acc.length - 1]
          if (lastCall.tool === tc.name) {
            lastCall.result = tc.result || ''
          }
        }
        return acc
      }, [])
    const finalToolCallsLog = doneToolCallsLog || (localToolCallsLog.length > 0 ? localToolCallsLog : null)
    const finalReasoning = doneReasoningSnapshot || reasoning || undefined

    setMessages(prev => prev.map((m, idx) =>
      idx === prev.length - 1 && m.isStreaming
        ? {
            ...m,
            content: content || m.content,
            reasoning_snapshot: finalReasoning,
            tool_calls_log: finalToolCallsLog ? JSON.stringify(finalToolCallsLog) : undefined,
            isStreaming: false,
            statusText: undefined,
            toolCalls: undefined,
            isInterrupted,
            interruptedRound: isInterrupted ? interruptedRound : undefined,
            is_complete: !isInterrupted
          }
        : m
    ))
    setStreamingContent('')
    setSending(false)
    fetchConversations()
  } catch (e) {
    console.error('Polling error:', e)
    setMessages(prev => prev.map((m, idx) =>
      idx === prev.length - 1 && m.isStreaming
        ? { ...m, isStreaming: false, content: content || t('hyperAi.connectionLost', 'Connection lost') }
        : m
    ))
    setSending(false)
  }
}
