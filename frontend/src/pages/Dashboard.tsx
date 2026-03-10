import { useQuery } from '@tanstack/react-query'
import { format, parseISO } from 'date-fns'
import { de } from 'date-fns/locale'
import { getSummary, getComparison, getLatestMonth } from '../api/dashboard'
import { getInsights } from '../api/insights'
import { getTransactions } from '../api/transactions'
import SpendChart from '../components/SpendChart'
import UploadZone from '../components/UploadZone'
import InsightCard from '../components/InsightCard'

const fmt = (v: number) =>
  `${v.toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`

export default function Dashboard() {
  const { data: latestMonthData } = useQuery({
    queryKey: ['dashboard', 'latest-month'],
    queryFn: () => getLatestMonth().then(r => r.data),
  })

  // Use the most recent month with data; fall back to current month while loading
  const currentMonth = latestMonthData?.month ?? format(new Date(), 'yyyy-MM')

  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ['dashboard', 'summary', currentMonth],
    queryFn: () => getSummary(currentMonth).then(r => r.data),
    enabled: !!latestMonthData,
  })

  const { data: comparison } = useQuery({
    queryKey: ['dashboard', 'comparison', currentMonth],
    queryFn: () => getComparison(currentMonth).then(r => r.data),
    enabled: !!latestMonthData,
  })

  const { data: insights } = useQuery({
    queryKey: ['insights'],
    queryFn: () => getInsights().then(r => r.data),
  })

  const { data: recentTxns } = useQuery({
    queryKey: ['transactions', 'recent'],
    queryFn: () => getTransactions({ limit: 10 }).then(r => r.data),
  })

  const chartData = summary?.categories.map(c => ({
    category: c.category,
    total: c.total,
  })) ?? []

  const delta = comparison?.delta ?? null
  const deltaPct = comparison?.delta_pct

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Übersicht</h1>
          <p className="text-gray-400 text-sm mt-0.5">
            {currentMonth ? format(parseISO(`${currentMonth}-01`), 'MMMM yyyy', { locale: de }) : ''}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: charts + upload */}
        <div className="lg:col-span-2 space-y-6">
          {/* Stats row */}
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <div className="text-gray-400 text-sm mb-1">Gesamt ausgegeben</div>
              <div className="text-2xl font-bold text-white">
                {summaryLoading ? '...' : fmt(summary?.total ?? 0)}
              </div>
              {delta !== null && (
                <div className={`text-sm mt-1 ${delta > 0 ? 'text-red-400' : 'text-green-400'}`}>
                  {delta > 0 ? '▲' : '▼'} {fmt(Math.abs(delta))} vs. letzten Monat
                  {deltaPct != null && ` (${Math.abs(deltaPct).toFixed(1)}%)`}
                </div>
              )}
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <div className="text-gray-400 text-sm mb-1">Kategorien</div>
              <div className="text-2xl font-bold text-white">
                {summary?.categories.length ?? 0}
              </div>
              <div className="text-sm text-gray-500 mt-1">diesen Monat</div>
            </div>
          </div>

          {/* Spend chart */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <h2 className="text-base font-semibold text-white mb-4">Ausgaben nach Kategorie</h2>
            {chartData.length > 0 ? (
              <SpendChart data={chartData} />
            ) : (
              <div className="h-48 flex items-center justify-center text-gray-600 text-sm">
                Lade einen Kontoauszug hoch, um deine Ausgaben zu sehen
              </div>
            )}
          </div>

          {/* Upload zone */}
          <UploadZone />

          {/* Recent transactions */}
          {recentTxns && recentTxns.items.length > 0 && (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <h2 className="text-base font-semibold text-white mb-4">Letzte Transaktionen</h2>
              <div className="space-y-2">
                {recentTxns.items.map(txn => (
                  <div key={txn.id} className="flex items-center justify-between py-2 border-b border-gray-800 last:border-0">
                    <div>
                      <div className="text-sm text-gray-200">{txn.merchant}</div>
                      <div className="text-xs text-gray-500">{txn.date} · {txn.category}</div>
                    </div>
                    <div className={`text-sm font-medium ${txn.type === 'credit' ? 'text-green-400' : 'text-gray-200'}`}>
                      {txn.type === 'credit' ? '+' : '-'}{parseFloat(txn.amount).toFixed(2)} €
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right: insights sidebar */}
        <div className="space-y-4">
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold text-white">✂ Cut the Fat</h2>
              <span className="text-xs text-gray-500">Empfehlungen</span>
            </div>
            {insights?.insights.length ? (
              <div className="space-y-3">
                {insights.insights.slice(0, 3).map(insight => (
                  <InsightCard key={insight.id} insight={insight} />
                ))}
              </div>
            ) : (
              <div className="text-gray-600 text-sm text-center py-6">
                Kontoauszüge hochladen für personalisierte Empfehlungen
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
