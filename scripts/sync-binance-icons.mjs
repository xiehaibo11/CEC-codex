import { mkdir, readdir, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const ICON_ROOT = path.join(ROOT, 'frontend/public/crypto-icons')
const COLOR_DIR = path.join(ICON_ROOT, 'color')
const BINANCE_DIR = path.join(ICON_ROOT, 'binance')
const MANIFEST_PATH = path.join(ICON_ROOT, 'manifest.json')
const AUDIT_PATH = path.join(ROOT, 'docs/settings-icon-audit.json')
const CRAWL_PATH = path.join(ROOT, 'docs/binance-icon-crawl.json')

const BINANCE_ASSETS_URL = 'https://www.binance.com/bapi/asset/v2/public/asset/asset/get-all-asset'
const SYMBOLS_URL = process.env.SYMBOLS_URL || 'http://127.0.0.1:8802/api/binance/symbols/available'
const IMAGE_EXTENSIONS = new Set(['svg', 'png', 'jpg', 'jpeg', 'webp'])
const QUOTE_SUFFIXES = ['USDT', 'USDC', 'BUSD', 'FDUSD', 'TUSD', 'USD', 'PERP']
const ICON_ALIASES = {
  IOTA: ['MIOTA'],
}

function stripPrefix(symbol) {
  return String(symbol || '').replace(/^k(?=[A-Z])/, '')
}

function normalizeSymbol(symbol) {
  let clean = stripPrefix(symbol).toUpperCase().replace(/[^A-Z0-9]/g, '')
  for (const suffix of QUOTE_SUFFIXES) {
    if (clean.endsWith(suffix) && clean.length > suffix.length + 1) {
      clean = clean.slice(0, -suffix.length)
      break
    }
  }
  return clean
}

function iconCandidates(symbol) {
  const clean = normalizeSymbol(symbol)
  const candidates = [clean]
  if (clean.startsWith('1000') && clean.length > 4) candidates.push(clean.slice(4))
  const noNumericPrefix = clean.replace(/^\d+(?=[A-Z])/, '')
  if (noNumericPrefix && noNumericPrefix !== clean) candidates.push(noNumericPrefix)
  if (clean.startsWith('1M') && clean.length > 2) candidates.push(clean.slice(2))
  if (clean.endsWith('X') && clean.length > 2) candidates.push(clean.slice(0, -1))
  if (/^LUNA\d+$/.test(clean)) candidates.push('LUNA')
  candidates.push(...(ICON_ALIASES[clean] || []))
  return [...new Set(candidates.filter(Boolean))]
}

async function readJson(file) {
  return JSON.parse(await readFile(file, 'utf8'))
}

async function fetchJson(url) {
  const response = await fetch(url, {
    headers: { 'user-agent': 'Hyper-Alpha-Arena icon sync' },
  })
  if (!response.ok) {
    throw new Error(`${url} returned ${response.status}`)
  }
  return response.json()
}

async function listImageFiles(dir) {
  try {
    const entries = await readdir(dir, { withFileTypes: true })
    return entries
      .filter(entry => entry.isFile())
      .map(entry => entry.name)
      .filter(file => IMAGE_EXTENSIONS.has(path.extname(file).slice(1).toLowerCase()))
      .sort()
  } catch (error) {
    if (error?.code === 'ENOENT') return []
    throw error
  }
}

async function loadSymbols() {
  try {
    const data = await fetchJson(SYMBOLS_URL)
    if (Array.isArray(data?.symbols) && data.symbols.length > 0) {
      return {
        source: SYMBOLS_URL,
        symbols: data.symbols.map(item => ({
          symbol: item.symbol,
          name: item.name || item.symbol,
          label: item.label || item.name || item.symbol,
          type: item.type || 'unknown',
        })),
      }
    }
  } catch (error) {
    console.warn(`Failed to load symbols from ${SYMBOLS_URL}: ${error.message}`)
  }

  const audit = await readJson(AUDIT_PATH)
  const symbols = [...(audit.matched || []), ...(audit.missing || [])].map(item => ({
    symbol: item.symbol,
    name: item.name || item.symbol,
    label: item.label || item.name || item.symbol,
    type: item.type || 'unknown',
  }))
  return { source: AUDIT_PATH, symbols }
}

async function buildIconMap() {
  const icons = {}
  for (const file of await listImageFiles(COLOR_DIR)) {
    const key = path.basename(file, path.extname(file)).toUpperCase()
    icons[key] = `/crypto-icons/color/${file}`
  }
  for (const file of await listImageFiles(BINANCE_DIR)) {
    const key = path.basename(file, path.extname(file)).toUpperCase()
    if (!icons[key]) {
      icons[key] = `/crypto-icons/binance/${file}`
    }
  }
  return Object.fromEntries(Object.entries(icons).sort(([a], [b]) => a.localeCompare(b)))
}

function auditSymbols(symbols, icons) {
  const matched = []
  const missing = []

  for (const item of symbols) {
    const candidates = iconCandidates(item.symbol)
    const matchedKey = candidates.find(candidate => icons[candidate])
    const record = {
      symbol: item.symbol,
      name: item.name || item.symbol,
      label: item.label || item.name || item.symbol,
      type: item.type || 'unknown',
      candidates,
      matched_icon_key: matchedKey || null,
      icon_path: matchedKey ? icons[matchedKey] : null,
    }
    ;(matchedKey ? matched : missing).push(record)
  }

  const total = symbols.length
  return {
    total,
    matched_count: matched.length,
    missing_count: missing.length,
    matched_pct: total ? Number(((matched.length / total) * 100).toFixed(2)) : 0,
    missing_pct: total ? Number(((missing.length / total) * 100).toFixed(2)) : 0,
    matched,
    missing,
  }
}

function buildBinanceAssetMap(assets) {
  const map = new Map()
  for (const asset of assets) {
    if (!asset?.logoUrl) continue
    const key = normalizeSymbol(asset.assetCode)
    if (key && !map.has(key)) {
      map.set(key, {
        key,
        asset_code: asset.assetCode,
        asset_name: asset.assetName,
        logo_url: asset.logoUrl,
      })
    }
  }
  return map
}

function findBinanceAsset(record, binanceAssets) {
  const values = [record.symbol, record.name, record.label]
  const candidates = [...new Set(values.flatMap(value => iconCandidates(value)))]
  for (const candidate of candidates) {
    const asset = binanceAssets.get(candidate)
    if (asset) {
      return { ...asset, candidates }
    }
  }
  return { candidates }
}

function imageExtensionFromUrl(url) {
  const ext = path.extname(new URL(url).pathname).slice(1).toLowerCase()
  if (IMAGE_EXTENSIONS.has(ext)) return ext === 'jpeg' ? 'jpg' : ext
  return null
}

function imageExtensionFromContentType(contentType) {
  if (!contentType) return 'png'
  if (contentType.includes('svg')) return 'svg'
  if (contentType.includes('webp')) return 'webp'
  if (contentType.includes('jpeg') || contentType.includes('jpg')) return 'jpg'
  return 'png'
}

function filenameForKey(key, ext) {
  return `${key.toLowerCase().replace(/[^a-z0-9]/g, '')}.${ext}`
}

async function existingBinanceFiles() {
  const files = await listImageFiles(BINANCE_DIR)
  return new Map(files.map(file => [path.basename(file, path.extname(file)).toUpperCase(), file]))
}

async function downloadIcon(task, existingFiles) {
  const existing = existingFiles.get(task.key)
  if (existing) {
    return { ...task, status: 'reused', local_path: `/crypto-icons/binance/${existing}` }
  }

  const response = await fetch(task.logo_url, {
    headers: { 'user-agent': 'Hyper-Alpha-Arena icon sync' },
  })
  if (!response.ok) {
    throw new Error(`${task.key} returned ${response.status}`)
  }
  const buffer = Buffer.from(await response.arrayBuffer())
  if (buffer.length < 100) {
    throw new Error(`${task.key} image is too small (${buffer.length} bytes)`)
  }

  const contentType = response.headers.get('content-type') || ''
  const ext = imageExtensionFromUrl(task.logo_url) || imageExtensionFromContentType(contentType)
  const file = filenameForKey(task.key, ext)
  await writeFile(path.join(BINANCE_DIR, file), buffer)
  existingFiles.set(task.key, file)
  return {
    ...task,
    status: 'downloaded',
    bytes: buffer.length,
    content_type: contentType,
    local_path: `/crypto-icons/binance/${file}`,
  }
}

async function runLimited(items, limit, worker) {
  const results = []
  let next = 0
  await Promise.all(
    Array.from({ length: Math.min(limit, items.length) }, async () => {
      while (next < items.length) {
        const index = next
        next += 1
        results[index] = await worker(items[index], index)
      }
    }),
  )
  return results
}

async function main() {
  await mkdir(BINANCE_DIR, { recursive: true })
  await mkdir(path.dirname(AUDIT_PATH), { recursive: true })

  const [{ source: symbols_source, symbols }, binanceResponse] = await Promise.all([
    loadSymbols(),
    fetchJson(BINANCE_ASSETS_URL),
  ])
  const assets = Array.isArray(binanceResponse?.data) ? binanceResponse.data : []
  const binanceAssets = buildBinanceAssetMap(assets)
  const beforeIcons = await buildIconMap()
  const beforeAudit = auditSymbols(symbols, beforeIcons)

  const tasksByKey = new Map()
  const fillable = []
  const unavailable = []
  for (const record of beforeAudit.missing) {
    const match = findBinanceAsset(record, binanceAssets)
    if (!match.key) {
      unavailable.push({ ...record, binance_candidates: match.candidates })
      continue
    }
    const task = {
      key: match.key,
      asset_code: match.asset_code,
      asset_name: match.asset_name,
      logo_url: match.logo_url,
    }
    tasksByKey.set(match.key, task)
    fillable.push({ ...record, binance_candidates: match.candidates, binance_key: match.key, binance_url: match.logo_url })
  }

  const existingFiles = await existingBinanceFiles()
  const results = await runLimited([...tasksByKey.values()], 8, async task => {
    try {
      return await downloadIcon(task, existingFiles)
    } catch (error) {
      return { ...task, status: 'failed', error: error.message }
    }
  })

  const afterIcons = await buildIconMap()
  const afterAudit = auditSymbols(symbols, afterIcons)
  const manifest = {
    generated_at: new Date().toISOString(),
    source: 'spothq/cryptocurrency-icons + Binance asset logo crawl',
    license: 'spothq icons: CC0-1.0; Binance asset logos: sourced from Binance public asset metadata',
    count: Object.keys(afterIcons).length,
    icons: afterIcons,
  }

  const audit = {
    generated_at: new Date().toISOString(),
    symbols_source,
    total: afterAudit.total,
    local_icon_count: manifest.count,
    matched_count: afterAudit.matched_count,
    missing_count: afterAudit.missing_count,
    matched_pct: afterAudit.matched_pct,
    missing_pct: afterAudit.missing_pct,
    matched: afterAudit.matched,
    missing: afterAudit.missing,
  }

  const crawlReport = {
    generated_at: new Date().toISOString(),
    binance_assets_url: BINANCE_ASSETS_URL,
    binance_asset_count: assets.length,
    binance_logo_count: assets.filter(asset => asset?.logoUrl).length,
    symbols_source,
    symbols_total: symbols.length,
    before: {
      local_icon_count: Object.keys(beforeIcons).length,
      matched_count: beforeAudit.matched_count,
      missing_count: beforeAudit.missing_count,
      matched_pct: beforeAudit.matched_pct,
    },
    fillable_records_count: fillable.length,
    unique_download_tasks_count: tasksByKey.size,
    unavailable_records_count: unavailable.length,
    downloaded_count: results.filter(item => item.status === 'downloaded').length,
    reused_count: results.filter(item => item.status === 'reused').length,
    failed_count: results.filter(item => item.status === 'failed').length,
    after: {
      local_icon_count: manifest.count,
      matched_count: afterAudit.matched_count,
      missing_count: afterAudit.missing_count,
      matched_pct: afterAudit.matched_pct,
    },
    fillable,
    unavailable,
    results,
  }

  await writeFile(MANIFEST_PATH, `${JSON.stringify(manifest, null, 2)}\n`)
  await writeFile(AUDIT_PATH, `${JSON.stringify(audit, null, 2)}\n`)
  await writeFile(CRAWL_PATH, `${JSON.stringify(crawlReport, null, 2)}\n`)

  console.log(JSON.stringify({
    symbols: symbols.length,
    binance_assets: assets.length,
    before_missing: beforeAudit.missing_count,
    fillable_records: fillable.length,
    unique_tasks: tasksByKey.size,
    downloaded: crawlReport.downloaded_count,
    reused: crawlReport.reused_count,
    failed: crawlReport.failed_count,
    after_missing: afterAudit.missing_count,
    manifest_count: manifest.count,
  }, null, 2))
}

main().catch(error => {
  console.error(error)
  process.exit(1)
})
