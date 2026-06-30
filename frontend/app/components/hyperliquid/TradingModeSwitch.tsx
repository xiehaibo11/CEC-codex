/**
 * Global Trading Mode Switch
 *
 * Allows switching between Testnet and Mainnet for all AI Traders
 */

import { useState, useEffect } from 'react'
import toast from 'react-hot-toast'
import { Button } from '@/components/ui/button'
import { AlertTriangle, RefreshCw } from 'lucide-react'
import {
  getGlobalTradingMode,
  setGlobalTradingMode,
  type TradingModeInfo,
} from '@/lib/hyperliquidApi'

export default function TradingModeSwitch() {
  const [modeInfo, setModeInfo] = useState<TradingModeInfo | null>(null)
  const [loading, setLoading] = useState(false)
  const [switching, setSwitching] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [targetMode, setTargetMode] = useState<'testnet' | 'mainnet'>('testnet')

  useEffect(() => {
    loadModeInfo()
  }, [])

  const loadModeInfo = async () => {
    try {
      setLoading(true)
      const info = await getGlobalTradingMode()
      setModeInfo(info)
    } catch (error) {
      console.error('Failed to load trading mode:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSwitchClick = (newMode: 'testnet' | 'mainnet') => {
    setTargetMode(newMode)
    setShowConfirm(true)
  }

  const handleConfirmSwitch = async () => {
    try {
      setSwitching(true)
      const result = await setGlobalTradingMode(targetMode)

      if (result.success && result.changed) {
        toast.success(`✅ 已切换至${targetMode === 'mainnet' ? '主网' : '测试网'}`)
        await loadModeInfo()
      } else if (result.success && !result.changed) {
        toast(`当前已在${targetMode === 'mainnet' ? '主网' : '测试网'}`)
      } else {
        toast.error('切换交易模式失败')
      }

      setShowConfirm(false)
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to switch mode'
      toast.error(message)
    } finally {
      setSwitching(false)
    }
  }

  if (loading && !modeInfo) {
    return (
      <div className="p-6 border rounded-lg">
        <div className="flex items-center justify-center">
          <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      </div>
    )
  }

  const isTestnet = modeInfo?.mode === 'testnet'

  return (
    <div className="p-6 border rounded-lg space-y-4">
      <div>
        <h3 className="text-lg font-medium mb-1">全局交易环境</h3>
        <p className="text-sm text-muted-foreground">
          控制所有AI交易员连接的网络环境
        </p>
      </div>

      {/* Current Mode Display */}
      <div className="p-4 rounded-lg bg-muted">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm text-muted-foreground mb-1">当前模式</div>
            <div className="flex items-center gap-2">
              <div
                className={`text-2xl font-bold ${
                  isTestnet ? 'text-green-600' : 'text-orange-600'
                }`}
              >
                {isTestnet ? '测试网' : '主网'}
              </div>
            </div>
            <div className="text-sm text-muted-foreground mt-1">
              {modeInfo?.description}
            </div>
          </div>
        </div>
      </div>

      {/* Mode Switch Buttons */}
      {!showConfirm ? (
        <div className="grid grid-cols-2 gap-3">
          <Button
            variant={isTestnet ? 'default' : 'outline'}
            onClick={() => handleSwitchClick('testnet')}
            disabled={isTestnet}
            className="h-20 flex-col"
          >
            <div className="text-lg font-semibold mb-1">TEST</div>
            <div>测试网</div>
            <div className="text-xs opacity-70">模拟交易</div>
          </Button>
          <Button
            variant={!isTestnet ? 'default' : 'outline'}
            onClick={() => handleSwitchClick('mainnet')}
            disabled={!isTestnet}
            className="h-20 flex-col"
          >
            <div className="text-lg font-semibold mb-1">MAIN</div>
            <div>主网</div>
            <div className="text-xs opacity-70">真实资金</div>
          </Button>
        </div>
      ) : (
        /* Confirmation Dialog */
        <div className="p-4 border-2 border-orange-500 rounded-lg space-y-3">
          <div className="flex items-start gap-2">
            <AlertTriangle className="h-5 w-5 text-orange-500 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <div className="font-medium text-orange-700">
                {targetMode === 'mainnet'
                  ? '切换到主网？'
                  : '切换回测试网？'}
              </div>
              <div className="text-sm text-muted-foreground mt-1">
                {targetMode === 'mainnet' ? (
                  <>
                    <p className="font-medium text-orange-700 mb-2">
                      ⚠️ 警告：此操作将使用真实资金！
                    </p>
                    <p>所有AI交易员将连接到Hyperliquid主网并用真实资金执行交易。请确认：</p>
                    <ul className="list-disc list-inside mt-1 space-y-1">
                      <li>所有策略已在测试网上充分验证</li>
                      <li>钱包地址余额充足</li>
                      <li>您了解其中涉及的风险</li>
                    </ul>
                  </>
                ) : (
                  <>
                    <p>所有AI交易员将切换至测试网（模拟交易），不会使用真实资金。</p>
                  </>
                )}
              </div>
            </div>
          </div>

          <div className="flex gap-2">
            <Button
              variant={targetMode === 'mainnet' ? 'destructive' : 'default'}
              onClick={handleConfirmSwitch}
              disabled={switching}
              className="flex-1"
            >
              {switching ? (
                <>
                  <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                  切换中...
                </>
              ) : (
                `确认切换至${targetMode === 'mainnet' ? '主网' : '测试网'}`
              )}
            </Button>
            <Button
              variant="outline"
              onClick={() => setShowConfirm(false)}
              disabled={switching}
            >
              取消
            </Button>
          </div>
        </div>
      )}

      {/* Info Box */}
      <div className="text-xs text-muted-foreground space-y-1">
        <p>
          • <strong>测试网：</strong>使用模拟资金的安全测试环境，适合策略开发验证。
        </p>
        <p>
          • <strong>主网：</strong>使用真实资金交易，仅在策略经过充分验证后切换。
        </p>
      </div>
    </div>
  )
}
