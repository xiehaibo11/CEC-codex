import { useTranslation } from 'react-i18next'
import { DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { TradingAccount } from '@/lib/api'
import PacmanLoader from '@/components/ui/pacman-loader'
import type { Conversation } from './types'

interface ChatHeaderProps {
  promptName?: string | null
  accountsLoading: boolean
  loadingConversations: boolean
  aiAccounts: TradingAccount[]
  selectedAccountId: number | null
  setSelectedAccountId: (id: number) => void
  conversations: Conversation[]
  currentConversationId: number | null
  setCurrentConversationId: (id: number) => void
  startNewConversation: () => void
}

export function ChatHeader({
  promptName,
  accountsLoading,
  loadingConversations,
  aiAccounts,
  selectedAccountId,
  setSelectedAccountId,
  conversations,
  currentConversationId,
  setCurrentConversationId,
  startNewConversation,
}: ChatHeaderProps) {
  const { t } = useTranslation()

  return (
    <DialogHeader className="px-6 py-4 border-b">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <DialogTitle>{t('aiPrompt.title', 'AI Strategy Prompt Generator')}</DialogTitle>
          {/* Show prompt name badge when editing */}
          {promptName && (
            <span className="text-xs bg-primary/10 text-primary px-2 py-1 rounded font-medium">
              {t('aiPrompt.editing', 'Editing')}: {promptName}
            </span>
          )}
        </div>
        {(accountsLoading || loadingConversations) && (
          <PacmanLoader className="w-8 h-4" />
        )}
      </div>
      <div className="flex items-center gap-4 mt-4">
        <div className="flex-1">
          <label className="text-xs text-muted-foreground mb-1 block">{t('aiPrompt.aiTrader', 'AI Trader')}</label>
          <Select
            value={selectedAccountId?.toString()}
            onValueChange={(val) => setSelectedAccountId(parseInt(val))}
            disabled={accountsLoading}
          >
            <SelectTrigger>
              <SelectValue placeholder={accountsLoading ? t('common.loading', 'Loading...') : t('aiPrompt.selectAiTrader', 'Select AI Trader')} />
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
          <label className="text-xs text-muted-foreground mb-1 block">{t('aiPrompt.conversation', 'Conversation')}</label>
          <div className="flex gap-2">
            <Select
              value={currentConversationId?.toString() || 'new'}
              onValueChange={(val) => {
                if (val === 'new') {
                  startNewConversation()
                } else {
                  setCurrentConversationId(parseInt(val))
                }
              }}
              disabled={loadingConversations}
            >
              <SelectTrigger>
                <SelectValue placeholder={loadingConversations ? t('common.loading', 'Loading...') : t('aiPrompt.newConversation', 'New Conversation')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="new">{t('aiPrompt.newConversation', 'New Conversation')}</SelectItem>
                {conversations.map(conv => (
                  <SelectItem key={conv.id} value={conv.id.toString()}>
                    {conv.title} ({conv.messageCount} {t('aiPrompt.msgs', 'msgs')})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              variant="outline"
              size="sm"
              onClick={startNewConversation}
              className="shrink-0"
            >
              {t('aiPrompt.new', 'New')}
            </Button>
          </div>
        </div>
      </div>
    </DialogHeader>
  )
}
