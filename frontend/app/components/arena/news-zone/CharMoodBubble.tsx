import type { MoodOption } from './types'

export function CharMoodBubble({ mood }: { mood: MoodOption }) {
  return (
    <div style={{
      position: 'absolute', top: 6, right: -8, zIndex: 15,
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
