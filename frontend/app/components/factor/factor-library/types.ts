export interface FactorDef {
  name: string; category: string; display_name: string; display_name_zh?: string
  description: string; description_zh?: string; value_range?: string; unit?: string
}

export interface FactorLibraryData {
  factors: FactorDef[]
  categories: string[]
  category_labels: any
}

export type DialogStep = 'confirm' | 'progress' | 'done'

export interface AnalysisFactor {
  name: string
  displayName: string
}
