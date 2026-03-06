import api from './index'

/**
 * Get version info
 */
export function getVersion() {
  return api.get('/version')
}
