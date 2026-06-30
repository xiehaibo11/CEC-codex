import type { RefObject } from 'react'
import { ScrollArea } from '@/components/ui/scroll-area'
import { MessageBubble } from './MessageBubble'
import { WelcomeMessage } from './WelcomeMessage'
import type { CompressionPoint, Message } from './types'

interface ChatMessagesProps {
  messages: Message[]
  compressionPoints: CompressionPoint[]
  nickname: string
  sending: boolean
  messagesEndRef: RefObject<HTMLDivElement | null>
  onSuggestionClick: (question: string) => void
  onContinue: () => void
  onToolConfirmation: (taskId: string, confirmationId: string, confirmed: boolean) => void
  t: any
}

export function ChatMessages({
  messages,
  compressionPoints,
  nickname,
  sending,
  messagesEndRef,
  onSuggestionClick,
  onContinue,
  onToolConfirmation,
  t,
}: ChatMessagesProps) {
  if (messages.length === 0) {
    return (
      <WelcomeMessage
        nickname={nickname}
        t={t}
        onSuggestionClick={onSuggestionClick}
      />
    )
  }

  return (
    <ScrollArea className="flex-1 p-4">
      <div className="space-y-4 max-w-5xl mx-auto">
        {messages.map((msg, idx) => {
          const compressionPoint = compressionPoints.find(cp => cp.message_id === msg.id)
          return (
            <div key={idx}>
              <MessageBubble
                message={msg}
                onContinue={msg.isInterrupted && !sending ? onContinue : undefined}
                onToolConfirmation={onToolConfirmation}
                t={t}
              />
              {compressionPoint && (
                <div className="flex items-center gap-3 my-4 text-xs text-muted-foreground">
                  <div className="flex-1 border-t border-dashed border-muted-foreground/30" />
                  <span className="px-2 py-1 bg-muted rounded text-[10px]">
                    {t('hyperAi.compressionPoint', 'Context compressed')}
                  </span>
                  <div className="flex-1 border-t border-dashed border-muted-foreground/30" />
                </div>
              )}
            </div>
          )
        })}
        <div ref={messagesEndRef} />
      </div>
    </ScrollArea>
  )
}
