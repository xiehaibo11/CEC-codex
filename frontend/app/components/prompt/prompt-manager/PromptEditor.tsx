import { useTranslation } from 'react-i18next'

import type { PromptTemplate } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

interface PromptEditorProps {
  selectedTemplate: PromptTemplate | null
  nameDraft: string
  descriptionDraft: string
  templateDraft: string
  saving: boolean
  onNameChange: (value: string) => void
  onDescriptionChange: (value: string) => void
  onTemplateChange: (value: string) => void
  onAiWriteClick: () => void
  onPreviewClick: () => void
  onSaveTemplate: () => void
}

export default function PromptEditor({
  selectedTemplate,
  nameDraft,
  descriptionDraft,
  templateDraft,
  saving,
  onNameChange,
  onDescriptionChange,
  onTemplateChange,
  onAiWriteClick,
  onPreviewClick,
  onSaveTemplate,
}: PromptEditorProps) {
  const { t } = useTranslation()

  return (
    <>
      <div>
        <label className="text-xs uppercase text-muted-foreground">
          {t('prompt.templateName', 'Template Name')}
        </label>
        <Input
          value={nameDraft}
          onChange={(event) => onNameChange(event.target.value)}
          placeholder={t('prompt.templateNamePlaceholder', 'Template name')}
          disabled={!selectedTemplate || saving}
        />
      </div>

      <div>
        <label className="text-xs uppercase text-muted-foreground">
          {t('common.description', 'Description')}
        </label>
        <Input
          value={descriptionDraft}
          onChange={(event) => onDescriptionChange(event.target.value)}
          placeholder={t('prompt.descriptionPlaceholder', 'Prompt description')}
          disabled={!selectedTemplate || saving}
        />
        {selectedTemplate?.isSystem === 'true' && (
          <p className="mt-1 text-xs text-muted-foreground">
            {t(
              'prompt.testTemplateHint',
              'For learning and workflow testing only. Not a profit guarantee.',
            )}
          </p>
        )}
      </div>

      <div className="flex-1 flex flex-col overflow-hidden">
        <label className="text-xs uppercase text-muted-foreground mb-2">
          {t('prompt.templateText', 'Template Text')}
        </label>
        <textarea
          className="flex-1 w-full rounded-md border bg-background p-3 font-mono text-sm leading-relaxed focus:outline-none focus:ring-1 focus:ring-ring"
          value={templateDraft}
          onChange={(event) => onTemplateChange(event.target.value)}
          disabled={!selectedTemplate || saving}
        />
      </div>

      <div className="flex justify-between mt-2 gap-2">
        <div className="flex gap-2">
          <Button
            onClick={onAiWriteClick}
            disabled={!selectedTemplate || saving}
            className="bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white border-0 shadow-lg hover:shadow-xl transition-all"
          >
            ✨ {t('prompt.aiWritePrompt', 'AI Write Strategy Prompt')}
          </Button>
          <Button
            variant="outline"
            onClick={onPreviewClick}
            disabled={!selectedTemplate || saving}
          >
            💡 {t('prompt.previewFilled', 'Preview Filled')}
          </Button>
        </div>
        <div className="flex gap-2">
          <Button onClick={onSaveTemplate} disabled={!selectedTemplate || saving}>
            {t('prompt.saveTemplate', 'Save Template')}
          </Button>
        </div>
      </div>
    </>
  )
}
