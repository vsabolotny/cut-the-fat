import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { useQueryClient } from '@tanstack/react-query'
import { uploadFile } from '../api/uploads'

export default function UploadZone() {
  const queryClient = useQueryClient()
  const [status, setStatus] = useState<'idle' | 'uploading' | 'done' | 'error'>('idle')
  const [message, setMessage] = useState('')
  const [progress, setProgress] = useState(0)

  const onDrop = useCallback(async (files: File[]) => {
    if (!files.length) return
    const file = files[0]
    setStatus('uploading')
    setProgress(0)
    setMessage('')
    try {
      const res = await uploadFile(file, setProgress)
      setStatus('done')
      setMessage(`${res.data.imported} Transaktionen importiert (${res.data.skipped} übersprungen)`)
      queryClient.invalidateQueries()
    } catch (err: any) {
      setStatus('error')
      const detail = err.response?.data?.detail || err.message || 'Upload failed'
      setMessage(detail)
    }
  }, [queryClient])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/csv': ['.csv'],
      'application/vnd.ms-excel': ['.xls'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/pdf': ['.pdf'],
    },
    multiple: false,
    disabled: status === 'uploading',
  })

  const borderColor = isDragActive
    ? 'border-indigo-400'
    : status === 'done'
    ? 'border-green-500'
    : status === 'error'
    ? 'border-red-500'
    : 'border-gray-700'

  const bgColor = isDragActive ? 'bg-indigo-900/20' : 'bg-gray-900'

  return (
    <div
      {...getRootProps()}
      className={`border-2 border-dashed ${borderColor} ${bgColor} rounded-xl p-8 text-center cursor-pointer transition-all hover:border-indigo-500 hover:bg-indigo-900/10`}
    >
      <input {...getInputProps()} />
      {status === 'uploading' ? (
        <div className="space-y-3">
          <div className="text-gray-300 text-sm">Wird hochgeladen und kategorisiert...</div>
          <div className="w-full bg-gray-700 rounded-full h-2">
            <div
              className="bg-indigo-500 h-2 rounded-full transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="text-xs text-gray-500">{progress}%</div>
        </div>
      ) : (
        <div className="space-y-2">
          <div className="text-4xl">📂</div>
          <div className="text-gray-200 font-medium">
            {isDragActive ? 'Kontoauszug ablegen' : 'Kontoauszug hier ablegen'}
          </div>
          <div className="text-sm text-gray-500">CSV, Excel (.xlsx/.xls) oder PDF</div>
          {status === 'done' && (
            <div className="text-green-400 text-sm font-medium mt-2">✓ {message}</div>
          )}
          {status === 'error' && (
            <div className="text-red-400 text-sm mt-2">⚠ {message}</div>
          )}
          {status === 'idle' && (
            <div className="text-xs text-gray-600 mt-1">oder hier klicken</div>
          )}
        </div>
      )}
    </div>
  )
}
