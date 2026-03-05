import api from './index'

/**
 * Get session info with tasks
 */
export function getSession(uuid) {
  return api.get(`/session/${uuid}`)
}

/**
 * Refresh session expiration
 */
export function refreshSession(uuid) {
  return api.post(`/session/${uuid}/refresh`)
}

/**
 * Delete session
 */
export function deleteSession(uuid) {
  return api.delete(`/session/${uuid}`)
}
