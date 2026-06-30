import { useMemo, type RefObject } from 'react'
import { useTranslation } from 'react-i18next'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Wrench } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { CompressionPoint, Message } from './types'

interface ChatMessageListProps {
  messages: Message[]
  compressionPoints: CompressionPoint[]
  loading: boolean
  messagesEndRef: RefObject<HTMLDivElement>
  onContinue: () => void
}

export function ChatMessageList({
  messages,
  compressionPoints,
  loading,
  messagesEndRef,
  onContinue,
}: ChatMessageListProps) {
  const { t } = useTranslation()

  return (
    <div className="space-y-4">
      {messages.length === 0 && (
        <div className="text-center text-muted-foreground py-8">
          <p className="text-sm">{t('aiPrompt.startHint', 'Start by describing your trading strategy')}</p>
          <p className="text-xs mt-2">{t('aiPrompt.example', 'Example: "I want a trend-following strategy using MA crossovers"')}</p>
        </div>
      )}
      {/* Memoize message list rendering to prevent re-renders on input typing.
          Without this, every keystroke re-renders all messages (including expensive
          ReactMarkdown parsing), causing noticeable input lag with long conversations. */}
      {useMemo(() => messages.map((msg) => {
        const compressionPoint = compressionPoints.find(cp => cp.message_id === msg.id)
        return (
          <div key={msg.id}>
            <div
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[85%] rounded-lg p-3 ${
                  msg.role === 'user'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted'
                }`}
              >
            <div className={`text-xs font-semibold mb-1 ${msg.role === 'user' ? 'text-primary-foreground/70' : 'opacity-70'}`}>
              {msg.role === 'user' ? t('aiPrompt.you', 'You') : t('aiPrompt.aiAssistant', 'AI Assistant')}
              {msg.isStreaming && msg.statusText && (
                <span className="ml-2 text-primary animate-pulse">({msg.statusText})</span>
              )}
            </div>
            {/* Tool calls progress during streaming */}
            {msg.isStreaming && msg.toolCalls && msg.toolCalls.length > 0 && (
              <div className="mb-2 text-xs bg-background/50 rounded p-2 max-h-32 overflow-y-auto">
                {msg.toolCalls.slice(-5).map((entry, idx) => (
                  <div key={idx} className="mb-1 last:mb-0">
                    {entry.type === 'tool_call' && (
                      <span className="text-blue-500">→ {entry.name}</span>
                    )}
                    {entry.type === 'tool_result' && (
                      <span className="text-green-500">← {entry.name}: done</span>
                    )}
                    {entry.type === 'reasoning' && (
                      <span className="text-gray-500 italic">{(entry.content || '').slice(0, 100)}...</span>
                    )}
                  </div>
                ))}
              </div>
            )}
            {/* Tool calls log - above content, HyperAI style */}
            {!msg.isStreaming && msg.toolCallsLog && msg.toolCallsLog.length > 0 && (
              <details className="mb-3 text-xs border rounded-md">
                <summary className="px-3 py-2 cursor-pointer bg-muted/50 hover:bg-muted font-medium flex items-center gap-1">
                  <Wrench className="w-3 h-3" />
                  {t('aiPrompt.toolCallsDetail', 'Tool calls ({{count}})').replace('{{count}}', msg.toolCallsLog.length.toString())}
                </summary>
                <div className="p-3 space-y-3 max-h-96 overflow-y-auto">
                  {msg.toolCallsLog.map((entry, idx) => {
                    const resultStr = typeof entry.result === 'string' ? entry.result : JSON.stringify(entry.result || '')
                    return (
                    <div key={idx} className="border-b pb-2 last:border-b-0 last:pb-0">
                      <div className="font-medium text-blue-600 dark:text-blue-400 mb-1">
                        Round {idx + 1}: {entry.tool}
                      </div>
                      {entry.args && Object.keys(entry.args).length > 0 && (
                        <div className="mb-1">
                          {Object.entries(entry.args).map(([key, value]) => (
                            <div key={key} className="ml-2">
                              {key === 'prompt_text' ? (
                                <div>
                                  <span className="text-muted-foreground">prompt_text:</span>
                                  <pre className="mt-1 p-2 bg-muted rounded text-xs overflow-x-auto max-h-48 overflow-y-auto">
                                    <code>{String(value)}</code>
                                  </pre>
                                </div>
                              ) : (
                                <span className="text-muted-foreground">{key}: {JSON.stringify(value)}</span>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                      <div className="ml-2 text-green-600 dark:text-green-400">
                        Result: {resultStr.length > 200 ? resultStr.slice(0, 200) + '...' : resultStr}
                      </div>
                    </div>
                    )
                  })}
                </div>
              </details>
            )}
            {/* Reasoning snapshot - above content, HyperAI style */}
            {!msg.isStreaming && msg.reasoningSnapshot && (
              <details className="mb-3 text-xs border rounded-md">
                <summary className="px-3 py-2 cursor-pointer bg-muted/50 hover:bg-muted font-medium">
                  {t('aiPrompt.reasoningProcess', 'Reasoning process')}
                </summary>
                <div className="p-3 max-h-96 overflow-y-auto">
                  <pre className="whitespace-pre-wrap text-muted-foreground">{msg.reasoningSnapshot}</pre>
                </div>
              </details>
            )}
            <div className={`text-sm prose prose-sm max-w-none ${msg.role === 'user' ? 'prose-invert' : 'dark:prose-invert'}`}>
              {msg.content ? (
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    pre: ({ node, children, ...props }) => {
                      // Check if this pre contains a prompt code block
                      const child = node?.children?.[0] as { properties?: { className?: string[] } } | undefined
                      const className = child?.properties?.className || []
                      if (className.includes('language-prompt')) {
                        return null
                      }
                      return <pre {...props}>{children}</pre>
                    },
                    code: ({ node, inline, className, children, ...props }) => {
                      const match = /language-(\w+)/.exec(className || '')
                      if (!inline && match?.[1] === 'prompt') {
                        return null
                      }
                      return <code className={className} {...props}>{children}</code>
                    },
                  }}
                >
                  {msg.content}
                </ReactMarkdown>
              ) : msg.isStreaming ? (
                <span className="text-muted-foreground italic">{t('aiPrompt.generating', 'Generating...')}</span>
              ) : null}
            </div>
            {/* Continue button for interrupted messages */}
            {msg.isInterrupted && !loading && (
              <div className="mt-3 pt-3 border-t border-border/50">
                <div className="flex items-center gap-2 text-xs text-amber-600 dark:text-amber-400 mb-2">
                  <span>⚠️</span>
                  <span>{t('aiPrompt.interruptedAt', 'Interrupted at round {{round}}').replace('{{round}}', String(msg.interruptedRound || '?'))}</span>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={onContinue}
                  className="text-xs"
                >
                  {t('aiPrompt.continueButton', 'Continue')}
                </Button>
              </div>
            )}
          </div>
        </div>
        {compressionPoint && (
          <div className="flex items-center gap-3 my-4 text-xs text-muted-foreground">
            <div className="flex-1 border-t border-dashed border-muted-foreground/30" />
            <span className="px-2 py-1 bg-muted rounded text-[10px]">
              {t('aiPrompt.compressionPoint', 'Context compressed')}
            </span>
            <div className="flex-1 border-t border-dashed border-muted-foreground/30" />
          </div>
        )}
      </div>
    )
  }), [messages, compressionPoints, loading])}
      <div ref={messagesEndRef} />
    </div>
  )
}
