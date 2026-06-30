export interface PlacedAsset {
  id: string
  src: string
  label: string
  x: number
  y: number
  scale: number
  cropX: number
  cropY: number
  cropW: number
  cropH: number
}

export interface WorkstationArea {
  x: number; y: number; w: number; h: number; scale: number
}

export interface NewsArea {
  x: number; y: number; w: number; h: number; scale: number
}

export interface SceneConfig {
  sceneVersion?: number
  assets: PlacedAsset[]
  animationMap: Record<string, string>
  workstationArea?: WorkstationArea
  newsArea?: NewsArea
}

// Pre-extracted individual item PNGs (auto-cropped by PIL)
export interface AssetItem {
  id: string
  label: string
  file: string  // filename in /static/arena-sprites/assets/items/
  w: number
  h: number
}
