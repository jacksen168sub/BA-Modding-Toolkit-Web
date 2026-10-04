import api from './index'

/**
 * Get service status (task totals, queue depth, host load, storage)
 */
export function getStatus() {
  return api.get('/status')
}
