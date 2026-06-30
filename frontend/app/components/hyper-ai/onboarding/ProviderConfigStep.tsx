import { useTranslation } from 'react-i18next'
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  Loader2,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { hasProviderModels, isCustomProvider } from './providerHelpers'
import type { LLMProvider, TestResult } from './types'

interface ProviderConfigStepProps {
  providers: LLMProvider[]
  selectedProvider: string
  currentProvider?: LLMProvider
  apiKey: string
  modelInput: string
  customBaseUrl: string
  testing: boolean
  testResult: TestResult
  error: string
  onProviderChange: (value: string) => void
  onApiKeyChange: (value: string) => void
  onModelInputChange: (value: string) => void
  onCustomBaseUrlChange: (value: string) => void
  onSkip: () => void
  onContinue: () => void
}

export function ProviderConfigStep({
  providers,
  selectedProvider,
  currentProvider,
  apiKey,
  modelInput,
  customBaseUrl,
  testing,
  testResult,
  error,
  onProviderChange,
  onApiKeyChange,
  onModelInputChange,
  onCustomBaseUrlChange,
  onSkip,
  onContinue,
}: ProviderConfigStepProps) {
  const { t } = useTranslation()
  const providerModels = currentProvider?.models ?? []

  return (
    <div className="fixed inset-0 bg-background/95 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="w-full max-w-md p-8 space-y-6">
        <div className="text-center space-y-2">
          <img
            src="/static/arena_logo_app_small.png"
            alt="CEC-codex"
            className="w-16 h-16 mx-auto mb-4"
          />
          <h1 className="text-2xl font-bold">
            {t('hyperAi.onboarding.welcome', 'Welcome to CEC-codex')}
          </h1>
          <p className="text-muted-foreground">
            {t('hyperAi.onboarding.configureAi', 'Configure Hyper AI to get started')}
          </p>
        </div>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label>{t('hyperAi.onboarding.provider', 'AI Provider')}</Label>
            <Select value={selectedProvider} onValueChange={onProviderChange}>
              <SelectTrigger>
                <SelectValue placeholder={t('hyperAi.onboarding.selectProvider', 'Select provider')} />
              </SelectTrigger>
              <SelectContent>
                {providers.map(provider => (
                  <SelectItem key={provider.id} value={provider.id}>
                    {provider.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {isCustomProvider(selectedProvider) && (
            <div className="space-y-2">
              <Label>{t('hyperAi.onboarding.baseUrl', 'Base URL')}</Label>
              <Input
                value={customBaseUrl}
                onChange={event => onCustomBaseUrlChange(event.target.value)}
                placeholder="https://api.example.com/v1"
              />
            </div>
          )}

          <div className="space-y-2">
            <Label>{t('hyperAi.onboarding.apiKey', 'API Key')}</Label>
            <Input
              type="password"
              value={apiKey}
              onChange={event => onApiKeyChange(event.target.value)}
              placeholder="sk-..."
            />
          </div>

          {selectedProvider && (
            <div className="space-y-2">
              <Label>{t('hyperAi.onboarding.model', 'Model')}</Label>
              <div className="flex gap-1">
                <Input
                  value={modelInput}
                  onChange={event => onModelInputChange(event.target.value)}
                  placeholder={t('hyperAi.onboarding.modelPlaceholder', 'Enter or select model')}
                  className="flex-1"
                />
                {hasProviderModels(currentProvider) && (
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="outline" size="icon" className="shrink-0">
                        <ChevronDown className="w-4 h-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="max-h-60 overflow-y-auto">
                      {providerModels.map(model => (
                        <DropdownMenuItem key={model} onClick={() => onModelInputChange(model)}>
                          {model}
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
            <AlertCircle className="w-4 h-4" />
            {error}
          </div>
        )}

        {testResult === 'success' && (
          <div className="flex items-center gap-2 text-green-600 text-sm">
            <CheckCircle2 className="w-4 h-4" />
            {t('hyperAi.onboarding.connectionSuccess', 'Connection successful!')}
          </div>
        )}

        <div className="flex gap-3">
          <Button variant="ghost" onClick={onSkip} className="flex-1">
            {t('common.skip', 'Skip')}
          </Button>
          <Button
            onClick={onContinue}
            disabled={!selectedProvider || !apiKey || testing}
            className="flex-1"
          >
            {testing ? (
              <Loader2 className="w-4 h-4 animate-spin mr-2" />
            ) : (
              <ArrowRight className="w-4 h-4 mr-2" />
            )}
            {t('common.next', 'Continue')}
          </Button>
        </div>
      </div>
    </div>
  )
}
