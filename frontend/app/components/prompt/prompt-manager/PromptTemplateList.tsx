import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { ExternalLink } from 'lucide-react'

import type { PromptTemplate } from '@/lib/api'
import { STRATEGY_RADAR_URL } from '@/lib/strategyRadar'
import { Button } from '@/components/ui/button'
import { CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

interface PromptTemplateListProps {
  templates: PromptTemplate[]
  selectedId: number | null
  selectedTemplate: PromptTemplate | null
  loading: boolean
  children: ReactNode
  onOpenVariablesRef: () => void
  onSelectTemplate: (id: string) => void
  onCreateClick: () => void
  onCopyClick: () => void
  onDeleteTemplate: () => void
}

export default function PromptTemplateList({
  templates,
  selectedId,
  selectedTemplate,
  loading,
  children,
  onOpenVariablesRef,
  onSelectTemplate,
  onCreateClick,
  onCopyClick,
  onDeleteTemplate,
}: PromptTemplateListProps) {
  const { t } = useTranslation()

  return (
    <>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CardTitle className="text-base">
              {t('prompt.templateEditor', 'Prompt Template Editor')}
            </CardTitle>
            <Button size="sm" variant="outline" onClick={onOpenVariablesRef}>
              📖 {t('prompt.variablesGuide', 'Variables Guide')}
            </Button>
            <Button size="sm" variant="outline" asChild>
              <a href={STRATEGY_RADAR_URL} target="_blank" rel="noopener noreferrer">
                {t('prompt.strategyIdeasLink', 'Need strategy ideas?')}
                <ExternalLink className="h-3 w-3" />
              </a>
            </Button>
          </div>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={onCreateClick}>
              ➕ {t('prompt.new', 'New')}
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={onCopyClick}
              disabled={!selectedTemplate}
            >
              📋 {t('prompt.copy', 'Copy')}
            </Button>
            {selectedTemplate && selectedTemplate.isSystem !== 'true' && (
              <Button
                size="sm"
                variant="outline"
                onClick={onDeleteTemplate}
                className="text-destructive"
              >
                🗑️ {t('common.delete', 'Delete')}
              </Button>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-4 h-[100%] flex-1 overflow-hidden">
        <div>
          <label className="text-xs uppercase text-muted-foreground">
            {t('prompt.template', 'Template')}
          </label>
          <Select
            value={selectedId ? String(selectedId) : ''}
            onValueChange={onSelectTemplate}
            disabled={loading}
          >
            <SelectTrigger>
              <SelectValue
                placeholder={
                  loading
                    ? t('common.loading', 'Loading...')
                    : t('prompt.selectTemplate', 'Select a template')
                }
              />
            </SelectTrigger>
            <SelectContent>
              {templates.map((tpl) => (
                <SelectItem key={tpl.id} value={String(tpl.id)}>
                  <div className="flex flex-col items-start">
                    <span className="font-semibold">
                      {tpl.name}
                      {tpl.isSystem === 'true' && (
                        <span className="ml-2 text-xs text-muted-foreground">
                          [{t('prompt.system', 'System')}]
                        </span>
                      )}
                      {tpl.isSystem === 'true' && (
                        <span className="ml-2 text-xs text-muted-foreground">
                          [{t('prompt.testTemplate', 'Test template')}]
                        </span>
                      )}
                    </span>
                    <span className="text-xs text-muted-foreground">{tpl.key}</span>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {children}
      </CardContent>
    </>
  )
}
