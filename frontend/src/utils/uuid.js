const UUID_KEY = 'bamt_session_uuid'

/**
 * Generate a new UUID v4
 */
export function generateUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0
    const v = c === 'x' ? r : (r & 0x3 | 0x8)
    return v.toString(16)
  })
}

/**
 * Get or create session UUID from localStorage
 */
export function getSessionUUID() {
  let uuid = localStorage.getItem(UUID_KEY)
  
  if (!uuid) {
    uuid = generateUUID()
    localStorage.setItem(UUID_KEY, uuid)
  }
  
  return uuid
}

/**
 * Clear session UUID from localStorage
 */
export function clearSessionUUID() {
  localStorage.removeItem(UUID_KEY)
}

/**
 * Set a new session UUID
 */
export function setSessionUUID(uuid) {
  localStorage.setItem(UUID_KEY, uuid)
}
