import type { ReactNode } from 'react'

interface SummaryMetricCardProps {
  label: ReactNode
  children: ReactNode
}

export default function SummaryMetricCard({ label, children }: SummaryMetricCardProps) {
  return (
    <div>
      <div className="text-[10px] text-muted-foreground">{label}</div>
      {children}
    </div>
  )
}
