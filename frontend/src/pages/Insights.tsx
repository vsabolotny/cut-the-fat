import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getInsights } from '../api/insights'
import { getUploads, deleteUpload } from '../api/uploads'
import InsightCard from '../components/InsightCard'
import { format } from 'date-fns'

export default function Insights() {
  const queryClient = useQueryClient()

  const { data: insights, isLoading, refetch } = useQuery({
    queryKey: ['insights'],
    queryFn: () => getInsights().then(r => r.data),
  })

  const { data: uploads } = useQuery({
    queryKey: ['uploads'],
    queryFn: () => getUploads().then(r => r.data),
  })

  const deleteMutation = useMutation({
    mutationFn: deleteUpload,
    onSuccess: () => queryClient.invalidateQueries(),
  })

  const handleForceRefresh = async () => {
    await getInsights(true)
    queryClient.invalidateQueries({ queryKey: ['insights'] })
    refetch()
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Insights</h1>
          <p className="text-gray-400 text-sm mt-0.5">AI-powered cost-cutting recommendations</p>
        </div>
        <button
          onClick={handleForceRefresh}
          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-lg transition-colors"
        >
          Refresh Insights
        </button>
      </div>

      {/* Insights list */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-3">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-base font-semibold text-white">✂ Cut the Fat Recommendations</h2>
          {insights?.cached && (
            <span className="text-xs text-gray-500">Cached</span>
          )}
          {insights?.generated_at && (
            <span className="text-xs text-gray-600">
              {(() => {
                try { return format(new Date(insights.generated_at), 'MMM d, h:mm a') }
                catch { return '' }
              })()}
            </span>
          )}
        </div>
        {isLoading ? (
          <div className="text-gray-600 text-sm py-8 text-center">Generating insights...</div>
        ) : insights?.insights.length ? (
          insights.insights.map(insight => (
            <InsightCard key={insight.id} insight={insight} />
          ))
        ) : (
          <div className="text-gray-600 text-sm py-8 text-center">
            No insights yet. Upload bank statements to get started.
          </div>
        )}
      </div>

      {/* Upload history */}
      {uploads && uploads.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <h2 className="text-base font-semibold text-white mb-4">Upload History</h2>
          <div className="space-y-2">
            {uploads.map(upload => (
              <div key={upload.id} className="flex items-center justify-between py-2 border-b border-gray-800 last:border-0">
                <div>
                  <div className="text-sm text-gray-200">{upload.filename}</div>
                  <div className="text-xs text-gray-500">
                    {(() => {
                      try { return format(new Date(upload.uploaded_at), 'MMM d, yyyy h:mm a') }
                      catch { return upload.uploaded_at }
                    })()} · {upload.row_count} transactions
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    upload.status === 'done' ? 'bg-green-900/40 text-green-300' :
                    upload.status === 'error' ? 'bg-red-900/40 text-red-300' :
                    'bg-yellow-900/40 text-yellow-300'
                  }`}>
                    {upload.status}
                  </span>
                  <button
                    onClick={() => {
                      if (confirm('Delete this upload and all its transactions?')) {
                        deleteMutation.mutate(upload.id)
                      }
                    }}
                    className="text-gray-600 hover:text-red-400 text-sm transition-colors"
                    title="Delete upload"
                  >
                    ✕
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
