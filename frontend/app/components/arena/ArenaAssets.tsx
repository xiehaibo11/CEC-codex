import { useState } from 'react'

import {
  AnimationsTab,
  CurrentTab,
  MoodsTab,
  SceneTab,
} from './arena-assets'
import SceneEditor from './SceneEditor'

type Tab = 'animations' | 'current' | 'moods' | 'scene' | 'editor'

export default function ArenaAssets() {
  const [tab, setTab] = useState<Tab>('animations')
  const [selectedPreset, setSelectedPreset] = useState(1)

  const tabs: { key: Tab; label: string }[] = [
    { key: 'animations', label: 'All Animations (Full Sheet)' },
    { key: 'current', label: 'Current Mappings' },
    { key: 'moods', label: 'Mood Bubbles' },
    { key: 'scene', label: 'Scene Assets' },
    { key: 'editor', label: 'Scene Editor' },
  ]

  return (
    <div className="flex flex-col gap-4 h-full overflow-y-auto p-4">
      <h1 className="text-xl font-bold">Arena Asset Library</h1>
      <div className="flex flex-wrap gap-2">
        {tabs.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-3 py-1.5 rounded text-sm font-medium ${
              tab === t.key ? 'bg-primary text-primary-foreground' : 'bg-muted'
            }`}>{t.label}</button>
        ))}
      </div>
      {tab === 'animations' && <AnimationsTab preset={selectedPreset} onPresetChange={setSelectedPreset} />}
      {tab === 'current' && <CurrentTab preset={selectedPreset} onPresetChange={setSelectedPreset} />}
      {tab === 'moods' && <MoodsTab />}
      {tab === 'scene' && <SceneTab />}
      {tab === 'editor' && <SceneEditor />}
    </div>
  )
}
