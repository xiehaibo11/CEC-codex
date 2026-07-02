import { getModelChartLogo } from '../logoAssets'
import type {
  AccountMeta,
  AccountSummary,
  AssetCurveData,
  BaseProcessedAssetCurve,
  ChartPoint,
  ProcessedAssetCurve,
} from './types'

const CHART_COLORS = [
  '#f7931a',
  '#627eea',
  '#9945ff',
  '#f3ba2f',
  '#23292f',
  '#c2a633',
  '#000000',
  '#333333',
]

function parseTimestamp(value: string) {
  if (/^\d+$/.test(value)) {
    const numeric = Number(value)
    const milliseconds = value.length <= 10 ? numeric * 1000 : numeric
    return new Date(milliseconds)
  }
  return new Date(value)
}

export function formatAccountName(username?: string | null) {
  return (username || 'NA').replace('default_', '').toUpperCase()
}

export function buildBaseProcessedData(data: AssetCurveData[]): BaseProcessedAssetCurve {
  if (!data || data.length === 0) {
    return {
      chartData: [],
      accountSummaries: [],
      uniqueUsers: [],
      userAccountMap: new Map(),
    }
  }

  const uniqueUsers = Array.from(new Set(data.map((item) => item.username))).sort()
  const userAccountMap = new Map<string, number | undefined>()

  const groupedData = data.reduce<Record<string, Record<string, number | string | null>>>(
    (acc, item) => {
      const key = item.datetime_str || item.date || item.timestamp?.toString() || ''
      if (!acc[key]) acc[key] = { timestamp: key }

      if (!userAccountMap.has(item.username)) {
        userAccountMap.set(item.username, item.account_id)
      }

      acc[key][item.username] = item.total_assets ?? null
      return acc
    },
    {},
  )

  const timestamps = Object.keys(groupedData).sort((a, b) => {
    const dateA = parseTimestamp(a).getTime()
    const dateB = parseTimestamp(b).getTime()
    return dateA - dateB
  })

  const chartData = timestamps.map<ChartPoint>((ts) => {
    const date = parseTimestamp(ts)
    const formattedTime = date.toLocaleString('en-US', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    })

    return {
      timestamp: ts,
      formattedTime,
      ...uniqueUsers.reduce<Record<string, number | null>>((acc, username) => {
        acc[username] = (groupedData[ts][username] as number | null | undefined) ?? null
        return acc
      }, {}),
    }
  })

  const accountSummaries = uniqueUsers.map<AccountSummary>((username) => {
    const latestData = data
      .filter((item) => item.username === username)
      .sort((a, b) => {
        const dateA = new Date(a.datetime_str || a.date || 0).getTime()
        const dateB = new Date(b.datetime_str || b.date || 0).getTime()
        return dateB - dateA
      })[0]

    return {
      username,
      assets: latestData?.total_assets || 0,
      accountId: latestData?.account_id,
      logo: getModelChartLogo(username),
    }
  })

  return { chartData, accountSummaries, uniqueUsers, userAccountMap }
}

export function applyLiveAccountTotals(
  baseData: BaseProcessedAssetCurve,
  liveAccountTotals: Map<number, number>,
): ProcessedAssetCurve {
  const { chartData, accountSummaries, uniqueUsers, userAccountMap } = baseData
  const updatedChartData = [...chartData]

  if (updatedChartData.length > 0) {
    const lastPoint = { ...updatedChartData[updatedChartData.length - 1] }
    uniqueUsers.forEach((username) => {
      const accountId = userAccountMap.get(username)
      if (accountId !== undefined && accountId !== null) {
        const liveOverride = liveAccountTotals.get(accountId)
        if (liveOverride !== undefined) {
          lastPoint[username] = liveOverride
        }
      }
    })
    updatedChartData[updatedChartData.length - 1] = lastPoint
  }

  const updatedAccountSummaries = accountSummaries.map((account) => {
    const liveOverride =
      account.accountId !== undefined ? liveAccountTotals.get(account.accountId) : undefined
    return {
      ...account,
      assets: liveOverride ?? account.assets,
    }
  })

  return {
    chartData: updatedChartData,
    accountSummaries: updatedAccountSummaries,
    uniqueUsers,
    rankedAccounts: updatedAccountSummaries.slice().sort((a, b) => b.assets - a.assets),
  }
}

export function buildYAxisDomain(
  chartData: ChartPoint[],
  uniqueUsers: string[],
  accountSummaries: AccountSummary[],
  activeLegendAccountId: number | null,
): [number, number] {
  if (!chartData.length) return [0, 100000]

  let min = Infinity
  let max = -Infinity
  const usersToConsider = activeLegendAccountId
    ? uniqueUsers.filter((username) => {
        const account = accountSummaries.find((acc) => acc.username === username)
        return account?.accountId === activeLegendAccountId
      })
    : uniqueUsers

  chartData.forEach((point) => {
    usersToConsider.forEach((username) => {
      const value = point[username]
      if (typeof value === 'number' && !isNaN(value)) {
        min = Math.min(min, value)
        max = Math.max(max, value)
      }
    })
  })

  if (min === Infinity || max === -Infinity) return [0, 100000]

  const range = max - min
  const paddingPercent = activeLegendAccountId ? 0.15 : 0.05
  const padding = Math.max(range * paddingPercent, 50)

  return [Math.max(0, min - padding), max + padding]
}

export function buildAccountMeta(
  uniqueUsers: string[],
  accountSummaries: AccountSummary[],
): Map<string, AccountMeta> {
  const meta = new Map<string, AccountMeta>()
  uniqueUsers.forEach((username, index) => {
    const account = accountSummaries.find((acc) => acc.username === username)
    const chartLogo = getModelChartLogo(username)
    meta.set(username, {
      accountId: account?.accountId,
      color: chartLogo.color || CHART_COLORS[index % CHART_COLORS.length],
      logo: account?.logo,
    })
  })
  return meta
}
