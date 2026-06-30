type MiniEquityLineProps = {
  data: number[]
  color: string
  width: number
  height: number
}

export function MiniEquityLine({ data, color, width, height }: MiniEquityLineProps) {
  if (data.length < 2) return null
  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1
  const pad = 1
  const w = width - pad * 2
  const h = height - pad * 2
  const points = data.map((v, i) => {
    const x = pad + (i / (data.length - 1)) * w
    const y = pad + h - ((v - min) / range) * h
    return `${x},${y}`
  }).join(' ')
  return (
    <svg width={width} height={height} style={{ display: 'block' }}>
      <polyline points={points} fill="none" stroke={color} strokeWidth={1.2} opacity={0.7} />
    </svg>
  )
}
