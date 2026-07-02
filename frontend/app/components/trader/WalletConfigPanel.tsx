/**
 * Wallet Configuration Panel for AI Traders
 *
 * Displays and configures BOTH Testnet and Mainnet wallets for each AI Trader
 */

import { useState, useEffect } from 'react'
import toast from 'react-hot-toast'
import { Wallet, RefreshCw } from 'lucide-react'
import {
  getAccountWallet,
  configureAccountWallet,
  testWalletConnection,
  deleteAccountWallet,
} from '@/lib/hyperliquidApi'
import { type UnauthorizedAccount } from '@/lib/api'
import { checkBuilderFeeAuthorized, approveBuilderFee } from '@/lib/hyperliquidWalletSetup'
import { AuthorizationModal } from '@/components/hyperliquid'
import { useTranslation } from 'react-i18next'
import { HyperliquidWalletBlock } from './hyperliquid-wallet-panel/HyperliquidWalletBlock'
import { detectInputType, formatPrivateKey } from './hyperliquid-wallet-panel/privateKeyInput'
import type { WalletData, WalletEnvironment } from './hyperliquid-wallet-panel/types'

interface WalletConfigPanelProps {
  accountId: number
  accountName: string
  onWalletConfigured?: () => void
}

export default function WalletConfigPanel({
  accountId,
  accountName,
  onWalletConfigured
}: WalletConfigPanelProps) {
  const { t } = useTranslation()
  const [testnetWallet, setTestnetWallet] = useState<WalletData | null>(null)
  const [mainnetWallet, setMainnetWallet] = useState<WalletData | null>(null)
  const [loading, setLoading] = useState(false)
  const [testingTestnet, setTestingTestnet] = useState(false)
  const [testingMainnet, setTestingMainnet] = useState(false)

  // Editing states
  const [editingTestnet, setEditingTestnet] = useState(false)
  const [editingMainnet, setEditingMainnet] = useState(false)
  const [showTestnetKey, setShowTestnetKey] = useState(false)
  const [showMainnetKey, setShowMainnetKey] = useState(false)

  // Form states for testnet
  const [testnetPrivateKey, setTestnetPrivateKey] = useState('')
  const [testnetMaxLeverage, setTestnetMaxLeverage] = useState(3)
  const [testnetDefaultLeverage, setTestnetDefaultLeverage] = useState(1)
  const [testnetInputWarning, setTestnetInputWarning] = useState<string | null>(null)

  // Form states for mainnet
  const [mainnetPrivateKey, setMainnetPrivateKey] = useState('')
  const [mainnetMaxLeverage, setMainnetMaxLeverage] = useState(3)
  const [mainnetDefaultLeverage, setMainnetDefaultLeverage] = useState(1)
  const [mainnetInputWarning, setMainnetInputWarning] = useState<string | null>(null)

  // Authorization modal states
  const [unauthorizedAccounts, setUnauthorizedAccounts] = useState<UnauthorizedAccount[]>([])
  const [authModalOpen, setAuthModalOpen] = useState(false)

  useEffect(() => {
    loadWalletInfo()
  }, [accountId])

  const loadWalletInfo = async () => {
    try {
      setLoading(true)
      const info = await getAccountWallet(accountId)

      if (info.testnetWallet) {
        setTestnetWallet(info.testnetWallet)
        setTestnetMaxLeverage(info.testnetWallet.maxLeverage)
        setTestnetDefaultLeverage(info.testnetWallet.defaultLeverage)
      } else {
        setTestnetWallet(null)
      }

      if (info.mainnetWallet) {
        setMainnetWallet(info.mainnetWallet)
        setMainnetMaxLeverage(info.mainnetWallet.maxLeverage)
        setMainnetDefaultLeverage(info.mainnetWallet.defaultLeverage)
      } else {
        setMainnetWallet(null)
      }
    } catch (error) {
      console.error('Failed to load wallet info:', error)
      toast.error('Failed to load wallet information')
    } finally {
      setLoading(false)
    }
  }

  const handleSaveWallet = async (environment: WalletEnvironment) => {
    const rawPrivateKey = environment === 'testnet' ? testnetPrivateKey : mainnetPrivateKey
    const maxLeverage = environment === 'testnet' ? testnetMaxLeverage : mainnetMaxLeverage
    const defaultLeverage = environment === 'testnet' ? testnetDefaultLeverage : mainnetDefaultLeverage

    if (!rawPrivateKey.trim()) {
      toast.error('Please enter a private key')
      return
    }

    // Auto-format private key (add 0x prefix if missing)
    const privateKey = formatPrivateKey(rawPrivateKey)
    if (privateKey !== rawPrivateKey) {
      if (environment === 'testnet') {
        setTestnetPrivateKey(privateKey)
      } else {
        setMainnetPrivateKey(privateKey)
      }
      toast.success('Added 0x prefix automatically')
    }

    // Check for common mistakes
    const inputType = detectInputType(privateKey)
    if (inputType === 'wallet_address') {
      toast.error('You entered a wallet ADDRESS (40 chars), not a private key (64 chars). Please export your private key from your wallet.')
      return
    }

    // Validate private key format
    if (inputType !== 'valid_key') {
      toast.error('Invalid private key format. Must be 64 hex characters (0x prefix will be added automatically).')
      return
    }

    if (maxLeverage < 1 || maxLeverage > 50) {
      toast.error('Max leverage must be between 1 and 50')
      return
    }

    if (defaultLeverage < 1 || defaultLeverage > maxLeverage) {
      toast.error(`Default leverage must be between 1 and ${maxLeverage}`)
      return
    }

    try {
      setLoading(true)
      const result = await configureAccountWallet(accountId, {
        privateKey,
        maxLeverage,
        defaultLeverage,
        environment
      })

      if (result.success) {
        toast.success(`${environment === 'testnet' ? 'Testnet' : 'Mainnet'} wallet configured: ${result.walletAddress.substring(0, 10)}...`)

        // Check if builder binding is required
        // Note: Backend returns snake_case field name
        if (result.requires_authorization && result.walletAddress) {
          setUnauthorizedAccounts([{
            account_id: accountId,
            account_name: accountName,
            wallet_address: result.walletAddress,
            max_fee: 0,
            required_fee: 30
          }])
          setAuthModalOpen(true)
        }

        // Clear form
        if (environment === 'testnet') {
          setTestnetPrivateKey('')
          setEditingTestnet(false)
        } else {
          setMainnetPrivateKey('')
          setEditingMainnet(false)
        }

        await loadWalletInfo()
        onWalletConfigured?.()
      } else {
        toast.error('Failed to configure wallet')
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to configure wallet'
      toast.error(message)
    } finally {
      setLoading(false)
    }
  }

  const handleTestConnection = async (environment: WalletEnvironment) => {
    try {
      if (environment === 'testnet') {
        setTestingTestnet(true)
      } else {
        setTestingMainnet(true)
      }

      const result = await testWalletConnection(accountId)

      if (result.success && result.connection === 'successful') {
        toast.success(`✅ ${environment === 'testnet' ? 'Testnet' : 'Mainnet'} connection successful! Balance: $${result.accountState?.totalEquity.toFixed(2)}`)
        // Builder fee check for mainnet wallet after successful connection
        if (environment === 'mainnet') {
          try {
            const ethereum = (window as any).ethereum
            if (ethereum) {
              const accts: string[] = await ethereum.request({ method: 'eth_accounts' })
              if (accts && accts.length > 0) {
                const masterAddr = accts[0]
                const authorized = await checkBuilderFeeAuthorized(masterAddr, 'mainnet')
                if (!authorized) {
                  await approveBuilderFee(masterAddr, 'mainnet')
                }
              }
            }
          } catch (err) {
            console.error('Builder fee authorization failed:', err)
          }
        }
      } else {
        toast.error(`❌ Connection failed: ${result.error || 'Unknown error'}`)
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Connection test failed'
      toast.error(message)
    } finally {
      if (environment === 'testnet') {
        setTestingTestnet(false)
      } else {
        setTestingMainnet(false)
      }
    }
  }

  const handleDeleteWallet = async (environment: WalletEnvironment) => {
    const envName = environment === 'testnet' ? 'Testnet' : 'Mainnet'

    if (!confirm(`Are you sure you want to delete the ${envName} wallet? This action cannot be undone.`)) {
      return
    }

    try {
      setLoading(true)
      const result = await deleteAccountWallet(accountId, environment)

      if (result.success) {
        toast.success(`${envName} wallet deleted successfully`)
        await loadWalletInfo()
        onWalletConfigured?.()
      } else {
        toast.error('Failed to delete wallet')
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to delete wallet'
      toast.error(message)
    } finally {
      setLoading(false)
    }
  }

  if (loading && !testnetWallet && !mainnetWallet) {
    return (
      <div className="p-4 border rounded-lg">
        <div className="flex items-center justify-center py-8">
          <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Wallet className="h-4 w-4 text-muted-foreground" />
        <h4 className="text-sm font-medium">{t('wallet.hyperliquidWallets', 'Hyperliquid Wallets')}</h4>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <HyperliquidWalletBlock
          environment="testnet"
          wallet={testnetWallet}
          editing={editingTestnet}
          setEditing={setEditingTestnet}
          privateKey={testnetPrivateKey}
          setPrivateKey={setTestnetPrivateKey}
          maxLeverage={testnetMaxLeverage}
          setMaxLeverage={setTestnetMaxLeverage}
          defaultLeverage={testnetDefaultLeverage}
          setDefaultLeverage={setTestnetDefaultLeverage}
          showKey={showTestnetKey}
          setShowKey={setShowTestnetKey}
          testing={testingTestnet}
          loading={loading}
          inputWarning={testnetInputWarning}
          setInputWarning={setTestnetInputWarning}
          onSaveWallet={handleSaveWallet}
          onTestConnection={handleTestConnection}
          onDeleteWallet={handleDeleteWallet}
        />

        <HyperliquidWalletBlock
          environment="mainnet"
          wallet={mainnetWallet}
          editing={editingMainnet}
          setEditing={setEditingMainnet}
          privateKey={mainnetPrivateKey}
          setPrivateKey={setMainnetPrivateKey}
          maxLeverage={mainnetMaxLeverage}
          setMaxLeverage={setMainnetMaxLeverage}
          defaultLeverage={mainnetDefaultLeverage}
          setDefaultLeverage={setMainnetDefaultLeverage}
          showKey={showMainnetKey}
          setShowKey={setShowMainnetKey}
          testing={testingMainnet}
          loading={loading}
          inputWarning={mainnetInputWarning}
          setInputWarning={setMainnetInputWarning}
          onSaveWallet={handleSaveWallet}
          onTestConnection={handleTestConnection}
          onDeleteWallet={handleDeleteWallet}
        />
      </div>

      <div className="text-xs text-muted-foreground bg-blue-50 border border-blue-200 rounded p-2">
        <p className="font-medium text-blue-900 mb-1">💡 {t('wallet.multiWalletSetup', 'Multi-Wallet Setup')}</p>
        <p className="text-blue-800">
          {t('wallet.multiWalletDesc', 'Each AI Trader can have separate wallets for testnet (paper trading) and mainnet (real funds). Configure both to seamlessly switch between environments without reconfiguring.')}
        </p>
      </div>

      {/* Authorization Modal */}
      <AuthorizationModal
        isOpen={authModalOpen}
        onClose={() => {
          setAuthModalOpen(false)
          setUnauthorizedAccounts([])
        }}
        unauthorizedAccounts={unauthorizedAccounts}
        onAuthorizationComplete={() => {
          setAuthModalOpen(false)
          setUnauthorizedAccounts([])
        }}
      />
    </div>
  )
}
