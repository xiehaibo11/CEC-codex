import { Dialog, DialogContent } from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import type { AiPromptChatModalProps } from './ai-prompt-chat/types'
import { useAiPromptChat } from './ai-prompt-chat/useAiPromptChat'
import { ChatHeader } from './ai-prompt-chat/ChatHeader'
import { ChatMessageList } from './ai-prompt-chat/ChatMessageList'
import { Composer } from './ai-prompt-chat/Composer'
import { ArtifactPanel } from './ai-prompt-chat/ArtifactPanel'

export default function AiPromptChatModal({
  open,
  onOpenChange,
  accounts,
  accountsLoading,
  onApplyPrompt,
  promptId,
  promptName,
}: AiPromptChatModalProps) {
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
    extractedPrompts,
    selectedPromptIndex,
    setSelectedPromptIndex,
    messagesEndRef,
    chatContainerRef,
    sendMessage,
    handleApplyPrompt,
    startNewConversation,
    continueConversation,
  } = useAiPromptChat({ open, onOpenChange, accounts, onApplyPrompt, promptId })

  const aiAccounts = accounts.filter(acc => acc.account_type === 'AI')

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="w-[95vw] max-w-[1600px] h-[85vh] flex flex-col p-0"
        onInteractOutside={(e) => e.preventDefault()}
      >
        <ChatHeader
          promptName={promptName}
          accountsLoading={accountsLoading}
          loadingConversations={loadingConversations}
          aiAccounts={aiAccounts}
          selectedAccountId={selectedAccountId}
          setSelectedAccountId={setSelectedAccountId}
          conversations={conversations}
          currentConversationId={currentConversationId}
          setCurrentConversationId={setCurrentConversationId}
          startNewConversation={startNewConversation}
        />

        <div className="flex-1 flex overflow-hidden">
          {/* Left: Chat Area (40%) */}
          <div className="w-[40%] flex flex-col border-r">
            <ScrollArea className="flex-1 p-4" ref={chatContainerRef}>
              <ChatMessageList
                messages={messages}
                compressionPoints={compressionPoints}
                loading={loading}
                messagesEndRef={messagesEndRef}
                onContinue={continueConversation}
              />
            </ScrollArea>

            <Composer
              userInput={userInput}
              setUserInput={setUserInput}
              loading={loading}
              selectedAccountId={selectedAccountId}
              tokenUsage={tokenUsage}
              onSend={sendMessage}
            />
          </div>

          {/* Right: Artifact Preview (60%) */}
          <ArtifactPanel
            extractedPrompts={extractedPrompts}
            selectedPromptIndex={selectedPromptIndex}
            setSelectedPromptIndex={setSelectedPromptIndex}
            onApply={handleApplyPrompt}
          />
        </div>
      </DialogContent>
    </Dialog>
  )
}
