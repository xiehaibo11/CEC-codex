import { useEffect, useState } from 'react'
import { Bot } from 'lucide-react'

export function WelcomeMessage({
  nickname,
  t,
  onSuggestionClick
}: {
  nickname?: string
  t: any
  onSuggestionClick: (question: string) => void
}) {
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [isNewUser, setIsNewUser] = useState(true)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/hyper-ai/suggestions')
      .then(res => res.json())
      .then(data => {
        setSuggestions(data.suggestions || [])
        setIsNewUser(data.is_new_user ?? true)
      })
      .catch(() => {
        setSuggestions([])
        setIsNewUser(true)
      })
      .finally(() => setLoading(false))
  }, [])

  const greeting = nickname
    ? t('hyperAi.welcomeWithName', { name: nickname, defaultValue: `你好，${nickname}！我是 Hyper AI，你的专属交易助手。` })
    : t('hyperAi.welcomeNoName', '你好！我是 Hyper AI，CEC-codex 的智能助手。')

  // Default suggestions for new users (follows i18n)
  const defaultSuggestions = [
    t('hyperAi.defaultSuggestions.intro', 'What can you help me with?'),
    t('hyperAi.defaultSuggestions.setup', 'Guide me through the initial setup'),
    t('hyperAi.defaultSuggestions.first', 'I want to create my first trading strategy'),
    t('hyperAi.defaultSuggestions.strategyRadar', 'Help me find strategy ideas from Strategy Radar'),
    t('hyperAi.defaultSuggestions.walletSignals', 'How do I connect CoinGlass wallet signals?'),
  ]

  const displaySuggestions = (isNewUser || suggestions.length === 0) ? defaultSuggestions : suggestions

  return (
    <div className="flex flex-col items-center justify-center h-full text-center px-4">
      <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mb-4">
        <Bot className="w-8 h-8 text-primary" />
      </div>
      <p className="text-lg mb-4">{greeting}</p>
      <div className="text-sm text-muted-foreground space-y-1 max-w-md">
        <p>{t('hyperAi.welcomeCapabilities', '我可以帮你：')}</p>
        <ul className="text-left list-disc list-inside space-y-1 mt-2">
          <li>{t('hyperAi.capability1', '了解系统功能和使用方法')}</li>
          <li>{t('hyperAi.capability2', '生成和优化 AI 交易策略')}</li>
          <li>{t('hyperAi.capability3', '管理 AI 交易员和钱包配置')}</li>
          <li>{t('hyperAi.capability4', '分析市场数据和交易表现')}</li>
        </ul>
        <p className="mt-4">{t('hyperAi.welcomePrompt', '有什么想了解的，直接问我就行。')}</p>
      </div>

      {/* Suggestion buttons */}
      {!loading && displaySuggestions.length > 0 && (
        <div className="mt-6 space-y-2 w-full max-w-md">
          {displaySuggestions.map((question, idx) => (
            <button
              key={idx}
              onClick={() => onSuggestionClick(question)}
              className="w-full px-4 py-3 text-left text-sm rounded-lg border border-border bg-card hover:bg-accent hover:border-primary/50 transition-colors"
            >
              {question}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
