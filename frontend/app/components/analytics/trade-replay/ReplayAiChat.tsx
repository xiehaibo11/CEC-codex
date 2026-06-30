import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { useTranslation } from 'react-i18next'
import rehypeRaw from 'rehype-raw'
import remarkGfm from 'remark-gfm'
import { Loader2, Send } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import type { AnalysisEntry, ChatMessage, ReplayAiChatProps } from './types'

export function ReplayAiChat({ tradeData, selectedAccountId }: ReplayAiChatProps) {
  const { t } = useTranslation()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async () => {
    if (!input.trim() || loading || !selectedAccountId) return

    const userMessage = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: userMessage }])
    setLoading(true)

    try {
      // Build context about the trade with explicit account and environment info
      const tradeContext = `[IMPORTANT: This is a specific trade analysis. DO NOT ask for environment or account - they are already known.]
[OUTPUT FORMAT: Please provide analysis in plain text only. Do NOT output JSON formatted diagnosis results or suggestions. Keep the response concise and readable.]

Trade #${tradeData.trade.id} ${tradeData.trade.symbol}:
- Account ID: ${tradeData.trade.account_id}
- Environment: ${tradeData.trade.hyperliquid_environment || 'mainnet'}
- Wallet: ${tradeData.trade.wallet_address}
- Entry: ${tradeData.entry_decision?.operation.toUpperCase()} at ${tradeData.summary.entry_time ? new Date(tradeData.summary.entry_time + 'Z').toLocaleString() : 'N/A'}
- Exit: ${tradeData.exit_decision?.exit_type || 'N/A'} at ${tradeData.summary.exit_time ? new Date(tradeData.summary.exit_time + 'Z').toLocaleString() : 'N/A'}
- Duration: ${tradeData.summary.hold_duration || 'N/A'}
- PnL: $${tradeData.summary.pnl.toFixed(2)}
- Entry Reason: ${tradeData.entry_decision?.reason || 'N/A'}
- Exit Reason: ${tradeData.exit_decision?.reason || 'N/A'}`

      const response = await fetch('/api/analytics/ai-attribution/chat-stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          accountId: selectedAccountId,
          userMessage: `[Trade Context]\n${tradeContext}\n\n[User Question]\n${userMessage}`,
          conversationId: null,
        }),
      })

      if (!response.ok) throw new Error('Failed to send message')

      // Add streaming assistant message
      setMessages(prev => [...prev, { role: 'assistant', content: '', isStreaming: true, analysisLog: [] }])

      let finalContent = ''

      // Check if response is JSON (background task mode) or SSE stream
      const contentType = response.headers.get('content-type') || ''
      if (contentType.includes('application/json')) {
        // Background task mode: poll for results
        const taskData = await response.json()
        const taskId = taskData.task_id

        const { pollAiStream } = await import('@/lib/pollAiStream')
        await pollAiStream(taskId, {
          onChunk: (chunk) => {
            const eventType = chunk.event_type
            const data = chunk.data

            if (eventType === 'reasoning') {
              const entry: AnalysisEntry = { type: 'reasoning', content: data.content }
              setMessages(prev => prev.map((m, i) =>
                i === prev.length - 1 ? { ...m, statusText: 'Thinking...', analysisLog: [...(m.analysisLog || []), entry] } : m
              ))
            } else if (eventType === 'tool_call') {
              const entry: AnalysisEntry = { type: 'tool_call', name: data.name }
              setMessages(prev => prev.map((m, i) =>
                i === prev.length - 1 ? { ...m, statusText: `Calling ${data.name}...`, analysisLog: [...(m.analysisLog || []), entry] } : m
              ))
            } else if (eventType === 'tool_result') {
              const entry: AnalysisEntry = { type: 'tool_result', name: data.name }
              setMessages(prev => prev.map((m, i) =>
                i === prev.length - 1 ? { ...m, statusText: `Got result from ${data.name}`, analysisLog: [...(m.analysisLog || []), entry] } : m
              ))
            } else if (eventType === 'content' || eventType === 'done') {
              finalContent = data.content || ''
              setMessages(prev => prev.map((m, i) =>
                i === prev.length - 1 ? { ...m, content: finalContent, statusText: undefined } : m
              ))
            }
          },
          onTaskLost: () => {
            setMessages(prev => prev.map((m, i) =>
              i === prev.length - 1 ? { ...m, content: 'Connection lost. Please try again.', isStreaming: false } : m
            ))
          },
        })

        // Mark streaming complete
        setMessages(prev => prev.map((m, i) =>
          i === prev.length - 1 ? { ...m, content: finalContent, isStreaming: false, statusText: undefined } : m
        ))
      } else {
        // SSE stream mode (legacy fallback)
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

                if (currentEventType === 'reasoning') {
                  const entry: AnalysisEntry = { type: 'reasoning', content: data.content }
                  setMessages(prev => prev.map((m, i) =>
                    i === prev.length - 1 ? { ...m, statusText: 'Thinking...', analysisLog: [...(m.analysisLog || []), entry] } : m
                  ))
                } else if (currentEventType === 'tool_call') {
                  const entry: AnalysisEntry = { type: 'tool_call', name: data.name }
                  setMessages(prev => prev.map((m, i) =>
                    i === prev.length - 1 ? { ...m, statusText: `Calling ${data.name}...`, analysisLog: [...(m.analysisLog || []), entry] } : m
                  ))
                } else if (currentEventType === 'tool_result') {
                  const entry: AnalysisEntry = { type: 'tool_result', name: data.name }
                  setMessages(prev => prev.map((m, i) =>
                    i === prev.length - 1 ? { ...m, statusText: `Got result from ${data.name}`, analysisLog: [...(m.analysisLog || []), entry] } : m
                  ))
                } else if (currentEventType === 'content' || data.content) {
                  setMessages(prev => prev.map((m, i) =>
                    i === prev.length - 1 ? { ...m, content: data.content, statusText: undefined } : m
                  ))
                }

                currentEventType = ''
              } catch {
                // Ignore parse errors
              }
            }
          }
        }

        // Mark streaming complete
        setMessages(prev => prev.map((m, i) =>
          i === prev.length - 1 ? { ...m, isStreaming: false, statusText: undefined } : m
        ))
      }
    } catch (err) {
      setMessages(prev => [...prev, { role: 'assistant', content: `Error: ${err instanceof Error ? err.message : 'Unknown error'}` }])
    } finally {
      setLoading(false)
    }
  }

  const suggestedQuestions = [
    t('attribution.replay.suggestWhy', 'Why did this trade lose/win?'),
    t('attribution.replay.suggestImprove', 'How could I improve?'),
  ]

  return (
    <div className="h-full flex flex-col overflow-hidden">
      <ScrollArea className="flex-1 p-4">
        <div className="space-y-4">
          {messages.length === 0 ? (
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground mb-3">
                {t('attribution.replay.askAboutTrade', 'Ask questions about this trade:')}
              </p>
              {suggestedQuestions.map((q, i) => (
                <Button
                  key={i}
                  variant="outline"
                  size="sm"
                  className="w-full justify-start text-left h-auto py-2 px-3"
                  onClick={() => setInput(q)}
                >
                  {q}
                </Button>
              ))}
            </div>
          ) : (
            messages.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[85%] rounded-lg p-3 ${
                  msg.role === 'user' ? 'bg-primary text-white' : 'bg-muted'
                }`}>
                  <div className={`text-xs font-semibold mb-1 ${msg.role === 'user' ? 'text-white/70' : 'opacity-70'}`}>
                    {msg.role === 'user' ? t('attribution.aiAnalysis.you', 'You') : t('attribution.aiAnalysis.aiAssistant', 'AI Assistant')}
                    {msg.isStreaming && msg.statusText && (
                      <span className="ml-2 text-primary animate-pulse">({msg.statusText})</span>
                    )}
                  </div>
                  {msg.analysisLog && msg.analysisLog.length > 0 && (
                    <details className="mb-2" open={msg.isStreaming}>
                      <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground">
                        {t('attribution.aiAnalysis.analysisProcess', 'Analysis Process')} ({msg.analysisLog.length} {t('attribution.aiAnalysis.steps', 'steps')})
                      </summary>
                      <div className="mt-1 text-xs bg-background/50 rounded p-2 max-h-32 overflow-y-auto">
                        {(msg.isStreaming ? msg.analysisLog.slice(-5) : msg.analysisLog).map((entry, idx) => (
                          <div key={idx} className="mb-1 last:mb-0">
                            {entry.type === 'tool_call' && <span className="text-blue-500">→ {entry.name}</span>}
                            {entry.type === 'tool_result' && <span className="text-green-500">← {entry.name}: done</span>}
                            {entry.type === 'reasoning' && <span className="text-gray-500 italic">{(entry.content || '').slice(0, 100)}...</span>}
                          </div>
                        ))}
                      </div>
                    </details>
                  )}
                  <div className={`text-sm prose prose-sm max-w-none ${
                    msg.role === 'user' ? 'prose-invert text-white' : 'dark:prose-invert'
                  } [&_table]:w-full [&_table]:border-collapse [&_th]:border [&_th]:border-border [&_th]:p-2 [&_th]:bg-muted [&_td]:border [&_td]:border-border [&_td]:p-2`}>
                    {msg.content ? (
                      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>{msg.content}</ReactMarkdown>
                    ) : msg.isStreaming ? (
                      <span className="text-muted-foreground italic">{t('attribution.aiAnalysis.analyzing', 'Analyzing...')}</span>
                    ) : null}
                  </div>
                </div>
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>
      </ScrollArea>
      <div className="px-3 pb-3 pt-2 flex-shrink-0">
        <div className="flex gap-2 items-center">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), sendMessage())}
            placeholder={t('attribution.replay.typeQuestion', 'Type a question...')}
            disabled={loading || !selectedAccountId}
            className="text-sm rounded-xl"
          />
          <Button size="icon" onClick={sendMessage} disabled={loading || !input.trim() || !selectedAccountId} className="rounded-full h-8 w-8 shrink-0">
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          </Button>
        </div>
      </div>
    </div>
  )
}
