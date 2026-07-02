/**
 * Binance Wallet Section - Testnet/Mainnet API key configuration
 *
 * Full wallet configuration UI for Binance Futures.
 * Uses API Key + Secret instead of private key (CEX vs DEX).
 */

import { useState, useEffect } from 'react'
import toast from 'react-hot-toast'
import { RefreshCw } from 'lucide-react'
import RebateIneligibleModal from '@/components/binance/RebateIneligibleModal'
import { BinanceWalletBlock } from './binance-wallet-section/BinanceWalletBlock'
import { getErrorMessage } from './binance-wallet-section/errors'
import type {
  BinanceWalletData,
  BinanceWalletEnvironment,
  MainnetQuota,
} from './binance-wallet-section/types'

interface BinanceWalletSectionProps {
  accountId: number
  accountName: string
  onStatusChange?: (env: 'testnet' | 'mainnet', configured: boolean) => void
  onWalletConfigured?: () => void
}

const API_BASE = '/api/binance'

export default function BinanceWalletSection({
  accountId,
  accountName,
  onStatusChange,
  onWalletConfigured
}: BinanceWalletSectionProps) {
  // Wallet data states
  const [testnetWallet, setTestnetWallet] = useState<BinanceWalletData | null>(null)
  const [mainnetWallet, setMainnetWallet] = useState<BinanceWalletData | null>(null)

  // Independent loading states
  const [loadingConfig, setLoadingConfig] = useState(false)
  const [savingTestnet, setSavingTestnet] = useState(false)
  const [savingMainnet, setSavingMainnet] = useState(false)
  const [testingTestnet, setTestingTestnet] = useState(false)
  const [testingMainnet, setTestingMainnet] = useState(false)

  // Editing states
  const [editingTestnet, setEditingTestnet] = useState(false)
  const [editingMainnet, setEditingMainnet] = useState(false)
  const [showTestnetKey, setShowTestnetKey] = useState(false)
  const [showMainnetKey, setShowMainnetKey] = useState(false)

  // Form states for testnet
  const [testnetApiKey, setTestnetApiKey] = useState('')
  const [testnetSecretKey, setTestnetSecretKey] = useState('')
  const [testnetMaxLeverage, setTestnetMaxLeverage] = useState(20)
  const [testnetDefaultLeverage, setTestnetDefaultLeverage] = useState(1)

  // Form states for mainnet
  const [mainnetApiKey, setMainnetApiKey] = useState('')
  const [mainnetSecretKey, setMainnetSecretKey] = useState('')
  const [mainnetMaxLeverage, setMainnetMaxLeverage] = useState(20)
  const [mainnetDefaultLeverage, setMainnetDefaultLeverage] = useState(1)

  // Rebate ineligible modal state
  const [showRebateModal, setShowRebateModal] = useState(false)
  const [rebateInfo, setRebateInfo] = useState<{ rebate_working: boolean; is_new_user: boolean } | undefined>()
  // Store pending mainnet binding params for confirm-limited-binding
  const [pendingMainnetBinding, setPendingMainnetBinding] = useState<{
    api_key: string
    secret_key: string
    max_leverage: number
    default_leverage: number
  } | null>(null)
  // Daily quota for mainnet non-rebate accounts
  const [mainnetQuota, setMainnetQuota] = useState<MainnetQuota | null>(null)

  useEffect(() => {
    loadWalletInfo()
  }, [accountId])

  const loadWalletInfo = async () => {
    try {
      setLoadingConfig(true)
      const res = await fetch(`${API_BASE}/accounts/${accountId}/config`)
      if (!res.ok) return

      const data = await res.json()
      const testnetConfigured = data.testnet_configured
      const mainnetConfigured = data.mainnet_configured

      onStatusChange?.('testnet', testnetConfigured)
      onStatusChange?.('mainnet', mainnetConfigured)

      if (testnetConfigured) {
        setTestnetWallet({
          configured: true,
          apiKeyMasked: data.testnet?.api_key_masked,
          maxLeverage: data.testnet?.max_leverage || 20,
          defaultLeverage: data.testnet?.default_leverage || 1,
          balance: undefined
        })
        setTestnetMaxLeverage(data.testnet?.max_leverage || 20)
        setTestnetDefaultLeverage(data.testnet?.default_leverage || 1)
        // Load balance
        try {
          const balanceRes = await fetch(`${API_BASE}/accounts/${accountId}/balance?environment=testnet`)
          if (balanceRes.ok) {
            const balance = await balanceRes.json()
            setTestnetWallet(prev => prev ? { ...prev, balance } : null)
          }
        } catch (e) {
          console.error('Failed to load testnet balance:', e)
        }
      } else {
        setTestnetWallet(null)
      }

      if (mainnetConfigured) {
        setMainnetWallet({
          configured: true,
          apiKeyMasked: data.mainnet?.api_key_masked,
          maxLeverage: data.mainnet?.max_leverage || 20,
          defaultLeverage: data.mainnet?.default_leverage || 1,
          balance: undefined
        })
        setMainnetMaxLeverage(data.mainnet?.max_leverage || 20)
        setMainnetDefaultLeverage(data.mainnet?.default_leverage || 1)
        // Load balance
        try {
          const balanceRes = await fetch(`${API_BASE}/accounts/${accountId}/balance?environment=mainnet`)
          if (balanceRes.ok) {
            const balance = await balanceRes.json()
            setMainnetWallet(prev => prev ? { ...prev, balance } : null)
          }
        } catch (e) {
          console.error('Failed to load mainnet balance:', e)
        }
        // Load daily quota for mainnet
        try {
          const quotaRes = await fetch(`${API_BASE}/accounts/${accountId}/daily-quota`)
          if (quotaRes.ok) {
            const quota = await quotaRes.json()
            if (quota.limited) {
              setMainnetQuota(quota)
            } else {
              setMainnetQuota(null)
            }
          }
        } catch (e) {
          console.error('Failed to load mainnet quota:', e)
        }
      } else {
        setMainnetWallet(null)
        setMainnetQuota(null)
      }
    } catch (error) {
      console.error('Failed to load Binance config:', error)
    } finally {
      setLoadingConfig(false)
    }
  }

  const handleSaveWallet = async (environment: BinanceWalletEnvironment) => {
    const setSaving = environment === 'testnet' ? setSavingTestnet : setSavingMainnet
    const apiKey = environment === 'testnet' ? testnetApiKey : mainnetApiKey
    const secretKey = environment === 'testnet' ? testnetSecretKey : mainnetSecretKey
    const maxLev = environment === 'testnet' ? testnetMaxLeverage : mainnetMaxLeverage
    const defaultLev = environment === 'testnet' ? testnetDefaultLeverage : mainnetDefaultLeverage

    // Clean input: remove whitespace, newlines, invisible characters
    const cleanApiKey = apiKey.trim().replace(/[\s\r\n\t\u200B-\u200D\uFEFF]/g, '')
    const cleanSecretKey = secretKey.trim().replace(/[\s\r\n\t\u200B-\u200D\uFEFF]/g, '')

    if (!cleanApiKey || !cleanSecretKey) {
      toast.error('Please enter both API Key and Secret Key')
      return
    }

    // Validate format: API Key and Secret should be alphanumeric
    if (!/^[A-Za-z0-9]+$/.test(cleanApiKey)) {
      toast.error('API Key contains invalid characters. Please check for spaces or special characters.')
      return
    }
    if (!/^[A-Za-z0-9]+$/.test(cleanSecretKey)) {
      toast.error('Secret Key contains invalid characters. Please check for spaces or special characters.')
      return
    }

    try {
      setSaving(true)
      const res = await fetch(`${API_BASE}/accounts/${accountId}/setup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          environment,
          api_key: cleanApiKey,
          secret_key: cleanSecretKey,
          max_leverage: maxLev,
          default_leverage: defaultLev
        })
      })

      const data = await res.json()

      // Check for rebate ineligible response (mainnet only)
      if (data.error_code === 'REBATE_INELIGIBLE') {
        setRebateInfo(data.rebate_info)
        // Store binding params for confirm-limited-binding
        setPendingMainnetBinding({
          api_key: cleanApiKey,
          secret_key: cleanSecretKey,
          max_leverage: maxLev,
          default_leverage: defaultLev
        })
        setShowRebateModal(true)
        return
      }

      if (res.ok && data.success !== false) {
        toast.success(`Binance ${environment} configured`)
        if (environment === 'testnet') {
          setTestnetApiKey('')
          setTestnetSecretKey('')
          setEditingTestnet(false)
        } else {
          setMainnetApiKey('')
          setMainnetSecretKey('')
          setEditingMainnet(false)
        }
        await loadWalletInfo()
        onWalletConfigured?.()
      } else {
        const errorMsg = getErrorMessage(data, 'Failed to configure')
        toast.error(errorMsg, { duration: 12000 })
      }
    } catch (error) {
      toast.error('Network error. Please check your connection and try again.')
    } finally {
      setSaving(false)
    }
  }

  const handleTestConnection = async (environment: BinanceWalletEnvironment) => {
    const setTesting = environment === 'testnet' ? setTestingTestnet : setTestingMainnet
    try {
      setTesting(true)
      const res = await fetch(`${API_BASE}/accounts/${accountId}/balance?environment=${environment}`)
      if (res.ok) {
        const data = await res.json()
        toast.success(`✅ Connected! Balance: $${data.total_equity?.toFixed(2) || '0.00'}`)
        // Update wallet balance
        if (environment === 'testnet' && testnetWallet) {
          setTestnetWallet({ ...testnetWallet, balance: data })
        } else if (environment === 'mainnet' && mainnetWallet) {
          setMainnetWallet({ ...mainnetWallet, balance: data })
        }
      } else {
        const err = await res.json()
        toast.error(`❌ ${err.detail || 'Connection failed'}`)
      }
    } catch (error) {
      toast.error('Connection test failed')
    } finally {
      setTesting(false)
    }
  }

  const handleConfirmLimitedBinding = async () => {
    if (!pendingMainnetBinding) return
    try {
      setSavingMainnet(true)
      const res = await fetch(`${API_BASE}/accounts/${accountId}/confirm-limited-binding`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          api_key: pendingMainnetBinding.api_key,
          secret_key: pendingMainnetBinding.secret_key,
          max_leverage: pendingMainnetBinding.max_leverage,
          default_leverage: pendingMainnetBinding.default_leverage
        })
      })
      const data = await res.json()
      if (res.ok && data.success !== false) {
        toast.success('Binance mainnet configured (daily quota: 20)')
        setMainnetApiKey('')
        setMainnetSecretKey('')
        setEditingMainnet(false)
        setPendingMainnetBinding(null)
        await loadWalletInfo()
        onWalletConfigured?.()
      } else {
        toast.error(getErrorMessage(data, 'Failed to configure'), { duration: 12000 })
      }
    } catch (error) {
      toast.error('Network error')
    } finally {
      setSavingMainnet(false)
    }
  }

  const handleDeleteWallet = async (environment: BinanceWalletEnvironment) => {
    if (!confirm(`Delete Binance ${environment} wallet?`)) return
    const setSaving = environment === 'testnet' ? setSavingTestnet : setSavingMainnet
    try {
      setSaving(true)
      const res = await fetch(`${API_BASE}/accounts/${accountId}/wallet?environment=${environment}`, {
        method: 'DELETE'
      })
      if (res.ok) {
        toast.success(`Binance ${environment} wallet deleted`)
        await loadWalletInfo()
        onWalletConfigured?.()
      }
    } catch (error) {
      toast.error('Failed to delete wallet')
    } finally {
      setSaving(false)
    }
  }

  if (loadingConfig && !testnetWallet && !mainnetWallet) {
    return (
      <div className="flex items-center justify-center py-4">
        <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-2">
      <BinanceWalletBlock
        environment="testnet"
        wallet={testnetWallet}
        editing={editingTestnet}
        setEditing={setEditingTestnet}
        apiKey={testnetApiKey}
        setApiKey={setTestnetApiKey}
        secretKey={testnetSecretKey}
        setSecretKey={setTestnetSecretKey}
        maxLeverage={testnetMaxLeverage}
        setMaxLeverage={setTestnetMaxLeverage}
        defaultLeverage={testnetDefaultLeverage}
        setDefaultLeverage={setTestnetDefaultLeverage}
        showKey={showTestnetKey}
        setShowKey={setShowTestnetKey}
        saving={savingTestnet}
        testing={testingTestnet}
        quota={null}
        onSaveWallet={handleSaveWallet}
        onTestConnection={handleTestConnection}
        onDeleteWallet={handleDeleteWallet}
      />
      <BinanceWalletBlock
        environment="mainnet"
        wallet={mainnetWallet}
        editing={editingMainnet}
        setEditing={setEditingMainnet}
        apiKey={mainnetApiKey}
        setApiKey={setMainnetApiKey}
        secretKey={mainnetSecretKey}
        setSecretKey={setMainnetSecretKey}
        maxLeverage={mainnetMaxLeverage}
        setMaxLeverage={setMainnetMaxLeverage}
        defaultLeverage={mainnetDefaultLeverage}
        setDefaultLeverage={setMainnetDefaultLeverage}
        showKey={showMainnetKey}
        setShowKey={setShowMainnetKey}
        saving={savingMainnet}
        testing={testingMainnet}
        quota={mainnetQuota}
        onSaveWallet={handleSaveWallet}
        onTestConnection={handleTestConnection}
        onDeleteWallet={handleDeleteWallet}
      />

      {/* Rebate Ineligible Modal */}
      <RebateIneligibleModal
        isOpen={showRebateModal}
        onClose={() => setShowRebateModal(false)}
        onConfirmLimited={handleConfirmLimitedBinding}
        rebateInfo={rebateInfo}
      />
    </div>
  )
}
