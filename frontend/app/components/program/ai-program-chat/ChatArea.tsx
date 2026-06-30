import { useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import rehypeRaw from 'rehype-raw'
import remarkGfm from 'remark-gfm'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Wrench, Send, Loader2 } from 'lucide-react'
import { Message, CompressionPoint, TokenUsage } from './types'

// Chat Area Component
export function ChatArea({
  messages, compressionPoints, tokenUsage, userInput, setUserInput, loading, sendMessage, messagesEndRef, hasAccount, t
}: {
  messages: Message[]
  compressionPoints: CompressionPoint[]
  tokenUsage: TokenUsage | null
  userInput: string
  setUserInput: (v: string) => void
  loading: boolean
  sendMessage: () => void
  messagesEndRef: React.RefObject<HTMLDivElement>
  hasAccount: boolean
  t: (key: string, fallback?: string) => string
}) {
  return (
    <div className="w-[45%] flex flex-col border-r">
      <ScrollArea className="flex-1 p-4">
        <div className="space-y-4">
          {messages.length === 0 && (
            <div className="text-center text-muted-foreground py-8">
              <p className="text-sm">{t('program.aiChat.describeProgram')}</p>
              <p className="text-xs mt-2">{t('program.aiChat.example')}</p>
            </div>
          )}
          {/* Memoize message list rendering to prevent re-renders on input typing.
              Without this, every keystroke re-renders all messages (including expensive
              ReactMarkdown parsing), causing noticeable input lag with long conversations. */}
          {useMemo(() => messages.map((msg) => {
            const compressionPoint = compressionPoints.find(cp => cp.message_id === msg.id)
            return (
              <div key={msg.id}>
                <div className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[85%] rounded-lg p-3 ${
                    msg.role === 'user' ? 'bg-primary text-white' : 'bg-muted'
                  }`}>
                <div className={`text-xs font-semibold mb-1 ${msg.role === 'user' ? 'text-white/70' : 'opacity-70'}`}>
                  {msg.role === 'user' ? t('program.aiChat.you') : t('program.aiChat.aiAssistant')}
                  {msg.isStreaming && msg.statusText && (
                    <span className="ml-2 text-primary animate-pulse">({msg.statusText})</span>
                  )}
                </div>
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
                      {t('program.aiChat.toolCallsDetail', { count: msg.toolCallsLog.length })}
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
                                  {key === 'code' ? (
                                    <div>
                                      <span className="text-muted-foreground">code:</span>
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
                      {t('program.aiChat.reasoningProcess', 'Reasoning process')}
                    </summary>
                    <div className="p-3 max-h-96 overflow-y-auto">
                      <pre className="whitespace-pre-wrap text-muted-foreground">{msg.reasoningSnapshot}</pre>
                    </div>
                  </details>
                )}
                <div className={`text-sm prose prose-sm max-w-none overflow-x-auto ${
                  msg.role === 'user' ? 'prose-invert text-white' : 'dark:prose-invert'
                } [&_table]:w-full [&_table]:table-fixed [&_th]:text-left [&_td]:break-words`}>
                  {msg.content ? (
                    <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>{msg.content}</ReactMarkdown>
                  ) : msg.isStreaming ? (
                    <span className="text-muted-foreground italic">{t('program.aiChat.generating')}</span>
                  ) : null}
                </div>
                {/* Show continue button for interrupted messages */}
                {msg.isInterrupted && !loading && (
                  <div className="mt-3 pt-3 border-t border-border/50">
                    <div className="flex items-center gap-2 text-xs text-amber-600 dark:text-amber-400 mb-2">
                      <span>⚠️</span>
                      <span>{t('program.aiChat.interruptedAt', { round: msg.interruptedRound })}</span>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setUserInput(t('program.aiChat.continueMessage'))
                        setTimeout(() => sendMessage(), 100)
                      }}
                      className="text-xs"
                    >
                      {t('program.aiChat.continueButton')}
                    </Button>
                  </div>
                )}
              </div>
            </div>
            {compressionPoint && (
              <div className="flex items-center gap-3 my-4 text-xs text-muted-foreground">
                <div className="flex-1 border-t border-dashed border-muted-foreground/30" />
                <span className="px-2 py-1 bg-muted rounded text-[10px]">
                  {t('program.aiChat.compressionPoint', 'Context compressed')}
                </span>
                <div className="flex-1 border-t border-dashed border-muted-foreground/30" />
              </div>
            )}
          </div>
        )
      }), [messages, compressionPoints, loading])}
          <div ref={messagesEndRef} />
        </div>
      </ScrollArea>
      <div className="px-4 pb-4 pt-2">
        <div className="relative">
          <textarea
            placeholder={t('program.aiChat.placeholder')}
            value={userInput}
            onChange={(e) => setUserInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault()
                sendMessage()
              }
            }}
            disabled={loading || !hasAccount}
            className="w-full min-h-[80px] max-h-[200px] rounded-xl border border-input bg-transparent px-4 py-3 pb-12 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 resize-y"
            rows={3}
          />
          <div className="absolute bottom-3 right-3 flex items-center gap-2">
            {tokenUsage?.show_warning && (
              <p className="text-xs text-amber-500">
                {t('program.contextWarning', 'Context remaining: {{percent}}% · Compressing soon', { percent: Math.max(0, Math.round((1 - tokenUsage.usage_ratio) * 100)) })}
              </p>
            )}
            <Button onClick={sendMessage} disabled={loading || !userInput.trim() || !hasAccount} size="icon" className="rounded-full h-8 w-8 shrink-0">
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
