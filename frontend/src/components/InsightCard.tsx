import { useState } from 'react'
import type { Insight } from '../api/insights'

interface InsightCardProps {
  insight: Insight
}

const icons: Record<string, string> = {
  warning: '⚠️',
  info: '💡',
  success: '✅',
}

const borders: Record<string, string> = {
  warning: 'border-amber-500/40 bg-amber-950/20',
  info: 'border-blue-500/40 bg-blue-950/20',
  success: 'border-green-500/40 bg-green-950/20',
}

export default function InsightCard({ insight }: InsightCardProps) {
  const [dismissed, setDismissed] = useState(false)

  if (dismissed) return null

  return (
    <div className={`border rounded-xl p-4 flex gap-3 ${borders[insight.type] ?? borders.info}`}>
      <span className="text-xl flex-shrink-0">{icons[insight.type] ?? '💡'}</span>
      <div className="flex-1">
        <p className="text-sm text-gray-200 leading-relaxed">{insight.text}</p>
      </div>
      <button
        onClick={() => setDismissed(true)}
        className="text-gray-600 hover:text-gray-400 flex-shrink-0 text-xs"
        title="Dismiss"
      >
        ✕
      </button>
    </div>
  )
}
