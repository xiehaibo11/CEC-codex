/**
 * HiBT Wallet Section - Testnet/Mainnet Access Key configuration.
 */

import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { RefreshCw } from 'lucide-react'
import { BinanceWalletBlock } from './binance-wallet-section/BinanceWalletBlock'
import { getErrorMessage } from './binance-wallet-section/errors'
import type {
  BinanceWalletData,
  BinanceWalletEnvironment,
} from './binance-wallet-section/types'

interface HibtWalletSectionProps {
  accountId: number
  accountName: string
  onStatusChange?: (env: 'testnet' | 'mainnet', configured: boolean) => void
  onWalletConfigured?: () => void
}

const API_BASE = '/api/hibt'

export default function HibtWalletSection({
  accountId,
  onStatusChange,
  onWalletConfigured,
}: HibtWalletSectionProps) {
  const [testnetWallet, setTestnetWallet] = useState<BinanceWalletData | null>(null)
  const [mainnetWallet, setMainnetWallet] = useState<BinanceWalletData | null>(null)

  const [loadingConfig, setLoadingConfig] = useState(false)
  const [savingTestnet, setSavingTestnet] = useState(false)
  const [savingMainnet, setSavingMainnet] = useState(false)
  const [testingTestnet, setTestingTestnet] = useState(false)
  const [testingMainnet, setTestingMainnet] = useState(false)

  const [editingTestnet, setEditingTestnet] = useState(false)
  const [editingMainnet, setEditingMainnet] = useState(false)
  const [showTestnetKey, setShowTestnetKey] = useState(false)
  const [showMainnetKey, setShowMainnetKey] = useState(false)

  const [testnetAccessKey, setTestnetAccessKey] = useState('')
  const [testnetSecretKey, setTestnetSecretKey] = useState('')
  const [testnetMaxLeverage, setTestnetMaxLeverage] = useState(20)
  const [testnetDefaultLeverage, setTestnetDefaultLeverage] = useState(1)

  const [mainnetAccessKey, setMainnetAccessKey] = useState('')
  const [mainnetSecretKey, setMainnetSecretKey] = useState('')
  const [mainnetMaxLeverage, setMainnetMaxLeverage] = useState(20)
  const [mainnetDefaultLeverage, setMainnetDefaultLeverage] = useState(1)

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
          apiKeyMasked: data.testnet?.access_key_masked || data.testnet?.api_key_masked,
          maxLeverage: data.testnet?.max_leverage || 20,
          defaultLeverage: data.testnet?.default_leverage || 1,
        })
        setTestnetMaxLeverage(data.testnet?.max_leverage || 20)
        setTestnetDefaultLeverage(data.testnet?.default_leverage || 1)
        await loadBalance('testnet')
      } else {
        setTestnetWallet(null)
      }

      if (mainnetConfigured) {
        setMainnetWallet({
          configured: true,
          apiKeyMasked: data.mainnet?.access_key_masked || data.mainnet?.api_key_masked,
          maxLeverage: data.mainnet?.max_leverage || 20,
          defaultLeverage: data.mainnet?.default_leverage || 1,
        })
        setMainnetMaxLeverage(data.mainnet?.max_leverage || 20)
        setMainnetDefaultLeverage(data.mainnet?.default_leverage || 1)
        await loadBalance('mainnet')
      } else {
        setMainnetWallet(null)
      }
    } catch (error) {
      console.error('Failed to load HiBT config:', error)
    } finally {
      setLoadingConfig(false)
    }
  }

  const loadBalance = async (environment: BinanceWalletEnvironment) => {
    try {
      const balanceRes = await fetch(`${API_BASE}/accounts/${accountId}/balance?environment=${environment}`)
      if (!balanceRes.ok) return
      const balance = await balanceRes.json()
      if (environment === 'testnet') {
        setTestnetWallet(prev => prev ? { ...prev, balance } : prev)
      } else {
        setMainnetWallet(prev => prev ? { ...prev, balance } : prev)
      }
    } catch (error) {
      console.error(`Failed to load HiBT ${environment} balance:`, error)
    }
  }

  const handleSaveWallet = async (environment: BinanceWalletEnvironment) => {
    const setSaving = environment === 'testnet' ? setSavingTestnet : setSavingMainnet
    const accessKey = environment === 'testnet' ? testnetAccessKey : mainnetAccessKey
    const secretKey = environment === 'testnet' ? testnetSecretKey : mainnetSecretKey
    const maxLev = environment === 'testnet' ? testnetMaxLeverage : mainnetMaxLeverage
    const defaultLev = environment === 'testnet' ? testnetDefaultLeverage : mainnetDefaultLeverage

    const cleanAccessKey = accessKey.trim().replace(/[\s\r\n\t\u200B-\u200D\uFEFF]/g, '')
    const cleanSecretKey = secretKey.trim().replace(/[\s\r\n\t\u200B-\u200D\uFEFF]/g, '')

    if (!cleanAccessKey || !cleanSecretKey) {
      toast.error('Please enter both HiBT Access Key and Secret Key')
      return
    }

    try {
      setSaving(true)
      const res = await fetch(`${API_BASE}/accounts/${accountId}/setup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          environment,
          access_key: cleanAccessKey,
          secret_key: cleanSecretKey,
          max_leverage: maxLev,
          default_leverage: defaultLev,
        }),
      })
      const data = await res.json()

      if (res.ok && data.success !== false) {
        toast.success(`HiBT ${environment} configured`)
        if (environment === 'testnet') {
          setTestnetAccessKey('')
          setTestnetSecretKey('')
          setEditingTestnet(false)
        } else {
          setMainnetAccessKey('')
          setMainnetSecretKey('')
          setEditingMainnet(false)
        }
        await loadWalletInfo()
        onWalletConfigured?.()
      } else {
        toast.error(getErrorMessage(data, 'Failed to configure HiBT'), { duration: 12000 })
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

  const handleDeleteWallet = async (environment: BinanceWalletEnvironment) => {
    if (!confirm(`Delete HiBT ${environment} wallet?`)) return
    const setSaving = environment === 'testnet' ? setSavingTestnet : setSavingMainnet
    try {
      setSaving(true)
      const res = await fetch(`${API_BASE}/accounts/${accountId}/wallet?environment=${environment}`, {
        method: 'DELETE',
      })
      if (res.ok) {
        toast.success(`HiBT ${environment} wallet deleted`)
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

  const commonBlockProps = {
    platformName: 'HiBT',
    apiKeyLabel: 'Access Key',
    secretKeyLabel: 'Secret Key',
    positionModeHint: 'HiBT close-position requests use the exchange position ID. Confirm the API key has perpetual query/trading permissions before live orders.',
    authenticationHint: 'HiBT private endpoints use X-ACCESS-KEY, X-SIGNATURE and X-TIMESTAMP headers. The key must match this environment.',
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-2">
      <BinanceWalletBlock
        {...commonBlockProps}
        credentialHint="HiBT docs publish the production REST base. Testnet will use HIBT_TESTNET_FAPI_BASE_URL if configured; otherwise it follows the default HiBT REST base."
        environment="testnet"
        wallet={testnetWallet}
        editing={editingTestnet}
        setEditing={setEditingTestnet}
        apiKey={testnetAccessKey}
        setApiKey={setTestnetAccessKey}
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
        {...commonBlockProps}
        credentialHint="Use a HiBT Perpetual Contract Access Key and Secret Key from API management. Enable query permission for balance/positions and trading permission for orders."
        environment="mainnet"
        wallet={mainnetWallet}
        editing={editingMainnet}
        setEditing={setEditingMainnet}
        apiKey={mainnetAccessKey}
        setApiKey={setMainnetAccessKey}
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
        quota={null}
        onSaveWallet={handleSaveWallet}
        onTestConnection={handleTestConnection}
        onDeleteWallet={handleDeleteWallet}
      />
    </div>
  )
}
