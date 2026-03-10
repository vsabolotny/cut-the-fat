import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import { CATEGORY_COLORS } from '../api/transactions'

interface SpendChartProps {
  data: Array<{ category: string; total: number }>
}

const fmt = (v: number) => `$${v.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`

export default function SpendChart({ data }: SpendChartProps) {
  const sorted = [...data].sort((a, b) => b.total - a.total)

  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={sorted} margin={{ top: 0, right: 0, left: 10, bottom: 60 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
        <XAxis
          dataKey="category"
          tick={{ fill: '#9ca3af', fontSize: 12 }}
          angle={-40}
          textAnchor="end"
          interval={0}
        />
        <YAxis tick={{ fill: '#9ca3af', fontSize: 12 }} tickFormatter={fmt} />
        <Tooltip
          formatter={(v: any) => [fmt(Number(v ?? 0)), 'Spent']}
          contentStyle={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 8 }}
          labelStyle={{ color: '#f9fafb' }}
        />
        <Bar dataKey="total" radius={[4, 4, 0, 0]}>
          {sorted.map((entry) => (
            <Cell key={entry.category} fill={CATEGORY_COLORS[entry.category] ?? '#6366f1'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
