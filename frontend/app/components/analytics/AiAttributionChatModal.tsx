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
import { ChatArea } from './ai-attribution-chat/ChatArea'
import { DiagnosisCardsPanel } from './ai-attribution-chat/DiagnosisCardsPanel'
import { useAiAttributionChat } from './ai-attribution-chat/useAiAttributionChat'
import type { AiAttributionChatModalProps } from './ai-attribution-chat/types'

export default function AiAttributionChatModal({
  open,
  onOpenChange,
  accounts,
  accountsLoading,
}: AiAttributionChatModalProps) {
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
    allDiagnosisResults,
    aiAccounts,
    messagesEndRef,
    sendMessage,
    startNewConversation,
  } = useAiAttributionChat(open, accounts)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="w-[95vw] max-w-[1400px] h-[85vh] flex flex-col p-0"
        onInteractOutside={(e) => e.preventDefault()}
      >
        <DialogHeader className="px-6 py-4 border-b">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <DialogTitle>{t('attribution.aiAnalysis.title', 'AI Strategy Diagnosis')}</DialogTitle>
              <span className="text-xs text-muted-foreground">
                {t('attribution.aiAnalysis.subtitle', '(Analyze trading performance and get improvement suggestions)')}
              </span>
            </div>
            {(loadingConversations || accountsLoading) && <PacmanLoader className="w-8 h-4" />}
          </div>
          <div className="flex items-center gap-4 mt-4">
            <div className="flex-1">
              <label className="text-xs text-muted-foreground mb-1 block">{t('attribution.aiAnalysis.aiTrader', 'AI Trader')}</label>
              <Select
                value={selectedAccountId?.toString()}
                onValueChange={(val) => setSelectedAccountId(parseInt(val))}
                disabled={accountsLoading}
              >
                <SelectTrigger>
                  <SelectValue placeholder={t('attribution.aiAnalysis.selectAiTrader', 'Select AI Trader')} />
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
              <label className="text-xs text-muted-foreground mb-1 block">{t('attribution.aiAnalysis.conversation', 'Conversation')}</label>
              <div className="flex gap-2">
                <Select
                  value={currentConversationId?.toString() || 'new'}
                  onValueChange={(val) => {
                    if (val === 'new') startNewConversation()
                    else setCurrentConversationId(parseInt(val))
                  }}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t('attribution.aiAnalysis.newConversation', 'New Conversation')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="new">{t('attribution.aiAnalysis.newConversation', 'New Conversation')}</SelectItem>
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
          {/* Left: Chat Area (45%) */}
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
          />

          {/* Right: Diagnosis Cards (55%) */}
          <DiagnosisCardsPanel results={allDiagnosisResults} />
        </div>
      </DialogContent>
    </Dialog>
  )
}
