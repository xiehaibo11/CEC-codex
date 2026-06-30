import type { Dispatch, SetStateAction } from 'react'
import { useTranslation } from 'react-i18next'

import type { PromptBinding, PromptTemplate, TradingAccount } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { DEFAULT_BINDING_FORM, type BindingFormState } from './types'

interface BindingsPanelProps {
  bindings: PromptBinding[]
  templates: PromptTemplate[]
  accountOptions: TradingAccount[]
  bindingForm: BindingFormState
  accountsLoading: boolean
  bindingSaving: boolean
  setBindingForm: Dispatch<SetStateAction<BindingFormState>>
  onEditBinding: (binding: PromptBinding) => void
  onDeleteBinding: (bindingId: number) => void
  onSubmit: () => void
}

export default function BindingsPanel({
  bindings,
  templates,
  accountOptions,
  bindingForm,
  accountsLoading,
  bindingSaving,
  setBindingForm,
  onEditBinding,
  onDeleteBinding,
  onSubmit,
}: BindingsPanelProps) {
  const { t } = useTranslation()

  return (
    <Card className="flex flex-col w-full lg:w-[40rem] flex-shrink-0 overflow-hidden">
      <CardHeader>
        <CardTitle className="text-base">
          {t('prompt.accountBindings', 'Account Prompt Bindings')}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 flex flex-col gap-6">
        <div className="flex-1 overflow-auto">
          <table className="min-w-full text-sm">
            <thead className="text-left text-muted-foreground">
              <tr>
                <th className="py-2 pr-4">{t('prompt.account', 'Account')}</th>
                <th className="py-2 pr-4">{t('prompt.model', 'Model')}</th>
                <th className="py-2 pr-4">{t('prompt.template', 'Template')}</th>
                <th className="py-2 pr-4 text-right">{t('common.actions', 'Actions')}</th>
              </tr>
            </thead>
            <tbody>
              {bindings.map((binding) => (
                <tr key={binding.id} className="border-t">
                  <td className="py-2 pr-4">{binding.accountName}</td>
                  <td className="py-2 pr-4 text-muted-foreground">
                    {binding.accountModel || '—'}
                  </td>
                  <td className="py-2 pr-4">{binding.promptName}</td>
                  <td className="py-2 pr-4 text-right space-x-2">
                    <Button variant="ghost" size="sm" onClick={() => onEditBinding(binding)}>
                      {t('common.edit', 'Edit')}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-destructive"
                      onClick={() => onDeleteBinding(binding.id)}
                    >
                      {t('common.delete', 'Delete')}
                    </Button>
                  </td>
                </tr>
              ))}
              {bindings.length === 0 && (
                <tr>
                  <td colSpan={4} className="py-4 text-center text-muted-foreground">
                    {t('prompt.noBindings', 'No prompt bindings configured.')}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="space-y-4 border-t pt-4">
          <div className="grid grid-cols-1 gap-3">
            <div>
              <label className="text-xs uppercase text-muted-foreground">
                {t('prompt.aiTrader', 'AI Trader')}
              </label>
              <Select
                value={bindingForm.accountId !== undefined ? String(bindingForm.accountId) : ''}
                onValueChange={(value) =>
                  setBindingForm((prev) => ({
                    ...prev,
                    accountId: Number(value),
                  }))
                }
                disabled={accountsLoading}
              >
                <SelectTrigger>
                  <SelectValue
                    placeholder={
                      accountsLoading
                        ? t('common.loading', 'Loading...')
                        : t('common.select', 'Select')
                    }
                  />
                </SelectTrigger>
                <SelectContent>
                  {accountOptions.map((account) => (
                    <SelectItem key={account.id} value={String(account.id)}>
                      {account.name}
                      {account.model ? ` (${account.model})` : ''}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-xs uppercase text-muted-foreground">
                {t('prompt.template', 'Template')}
              </label>
              <Select
                value={
                  bindingForm.promptTemplateId !== undefined
                    ? String(bindingForm.promptTemplateId)
                    : ''
                }
                onValueChange={(value) =>
                  setBindingForm((prev) => ({
                    ...prev,
                    promptTemplateId: Number(value),
                  }))
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder={t('common.select', 'Select')} />
                </SelectTrigger>
                <SelectContent>
                  {templates.map((tpl) => (
                    <SelectItem key={tpl.id} value={String(tpl.id)}>
                      {tpl.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              onClick={() => setBindingForm(DEFAULT_BINDING_FORM)}
              disabled={bindingSaving}
            >
              {t('common.reset', 'Reset')}
            </Button>
            <Button onClick={onSubmit} disabled={bindingSaving}>
              {t('prompt.saveBinding', 'Save Binding')}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
