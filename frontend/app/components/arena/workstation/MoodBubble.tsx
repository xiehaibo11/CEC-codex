import { useEffect, useState } from 'react'
import { STATE_MOODS } from './helpers'
import type { CharacterState } from './types'

export function MoodBubble({ state }: { state: CharacterState }) {
  const [moodIndex, setMoodIndex] = useState(0)

  useEffect(() => {
    const moods = STATE_MOODS[state] || []
    if (moods.length === 0) {
      setMoodIndex(0)
      return
    }

    const pickMoodIndex = () => {
      if (state === 'idle') {
        return Math.random() < 0.7 ? 0 : 1
      }
      return 0
    }

    setMoodIndex(pickMoodIndex())

    if (state !== 'idle') {
      return
    }

    const timer = setInterval(() => {
      setMoodIndex(pickMoodIndex())
    }, 6000)

    return () => clearInterval(timer)
  }, [state])

  const mood = (STATE_MOODS[state] || [])[moodIndex]
  if (!mood) return null

  return (
    <div className="absolute" style={{
      top: 6, right: -8, zIndex: 15,
    }}>
      <div style={{
        position: 'relative',
        background: mood.bg, border: '2px solid rgba(255,255,255,0.2)',
        borderRadius: 10, padding: 3,
        boxShadow: '0 2px 6px rgba(0,0,0,0.3)',
      }}>
        {mood.img ? (
          <img src={mood.img} alt="" style={{ width: 20, height: 20, display: 'block' }} />
        ) : (
          <span style={{ display: 'block', fontSize: 18, lineHeight: 1 }}>{mood.emoji}</span>
        )}
        <div style={{
          position: 'absolute', bottom: -6, left: 3,
          width: 0, height: 0,
          borderTop: `6px solid ${mood.bg}`,
          borderRight: '6px solid transparent',
        }} />
      </div>
    </div>
  )
}
