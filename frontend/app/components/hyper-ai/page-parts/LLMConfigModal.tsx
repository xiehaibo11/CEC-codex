import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  Loader2,
  X,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

import type { LLMProvider } from './types'

export function LLMConfigModal({
  open,
  onClose,
  providers,
  currentProfile,
  onSaved
}: {
  open: boolean
  onClose: () => void
  providers: LLMProvider[]
  currentProfile: any
  onSaved: () => void
}) {
  const { t } = useTranslation()
  const [selectedProvider, setSelectedProvider] = useState(currentProfile?.llm_provider || '')
  const [apiKey, setApiKey] = useState('')
  const [modelInput, setModelInput] = useState(currentProfile?.llm_model || '')
  const [customBaseUrl, setCustomBaseUrl] = useState(currentProfile?.llm_base_url || '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)

  const currentProvider = providers.find(p => p.id === selectedProvider)

  useEffect(() => {
    if (open) {
      setSelectedProvider(currentProfile?.llm_provider || '')
      setModelInput(currentProfile?.llm_model || '')
      setCustomBaseUrl(currentProfile?.llm_base_url || '')
      setApiKey('')
      setError('')
      setSuccess(false)
    }
  }, [open, currentProfile])

  // When provider changes, set default model if current model is empty
  useEffect(() => {
    if (selectedProvider && !modelInput) {
      const provider = providers.find(p => p.id === selectedProvider)
      if (provider && provider.models.length > 0) {
        setModelInput(provider.models[0])
      }
    }
  }, [selectedProvider])

  const handleSave = async () => {
    if (!selectedProvider || !apiKey) {
      setError(t('hyperAi.onboarding.fillRequired', 'Please fill in all required fields'))
      return
    }

    if (selectedProvider === 'custom' && !customBaseUrl) {
      setError(t('hyperAi.onboarding.baseUrlRequired', 'Base URL is required for custom provider'))
      return
    }

    setSaving(true)
    setError('')

    try {
      const res = await fetch('/api/hyper-ai/profile/llm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: selectedProvider,
          api_key: apiKey,
          model: modelInput,
          base_url: selectedProvider === 'custom' ? customBaseUrl : undefined
        })
      })

      if (!res.ok) {
        const errData = await res.json()
        throw new Error(errData.detail || 'Connection test failed')
      }

      setSuccess(true)
      setTimeout(() => {
        onSaved()
        onClose()
      }, 800)
    } catch (e: any) {
      setError(e.message || 'Failed to save')
    } finally {
      setSaving(false)
    }
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="w-full max-w-md bg-background rounded-lg shadow-xl p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">{t('hyperAi.configTitle', 'Hyper AI Config')}</h2>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="w-4 h-4" />
          </Button>
        </div>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label>{t('hyperAi.onboarding.provider', 'AI Provider')}</Label>
            <Select value={selectedProvider} onValueChange={(v) => { setSelectedProvider(v); setModelInput('') }}>
              <SelectTrigger>
                <SelectValue placeholder={t('hyperAi.onboarding.selectProvider', 'Select provider')} />
              </SelectTrigger>
              <SelectContent>
                {providers.map(p => (
                  <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {selectedProvider === 'custom' && (
            <div className="space-y-2">
              <Label>{t('hyperAi.onboarding.baseUrl', 'Base URL')}</Label>
              <Input
                value={customBaseUrl}
                onChange={e => setCustomBaseUrl(e.target.value)}
                placeholder="https://api.example.com/v1"
              />
            </div>
          )}

          <div className="space-y-2">
            <Label>{t('hyperAi.onboarding.apiKey', 'API Key')}</Label>
            <Input
              type="password"
              value={apiKey}
              onChange={e => setApiKey(e.target.value)}
              placeholder={currentProfile?.llm_configured ? t('hyperAi.onboarding.apiKeyConfigured', 'Enter new API key to update') : 'sk-...'}
            />
          </div>

          {selectedProvider && (
            <div className="space-y-2">
              <Label>{t('hyperAi.onboarding.model', 'Model')}</Label>
              <div className="flex gap-1">
                <Input
                  value={modelInput}
                  onChange={e => setModelInput(e.target.value)}
                  placeholder={t('hyperAi.onboarding.modelPlaceholder', 'Enter or select model')}
                  className="flex-1"
                />
                {currentProvider && currentProvider.models.length > 0 && (
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="outline" size="icon" className="shrink-0">
                        <ChevronDown className="w-4 h-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="max-h-60 overflow-y-auto">
                      {currentProvider.models.map(m => (
                        <DropdownMenuItem key={m} onClick={() => setModelInput(m)}>
                          {m}
                        </DropdownMenuItem>
                      ))}
                    </DropdownMenuContent>
                  </DropdownMenu>
                )}
              </div>
            </div>
          )}
        </div>

        {error && (
          <div className="flex items-center gap-2 text-destructive text-sm">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span className="break-all">{error}</span>
          </div>
        )}

        {success && (
          <div className="flex items-center gap-2 text-green-600 text-sm">
            <CheckCircle2 className="w-4 h-4" />
            {t('hyperAi.onboarding.connectionSuccess', 'Connection successful!')}
          </div>
        )}

        <div className="flex gap-3 pt-2">
          <Button variant="outline" onClick={onClose} className="flex-1">
            {t('common.cancel', 'Cancel')}
          </Button>
          <Button onClick={handleSave} disabled={!selectedProvider || !apiKey || saving} className="flex-1">
            {saving && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
            {saving ? t('hyperAi.onboarding.testing', 'Testing...') : t('common.save', 'Save')}
          </Button>
        </div>
      </div>
    </div>
  )
}
