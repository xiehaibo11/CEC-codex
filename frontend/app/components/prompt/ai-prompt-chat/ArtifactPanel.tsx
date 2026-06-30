import { useTranslation } from 'react-i18next'
import { toast } from 'react-hot-toast'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { copyToClipboard } from '@/lib/utils'
import type { ExtractedPrompt } from './types'

interface ArtifactPanelProps {
  extractedPrompts: ExtractedPrompt[]
  selectedPromptIndex: number
  setSelectedPromptIndex: (index: number) => void
  onApply: () => void
}

export function ArtifactPanel({
  extractedPrompts,
  selectedPromptIndex,
  setSelectedPromptIndex,
  onApply,
}: ArtifactPanelProps) {
  const { t } = useTranslation()

  return (
    <div className="w-[60%] flex flex-col bg-muted/30">
      <div className="p-4 border-b">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold">{t('aiPrompt.generatedPrompts', 'Generated Prompts')}</h3>
            <p className="text-xs text-muted-foreground mt-1">
              {extractedPrompts.length > 0
                ? t('aiPrompt.versionsAvailable', '{{count}} version(s) available').replace('{{count}}', extractedPrompts.length.toString())
                : t('aiPrompt.promptWillAppear', 'The AI-generated strategy prompt will appear here')}
            </p>
          </div>
          {extractedPrompts.length > 1 && (
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSelectedPromptIndex(Math.max(0, selectedPromptIndex - 1))}
                disabled={selectedPromptIndex === 0}
                className="h-7 px-2"
              >
                ← {t('aiPrompt.prev', 'Prev')}
              </Button>
              <span className="text-xs text-muted-foreground">
                {selectedPromptIndex + 1} / {extractedPrompts.length}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSelectedPromptIndex(Math.min(extractedPrompts.length - 1, selectedPromptIndex + 1))}
                disabled={selectedPromptIndex === extractedPrompts.length - 1}
                className="h-7 px-2"
              >
                {t('aiPrompt.next', 'Next')} →
              </Button>
            </div>
          )}
        </div>
      </div>

      <ScrollArea className="flex-1 p-4">
        {extractedPrompts.length > 0 ? (
          <div className="space-y-4">
            {extractedPrompts.length > 1 && (
              <div className="text-xs text-muted-foreground bg-muted/50 rounded p-2">
                {t('aiPrompt.versionOf', 'Version {{current}} of {{total}}').replace('{{current}}', (selectedPromptIndex + 1).toString()).replace('{{total}}', extractedPrompts.length.toString())}
                {selectedPromptIndex === extractedPrompts.length - 1 && ` (${t('aiPrompt.latest', 'Latest')})`}
              </div>
            )}
            <div className="rounded-lg overflow-hidden border bg-muted/50 p-4">
              <pre className="text-sm whitespace-pre-wrap break-words font-mono">
                {extractedPrompts[selectedPromptIndex]?.content || ''}
              </pre>
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            <div className="text-center">
              <p className="text-sm">{t('aiPrompt.noPromptYet', 'No prompt generated yet')}</p>
              <p className="text-xs mt-2">
                {t('aiPrompt.startConversation', 'Start a conversation to generate a strategy prompt')}
              </p>
            </div>
          </div>
        )}
      </ScrollArea>

      {extractedPrompts.length > 0 && (
        <div className="p-4 border-t flex justify-end gap-2">
          <Button
            variant="outline"
            onClick={async () => {
              const currentPrompt = extractedPrompts[selectedPromptIndex]
              if (currentPrompt) {
                const success = await copyToClipboard(currentPrompt.content)
                if (success) {
                  toast.success(t('aiPrompt.copied', 'Prompt copied to clipboard'))
                } else {
                  toast.error(t('aiPrompt.copyFailed', 'Failed to copy to clipboard'))
                }
              }
            }}
          >
            {t('aiPrompt.copy', 'Copy')}
          </Button>
          <Button onClick={onApply}>
            {t('aiPrompt.applyToEditor', 'Apply to Editor')}
          </Button>
        </div>
      )}
    </div>
  )
}
