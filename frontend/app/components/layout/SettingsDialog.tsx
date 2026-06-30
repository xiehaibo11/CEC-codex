import { useState, useEffect } from 'react'
import toast from 'react-hot-toast'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Plus } from 'lucide-react'
import { getAccounts, createAccount, updateAccount, testLLMConnection, exportTraderData, type UnauthorizedAccount } from '@/lib/api'
import { connectBrowserWallet, checkBuilderFeeAuthorized, approveBuilderFee } from '@/lib/hyperliquidWalletSetup'
import { AuthorizationModal } from '@/components/hyperliquid'
import TraderDataImportDialog from '@/components/trader/TraderDataImportDialog'
import { useTranslation } from 'react-i18next'
import { TraderAccountCard } from './settings-dialog/TraderAccountCard'
import { TraderAccountForm } from './settings-dialog/TraderAccountForm'
import type { AIAccount, AIAccountCreate } from './settings-dialog/types'

interface SettingsDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onAccountUpdated?: () => void  // Add callback for when account is updated
  embedded?: boolean  // Add embedded mode support
}

function formatDependencies(deps: string[], t: (key: string) => string): string {
  const keyMap: [RegExp, string][] = [
    [/Prompt binding/i, 'common.dependencyPromptBinding'],
    [/Program binding/i, 'common.dependencyProgramBinding'],
    [/Open position/i, 'common.dependencyOpenPosition'],
    [/Signal Pool/i, 'common.dependencySignalPool'],
    [/Bound to.*Trader/i, 'common.dependencyActiveBinding'],
    [/is currently active/i, 'common.dependencyBindingActive'],
  ]
  const messages = new Set<string>()
  for (const dep of deps) {
    const match = keyMap.find(([re]) => re.test(dep))
    messages.add(match ? t(match[1]) : dep)
  }
  return Array.from(messages).join(' ')
}

export default function SettingsDialog({ open, onOpenChange, onAccountUpdated, embedded = false }: SettingsDialogProps) {
  const { t } = useTranslation()
  const [accounts, setAccounts] = useState<AIAccount[]>([])
  const [loading, setLoading] = useState(false)
  const [toggleLoadingId, setToggleLoadingId] = useState<number | null>(null)
  const [showAddForm, setShowAddForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<string | null>(null)
  const [testing, setTesting] = useState(false)
  const [authModalOpen, setAuthModalOpen] = useState(false)
  const [unauthorizedAccounts, setUnauthorizedAccounts] = useState<UnauthorizedAccount[]>([])
  const [importDialogOpen, setImportDialogOpen] = useState(false)
  const [importTargetAccount, setImportTargetAccount] = useState<AIAccount | null>(null)
  const [newAccount, setNewAccount] = useState<AIAccountCreate>({
    name: '',
    model: '',
    base_url: '',
    api_key: 'default-key-please-update-in-settings',
    auto_trading_enabled: true,
  })
  const [editAccount, setEditAccount] = useState<AIAccountCreate>({
    name: '',
    model: '',
    base_url: '',
    api_key: 'default-key-please-update-in-settings',
    auto_trading_enabled: true,
  })

  const loadAccounts = async () => {
    try {
      setLoading(true)
      const data = await getAccounts()
      setAccounts(data)
    } catch (error) {
      console.error('Failed to load accounts:', error)
      toast.error('Failed to load AI traders')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (open) {
      loadAccounts()
      setError(null)
      setTestResult(null)
      setShowAddForm(false)
      setEditingId(null)
    }
  }, [open])

  const handleCreateAccount = async () => {
    try {
      setLoading(true)
      setTesting(true)
      setError(null)
      setTestResult(null)

      if (!newAccount.name || !newAccount.name.trim()) {
        setError('交易员名称不能为空')
        setLoading(false)
        setTesting(false)
        return
      }

      // If AI fields are provided, test LLM connection first
      if (newAccount.model || newAccount.base_url || newAccount.api_key) {
        setTestResult('正在测试LLM连接...')
        try {
          const testResponse = await testLLMConnection({
            model: newAccount.model,
            base_url: newAccount.base_url,
            api_key: newAccount.api_key,
          })
          if (!testResponse.success) {
            const message = testResponse.message || 'LLM连接测试失败'
            setError(`LLM测试失败：${message}`)
            setTestResult(`❌ 测试失败：${message}`)
            setLoading(false)
            setTesting(false)
            return
          }
          setTestResult('✅ LLM连接测试通过！正在创建AI交易员...')
        } catch (testError) {
          const message = testError instanceof Error ? testError.message : 'LLM连接测试失败'
          setError(`LLM测试失败：${message}`)
          setTestResult(`❌ 测试失败：${message}`)
          setLoading(false)
          setTesting(false)
          return
        }
      }

      console.log('Creating account with data:', newAccount)
      await createAccount(newAccount)
      setNewAccount({ name: '', model: '', base_url: '', api_key: 'default-key-please-update-in-settings', auto_trading_enabled: true })
      setShowAddForm(false)
      await loadAccounts()

      toast.success('AI交易员创建成功！')

      // Notify parent component that account was created
      onAccountUpdated?.()
    } catch (error) {
      console.error('Failed to create account:', error)
      const errorMessage = error instanceof Error ? error.message : '创建AI交易员失败'
      setError(errorMessage)
      toast.error(`创建AI交易员失败：${errorMessage}`)
    } finally {
      setLoading(false)
      setTesting(false)
      setTestResult(null)
    }
  }

  const handleUpdateAccount = async () => {
    if (!editingId) return
    try {
      setLoading(true)
      setTesting(true)
      setError(null)
      setTestResult(null)
      
      if (!editAccount.name || !editAccount.name.trim()) {
        setError('交易员名称不能为空')
        setLoading(false)
        setTesting(false)
        return
      }
      
      // Test LLM connection first if AI model data is provided
      if (editAccount.model || editAccount.base_url || editAccount.api_key) {
        setTestResult('正在测试LLM连接...')
        
        try {
          const testResponse = await testLLMConnection({
            model: editAccount.model,
            base_url: editAccount.base_url,
            api_key: editAccount.api_key
          })
          
          if (!testResponse.success) {
            setError(`LLM测试失败：${testResponse.message}`)
            setTestResult(`❌ 测试失败：${testResponse.message}`)
            setLoading(false)
            setTesting(false)
            return
          }

          setTestResult('✅ LLM连接测试通过！')
        } catch (testError) {
          const errorMessage = testError instanceof Error ? testError.message : 'LLM连接测试失败'
          setError(`LLM测试失败：${errorMessage}`)
          setTestResult(`❌ 测试失败：${errorMessage}`)
          setLoading(false)
          setTesting(false)
          return
        }
      }
      
      setTesting(false)
      setTestResult('测试通过！正在保存AI交易员...')

      console.log('Updating account with data:', editAccount)
      await updateAccount(editingId, editAccount)
      setEditingId(null)
      setEditAccount({ name: '', model: '', base_url: '', api_key: '', auto_trading_enabled: true })
      setTestResult(null)
      await loadAccounts()
      
      toast.success('AI交易员更新成功！')
      
      // Notify parent component that account was updated
      onAccountUpdated?.()
    } catch (error) {
      console.error('Failed to update account:', error)
      const errorMessage = error instanceof Error ? error.message : '更新AI交易员失败'
      setError(errorMessage)
      setTestResult(null)
      toast.error(`更新AI交易员失败：${errorMessage}`)
    } finally {
      setLoading(false)
      setTesting(false)
    }
  }

  const startEdit = (account: AIAccount) => {
    setEditingId(account.id)
    setEditAccount({
      name: account.name,
      model: account.model || '',
      base_url: account.base_url || '',
      api_key: account.api_key || '',
      auto_trading_enabled: account.auto_trading_enabled ?? true,
    })
  }

  const cancelEdit = () => {
    setEditingId(null)
    setEditAccount({ name: '', model: '', base_url: '', api_key: 'default-key-please-update-in-settings', auto_trading_enabled: true })
    setTestResult(null)
    setError(null)
  }

  const handleToggleAutoTrading = async (account: AIAccount, nextValue: boolean) => {
    try {
      setToggleLoadingId(account.id)

      // If enabling trading and account has mainnet wallet, check builder fee via browser wallet
      if (nextValue && account.has_mainnet_wallet) {
        try {
          const masterAddress = await connectBrowserWallet()
          const authorized = await checkBuilderFeeAuthorized(masterAddress, 'mainnet')
          if (!authorized) {
            toast.loading(t('wallet.builder.signing', 'Please approve trading authorization in your wallet...'), { id: 'builder-auth' })
            await approveBuilderFee(masterAddress, 'mainnet')
            toast.dismiss('builder-auth')
            toast.success(t('wallet.builder.success', 'Trading authorization approved!'))
          }
        } catch (err: any) {
          toast.dismiss('builder-auth')
          console.error('Builder fee authorization failed:', err)
          if (err?.errorCode === 'NO_BROWSER_WALLET') {
            toast.error(t('wallet.error.noWallet', 'No browser wallet detected. Please install MetaMask or Rabby.'))
          } else if (err?.errorCode === 'NO_ACCOUNT_SELECTED') {
            toast.error(t('wallet.error.noAccount', 'No account selected in wallet. Please unlock your wallet and try again.'))
          } else if (err?.code === 4001) {
            toast.error(t('wallet.error.userRejected', 'Authorization rejected by user.'))
          } else {
            toast.error(t('wallet.error.authorizationFailedWrongAccount', 'Authorization failed. Please check that your wallet is switched to the correct account, then try again.'))
          }
          setToggleLoadingId(null)
          return
        }
      }

      await updateAccount(account.id, { auto_trading_enabled: nextValue })
      setAccounts((prev) =>
        prev.map((acc) => (acc.id === account.id ? { ...acc, auto_trading_enabled: nextValue } : acc))
      )
      toast.success(nextValue ? `已为 ${account.name} 启动自动交易` : `已为 ${account.name} 暂停自动交易`)
      onAccountUpdated?.()
    } catch (error) {
      console.error('Failed to toggle auto trading:', error)
      const errorMessage = error instanceof Error ? error.message : '更新交易状态失败'
      toast.error(errorMessage)
    } finally {
      setToggleLoadingId(null)
    }
  }

  const handleAuthorizationComplete = async () => {
    setAuthModalOpen(false)
    // After authorization complete, enable trading for the authorized accounts
    for (const account of unauthorizedAccounts) {
      try {
        await updateAccount(account.account_id, { auto_trading_enabled: true })
        setAccounts((prev) =>
          prev.map((acc) => (acc.id === account.account_id ? { ...acc, auto_trading_enabled: true } : acc))
        )
        toast.success(`Auto trading enabled for ${account.account_name}`)
      } catch (error) {
        console.error(`Failed to enable trading for ${account.account_name}:`, error)
      }
    }
    setUnauthorizedAccounts([])
    onAccountUpdated?.()
  }

  const handleAuthModalClose = () => {
    setAuthModalOpen(false)
    setUnauthorizedAccounts([])
    loadAccounts() // Reload to get updated trading status
  }

  const handleExport = async (account: AIAccount) => {
    try {
      const data = await exportTraderData(account.id)
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `trader-${account.name}-${new Date().toISOString().split('T')[0]}.json`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      toast.success(t('traderData.exportSuccess', { count: data.decision_logs.length }))
    } catch (error) {
      console.error('Export failed:', error)
      toast.error(t('traderData.exportFailed'))
    }
  }

  const handleImportClick = (account: AIAccount) => {
    setImportTargetAccount(account)
    setImportDialogOpen(true)
  }

  const handleImportComplete = () => {
    setImportDialogOpen(false)
    setImportTargetAccount(null)
    loadAccounts()
    onAccountUpdated?.()
  }

  const handleDeleteTrader = async (account: AIAccount) => {
    if (!confirm(t('trader.confirmDeleteDesc'))) return
    try {
      const res = await fetch(`/api/account/${account.id}`, { method: 'DELETE' })
      const data = await res.json()
      if (res.ok && data.deleted) {
        toast.success(t('common.delete') + ' OK')
        loadAccounts()
        onAccountUpdated?.()
      } else if (data.dependencies) {
        const msg = formatDependencies(data.dependencies, t)
        toast.error(`${t('common.cannotDelete')}: ${msg}`, { duration: 5000 })
      } else {
        toast.error(data.error || data.detail || 'Failed to delete')
      }
    } catch {
      toast.error('Failed to delete trader')
    }
  }

  const content = (
    <>
      {!embedded && (
        <DialogHeader>
          <DialogTitle>AI交易员管理</DialogTitle>
          <DialogDescription>
            管理AI交易员及其配置
          </DialogDescription>
        </DialogHeader>
      )}

        <div className="space-y-6">
          {/* Existing Accounts */}
          <div className="space-y-4 flex-1 flex flex-col overflow-hidden"  style={{maxHeight: 'calc(100vh - 300px)'}}>
            {error && (
            <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded">
              {error}
            </div>
          )}
            <div className="flex items-center justify-between">
              <Button
                onClick={() => setShowAddForm(!showAddForm)}
                size="sm"
                className="flex items-center gap-2"
              >
                <Plus className="h-4 w-4" />
                添加AI交易员
              </Button>
            </div>

            {loading && accounts.length === 0 ? (
              <div>加载AI交易员中...</div>
            ) : (
              <div className="space-y-3 overflow-y-auto">
                {/* Add New Account Form */}
                {showAddForm && (
                  <TraderAccountForm
                    mode="create"
                    account={newAccount}
                    onAccountChange={setNewAccount}
                    onSubmit={handleCreateAccount}
                    onCancel={() => setShowAddForm(false)}
                    loading={loading}
                    testResult={testResult}
                  />
                )}

                {accounts.map((account) => (
                  <TraderAccountCard
                    key={account.id}
                    account={account}
                    isEditing={editingId === account.id}
                    editAccount={editAccount}
                    onEditAccountChange={setEditAccount}
                    onSaveEdit={handleUpdateAccount}
                    onCancelEdit={cancelEdit}
                    loading={loading}
                    testing={testing}
                    testResult={testResult}
                    toggleLoadingId={toggleLoadingId}
                    onToggleAutoTrading={handleToggleAutoTrading}
                    onExport={handleExport}
                    onImportClick={handleImportClick}
                    onStartEdit={startEdit}
                    onDeleteTrader={handleDeleteTrader}
                    onWalletConfigured={loadAccounts}
                  />
                ))}
              </div>
            )}
          </div>

        </div>
    </>
  )

  if (embedded) {
    return (
      <>
        {content}
        <AuthorizationModal
          isOpen={authModalOpen}
          onClose={handleAuthModalClose}
          unauthorizedAccounts={unauthorizedAccounts}
          onAuthorizationComplete={handleAuthorizationComplete}
        />
        {importTargetAccount && (
          <TraderDataImportDialog
            open={importDialogOpen}
            onOpenChange={setImportDialogOpen}
            account={importTargetAccount}
            onImportComplete={handleImportComplete}
          />
        )}
      </>
    )
  }

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-[600px]">
          {content}
        </DialogContent>
      </Dialog>
      <AuthorizationModal
        isOpen={authModalOpen}
        onClose={handleAuthModalClose}
        unauthorizedAccounts={unauthorizedAccounts}
        onAuthorizationComplete={handleAuthorizationComplete}
      />
      {importTargetAccount && (
        <TraderDataImportDialog
          open={importDialogOpen}
          onOpenChange={setImportDialogOpen}
          account={importTargetAccount}
          onImportComplete={handleImportComplete}
        />
      )}
    </>
  )
}

export { SettingsDialog }
