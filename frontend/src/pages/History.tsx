import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import { getHistory } from '../api/dashboard'
import { CATEGORY_COLORS } from '../api/transactions'

const fmt = (v: number) => `$${v.toLocaleString('en-US', { minimumFractionDigits: 0 })}`

export default function History() {
  const [months, setMonths] = useState(6)

  const { data, isLoading } = useQuery({
    queryKey: ['history', months],
    queryFn: () => getHistory(months).then(r => r.data),
  })

  const chartData = data?.months.map((month, i) => {
    const point: Record<string, string | number> = { month }
    for (const cat of data.categories) {
      point[cat] = Number(data.data[cat]?.[i] ?? 0)
    }
    return point
  }) ?? []

  // Compute month totals
  const monthTotals = chartData.map(point => ({
    month: point.month as string,
    total: data?.categories.reduce((sum, cat) => sum + Number(point[cat] ?? 0), 0) ?? 0,
  }))

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">History</h1>
        <select
          value={months}
          onChange={e => setMonths(Number(e.target.value))}
          className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-indigo-500"
        >
          <option value={3}>Last 3 months</option>
          <option value={6}>Last 6 months</option>
          <option value={12}>Last 12 months</option>
        </select>
      </div>

      {/* Monthly totals */}
      {monthTotals.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {monthTotals.map(({ month, total }) => (
            <div key={month} className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-center">
              <div className="text-xs text-gray-500 mb-1">{month}</div>
              <div className="text-lg font-bold text-white">{fmt(total)}</div>
            </div>
          ))}
        </div>
      )}

      {/* Trend chart */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <h2 className="text-base font-semibold text-white mb-4">Spending Trends by Category</h2>
        {isLoading ? (
          <div className="h-64 flex items-center justify-center text-gray-600">Loading...</div>
        ) : chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={320}>
            <LineChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="month" tick={{ fill: '#9ca3af', fontSize: 12 }} />
              <YAxis tick={{ fill: '#9ca3af', fontSize: 12 }} tickFormatter={fmt} />
              <Tooltip
                formatter={(v: any) => [fmt(Number(v ?? 0))]}
                contentStyle={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 8 }}
                labelStyle={{ color: '#f9fafb' }}
              />
              <Legend wrapperStyle={{ color: '#9ca3af', fontSize: 12 }} />
              {data?.categories.map(cat => (
                <Line
                  key={cat}
                  type="monotone"
                  dataKey={cat}
                  stroke={CATEGORY_COLORS[cat] ?? '#6366f1'}
                  strokeWidth={2}
                  dot={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-64 flex items-center justify-center text-gray-600 text-sm">
            Upload statements to see your spending history
          </div>
        )}
      </div>
    </div>
  )
}
