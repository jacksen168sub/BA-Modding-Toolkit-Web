import api from './index'

/**
 * Upload a file
 */
export async function uploadFile(file, sessionUuid, onProgress) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('session_uuid', sessionUuid)
  
  const config = {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  }
  
  if (onProgress) {
    config.onUploadProgress = (progressEvent) => {
      const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total)
      onProgress(percentCompleted)
    }
  }
  
  return api.post('/files/upload', formData, config)
}

/**
 * Get file info
 */
export function getFileInfo(fileId) {
  return api.get(`/files/${fileId}`)
}

/**
 * Get download URL
 */
export function getDownloadUrl(fileId) {
  return `/api/files/download/${fileId}`
}

/**
 * Delete a file
 */
export function deleteFile(fileId) {
  return api.delete(`/files/${fileId}`)
}

/**
 * List session files
 */
export function listSessionFiles(sessionUuid) {
  return api.get(`/files/session/${sessionUuid}`)
}
