import { useTranslation } from 'react-i18next'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'

interface VariablesReferenceDialogProps {
  open: boolean
  loading: boolean
  content: string
  onOpenChange: (open: boolean) => void
  onTryAiWrite: () => void
}

export default function VariablesReferenceDialog({
  open,
  loading,
  content,
  onOpenChange,
  onTryAiWrite,
}: VariablesReferenceDialogProps) {
  const { t } = useTranslation()

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-5xl max-h-[80vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>
            {t('prompt.variablesReference', 'Strategy Variables Reference')}
          </DialogTitle>
          <DialogDescription>
            {t(
              'prompt.variablesReferenceDesc',
              'All available variables for prompt templates',
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 flex gap-4 overflow-hidden">
          <div className="w-56 flex-shrink-0">
            <div className="bg-gradient-to-b from-purple-50 to-pink-50 dark:from-purple-950/30 dark:to-pink-950/30 border border-purple-200 dark:border-purple-800 rounded-lg p-4 h-full flex flex-col">
              <div className="text-2xl mb-3">✨</div>
              <p className="text-sm font-medium text-foreground mb-3">
                {t('prompt.needHelpWriting', 'Need help writing prompts?')}
              </p>
              <p className="text-xs text-muted-foreground mb-3">
                {t('prompt.tryAiPromptGeneration', 'Try')}{' '}
                <span className="font-semibold text-purple-600 dark:text-purple-400">
                  {t('prompt.aiPromptGeneration', 'AI Prompt Generation')}
                </span>{' '}
                {t('prompt.toCreateStrategies', 'to create professional trading strategies.')}
              </p>
              <div className="text-xs text-muted-foreground space-y-1 mb-4">
                <p className="font-medium">{t('prompt.aiWillHelp', 'AI will help you:')}</p>
                <ul className="list-disc list-inside space-y-0.5 text-[11px]">
                  <li>{t('prompt.generateOptimized', 'Generate optimized prompts')}</li>
                  <li>{t('prompt.selectVariables', 'Select appropriate variables')}</li>
                  <li>{t('prompt.addRiskManagement', 'Add risk management')}</li>
                  <li>{t('prompt.refineViaConversation', 'Refine via conversation')}</li>
                </ul>
              </div>
              <Button
                size="sm"
                onClick={onTryAiWrite}
                className="w-full bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white border-0 shadow-md hover:shadow-lg transition-all text-xs"
              >
                ✨ {t('prompt.tryAiWrite', 'Try AI Write')}
              </Button>
            </div>
          </div>

          <ScrollArea className="flex-1 pr-4">
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <span className="text-muted-foreground">
                  {t('common.loading', 'Loading...')}
                </span>
              </div>
            ) : (
              <div className="prose prose-sm dark:prose-invert max-w-none prose-headings:text-foreground prose-p:text-foreground prose-strong:text-foreground prose-code:text-primary prose-code:bg-muted prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-pre:bg-muted prose-hr:border-border">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    table: ({ children }) => (
                      <div className="overflow-x-auto my-4">
                        <table className="min-w-full border-collapse border border-border text-sm">
                          {children}
                        </table>
                      </div>
                    ),
                    thead: ({ children }) => <thead className="bg-muted">{children}</thead>,
                    th: ({ children }) => (
                      <th className="border border-border px-3 py-2 text-left font-semibold">
                        {children}
                      </th>
                    ),
                    td: ({ children }) => (
                      <td className="border border-border px-3 py-2">{children}</td>
                    ),
                    code: ({ children, className }) => {
                      const isInline = !className
                      return isInline ? (
                        <code className="bg-muted text-primary px-1 py-0.5 rounded text-xs">
                          {children}
                        </code>
                      ) : (
                        <code className={className}>{children}</code>
                      )
                    },
                  }}
                >
                  {content}
                </ReactMarkdown>
              </div>
            )}
          </ScrollArea>
        </div>
        <DialogFooter>
          <Button onClick={() => onOpenChange(false)}>{t('common.close', 'Close')}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
