import BotIntegrationModal from '../BotIntegrationModal'
import NotificationConfigModal from '../NotificationConfigModal'
import ToolConfigModal, { type ToolInfo } from '../ToolConfigModal'
import { LLMConfigModal } from './LLMConfigModal'
import { MemoryModal } from './MemoryModal'
import type { BotConfig, DiscordBotConfig, LLMProvider } from './types'

interface HyperAiModalsProps {
  showConfigModal: boolean
  showMemoryModal: boolean
  showBotModal: boolean
  showDiscordBotModal: boolean
  showNotificationModal: boolean
  showToolModal: boolean
  providers: LLMProvider[]
  profile: any
  botConfig: BotConfig | null
  discordBotConfig: DiscordBotConfig | null
  selectedTool: ToolInfo | null
  onCloseConfig: () => void
  onCloseMemory: () => void
  onCloseBot: () => void
  onCloseDiscordBot: () => void
  onCloseNotification: () => void
  onCloseTool: () => void
  onProfileSaved: () => void
  onBotConnected: () => void
  onDiscordBotConnected: () => void
  onNotificationConfigChange: (count: number) => void
  onToolSaved: () => void
}

export function HyperAiModals({
  showConfigModal,
  showMemoryModal,
  showBotModal,
  showDiscordBotModal,
  showNotificationModal,
  showToolModal,
  providers,
  profile,
  botConfig,
  discordBotConfig,
  selectedTool,
  onCloseConfig,
  onCloseMemory,
  onCloseBot,
  onCloseDiscordBot,
  onCloseNotification,
  onCloseTool,
  onProfileSaved,
  onBotConnected,
  onDiscordBotConnected,
  onNotificationConfigChange,
  onToolSaved,
}: HyperAiModalsProps) {
  return (
    <>
      <LLMConfigModal
        open={showConfigModal}
        onClose={onCloseConfig}
        providers={providers}
        currentProfile={profile}
        onSaved={onProfileSaved}
      />
      <MemoryModal
        open={showMemoryModal}
        onClose={onCloseMemory}
      />
      <BotIntegrationModal
        open={showBotModal}
        onClose={onCloseBot}
        platform="telegram"
        onConnected={onBotConnected}
        currentBotUsername={botConfig?.status === 'connected' ? botConfig.bot_username : undefined}
      />
      <BotIntegrationModal
        open={showDiscordBotModal}
        onClose={onCloseDiscordBot}
        platform="discord"
        onConnected={onDiscordBotConnected}
        currentBotUsername={discordBotConfig?.status === 'connected' ? discordBotConfig.bot_username : undefined}
        currentBotAppId={discordBotConfig?.bot_app_id}
      />
      <NotificationConfigModal
        open={showNotificationModal}
        onClose={onCloseNotification}
        onConfigChange={onNotificationConfigChange}
      />
      <ToolConfigModal
        open={showToolModal}
        onClose={onCloseTool}
        tool={selectedTool}
        onSaved={onToolSaved}
      />
    </>
  )
}
