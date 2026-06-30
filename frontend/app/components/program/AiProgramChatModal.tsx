import { useTranslation } from 'react-i18next'
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
import { TradingAccount } from '@/lib/api'
import { useAiProgramChat } from './ai-program-chat/useAiProgramChat'
import { ChatArea } from './ai-program-chat/ChatArea'
import { CodeSuggestionsPanel } from './ai-program-chat/CodeSuggestionsPanel'

interface AiProgramChatModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSaveCode: (code: string, name: string, description: string) => Promise<boolean>
  accounts: TradingAccount[]
  accountsLoading: boolean
  programId?: number | null
  programName?: string | null
  programDescription?: string | null
  currentCode?: string
  isNewProgram?: boolean
}

export default function AiProgramChatModal({
  open,
  onOpenChange,
  onSaveCode,
  accounts,
  accountsLoading,
  programId,
  programName,
  programDescription,
  currentCode,
  isNewProgram,
}: AiProgramChatModalProps) {
  const { t } = useTranslation()
  const {
    selectedAccountId,
    setSelectedAccountId,
    conversations,
    loadingConversations,
    currentConversationId,
    setCurrentConversationId,
    messages,
    compressionPoints,
    tokenUsage,
    userInput,
    setUserInput,
    loading,
    allCodeSuggestions,
    aiAccounts,
    messagesEndRef,
    startNewConversation,
    sendMessage,
    handleSaveCode,
  } = useAiProgramChat({
    open,
    onSaveCode,
    accounts,
    programId,
    programName,
    programDescription,
    isNewProgram,
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="w-[95vw] max-w-[1400px] h-[85vh] flex flex-col p-0"
        onInteractOutside={(e) => e.preventDefault()}
      >
        <DialogHeader className="px-6 py-4 border-b">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <DialogTitle>
                {isNewProgram ? t('program.aiChat.titleNew') : t('program.aiChat.titleEdit')}
              </DialogTitle>
              {/* Show program name badge when editing */}
              {!isNewProgram && programName && (
                <span className="text-xs bg-primary/10 text-primary px-2 py-1 rounded font-medium">
                  {t('program.aiChat.editing')}: {programName}
                </span>
              )}
              {isNewProgram && (
                <span className="text-xs bg-green-500/10 text-green-600 px-2 py-1 rounded font-medium">
                  {t('program.aiChat.creatingNew')}
                </span>
              )}
              <span className="text-xs text-muted-foreground">
                {t('program.aiChat.subtitle')}
              </span>
            </div>
            {(loadingConversations || accountsLoading) && <PacmanLoader className="w-8 h-4" />}
          </div>
          <div className="flex items-center gap-4 mt-4">
            <div className="flex-1">
              <label className="text-xs text-muted-foreground mb-1 block">
                {t('program.aiChat.aiTrader')}
              </label>
              <Select
                value={selectedAccountId?.toString()}
                onValueChange={(val) => setSelectedAccountId(parseInt(val))}
                disabled={accountsLoading}
              >
                <SelectTrigger>
                  <SelectValue placeholder={accountsLoading ? t('common.loading') : t('program.aiChat.selectAI')} />
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
              <label className="text-xs text-muted-foreground mb-1 block">
                {t('program.aiChat.conversation')}
              </label>
              <div className="flex gap-2">
                <Select
                  value={currentConversationId?.toString() || 'new'}
                  onValueChange={(val) => {
                    if (val === 'new') startNewConversation()
                    else setCurrentConversationId(parseInt(val))
                  }}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t('program.aiChat.newChat')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="new">{t('program.aiChat.newChat')}</SelectItem>
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
          <CodeSuggestionsPanel
            suggestions={allCodeSuggestions}
            onSave={handleSaveCode}
            t={t}
          />
        </div>
      </DialogContent>
    </Dialog>
  )
}
