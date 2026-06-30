/**
 * HyperAiPage - Independent page for Hyper AI (three-column layout)
 * Left: Conversation list
 * Center: Chat area
 * Right: Config panel
 */
import { ChatHeader } from './page-parts/ChatHeader'
import { ChatMessages } from './page-parts/ChatMessages'
import { Composer } from './page-parts/Composer'
import { ConfigPanel } from './page-parts/ConfigPanel'
import { ConversationSidebar } from './page-parts/ConversationSidebar'
import { HyperAiModals } from './page-parts/HyperAiModals'
import { useHyperAiController } from './page-parts/useHyperAiController'

export default function HyperAiPage() {
  const page = useHyperAiController()

  return (
    <div className="flex h-full">
      <ConversationSidebar
        conversations={page.conversations}
        currentConvId={page.currentConvId}
        botConfig={page.botConfig}
        discordBotConfig={page.discordBotConfig}
        collapsed={page.sidebarCollapsed}
        onCollapse={() => page.setSidebarCollapsed(true)}
        onNewConversation={page.handleNewConversation}
        onSelectConversation={page.setCurrentConvId}
      />

      <div className="flex-1 flex flex-col min-w-0 relative">
        <ChatHeader
          sidebarCollapsed={page.sidebarCollapsed}
          onExpandSidebar={() => page.setSidebarCollapsed(false)}
        />
        <ChatMessages
          messages={page.messages}
          compressionPoints={page.compressionPoints}
          nickname={page.nickname}
          sending={page.sending}
          messagesEndRef={page.messagesEndRef}
          onSuggestionClick={page.handleSuggestionClick}
          onContinue={page.handleContinue}
          onToolConfirmation={page.handleToolConfirmation}
          t={page.t}
        />
        <Composer
          inputValue={page.inputValue}
          sending={page.sending}
          tokenUsage={page.tokenUsage}
          textareaRef={page.textareaRef}
          onInputChange={page.setInputValue}
          onKeyDown={page.handleKeyDown}
          onSend={page.handleSend}
        />
      </div>

      {page.showConfig && (
        <ConfigPanel
          profile={page.profile}
          skills={page.skills}
          activeSkill={page.activeSkill}
          skillsLoading={page.skillsLoading}
          skillsEditMode={page.skillsEditMode}
          pendingSkillToggles={page.pendingSkillToggles}
          externalTools={page.externalTools}
          currentLang={page.currentLang}
          botConfig={page.botConfig}
          discordBotConfig={page.discordBotConfig}
          notificationCount={page.notificationCount}
          onOpenConfigModal={() => page.setShowConfigModal(true)}
          onOpenMemoryModal={() => page.setShowMemoryModal(true)}
          onStartSkillsEdit={() => page.setSkillsEditMode(true)}
          onTogglePendingSkill={(name, enabled) =>
            page.setPendingSkillToggles(prev => ({ ...prev, [name]: enabled }))
          }
          onCancelSkillsEdit={page.handleSkillsEditCancel}
          onSaveSkillsEdit={page.handleSkillsEditSave}
          onSelectTool={page.openToolConfig}
          onOpenBotModal={() => page.setShowBotModal(true)}
          onOpenDiscordBotModal={() => page.setShowDiscordBotModal(true)}
          onOpenNotificationModal={() => page.setShowNotificationModal(true)}
        />
      )}

      <HyperAiModals
        showConfigModal={page.showConfigModal}
        showMemoryModal={page.showMemoryModal}
        showBotModal={page.showBotModal}
        showDiscordBotModal={page.showDiscordBotModal}
        showNotificationModal={page.showNotificationModal}
        showToolModal={page.showToolModal}
        providers={page.providers}
        profile={page.profile}
        botConfig={page.botConfig}
        discordBotConfig={page.discordBotConfig}
        selectedTool={page.selectedTool}
        onCloseConfig={() => page.setShowConfigModal(false)}
        onCloseMemory={() => page.setShowMemoryModal(false)}
        onCloseBot={() => page.setShowBotModal(false)}
        onCloseDiscordBot={() => page.setShowDiscordBotModal(false)}
        onCloseNotification={() => page.setShowNotificationModal(false)}
        onCloseTool={page.closeToolConfig}
        onProfileSaved={page.fetchProfile}
        onBotConnected={page.fetchBotConfig}
        onDiscordBotConnected={page.fetchDiscordBotConfig}
        onNotificationConfigChange={page.setNotificationCount}
        onToolSaved={page.fetchExternalTools}
      />
    </div>
  )
}
