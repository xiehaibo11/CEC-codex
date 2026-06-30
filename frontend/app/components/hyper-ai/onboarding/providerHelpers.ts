import type { LLMProvider, LlmProfilePayload } from './types'

export function getProviderById(providers: LLMProvider[], providerId: string) {
  return providers.find(provider => provider.id === providerId)
}

export function getDefaultModelForProvider(provider?: LLMProvider) {
  return provider?.models[0] ?? ''
}

export function hasProviderModels(provider?: LLMProvider) {
  return Boolean(provider?.models.length)
}

export function isCustomProvider(providerId: string) {
  return providerId === 'custom'
}

export function buildLlmProfilePayload({
  provider,
  apiKey,
  model,
  customBaseUrl,
}: {
  provider: string
  apiKey: string
  model: string
  customBaseUrl: string
}): LlmProfilePayload {
  return {
    provider,
    api_key: apiKey,
    model,
    base_url: isCustomProvider(provider) ? customBaseUrl : undefined,
  }
}
