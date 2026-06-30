import { useTranslation } from 'react-i18next'
import { MessageSquare, PanelLeftClose, Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  BotConvIcon,
  DiscordSmallIcon,
  TelegramSmallIcon,
} from './icons'
import type { BotConfig, Conversation, DiscordBotConfig } from './types'

interface ConversationSidebarProps {
  conversations: Conversation[]
  currentConvId: number | null
  botConfig: BotConfig | null
  discordBotConfig: DiscordBotConfig | null
  collapsed: boolean
  onCollapse: () => void
  onNewConversation: () => void
  onSelectConversation: (conversationId: number) => void
}

export function ConversationSidebar({
  conversations,
  currentConvId,
  botConfig,
  discordBotConfig,
  collapsed,
  onCollapse,
  onNewConversation,
  onSelectConversation,
}: ConversationSidebarProps) {
  const { t } = useTranslation()

  return (
    <div className={`border-r flex flex-col transition-all duration-200 ${collapsed ? 'w-0 overflow-hidden border-r-0' : 'w-64'}`}>
      <div className="p-3 flex items-center gap-2">
        <Button onClick={onNewConversation} className="flex-1" size="sm">
          <Plus className="w-4 h-4 mr-2" />
          {t('hyperAi.newChat', 'New Chat')}
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="px-2 shrink-0"
          onClick={onCollapse}
          title={t('hyperAi.collapseSidebar', 'Collapse sidebar')}
        >
          <PanelLeftClose className="w-4 h-4" />
        </Button>
      </div>
      <ScrollArea className="flex-1">
        <div className="p-2 space-y-1">
          {conversations.map(conv => (
            <button
              key={conv.id}
              onClick={() => onSelectConversation(conv.id)}
              className={`w-full text-left px-3 py-2.5 rounded-lg text-sm transition-colors ${
                conv.is_bot_conversation
                  ? 'border border-blue-500/30 bg-blue-500/5 mb-1 '
                  : ''
              }${
                currentConvId === conv.id
                  ? 'bg-secondary text-secondary-foreground'
                  : 'hover:bg-muted text-muted-foreground'
              }`}
            >
              {conv.is_bot_conversation ? (
                <>
                  <div className="flex items-center gap-2">
                    <BotConvIcon />
                    <span className="truncate font-medium">{conv.title}</span>
                  </div>
                  <div className="flex items-center gap-1.5 mt-1.5 ml-6">
                    {botConfig?.status === 'connected' && <TelegramSmallIcon />}
                    {discordBotConfig?.status === 'connected' && <DiscordSmallIcon />}
                  </div>
                </>
              ) : (
                <>
                  <div className="flex items-center gap-2">
                    <MessageSquare className="w-4 h-4 flex-shrink-0" />
                    <span className="truncate">{conv.title}</span>
                  </div>
                  <div className="text-xs text-muted-foreground mt-1">
                    {conv.message_count} {t('hyperAi.messages', 'messages')}
                  </div>
                </>
              )}
            </button>
          ))}
        </div>
      </ScrollArea>
    </div>
  )
}
