import { useEffect, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { ArrowRight, Bot, Loader2, Send, User } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { pollAiStream } from '@/lib/pollAiStream'
import { CompletionStep } from './CompletionStep'
import type { ChatMessage } from './types'

interface ChatStepProps {
  onSkip: () => void
  onComplete: () => void
}

function stripProfileMarkers(content: string): string {
  return content.replace(/\[PROFILE_DATA\][\s\S]*?\[COMPLETE\]/g, '').trim()
}

export function ChatStep({ onSkip, onComplete }: ChatStepProps) {
  const { t, i18n } = useTranslation()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [conversationId, setConversationId] = useState<number | null>(null)
  const [streamingContent, setStreamingContent] = useState('')
  const [onboardingComplete, setOnboardingComplete] = useState(false)
  const [showEnterButton, setShowEnterButton] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const initializedRef = useRef(false)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

  useEffect(() => {
    if (!initializedRef.current) {
      initializedRef.current = true
      void sendGreeting()
    }
  }, [])

  const sendGreeting = async () => {
    setLoading(true)
    setStreamingContent('')

    try {
      const lang = navigator.language.toLowerCase().startsWith('zh') ? 'zh' : 'en'

      const res = await fetch('/api/hyper-ai/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: '__GREETING__',
          conversation_id: null,
          mode: 'onboarding',
          lang,
        }),
      })

      if (!res.ok) throw new Error('Failed to start chat')

      const data = await res.json()
      setConversationId(data.conversation_id)
      await pollStreamResponse(data.task_id)
    } catch (e) {
      console.error('Greeting error:', e)
      setMessages([{
        role: 'assistant',
        content: t(
          'hyperAi.onboarding.defaultGreeting',
          'Hello! I\'m Hyper AI. Before we begin, I\'d like to learn about your trading background. Do you have experience with cryptocurrency trading?'
        ),
      }])
    } finally {
      setLoading(false)
      textareaRef.current?.focus()
    }
  }

  const sendMessage = async (text: string) => {
    if (!text.trim() || loading) return

    const userMessage: ChatMessage = { role: 'user', content: text }
    setMessages(prev => [...prev, userMessage])
    setInput('')
    setLoading(true)
    setStreamingContent('')

    try {
      const res = await fetch('/api/hyper-ai/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          conversation_id: conversationId,
          mode: 'onboarding',
          lang: i18n.language?.startsWith('zh') ? 'zh' : 'en',
        }),
      })

      if (!res.ok) throw new Error('Failed to send message')

      const data = await res.json()
      setConversationId(data.conversation_id)
      await pollStreamResponse(data.task_id)
    } catch (e) {
      console.error('Chat error:', e)
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: t('hyperAi.onboarding.chatError', 'Sorry, something went wrong. Please try again.'),
      }])
    } finally {
      setLoading(false)
      textareaRef.current?.focus()
    }
  }

  const pollStreamResponse = async (taskId: string) => {
    let content = ''
    let isOnboardingComplete = false

    await pollAiStream(taskId, {
      interval: 150,
      maxDuration: 2 * 60 * 1000,
      onChunk: (chunk) => {
        const eventType = chunk.event_type || chunk.data?.type
        if (eventType === 'content' && chunk.data?.text) {
          content += chunk.data.text
          setStreamingContent(content)
        } else if (eventType === 'done') {
          if (chunk.data?.onboarding_complete) {
            isOnboardingComplete = true
          }
        } else if (eventType === 'error') {
          throw new Error(chunk.data?.message || 'Stream error')
        }
      },
    })

    if (content) {
      setMessages(prev => [...prev, { role: 'assistant', content }])
      setStreamingContent('')
    }
    if (isOnboardingComplete) {
      setOnboardingComplete(true)
      setTimeout(() => setShowEnterButton(true), 2000)
    }
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void sendMessage(input)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="w-full max-w-3xl bg-background rounded-lg shadow-xl flex flex-col" style={{ height: '85vh' }}>
        <div className="border-b p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
              <Bot className="w-5 h-5 text-primary" />
            </div>
            <div>
              <h2 className="font-semibold">Hyper AI</h2>
              <p className="text-xs text-muted-foreground">
                {t('hyperAi.onboarding.gettingToKnowQuestions', 'Getting to know you (3-4 questions)')}
              </p>
            </div>
          </div>
          {!onboardingComplete && (
            <Button variant="ghost" size="sm" onClick={onSkip}>
              {t('common.skip', 'Skip')}
            </Button>
          )}
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.length === 0 && !streamingContent && loading && (
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                <Bot className="w-4 h-4 text-primary" />
              </div>
              <div className="rounded-lg px-4 py-2.5 bg-muted flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span className="text-sm text-muted-foreground">Hyper AI is typing...</span>
              </div>
            </div>
          )}

          {messages.map((message, index) => {
            const displayContent = message.role === 'assistant'
              ? stripProfileMarkers(message.content)
              : message.content
            if (!displayContent) return null
            return (
              <div key={index} className={`flex gap-3 ${message.role === 'user' ? 'justify-end' : ''}`}>
                {message.role === 'assistant' && (
                  <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                    <Bot className="w-4 h-4 text-primary" />
                  </div>
                )}
                <div className={`max-w-[80%] rounded-lg px-4 py-2.5 ${
                  message.role === 'user'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted'
                }`}>
                  <p className="text-sm whitespace-pre-wrap">{displayContent}</p>
                </div>
                {message.role === 'user' && (
                  <div className="w-8 h-8 rounded-full bg-secondary flex items-center justify-center shrink-0">
                    <User className="w-4 h-4" />
                  </div>
                )}
              </div>
            )
          })}

          {streamingContent && (
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                <Bot className="w-4 h-4 text-primary" />
              </div>
              <div className="max-w-[80%] rounded-lg px-4 py-2.5 bg-muted">
                <p className="text-sm whitespace-pre-wrap">{stripProfileMarkers(streamingContent)}</p>
              </div>
            </div>
          )}

          {loading && !streamingContent && messages.length > 0 && (
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                <Bot className="w-4 h-4 text-primary" />
              </div>
              <div className="rounded-lg px-4 py-2.5 bg-muted">
                <Loader2 className="w-4 h-4 animate-spin" />
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        <div className="border-t p-4">
          {showEnterButton ? (
            <CompletionStep onComplete={onComplete} />
          ) : (
            <div className="relative">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={event => setInput(event.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={t('hyperAi.onboarding.typeMessage', 'Type a message...')}
                disabled={loading || onboardingComplete}
                className="w-full min-h-[80px] max-h-[200px] rounded-xl border border-input bg-transparent px-4 py-3 pb-12 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 resize-y"
                rows={3}
              />
              <div className="absolute bottom-3 right-3">
                <Button
                  onClick={() => void sendMessage(input)}
                  disabled={!input.trim() || loading || onboardingComplete}
                  size="icon"
                  className="rounded-full h-8 w-8 shrink-0"
                >
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
