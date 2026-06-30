import { useState } from 'react'

import { SCENE_ASSETS } from './constants'

export default function SceneTab() {
  const [zoom, setZoom] = useState(2)

  return (
    <div className="space-y-8">
      <div className="flex items-center gap-4">
        <h2 className="text-sm font-semibold">Scene Assets from OpenGameArt.org</h2>
        <div className="flex items-center gap-2 text-xs">
          <span>Zoom:</span>
          {[1, 2, 3, 4].map(z => (
            <button key={z} onClick={() => setZoom(z)}
              className={`px-2 py-0.5 rounded ${zoom === z ? 'bg-primary text-primary-foreground' : 'bg-muted'}`}>
              {z}x
            </button>
          ))}
        </div>
      </div>

      {Object.entries(SCENE_ASSETS).map(([category, assets]) => (
        <div key={category}>
          <h3 className="text-sm font-semibold capitalize mb-3 text-primary">{category}</h3>
          <div className="flex flex-wrap gap-4">
            {assets.map(a => (
              <div key={a.file}
                className="bg-black/20 border border-border/30 rounded-lg p-3 flex flex-col items-center gap-2">
                <div className="bg-black/40 rounded p-2 overflow-auto"
                  style={{ maxWidth: 400, maxHeight: 400 }}>
                  <img src={`/static/arena-sprites/assets/${category}/${a.file}`} alt={a.label}
                    style={{ imageRendering: 'pixelated', transform: `scale(${zoom})`, transformOrigin: 'top left' }} />
                </div>
                <span className="text-xs text-muted-foreground text-center max-w-[200px]">{a.label}</span>
              </div>
            ))}
          </div>
        </div>
      ))}

      <div>
        <h3 className="text-sm font-semibold text-primary mb-3">Misc Atlas (all-in-one)</h3>
        <div className="bg-black/20 border border-border/30 rounded-lg p-3 overflow-auto">
          <img src="/static/arena-sprites/assets/misc-atlas.png" alt="Misc tile atlas"
            style={{ imageRendering: 'pixelated', transform: `scale(${zoom})`, transformOrigin: 'top left' }} />
        </div>
      </div>

      <div className="bg-amber-500/10 border border-amber-500/30 rounded p-3">
        <h3 className="text-sm font-semibold text-amber-400">Missing Assets</h3>
        <ul className="text-xs text-muted-foreground mt-1 space-y-0.5">
          <li>Door sprites — FOUND! See "doors" section above</li>
          <li>Gym/fitness equipment — does NOT exist on OpenGameArt</li>
          <li>Alternative: use coffee maker, water cooler for "break" activities</li>
        </ul>
      </div>

      <div className="bg-blue-500/10 border border-blue-500/30 rounded p-3">
        <h3 className="text-sm font-semibold text-blue-400">License Summary</h3>
        <ul className="text-xs text-muted-foreground mt-1 space-y-0.5">
          <li><b>CC0</b>: office-appliances, flowers, tv-modern, computer-screen, scifi-tiles</li>
          <li><b>CC-BY 3.0</b>: office-chairs, rpg-indoor-expansion</li>
          <li><b>CC-BY 4.0</b>: upholstery, lpc-plants</li>
          <li><b>CC-BY-SA 3.0</b>: The Office pack, wooden furniture, shelves, house interior</li>
        </ul>
      </div>
    </div>
  )
}
