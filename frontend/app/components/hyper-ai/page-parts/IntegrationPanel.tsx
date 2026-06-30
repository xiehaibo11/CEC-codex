import { useTranslation } from 'react-i18next'
import { Blocks } from 'lucide-react'
import {
  DiscordSmallIcon,
  NotificationBellSmallIcon,
  TelegramSmallIcon,
} from './icons'
import type { BotConfig, DiscordBotConfig } from './types'

interface IntegrationPanelProps {
  botConfig: BotConfig | null
  discordBotConfig: DiscordBotConfig | null
  notificationCount: number
  onOpenBotModal: () => void
  onOpenDiscordBotModal: () => void
  onOpenNotificationModal: () => void
}

export function IntegrationPanel({
  botConfig,
  discordBotConfig,
  notificationCount,
  onOpenBotModal,
  onOpenDiscordBotModal,
  onOpenNotificationModal,
}: IntegrationPanelProps) {
  const { t } = useTranslation()

  return (
    <div className="pt-4">
      <h4 className="text-sm font-medium flex items-center gap-1.5 mb-2">
        <Blocks className="w-4 h-4 shrink-0" />
        {t('hyperAi.integrations', 'Integrations')}
        <button
          onClick={onOpenNotificationModal}
          className="ml-auto flex items-center gap-0.5 px-1.5 py-0.5 rounded-full bg-primary/10 hover:bg-primary/20 transition-colors"
          title={t('bot.notificationSettings', 'Push Notifications')}
        >
          <NotificationBellSmallIcon />
          {notificationCount > 0 && (
            <span className="text-[10px] text-primary font-medium min-w-[14px] text-center">
              {notificationCount}
            </span>
          )}
        </button>
      </h4>
      <div className="space-y-2">
        <div
          className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-muted/30 hover:bg-muted/50 cursor-pointer transition-colors"
          onClick={onOpenBotModal}
        >
          <TelegramSmallIcon />
          <span className="text-xs">{t('hyperAi.telegramBot', 'Telegram Bot')}</span>
          {botConfig && botConfig.status === 'connected' ? (
            <>
              <span className="ml-auto text-[10px] text-muted-foreground">@{botConfig.bot_username}</span>
              <span className="w-2 h-2 rounded-full bg-green-500"></span>
            </>
          ) : (
            <span className="ml-auto text-[10px] text-primary">
              {t('bot.setup', 'Setup')}
            </span>
          )}
        </div>
        <div
          className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-muted/30 hover:bg-muted/50 cursor-pointer transition-colors"
          onClick={onOpenDiscordBotModal}
        >
          <DiscordSmallIcon />
          <span className="text-xs">{t('hyperAi.discordBot', 'Discord Bot')}</span>
          {discordBotConfig && discordBotConfig.status === 'connected' ? (
            <>
              <span className="ml-auto text-[10px] text-muted-foreground">@{discordBotConfig.bot_username}</span>
              <span className="w-2 h-2 rounded-full bg-green-500"></span>
            </>
          ) : (
            <span className="ml-auto text-[10px] text-primary">
              {t('bot.setup', 'Setup')}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
