import api from './index'

/**
 * Create update task
 */
export function createUpdateTask(data) {
  return api.post('/tasks/update', data)
}

/**
 * Create pack task
 */
export function createPackTask(data) {
  return api.post('/tasks/pack', data)
}

/**
 * Create extract task
 */
export function createExtractTask(data) {
  return api.post('/tasks/extract', data)
}

/**
 * Create CRC task
 */
export function createCrcTask(data) {
  return api.post('/tasks/crc', data)
}

/**
 * Get task status
 */
export function getTask(taskId) {
  return api.get(`/tasks/${taskId}`)
}

/**
 * List session tasks
 */
export function listSessionTasks(sessionUuid) {
  return api.get(`/tasks/session/${sessionUuid}`)
}

/**
 * Delete task
 */
export function deleteTask(taskId) {
  return api.delete(`/tasks/${taskId}`)
}

/**
 * Get queue status (pending and processing counts)
 */
export function getQueueStatus() {
  return api.get('/tasks/queue/status')
}
