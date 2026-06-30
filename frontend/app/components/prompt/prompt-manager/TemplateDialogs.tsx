import { useTranslation } from 'react-i18next'

import type { PromptTemplate } from '@/lib/api'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'

interface TemplateDialogsProps {
  selectedTemplate: PromptTemplate | null
  newTemplateDialogOpen: boolean
  newTemplateName: string
  newTemplateDescription: string
  creating: boolean
  copyDialogOpen: boolean
  copyName: string
  copying: boolean
  onNewTemplateOpenChange: (open: boolean) => void
  onNewTemplateNameChange: (value: string) => void
  onNewTemplateDescriptionChange: (value: string) => void
  onCreateTemplate: () => void
  onCopyDialogOpenChange: (open: boolean) => void
  onCopyNameChange: (value: string) => void
  onCopyTemplate: () => void
}

export default function TemplateDialogs({
  selectedTemplate,
  newTemplateDialogOpen,
  newTemplateName,
  newTemplateDescription,
  creating,
  copyDialogOpen,
  copyName,
  copying,
  onNewTemplateOpenChange,
  onNewTemplateNameChange,
  onNewTemplateDescriptionChange,
  onCreateTemplate,
  onCopyDialogOpenChange,
  onCopyNameChange,
  onCopyTemplate,
}: TemplateDialogsProps) {
  const { t } = useTranslation()

  return (
    <>
      <Dialog open={newTemplateDialogOpen} onOpenChange={onNewTemplateOpenChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('prompt.createNewTemplate', 'Create New Template')}</DialogTitle>
            <DialogDescription>
              {t(
                'prompt.createNewTemplateDesc',
                'Create a new prompt template from scratch. It will be initialized with the default template content.',
              )}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <label className="text-sm font-medium">
                {t('prompt.templateName', 'Template Name')}
              </label>
              <Input
                value={newTemplateName}
                onChange={(event) => onNewTemplateNameChange(event.target.value)}
                placeholder={t('prompt.myCustomTemplate', 'My Custom Template')}
              />
            </div>
            <div>
              <label className="text-sm font-medium">
                {t('prompt.descriptionOptional', 'Description (Optional)')}
              </label>
              <Input
                value={newTemplateDescription}
                onChange={(event) => onNewTemplateDescriptionChange(event.target.value)}
                placeholder={t(
                  'prompt.templateDescPlaceholder',
                  'Description of this template',
                )}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => onNewTemplateOpenChange(false)}>
              {t('common.cancel', 'Cancel')}
            </Button>
            <Button onClick={onCreateTemplate} disabled={creating}>
              {t('common.create', 'Create')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={copyDialogOpen} onOpenChange={onCopyDialogOpenChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('prompt.copyTemplate', 'Copy Template')}</DialogTitle>
            <DialogDescription>
              {t(
                'prompt.copyTemplateDesc',
                'Create a copy of "{name}". You can specify a new name or leave blank to auto-generate.',
              ).replace('{name}', selectedTemplate?.name || '')}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <label className="text-sm font-medium">
                {t('prompt.newNameOptional', 'New Name (Optional)')}
              </label>
              <Input
                value={copyName}
                onChange={(event) => onCopyNameChange(event.target.value)}
                placeholder={`${selectedTemplate?.name} (Copy)`}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => onCopyDialogOpenChange(false)}>
              {t('common.cancel', 'Cancel')}
            </Button>
            <Button onClick={onCopyTemplate} disabled={copying}>
              {t('prompt.copy', 'Copy')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
