import { api } from './client'

export interface Upload {
  id: number
  filename: string
  uploaded_at: string
  row_count: number
  status: string
  error_message?: string
}

export interface UploadResult {
  upload: Upload
  imported: number
  skipped: number
}

export const uploadFile = (file: File, onProgress?: (pct: number) => void) => {
  const form = new FormData()
  form.append('file', file)
  return api.post<UploadResult>('/api/uploads', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: e => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100))
    },
  })
}

export const getUploads = () => api.get<Upload[]>('/api/uploads')

export const deleteUpload = (id: number) => api.delete(`/api/uploads/${id}`)
