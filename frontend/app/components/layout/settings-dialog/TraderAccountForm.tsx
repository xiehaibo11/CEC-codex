import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import type { AIAccountCreate } from './types'

interface TraderAccountFormProps {
  mode: 'create' | 'edit'
  account: AIAccountCreate
  onAccountChange: (account: AIAccountCreate) => void
  onSubmit: () => void
  onCancel: () => void
  loading: boolean
  testing?: boolean
  testResult?: string | null
}

export function TraderAccountForm({
  mode,
  account,
  onAccountChange,
  onSubmit,
  onCancel,
  loading,
  testing = false,
  testResult,
}: TraderAccountFormProps) {
  const isCreate = mode === 'create'
  const submitDisabled = isCreate ? loading : loading || testing
  const submitLabel = isCreate ? '测试并创建' : testing ? '测试中...' : '测试并保存'

  const content = (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <Input
          placeholder="交易员名称"
          value={account.name || ''}
          onChange={(e) => onAccountChange({ ...account, name: e.target.value })}
        />
        <Input
          placeholder={isCreate ? '模型（如 gpt-4）' : '模型'}
          value={account.model || ''}
          onChange={(e) => onAccountChange({ ...account, model: e.target.value })}
        />
      </div>
      <Input
        placeholder={isCreate ? 'Base URL (e.g., https://api.openai.com/v1)' : '基础URL'}
        value={account.base_url || ''}
        onChange={(e) => onAccountChange({ ...account, base_url: e.target.value })}
      />
      <Input
        placeholder="API密钥"
        type="password"
        value={account.api_key || ''}
        onChange={(e) => onAccountChange({ ...account, api_key: e.target.value })}
      />
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Switch
          checked={account.auto_trading_enabled ?? true}
          onCheckedChange={(checked) => onAccountChange({ ...account, auto_trading_enabled: checked })}
        />
        <span>启动交易</span>
      </div>
      {testResult && (
        <div
          className={
            isCreate
              ? 'text-sm text-muted-foreground'
              : `text-xs p-2 rounded ${
                  testResult.includes('❌')
                    ? 'bg-red-50 text-red-700 border border-red-200'
                    : 'bg-green-50 text-green-700 border border-green-200'
                }`
          }
        >
          {testResult}
        </div>
      )}
      <div className="flex gap-2">
        <Button onClick={onSubmit} disabled={submitDisabled} size={isCreate ? undefined : 'sm'}>
          {submitLabel}
        </Button>
        <Button
          variant="outline"
          onClick={onCancel}
          disabled={isCreate ? false : loading || testing}
          size={isCreate ? undefined : 'sm'}
        >
          取消
        </Button>
      </div>
    </div>
  )

  if (!isCreate) {
    return content
  }

  return (
    <div className="space-y-4 border rounded-lg p-4 bg-muted/50">
      <h3 className="text-lg font-medium">添加新AI交易员</h3>
      {content}
    </div>
  )
}
