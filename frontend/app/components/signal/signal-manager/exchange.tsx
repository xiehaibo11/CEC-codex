export const HyperliquidLogo = ({ className = '' }: { className?: string }) => (
  <svg width="16" height="16" viewBox="0 0 144 144" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
    <path d="M144 71.6991C144 119.306 114.866 134.582 99.5156 120.98C86.8804 109.889 83.1211 86.4521 64.116 84.0456C39.9942 81.0113 37.9057 113.133 22.0334 113.133C3.5504 113.133 0 86.2428 0 72.4315C0 58.3063 3.96809 39.0542 19.736 39.0542C38.1146 39.0542 39.1588 66.5722 62.132 65.1073C85.0007 63.5379 85.4184 34.8689 100.247 22.6271C113.195 12.0593 144 23.4641 144 71.6991Z" fill="#50e3c2"/>
  </svg>
)

export const BinanceLogo = ({ className = '' }: { className?: string }) => (
  <img src="/static/binance_logo.svg" alt="Binance" width="16" height="16" className={className} />
)

export const ExchangeBadge = ({ exchange, size = 'sm' }: { exchange: string; size?: 'sm' | 'xs' }) => {
  const isHyperliquid = exchange === 'hyperliquid'
  const textSize = size === 'xs' ? 'text-[10px]' : 'text-xs'
  return (
    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded ${isHyperliquid ? 'bg-emerald-500/10 text-emerald-400' : 'bg-yellow-500/10 text-yellow-400'}`}>
      {isHyperliquid ? <HyperliquidLogo /> : <BinanceLogo />}
      <span className={textSize}>{isHyperliquid ? 'Hyperliquid' : 'Binance'}</span>
    </span>
  )
}
