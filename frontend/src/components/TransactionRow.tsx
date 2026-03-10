import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { updateCategory, CATEGORIES, CATEGORY_COLORS, type Transaction } from '../api/transactions'
import { format } from 'date-fns'

interface TransactionRowProps {
  transaction: Transaction
}

const sourceBadge: Record<string, string> = {
  ai: 'bg-blue-900/40 text-blue-300',
  rule: 'bg-purple-900/40 text-purple-300',
  manual: 'bg-green-900/40 text-green-300',
}

export default function TransactionRow({ transaction: txn }: TransactionRowProps) {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)

  const mutation = useMutation({
    mutationFn: (category: string) => updateCategory(txn.id, category),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      setEditing(false)
    },
  })

  const color = CATEGORY_COLORS[txn.category] ?? '#9ca3af'
  const amount = parseFloat(txn.amount)
  const formattedDate = (() => {
    try { return format(new Date(txn.date + 'T00:00:00'), 'MMM d, yyyy') }
    catch { return txn.date }
  })()

  return (
    <tr className="border-b border-gray-800 hover:bg-gray-800/30 transition-colors">
      <td className="px-4 py-3 text-sm text-gray-400 whitespace-nowrap">{formattedDate}</td>
      <td className="px-4 py-3 text-sm text-gray-200 max-w-xs">
        <div className="truncate" title={txn.description}>{txn.merchant}</div>
        {txn.description !== txn.merchant && (
          <div className="text-xs text-gray-500 truncate">{txn.description}</div>
        )}
      </td>
      <td className="px-4 py-3 text-sm font-medium text-right whitespace-nowrap">
        <span className={txn.type === 'credit' ? 'text-green-400' : 'text-gray-200'}>
          {txn.type === 'credit' ? '+' : '-'}{amount.toFixed(2)} €
        </span>
      </td>
      <td className="px-4 py-3">
        {editing ? (
          <select
            className="bg-gray-800 border border-gray-600 rounded px-2 py-1 text-sm text-gray-200 focus:outline-none focus:border-indigo-500"
            value={txn.category}
            onChange={e => mutation.mutate(e.target.value)}
            onBlur={() => setEditing(false)}
            autoFocus
            disabled={mutation.isPending}
          >
            {CATEGORIES.map(cat => (
              <option key={cat} value={cat}>{cat}</option>
            ))}
          </select>
        ) : (
          <button
            onClick={() => setEditing(true)}
            className="flex items-center gap-1.5 group"
            title="Kategorie ändern"
          >
            <span
              className="inline-block w-2 h-2 rounded-full flex-shrink-0"
              style={{ backgroundColor: color }}
            />
            <span className="text-sm text-gray-300 group-hover:text-white">{txn.category}</span>
            <span className="text-gray-600 group-hover:text-gray-400 text-xs">✎</span>
          </button>
        )}
      </td>
      <td className="px-4 py-3">
        <span className={`text-xs px-2 py-0.5 rounded-full ${sourceBadge[txn.category_source] ?? sourceBadge.ai}`}>
          {txn.category_source === 'ai' ? 'KI' : txn.category_source === 'rule' ? 'Regel' : 'Manuell'}
        </span>
      </td>
    </tr>
  )
}
