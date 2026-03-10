import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getTransactions } from '../api/transactions'
import { useCategories } from '../hooks/useCategories'
import TransactionRow from '../components/TransactionRow'

export default function Transactions() {
  const [month, setMonth] = useState('')
  const [category, setCategory] = useState('')
  const [search, setSearch] = useState('')
  const [offset, setOffset] = useState(0)
  const limit = 50
  const { categories } = useCategories()

  const { data, isLoading } = useQuery({
    queryKey: ['transactions', { month, category, search, offset }],
    queryFn: () => getTransactions({ month: month || undefined, category: category || undefined, search: search || undefined, limit, offset }).then(r => r.data),
  })

  const totalPages = data ? Math.ceil(data.total / limit) : 0
  const currentPage = Math.floor(offset / limit)

  return (
    <div className="max-w-6xl mx-auto space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Transaktionen</h1>
        {data && (
          <span className="text-sm text-gray-400">{data.total.toLocaleString()} gesamt</span>
        )}
      </div>

      {/* Filters */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 flex flex-wrap gap-3">
        <input
          type="month"
          value={month}
          onChange={e => { setMonth(e.target.value); setOffset(0) }}
          className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-indigo-500"
        />
        <select
          value={category}
          onChange={e => { setCategory(e.target.value); setOffset(0) }}
          className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-indigo-500"
        >
          <option value="">Alle Kategorien</option>
          {categories.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <input
          type="search"
          placeholder="Händler suchen..."
          value={search}
          onChange={e => { setSearch(e.target.value); setOffset(0) }}
          className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-indigo-500 flex-1 min-w-40"
        />
      </div>

      {/* Table */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-800 text-xs text-gray-500 uppercase tracking-wide">
              <th className="px-4 py-3 text-left">Datum</th>
              <th className="px-4 py-3 text-left">Händler</th>
              <th className="px-4 py-3 text-right">Betrag</th>
              <th className="px-4 py-3 text-left">Kategorie</th>
              <th className="px-4 py-3 text-left">Quelle</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr><td colSpan={5} className="px-4 py-12 text-center text-gray-600">Wird geladen...</td></tr>
            ) : !data?.items.length ? (
              <tr><td colSpan={5} className="px-4 py-12 text-center text-gray-600">Keine Transaktionen gefunden</td></tr>
            ) : (
              data.items.map(txn => <TransactionRow key={txn.id} transaction={txn} />)
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <button
            onClick={() => setOffset(Math.max(0, offset - limit))}
            disabled={offset === 0}
            className="px-4 py-2 bg-gray-800 rounded-lg text-sm text-gray-400 hover:text-white disabled:opacity-40 transition-colors"
          >
            ← Zurück
          </button>
          <span className="text-sm text-gray-500">
            Seite {currentPage + 1} von {totalPages}
          </span>
          <button
            onClick={() => setOffset(offset + limit)}
            disabled={offset + limit >= (data?.total ?? 0)}
            className="px-4 py-2 bg-gray-800 rounded-lg text-sm text-gray-400 hover:text-white disabled:opacity-40 transition-colors"
          >
            Weiter →
          </button>
        </div>
      )}
    </div>
  )
}
