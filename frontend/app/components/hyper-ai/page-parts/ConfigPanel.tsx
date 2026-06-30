import { useTranslation } from 'react-i18next'
import { Brain, ChevronRight, Pencil, Settings } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { ToolInfo } from '../ToolConfigModal'
import { IntegrationPanel } from './IntegrationPanel'
import { SkillPanel } from './SkillPanel'
import { ToolPanel } from './ToolPanel'
import type { BotConfig, DiscordBotConfig, SkillInfo } from './types'

interface ConfigPanelProps {
  profile: any
  skills: SkillInfo[]
  activeSkill: string | null
  skillsLoading: boolean
  skillsEditMode: boolean
  pendingSkillToggles: Record<string, boolean>
  externalTools: ToolInfo[]
  currentLang: 'zh' | 'en'
  botConfig: BotConfig | null
  discordBotConfig: DiscordBotConfig | null
  notificationCount: number
  onOpenConfigModal: () => void
  onOpenMemoryModal: () => void
  onStartSkillsEdit: () => void
  onTogglePendingSkill: (skillName: string, enabled: boolean) => void
  onCancelSkillsEdit: () => void
  onSaveSkillsEdit: () => void
  onSelectTool: (tool: ToolInfo) => void
  onOpenBotModal: () => void
  onOpenDiscordBotModal: () => void
  onOpenNotificationModal: () => void
}

export function ConfigPanel({
  profile,
  skills,
  activeSkill,
  skillsLoading,
  skillsEditMode,
  pendingSkillToggles,
  externalTools,
  currentLang,
  botConfig,
  discordBotConfig,
  notificationCount,
  onOpenConfigModal,
  onOpenMemoryModal,
  onStartSkillsEdit,
  onTogglePendingSkill,
  onCancelSkillsEdit,
  onSaveSkillsEdit,
  onSelectTool,
  onOpenBotModal,
  onOpenDiscordBotModal,
  onOpenNotificationModal,
}: ConfigPanelProps) {
  const { t } = useTranslation()

  return (
    <div className="w-[500px] border-l p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium flex items-center gap-1.5">
          <Settings className="w-4 h-4 shrink-0" />
          {t('hyperAi.configTitle', 'Hyper AI Config')}
        </h3>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onOpenConfigModal}>
          <Pencil className="w-3.5 h-3.5" />
        </Button>
      </div>

      {profile && (
        <div
          className="space-y-1.5 text-sm cursor-pointer hover:bg-muted/50 rounded-lg p-2 -mx-2 transition-colors"
          onClick={onOpenConfigModal}
        >
          <div className="flex items-center">
            <span className="text-muted-foreground shrink-0 w-[72px]">Provider</span>
            <span className="truncate">{profile.llm_provider || 'Not configured'}</span>
          </div>
          <div className="flex items-center">
            <span className="text-muted-foreground shrink-0 w-[72px]">Model</span>
            <span className="truncate">{profile.llm_model || '-'}</span>
          </div>
          {profile.llm_base_url && (
            <div className="flex items-center">
              <span className="text-muted-foreground shrink-0 w-[72px]">Base URL</span>
              <span className="truncate">{profile.llm_base_url}</span>
            </div>
          )}
        </div>
      )}

      <div className="pt-4">
        <button
          onClick={onOpenMemoryModal}
          className="w-full flex items-center gap-1.5 py-1 rounded-lg text-sm hover:bg-muted/50 transition-colors text-left"
        >
          <Brain className="w-4 h-4 text-primary shrink-0" />
          <span className="text-sm font-medium">{t('hyperAi.memory.button', 'Memory')}</span>
          <ChevronRight className="w-3 h-3 text-muted-foreground ml-auto shrink-0" />
        </button>
      </div>

      <SkillPanel
        skills={skills}
        activeSkill={activeSkill}
        skillsLoading={skillsLoading}
        editMode={skillsEditMode}
        pendingToggles={pendingSkillToggles}
        onEdit={onStartSkillsEdit}
        onTogglePending={onTogglePendingSkill}
        onCancel={onCancelSkillsEdit}
        onSave={onSaveSkillsEdit}
      />
      <ToolPanel
        tools={externalTools}
        currentLang={currentLang}
        onSelectTool={onSelectTool}
      />
      <IntegrationPanel
        botConfig={botConfig}
        discordBotConfig={discordBotConfig}
        notificationCount={notificationCount}
        onOpenBotModal={onOpenBotModal}
        onOpenDiscordBotModal={onOpenDiscordBotModal}
        onOpenNotificationModal={onOpenNotificationModal}
      />
    </div>
  )
}
