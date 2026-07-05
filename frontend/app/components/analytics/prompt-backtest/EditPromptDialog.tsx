import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import type { SelectedRecord } from './types'

interface EditPromptDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  editingRecord: SelectedRecord | null
  setEditingRecord: (record: SelectedRecord | null) => void
  onSave: () => void
}

export default function EditPromptDialog({
  open,
  onOpenChange,
  editingRecord,
  setEditingRecord,
  onSave,
}: EditPromptDialogProps) {
  const { t } = useTranslation()

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[80vh] overflow-auto">
        <DialogHeader>
          <DialogTitle>{t('promptBacktest.editPrompt', 'Edit Prompt')}</DialogTitle>
          <DialogDescription>
            {t('promptBacktest.editPromptDesc', "Edit this record's prompt text, then save it back to the workspace.")}
          </DialogDescription>
        </DialogHeader>
        {editingRecord && (
          <div className="space-y-4">
            <Textarea
              value={editingRecord.modifiedPrompt}
              onChange={e => setEditingRecord({ ...editingRecord, modifiedPrompt: e.target.value })}
              className="min-h-[400px] font-mono text-xs"
            />
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                {t('common.cancel', 'Cancel')}
              </Button>
              <Button onClick={onSave}>
                {t('common.save', 'Save')}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
