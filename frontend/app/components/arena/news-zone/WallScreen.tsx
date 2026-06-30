import type { ReactNode } from 'react'
import { SCREEN_BORDER, SCREEN_H } from './constants'

interface WallScreenProps {
  x: number
  y: number
  w: number
  label: string
  children: ReactNode
}

export function WallScreen({ x, y, w, label, children }: WallScreenProps) {
  return (
    <div style={{
      position: 'absolute', left: x, top: y,
      width: w + SCREEN_BORDER * 2,
      height: SCREEN_H + SCREEN_BORDER * 2,
    }}>
      {/* Outer frame — dark metallic border */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'linear-gradient(180deg, #4a4a5a 0%, #2a2a3a 50%, #1a1a2a 100%)',
        borderRadius: 6,
        boxShadow: '0 4px 12px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.1)',
      }}>
        {/* Inner bezel */}
        <div style={{
          position: 'absolute',
          left: SCREEN_BORDER, top: SCREEN_BORDER,
          width: w, height: SCREEN_H,
          background: '#0a0e1a',
          borderRadius: 3,
          overflow: 'hidden',
          border: '1px solid #000',
        }}>
          {/* Scanline overlay */}
          <div style={{
            position: 'absolute', inset: 0, zIndex: 3, pointerEvents: 'none',
            backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.12) 2px, rgba(0,0,0,0.12) 4px)',
          }} />
          {/* Screen glow */}
          <div style={{
            position: 'absolute', inset: 0, zIndex: 2, pointerEvents: 'none',
            boxShadow: 'inset 0 0 20px rgba(56,189,248,0.1)',
          }} />
          {/* Label */}
          <div style={{
            position: 'absolute', top: 2, right: 6, fontSize: 9,
            color: '#334155', fontWeight: 'bold', zIndex: 4, letterSpacing: 1,
            fontFamily: 'monospace',
          }}>
            {label}
          </div>
          {/* Content */}
          <div style={{ position: 'relative', zIndex: 1, height: '100%', fontFamily: 'monospace' }}>
            {children}
          </div>
        </div>
      </div>
      {/* Wall mount bracket */}
      <div style={{
        position: 'absolute',
        top: -4, left: '50%', transform: 'translateX(-50%)',
        width: 40, height: 6,
        background: 'linear-gradient(180deg, #5a5a6a, #3a3a4a)',
        borderRadius: '3px 3px 0 0',
        boxShadow: '0 -1px 3px rgba(0,0,0,0.3)',
      }} />
      {/* Power LED */}
      <div style={{
        position: 'absolute',
        bottom: 2, right: SCREEN_BORDER + 6,
        width: 4, height: 4, borderRadius: '50%',
        background: '#22c55e',
        boxShadow: '0 0 4px #22c55e',
      }} />
    </div>
  )
}
