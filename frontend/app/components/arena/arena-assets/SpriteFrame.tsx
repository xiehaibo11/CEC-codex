type SpriteFrameProps = {
  presetId: number
  row: number
  col: number
  scale?: number
}

export default function SpriteFrame({ presetId, row, col, scale = 1.5 }: SpriteFrameProps) {
  const size = 64 * scale
  const sheetW = 13 * size
  const sheetH = 54 * size
  const sprite = `avatar_${String(presetId).padStart(2, '0')}.png`

  return (
    <div style={{
      width: size, height: size,
      backgroundImage: `url(/static/arena-sprites/${sprite})`,
      backgroundSize: `${sheetW}px ${sheetH}px`,
      backgroundPosition: `-${col * size}px -${row * size}px`,
      imageRendering: 'pixelated',
      flexShrink: 0,
    }} />
  )
}
