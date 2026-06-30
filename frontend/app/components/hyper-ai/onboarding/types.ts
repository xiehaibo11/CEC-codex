export interface LLMProvider {
  id: string
  name: string
  base_url: string
  models: string[]
  api_format: string
}

export interface HyperAiOnboardingProps {
  onComplete: () => void
  onSkip: () => void
}

export type OnboardingStep = 'config' | 'chat' | 'complete'

export type TestResult = 'success' | 'error' | null

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface LlmProfilePayload {
  provider: string
  api_key: string
  model: string
  base_url?: string
}
