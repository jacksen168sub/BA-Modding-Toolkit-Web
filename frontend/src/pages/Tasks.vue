<template>
  <div class="tasks-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <span>{{ $t('tasks.title') }}</span>
            <el-tag v-if="queueStatus.queueLength > 0" type="warning" class="queue-tag">
              {{ $t('tasks.queueStatus', { pending: queueStatus.pending, processing: queueStatus.processing, max: queueStatus.max_concurrent }) }}
            </el-tag>
          </div>
          <el-button type="primary" @click="refreshTasks" :loading="loading">
            {{ $t('common.refresh') }}
          </el-button>
        </div>
      </template>
      
      <!-- 移动端卡片视图 -->
      <div class="tasks-mobile" v-if="isMobile">
        <el-card v-for="(task, index) in tasks" :key="task.id" class="task-card-mobile" shadow="hover" @click="showTaskDetail(task.id)">
          <div class="task-card-row">
            <span class="label">{{ $t('tasks.name') }}:</span>
            <span class="task-name">{{ task.name || 'unknown' }}</span>
          </div>
          <div class="task-card-row">
            <span class="label">{{ $t('tasks.type') }}:</span>
            <el-tag size="small">{{ getTypeText(task.type) }}</el-tag>
          </div>
          <div class="task-card-row">
            <span class="label">{{ $t('tasks.status') }}:</span>
            <div class="status-with-queue">
              <el-tag :type="getStatusType(task.status)" size="small">{{ getStatusText(task.status) }}</el-tag>
              <el-tooltip v-if="task.queue_info" :content="getQueueTooltip(task.queue_info)" placement="top">
                <el-tag type="info" size="small" class="position-tag">
                  {{ $t('tasks.queuePosition', { position: task.queue_info.user_position }) }}
                </el-tag>
              </el-tooltip>
            </div>
          </div>
          <div class="task-card-row">
            <span class="label">{{ $t('tasks.createdAt') }}:</span>
            <span>{{ formatTime(task.created_at) }}</span>
          </div>
        </el-card>
        <el-empty v-if="!loading && tasks.length === 0" :description="$t('tasks.empty')" />
      </div>
      
      <!-- 桌面端表格视图 -->
      <el-table :data="tasks" stripe v-loading="loading" v-if="!isMobile">
        <el-table-column :label="$t('tasks.name')">
          <template #default="{ row }">
            <span class="task-name">{{ row.name || 'unknown' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="type" :label="$t('tasks.type')">
          <template #default="{ row }">
            <el-tag>{{ getTypeText(row.type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" :label="$t('tasks.status')">
          <template #default="{ row }">
            <div class="status-with-queue">
              <el-tag :type="getStatusType(row.status)">
                {{ getStatusText(row.status) }}
              </el-tag>
              <el-tooltip v-if="row.queue_info" :content="getQueueTooltip(row.queue_info)" placement="top">
                <el-tag type="info" size="small" class="position-tag">
                  {{ $t('tasks.queuePosition', { position: row.queue_info.user_position }) }}
                </el-tag>
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" :label="$t('tasks.createdAt')">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column :label="$t('tasks.actions')" width="100">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="showTaskDetail(row.id)">
              {{ $t('tasks.detail') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <el-empty v-if="!loading && tasks.length === 0 && !isMobile" :description="$t('tasks.empty')" />
    </el-card>
    
    <!-- Task Detail Dialog -->
    <el-dialog v-model="dialogVisible" :title="$t('tasks.detailTitle')" :width="isMobile ? '90%' : '600px'">
      <TaskStatus v-if="selectedTask" :task="selectedTask" />
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import TaskStatus from '@/components/TaskStatus.vue'
import { useSessionStore } from '@/stores/session'
import { useTasksStore } from '@/stores/tasks'
import { getTask, getQueueStatus } from '@/api/tasks'

const { t } = useI18n()
const sessionStore = useSessionStore()
const tasksStore = useTasksStore()

const loading = ref(false)
const tasks = ref([])
const dialogVisible = ref(false)
const selectedTask = ref(null)
const queueStatus = ref({ pending: 0, processing: 0, queueLength: 0, max_concurrent: 2 })
let refreshInterval = null

// 响应式检测移动端
const windowWidth = ref(window.innerWidth)
const isMobile = computed(() => windowWidth.value < 768)

const typeMap = {
  update: 'tasks.types.update',
  pack: 'tasks.types.pack',
  extract: 'tasks.types.extract',
  crc: 'tasks.types.crc',
  jp_gl_convert: 'tasks.types.jp_gl_convert'
}

const statusMap = {
  pending: { text: 'tasks.statuses.pending', type: 'info' },
  processing: { text: 'tasks.statuses.processing', type: 'warning' },
  completed: { text: 'tasks.statuses.completed', type: 'success' },
  failed: { text: 'tasks.statuses.failed', type: 'danger' }
}

function getTypeText(type) {
  return t(typeMap[type] || type)
}

function getStatusText(status) {
  return t(statusMap[status]?.text || status)
}

function getStatusType(status) {
  return statusMap[status]?.type || 'info'
}

function formatTime(time) {
  return new Date(time).toLocaleString()
}

// Get tooltip text for queue info
function getQueueTooltip(queueInfo) {
  const userQueue = t('tasks.userQueue', { count: queueInfo.user_queue_length })
  const globalQueue = t('tasks.globalQueue', { count: queueInfo.global_queue_length })
  return `${userQueue}\n${globalQueue}`
}

async function refreshTasks(showLoading = true) {
  if (showLoading) loading.value = true
  try {
    tasks.value = await tasksStore.fetchTasks(sessionStore.uuid)
    tasks.value = tasksStore.tasks
    // 获取队列状态
    queueStatus.value = await getQueueStatus()
  } finally {
    if (showLoading) loading.value = false
  }
}

async function showTaskDetail(taskId) {
  selectedTask.value = await getTask(taskId)
  dialogVisible.value = true
}

function handleResize() {
  windowWidth.value = window.innerWidth
}

onMounted(() => {
  refreshTasks()
  window.addEventListener('resize', handleResize)
  // Auto refresh every 3 seconds (without loading indicator)
  refreshInterval = setInterval(() => refreshTasks(false), 3000)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})
</script>

<style scoped>
.tasks-page {
  max-width: 1000px;
  margin: 0 auto;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.queue-tag {
  font-size: 12px;
}

.status-with-queue {
  display: flex;
  align-items: center;
  gap: 6px;
}

.position-tag {
  font-weight: bold;
}

/* 移动端卡片样式 */
.tasks-mobile {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.task-card-mobile {
  cursor: pointer;
  transition: transform 0.2s;
}

.task-card-mobile:active {
  transform: scale(0.98);
}

.task-card-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.task-card-row:last-child {
  border-bottom: none;
}

.task-card-row .label {
  color: #909399;
  font-size: 14px;
}

.task-name {
  font-weight: 500;
  color: #303133;
}

/* 移动端适配 */
@media (max-width: 768px) {
  .tasks-page {
    padding: 0 4px;
  }
  
  .card-header {
    flex-wrap: wrap;
    gap: 8px;
  }
  
  .card-header span {
    font-size: 16px;
  }
}
</style>