import { useTranslation } from 'react-i18next'
import { PanelLeftOpen } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface ChatHeaderProps {
  sidebarCollapsed: boolean
  onExpandSidebar: () => void
}

export function ChatHeader({ sidebarCollapsed, onExpandSidebar }: ChatHeaderProps) {
  const { t } = useTranslation()

  if (!sidebarCollapsed) return null

  return (
    <Button
      variant="ghost"
      size="sm"
      className="absolute top-2 left-2 z-10 px-2"
      onClick={onExpandSidebar}
      title={t('hyperAi.expandSidebar', 'Expand sidebar')}
    >
      <PanelLeftOpen className="w-4 h-4" />
    </Button>
  )
}
