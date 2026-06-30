import { Search as SearchIcon, Wrench } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { ToolInfo } from '../ToolConfigModal'

interface ToolPanelProps {
  tools: ToolInfo[]
  currentLang: 'zh' | 'en'
  onSelectTool: (tool: ToolInfo) => void
}

interface ToolCardProps {
  tool: ToolInfo
  currentLang: 'zh' | 'en'
  onSelectTool: (tool: ToolInfo) => void
}

export function ToolCard({ tool, currentLang, onSelectTool }: ToolCardProps) {
  const { t } = useTranslation()

  return (
    <div
      key={tool.name}
      className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-muted/30 hover:bg-muted/50 cursor-pointer transition-colors"
      onClick={() => onSelectTool(tool)}
    >
      <SearchIcon className="w-3.5 h-3.5 shrink-0 text-muted-foreground" />
      <span className="text-xs truncate flex-1">
        {currentLang === 'zh' ? tool.display_name_zh : tool.display_name}
      </span>
      {tool.configured ? (
        <span className="w-2 h-2 rounded-full bg-green-500 shrink-0"></span>
      ) : (
        <span className="text-[10px] text-primary shrink-0">
          {t('tools.setup', 'Setup')}
        </span>
      )}
    </div>
  )
}

export function ToolPanel({ tools, currentLang, onSelectTool }: ToolPanelProps) {
  const { t } = useTranslation()

  if (tools.length === 0) return null

  return (
    <div className="pt-4">
      <h4 className="text-sm font-medium flex items-center gap-1.5 mb-2">
        <Wrench className="w-4 h-4 shrink-0" />
        {t('hyperAi.tools', 'Tools')}
      </h4>
      <div className="space-y-1">
        {tools.map(tool => (
          <ToolCard
            key={tool.name}
            tool={tool}
            currentLang={currentLang}
            onSelectTool={onSelectTool}
          />
        ))}
      </div>
    </div>
  )
}
