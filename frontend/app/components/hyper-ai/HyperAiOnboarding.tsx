/**
 * HyperAiOnboarding - Full-screen onboarding overlay for Hyper AI setup
 * Step 1: LLM Provider configuration
 * Step 2: AI connectivity test + chat for user profile
 * Step 3: Completion message
 */
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ChatStep } from './onboarding/ChatStep'
import { ProviderConfigStep } from './onboarding/ProviderConfigStep'
import {
  buildLlmProfilePayload,
  getDefaultModelForProvider,
  getProviderById,
  isCustomProvider,
} from './onboarding/providerHelpers'
import type {
  HyperAiOnboardingProps,
  LLMProvider,
  OnboardingStep,
  TestResult,
} from './onboarding/types'

export default function HyperAiOnboarding({ onComplete, onSkip }: HyperAiOnboardingProps) {
  const { t, i18n } = useTranslation()
  const [step, setStep] = useState<OnboardingStep>('config')
  const [providers, setProviders] = useState<LLMProvider[]>([])
  const [selectedProvider, setSelectedProvider] = useState<string>('')
  const [apiKey, setApiKey] = useState('')
  const [modelInput, setModelInput] = useState('')
  const [customBaseUrl, setCustomBaseUrl] = useState('')
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<TestResult>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    const browserLang = navigator.language.toLowerCase()
    if (browserLang.startsWith('zh') && i18n.language !== 'zh') {
      void i18n.changeLanguage('zh')
    }
  }, [i18n])

  useEffect(() => {
    void fetchProviders()
  }, [])

  const currentProvider = getProviderById(providers, selectedProvider)

  useEffect(() => {
    if (selectedProvider && currentProvider && currentProvider.models.length > 0 && !modelInput) {
      setModelInput(getDefaultModelForProvider(currentProvider))
    }
  }, [selectedProvider, currentProvider])

  const fetchProviders = async () => {
    try {
      const res = await fetch('/api/hyper-ai/providers')
      const data = await res.json()
      setProviders(data.providers || [])
    } catch (e) {
      console.error('Failed to fetch providers:', e)
    }
  }

  const handleProviderChange = (value: string) => {
    setSelectedProvider(value)
    setModelInput('')
  }

  const handleTestAndContinue = async () => {
    if (!selectedProvider || !apiKey) {
      setError(t('hyperAi.onboarding.fillRequired', 'Please fill in all required fields'))
      return
    }

    if (isCustomProvider(selectedProvider) && !customBaseUrl) {
      setError(t('hyperAi.onboarding.baseUrlRequired', 'Base URL is required for custom provider'))
      return
    }

    setTesting(true)
    setError('')
    setTestResult(null)

    try {
      const saveRes = await fetch('/api/hyper-ai/profile/llm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildLlmProfilePayload({
          provider: selectedProvider,
          apiKey,
          model: modelInput,
          customBaseUrl,
        })),
      })

      if (!saveRes.ok) {
        const errData = await saveRes.json()
        throw new Error(errData.detail || 'Connection test failed')
      }

      setTestResult('success')
      setTimeout(() => setStep('chat'), 800)
    } catch (e) {
      setTestResult('error')
      setError(e instanceof Error ? e.message : 'Connection test failed')
    } finally {
      setTesting(false)
    }
  }

  if (step === 'chat') {
    return <ChatStep onSkip={onComplete} onComplete={onComplete} />
  }

  return (
    <ProviderConfigStep
      providers={providers}
      selectedProvider={selectedProvider}
      currentProvider={currentProvider}
      apiKey={apiKey}
      modelInput={modelInput}
      customBaseUrl={customBaseUrl}
      testing={testing}
      testResult={testResult}
      error={error}
      onProviderChange={handleProviderChange}
      onApiKeyChange={setApiKey}
      onModelInputChange={setModelInput}
      onCustomBaseUrlChange={setCustomBaseUrl}
      onSkip={onSkip}
      onContinue={handleTestAndContinue}
    />
  )
}
