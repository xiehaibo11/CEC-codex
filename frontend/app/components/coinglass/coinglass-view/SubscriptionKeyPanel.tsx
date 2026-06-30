import { KeyRound, Trash2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { displayError, displayPlan } from './formatters'
import type { CoinGlassSubscription } from './types'

interface SubscriptionKeyPanelProps {
  subscription: CoinGlassSubscription | null
  apiKeyInput: string
  savingKey: boolean
  onApiKeyInputChange: (value: string) => void
  onSave: () => void
  onDelete: () => void
}

export function SubscriptionKeyPanel({
  subscription,
  apiKeyInput,
  savingKey,
  onApiKeyInputChange,
  onSave,
  onDelete,
}: SubscriptionKeyPanelProps) {
  return (
    <Card className="flex-shrink-0">
      <CardContent className="flex flex-col gap-3 p-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <KeyRound className="h-4 w-4 text-primary" />
            <div className="text-sm font-medium">CoinGlass API 密钥</div>
            {subscription?.user_key_configured ? (
              <Badge variant="secondary">个人密钥</Badge>
            ) : subscription?.server_key_configured ? (
              <Badge variant="outline">服务器密钥</Badge>
            ) : (
              <Badge variant="destructive">未配置</Badge>
            )}
          </div>
          <div className="mt-1 text-xs text-muted-foreground">
            {subscription?.configured
              ? `正在使用${subscription.key_source === 'user' ? '个人密钥' : '服务器密钥'}${subscription.key_masked ? ` ${subscription.key_masked}` : ''}。当前等级：${subscription.level ? displayPlan(subscription.level) : '已配置'}`
              : subscription?.reason
                ? `当前 CoinGlass 密钥不可用：${displayError(subscription.reason)}。请保存有效的个人密钥或更新本地服务器密钥。`
                : '添加个人 CoinGlass 密钥后，将优先使用你的密钥查询付费接口。'}
          </div>
        </div>
        <div className="grid w-full grid-cols-1 gap-2 sm:grid-cols-[minmax(240px,420px)_auto_auto] lg:w-auto">
          <Input
            type="password"
            value={apiKeyInput}
            onChange={(event) => onApiKeyInputChange(event.target.value)}
            placeholder={subscription?.user_key_configured ? '输入新的密钥以替换当前个人密钥' : '粘贴你的 CoinGlass API 密钥'}
            autoComplete="off"
          />
          <Button onClick={onSave} disabled={savingKey || !apiKeyInput.trim()}>
            <KeyRound className="h-4 w-4" />
            {savingKey ? '保存中' : '保存密钥'}
          </Button>
          <Button
            variant="outline"
            onClick={onDelete}
            disabled={savingKey || !subscription?.user_key_configured}
          >
            <Trash2 className="h-4 w-4" />
            删除
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
