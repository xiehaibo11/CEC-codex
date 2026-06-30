import type { MutableRefObject } from 'react'
import AssetCurveWithData from '../AssetCurveWithData'
import type { ArenaAccountSelection } from './types'

interface AccountSelectorProps {
  allAssetCurves: any[]
  selectedAccount: ArenaAccountSelection
  wsRef?: MutableRefObject<WebSocket | null>
  onSelectedAccountChange: (accountId: ArenaAccountSelection) => void
}

export default function AccountSelector({
  allAssetCurves,
  selectedAccount,
  wsRef,
  onSelectedAccountChange,
}: AccountSelectorProps) {
  return (
    <AssetCurveWithData
      data={allAssetCurves}
      wsRef={wsRef}
      highlightAccountId={selectedAccount}
      onHighlightAccountChange={onSelectedAccountChange}
    />
  )
}
