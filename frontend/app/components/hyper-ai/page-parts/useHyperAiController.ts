import { useState, useEffect, useRef, type KeyboardEvent } from 'react'
import { useTranslation } from 'react-i18next'
import type { ToolInfo } from '../ToolConfigModal'
import { pollHyperAiTaskResponse } from './hyperAiTaskStream'
import type {
  BotConfig,
  CompressionPoint,
  Conversation,
  DiscordBotConfig,
  LLMProvider,
  Message,
  SkillInfo,
  TokenUsage,
} from './types'

export function useHyperAiController() {
  const { t, i18n } = useTranslation()
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [currentConvId, setCurrentConvId] = useState<number | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [compressionPoints, setCompressionPoints] = useState<CompressionPoint[]>([])
  const [tokenUsage, setTokenUsage] = useState<TokenUsage | null>(null)
  const [inputValue, setInputValue] = useState('')
  const [sending, setSending] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')
  const [providers, setProviders] = useState<LLMProvider[]>([])
  const [profile, setProfile] = useState<any>(null)
  const [nickname, setNickname] = useState<string>('')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [showConfig, setShowConfig] = useState(true)
  const [showConfigModal, setShowConfigModal] = useState(false)
  const [showMemoryModal, setShowMemoryModal] = useState(false)
  const [skills, setSkills] = useState<SkillInfo[]>([])
  const [activeSkill, setActiveSkill] = useState<string | null>(null)
  const [skillsLoading, setSkillsLoading] = useState(false)
  const [skillsEditMode, setSkillsEditMode] = useState(false)
  const [pendingSkillToggles, setPendingSkillToggles] = useState<Record<string, boolean>>({})
  const [showBotModal, setShowBotModal] = useState(false)
  const [showDiscordBotModal, setShowDiscordBotModal] = useState(false)
  const [botConfig, setBotConfig] = useState<BotConfig | null>(null)
  const [discordBotConfig, setDiscordBotConfig] = useState<DiscordBotConfig | null>(null)
  const [showNotificationModal, setShowNotificationModal] = useState(false)
  const [notificationCount, setNotificationCount] = useState(0)
  const [externalTools, setExternalTools] = useState<ToolInfo[]>([])
  const [showToolModal, setShowToolModal] = useState(false)
  const [selectedTool, setSelectedTool] = useState<ToolInfo | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const currentLang = i18n.language?.startsWith('zh') ? 'zh' : 'en'

  useEffect(() => {
    fetchConversations()
    fetchProviders()
    fetchProfile()
    fetchSkills()
    fetchBotConfig()
    fetchDiscordBotConfig()
    fetchNotificationConfig()
    fetchExternalTools()
  }, [])

  useEffect(() => {
    if (currentConvId && !sending) {
      fetchMessages(currentConvId)
    }
  }, [currentConvId])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

  useEffect(() => {
    const pending = localStorage.getItem('hyper-ai-pending-prompt')
    if (pending) {
      localStorage.removeItem('hyper-ai-pending-prompt')
      setInputValue(pending)
      setTimeout(() => textareaRef.current?.focus(), 200)
    }
  }, [])

  const fetchBotConfig = async () => {
    try {
      const res = await fetch('/api/bot/config/telegram')
      const data = await res.json()
      setBotConfig(data.config || null)
    } catch (e) {
      console.error('Failed to fetch bot config:', e)
    }
  }

  const fetchDiscordBotConfig = async () => {
    try {
      const res = await fetch('/api/bot/config/discord')
      const data = await res.json()
      setDiscordBotConfig(data.config || null)
    } catch (e) {
      console.error('Failed to fetch discord bot config:', e)
    }
  }

  const fetchNotificationConfig = async () => {
    try {
      const res = await fetch('/api/bot/notification-config')
      const data = await res.json()
      const cfg = data.config || { ai_trader: true, program_trader: true, signal_pools: {} }
      let count = 0
      if (cfg.ai_trader) count++
      if (cfg.program_trader) count++
      count += Object.values(cfg.signal_pools as Record<string, boolean>).filter(Boolean).length
      setNotificationCount(count)
    } catch (e) {
      console.error('Failed to fetch notification config:', e)
    }
  }

  const fetchExternalTools = async () => {
    try {
      const res = await fetch('/api/hyper-ai/tools')
      const data = await res.json()
      setExternalTools(data.tools || [])
    } catch (e) {
      console.error('Failed to fetch external tools:', e)
    }
  }

  const fetchConversations = async () => {
    try {
      const res = await fetch('/api/hyper-ai/conversations')
      const data = await res.json()
      setConversations(data.conversations || [])
    } catch (e) {
      console.error('Failed to fetch conversations:', e)
    }
  }

  const fetchMessages = async (convId: number) => {
    try {
      const res = await fetch(`/api/hyper-ai/conversations/${convId}/messages`)
      const data = await res.json()
      setMessages(data.messages || [])
      setCompressionPoints(data.compression_points || [])
      setTokenUsage(data.token_usage || null)
    } catch (e) {
      console.error('Failed to fetch messages:', e)
    }
  }

  const fetchProviders = async () => {
    try {
      const res = await fetch('/api/hyper-ai/providers')
      const data = await res.json()
      setProviders(data.providers || [])
    } catch (e) {
      console.error('Failed to fetch providers:', e)
    }
  }

  const fetchProfile = async () => {
    try {
      const res = await fetch('/api/hyper-ai/profile')
      const data = await res.json()
      setProfile(data)
      if (data.nickname) {
        setNickname(data.nickname)
      }
    } catch (e) {
      console.error('Failed to fetch profile:', e)
    }
  }

  const fetchSkills = async () => {
    try {
      const res = await fetch('/api/hyper-ai/skills')
      const data = await res.json()
      setSkills(data.skills || [])
    } catch (e) {
      console.error('Failed to fetch skills:', e)
    }
  }

  const handleSkillsEditSave = async () => {
    setSkillsLoading(true)
    try {
      for (const [name, enabled] of Object.entries(pendingSkillToggles)) {
        await fetch(`/api/hyper-ai/skills/${name}/toggle`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ enabled })
        })
      }
      setSkills(prev => prev.map(s =>
        pendingSkillToggles[s.name] !== undefined
          ? { ...s, enabled: pendingSkillToggles[s.name] }
          : s
      ))
    } catch (e) {
      console.error('Failed to save skill toggles:', e)
    } finally {
      setSkillsLoading(false)
      setSkillsEditMode(false)
      setPendingSkillToggles({})
    }
  }

  const handleSkillsEditCancel = () => {
    setSkillsEditMode(false)
    setPendingSkillToggles({})
  }

  const handleNewConversation = () => {
    setCurrentConvId(null)
    setMessages([])
    setCompressionPoints([])
    setTokenUsage(null)
    setActiveSkill(null)
  }

  const handleSend = async () => {
    if (!inputValue.trim() || sending) return

    const userMessage = inputValue.trim()
    setInputValue('')
    setSending(true)
    setStreamingContent('')

    setMessages(prev => [
      ...prev,
      { role: 'user', content: userMessage },
      {
        role: 'assistant',
        content: '',
        isStreaming: true,
        statusText: t('hyperAi.connecting', 'Connecting...'),
        toolCalls: []
      }
    ])

    try {
      const res = await fetch('/api/hyper-ai/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userMessage,
          conversation_id: currentConvId,
          lang: currentLang
        })
      })

      const data = await res.json()
      if (data.task_id) {
        pollTaskResponse(data.task_id, data.conversation_id)
        if (!currentConvId) {
          setCurrentConvId(data.conversation_id)
        }
      }
    } catch (e) {
      console.error('Failed to send message:', e)
      setMessages(prev => prev.slice(0, -1))
      setSending(false)
    }
  }

  const handleSuggestionClick = (question: string) => {
    setInputValue(question)
    setTimeout(() => handleSend(), 100)
  }

  const handleToolConfirmation = async (taskId: string, confirmationId: string, confirmed: boolean) => {
    const nextStatus = confirmed ? 'confirmed' : 'cancelled'
    setMessages(prev => prev.map(message => ({
      ...message,
      toolCalls: message.toolCalls?.map(entry =>
        entry.type === 'confirmation_required' && entry.confirmationId === confirmationId
          ? { ...entry, status: nextStatus }
          : entry
      )
    })))

    try {
      const res = await fetch('/api/hyper-ai/confirm-tool', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task_id: taskId,
          confirmation_id: confirmationId,
          confirmed,
        }),
      })
      if (!res.ok) {
        throw new Error(`Confirmation failed: ${res.status}`)
      }
    } catch (e) {
      console.error('Failed to submit tool confirmation:', e)
      setMessages(prev => prev.map(message => ({
        ...message,
        toolCalls: message.toolCalls?.map(entry =>
          entry.type === 'confirmation_required' && entry.confirmationId === confirmationId
            ? { ...entry, status: 'failed' }
            : entry
        )
      })))
    }
  }

  const pollTaskResponse = async (taskId: string, convId: number) => {
    await pollHyperAiTaskResponse({
      taskId,
      convId,
      currentConvId,
      t,
      messagesEndRef,
      fetchMessages,
      fetchConversations,
      setCurrentConvId,
      setMessages,
      setStreamingContent,
      setTokenUsage,
      setCompressionPoints,
      setActiveSkill,
      setSending,
    })
  }

  const handleContinue = () => {
    setInputValue(t('hyperAi.continueMessage', 'Please continue'))
    setTimeout(() => handleSend(), 100)
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const openToolConfig = (tool: ToolInfo) => {
    setSelectedTool(tool)
    setShowToolModal(true)
  }

  const closeToolConfig = () => {
    setShowToolModal(false)
    setSelectedTool(null)
  }

  return {
    t,
    conversations,
    currentConvId,
    messages,
    compressionPoints,
    tokenUsage,
    inputValue,
    sending,
    providers,
    profile,
    nickname,
    sidebarCollapsed,
    showConfig,
    showConfigModal,
    showMemoryModal,
    skills,
    activeSkill,
    skillsLoading,
    skillsEditMode,
    pendingSkillToggles,
    showBotModal,
    showDiscordBotModal,
    botConfig,
    discordBotConfig,
    showNotificationModal,
    notificationCount,
    externalTools,
    showToolModal,
    selectedTool,
    currentLang,
    messagesEndRef,
    textareaRef,
    setInputValue,
    setSidebarCollapsed,
    setShowConfig,
    setShowConfigModal,
    setShowMemoryModal,
    setSkillsEditMode,
    setPendingSkillToggles,
    setShowBotModal,
    setShowDiscordBotModal,
    setShowNotificationModal,
    setNotificationCount,
    handleSkillsEditSave,
    handleSkillsEditCancel,
    handleNewConversation,
    handleSend,
    handleSuggestionClick,
    handleToolConfirmation,
    handleContinue,
    handleKeyDown,
    setCurrentConvId,
    fetchProfile,
    fetchBotConfig,
    fetchDiscordBotConfig,
    fetchExternalTools,
    openToolConfig,
    closeToolConfig,
  }
}
