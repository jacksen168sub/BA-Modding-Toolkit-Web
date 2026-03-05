import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getSessionUUID } from '@/utils/uuid'
import { getSession, refreshSession } from '@/api/session'

export const useSessionStore = defineStore('session', () => {
  const uuid = ref(getSessionUUID())
  const sessionData = ref(null)
  const loading = ref(false)
  const error = ref(null)

  const expiresAt = computed(() => sessionData.value?.expires_at)
  const tasks = computed(() => sessionData.value?.tasks || [])

  async function fetchSession() {
    loading.value = true
    error.value = null
    
    try {
      sessionData.value = await getSession(uuid.value)
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function refresh() {
    try {
      sessionData.value = await refreshSession(uuid.value)
    } catch (e) {
      error.value = e.message
    }
  }

  return {
    uuid,
    sessionData,
    loading,
    error,
    expiresAt,
    tasks,
    fetchSession,
    refresh
  }
})
