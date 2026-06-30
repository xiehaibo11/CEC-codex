import { useEffect, useState } from 'react'

type AnimatedSpriteProps = {
  presetId: number
  baseRow: number
  dirOffset: number
  frames: number
  speed?: number
  scale?: number
}

export default function AnimatedSprite({
  presetId,
  baseRow,
  dirOffset,
  frames,
  speed = 200,
  scale = 1.2,
}: AnimatedSpriteProps) {
  const [col, setCol] = useState(0)
  const row = baseRow + dirOffset
  const size = 64 * scale
  const sheetW = 13 * size
  const sheetH = 54 * size
  const sprite = `avatar_${String(presetId).padStart(2, '0')}.png`

  useEffect(() => {
    if (frames <= 1) { setCol(0); return }
    let idx = 0
    const t = setInterval(() => { idx = (idx + 1) % frames; setCol(idx) }, speed)
    return () => clearInterval(t)
  }, [presetId, baseRow, dirOffset, frames, speed])

  return (
    <div style={{
      width: size, height: size,
      backgroundImage: `url(/static/arena-sprites/${sprite})`,
      backgroundSize: `${sheetW}px ${sheetH}px`,
      backgroundPosition: `-${col * size}px -${row * size}px`,
      imageRendering: 'pixelated',
    }} />
  )
}
