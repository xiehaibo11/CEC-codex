import { useTranslation } from 'react-i18next'
import { Pencil } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { ActiveSkillIcon, SkillsIcon } from './icons'
import type { SkillInfo } from './types'

interface SkillPanelProps {
  skills: SkillInfo[]
  activeSkill: string | null
  skillsLoading: boolean
  editMode: boolean
  pendingToggles: Record<string, boolean>
  onEdit: () => void
  onTogglePending: (skillName: string, enabled: boolean) => void
  onCancel: () => void
  onSave: () => void
}

export function SkillPanel({
  skills,
  activeSkill,
  skillsLoading,
  editMode,
  pendingToggles,
  onEdit,
  onTogglePending,
  onCancel,
  onSave,
}: SkillPanelProps) {
  const { t } = useTranslation()

  return (
    <div className="pt-4">
      <div className="flex items-center justify-between mb-1">
        <h4 className="text-sm font-medium flex items-center gap-1.5">
          <SkillsIcon />
          {t('hyperAi.skills', 'Skills')}
        </h4>
        {skills.length > 0 && !editMode && (
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onEdit}>
            <Pencil className="w-3.5 h-3.5" />
          </Button>
        )}
      </div>
      <p className="text-[10px] text-muted-foreground/60 mb-2 px-0.5">
        {t('hyperAi.skillsHint', 'Auto-loaded by AI, or type /command')}
      </p>
      {skills.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          {t('hyperAi.skillsLoading', 'Loading...')}
        </p>
      ) : (
        <>
          <div className="space-y-1">
            {skills.map(skill => {
              const isEnabled = pendingToggles[skill.name] !== undefined
                ? pendingToggles[skill.name]
                : skill.enabled
              return (
                <div
                  key={skill.name}
                  className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-muted/50 transition-colors"
                >
                  {editMode ? (
                    <Switch
                      checked={isEnabled}
                      onCheckedChange={v => onTogglePending(skill.name, v)}
                      disabled={skillsLoading}
                      className="scale-75 origin-left shrink-0"
                    />
                  ) : activeSkill === skill.name ? (
                    <ActiveSkillIcon />
                  ) : (
                    <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${isEnabled ? 'bg-green-500' : 'bg-muted-foreground/30'}`} />
                  )}
                  <span className="text-xs truncate flex-1">
                    {t(`hyperAi.skillNames.${skill.name}`, skill.name)}
                  </span>
                  <span className="text-[10px] text-muted-foreground/50 shrink-0 font-mono">{skill.command}</span>
                </div>
              )
            })}
          </div>
          {editMode && (
            <div className="flex gap-2 pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={onCancel}
                className="h-7 px-3 text-xs"
              >
                {t('hyperAi.skillsCancel', 'Cancel')}
              </Button>
              <Button
                size="sm"
                onClick={onSave}
                disabled={skillsLoading}
                className="h-7 px-3 text-xs"
              >
                {t('hyperAi.skillsSave', 'Save')}
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
