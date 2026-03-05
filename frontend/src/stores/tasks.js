import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getTask, listSessionTasks } from '@/api/tasks'

export const useTasksStore = defineStore('tasks', () => {
  const tasks = ref([])
  const currentTask = ref(null)
  const loading = ref(false)
  const error = ref(null)

  async function fetchTasks(sessionUuid) {
    loading.value = true
    error.value = null
    
    try {
      tasks.value = await listSessionTasks(sessionUuid)
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function fetchTask(taskId) {
    loading.value = true
    error.value = null
    
    try {
      currentTask.value = await getTask(taskId)
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function pollTask(taskId, interval = 3000, maxAttempts = 100) {
    let attempts = 0
    
    return new Promise((resolve, reject) => {
      const poll = async () => {
        attempts++
        
        try {
          const task = await getTask(taskId)
          currentTask.value = task
          
          if (task.status === 'completed') {
            resolve(task)
          } else if (task.status === 'failed') {
            reject(new Error(task.error_message || 'Task failed'))
          } else if (attempts >= maxAttempts) {
            reject(new Error('Polling timeout'))
          } else {
            setTimeout(poll, interval)
          }
        } catch (e) {
          reject(e)
        }
      }
      
      poll()
    })
  }

  return {
    tasks,
    currentTask,
    loading,
    error,
    fetchTasks,
    fetchTask,
    pollTask
  }
})
