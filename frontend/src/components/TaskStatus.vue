<template>
  <el-card v-if="task" class="task-status-card">
    <template #header>
      <div class="card-header">
        <span>{{ $t('taskDetail.type') }}</span>
        <el-tag :type="statusType">{{ statusText }}</el-tag>
      </div>
    </template>
    
    <el-descriptions :column="isMobile ? 1 : 2" border size="small">
      <el-descriptions-item :label="$t('taskDetail.type')">{{ taskTypeText }}</el-descriptions-item>
      <el-descriptions-item :label="$t('taskDetail.createdAt')">{{ formatTime(task.created_at) }}</el-descriptions-item>
      <el-descriptions-item :label="$t('taskDetail.completedAt')">
        {{ task.completed_at ? formatTime(task.completed_at) : '-' }}
      </el-descriptions-item>
    </el-descriptions>
    
    <!-- CLI 日志 / 错误信息 -->
    <div v-if="displayLog" class="cli-log" :class="{ 'has-error': task.status === 'failed' }">
      <div class="cli-log-header">
        <h4>{{ task.status === 'failed' ? $t('taskDetail.errorLog') : $t('taskDetail.cliLog') }}</h4>
        <el-button size="small" @click="copyLog">{{ $t('taskDetail.copyLog') }}</el-button>
      </div>
      <el-input
        :model-value="displayLogContent"
        type="textarea"
        :rows="isMobile ? 8 : 10"
        readonly
        class="log-textarea"
      />
    </div>
    
    <div v-if="task.files && task.files.length > 0" class="output-files">
      <h4>{{ $t('taskDetail.outputFiles') }}</h4>
      <el-table :data="task.files" stripe size="small">
        <el-table-column prop="original_name" :label="$t('taskDetail.fileName')" />
        <el-table-column prop="size" :label="$t('taskDetail.fileSize')">
          <template #default="{ row }">
            {{ formatSize(row.size) }}
          </template>
        </el-table-column>
        <el-table-column :label="$t('common.download')" width="80">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="downloadFile(row.id)">
              {{ $t('common.download') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
    
    <div v-if="task.status === 'processing'" class="progress">
      <el-progress :percentage="50" :indeterminate="true" />
      <p>{{ $t('taskDetail.processing') }}</p>
    </div>
  </el-card>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { getDownloadUrl } from '@/api/files'

const { t } = useI18n()

const props = defineProps({
  task: {
    type: Object,
    default: null
  }
})

// 响应式检测移动端
const windowWidth = ref(window.innerWidth)
const isMobile = computed(() => windowWidth.value < 768)

const statusMap = {
  pending: { text: 'tasks.statuses.pending', type: 'info' },
  processing: { text: 'tasks.statuses.processing', type: 'warning' },
  completed: { text: 'tasks.statuses.completed', type: 'success' },
  failed: { text: 'tasks.statuses.failed', type: 'danger' }
}

const typeMap = {
  update: 'tasks.types.update',
  pack: 'tasks.types.pack',
  extract: 'tasks.types.extract',
  crc: 'tasks.types.crc',
  jp_gl_convert: 'tasks.types.jp_gl_convert'
}

const statusType = computed(() => statusMap[props.task?.status]?.type || 'info')
const statusText = computed(() => t(statusMap[props.task?.status]?.text || 'unknown'))
const taskTypeText = computed(() => t(typeMap[props.task?.type] || props.task?.type))

// 是否显示日志区域（有 cli_log 或失败时有 error_message）
const displayLog = computed(() => {
  if (!props.task) return false
  return !!(props.task.cli_log || (props.task.status === 'failed' && props.task.error_message))
})

// 合并显示的日志内容
const displayLogContent = computed(() => {
  if (!props.task) return ''
  const parts = []
  if (props.task.status === 'failed' && props.task.error_message) {
    parts.push('[ERROR] ' + props.task.error_message)
  }
  if (props.task.cli_log) {
    parts.push(props.task.cli_log)
  }
  return parts.join('\n\n')
})

function formatTime(time) {
  return new Date(time).toLocaleString()
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB'
  return (bytes / 1024 / 1024).toFixed(2) + ' MB'
}

function downloadFile(fileId) {
  window.open(getDownloadUrl(fileId), '_blank')
}

function copyLog() {
  if (displayLogContent.value) {
    navigator.clipboard.writeText(displayLogContent.value)
    ElMessage.success(t('taskDetail.logCopied'))
  }
}

function handleResize() {
  windowWidth.value = window.innerWidth
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.task-status-card {
  margin-top: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.error-message {
  margin-top: 15px;
}

.cli-log {
  margin-top: 20px;
}

.cli-log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.cli-log-header h4 {
  margin: 0;
}

.log-textarea {
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 12px;
}

.log-textarea :deep(textarea) {
  background-color: #1e1e1e;
  color: #d4d4d4;
}

.cli-log.has-error .log-textarea :deep(textarea) {
  border-color: #f56c6c;
}

.output-files {
  margin-top: 20px;
}

.output-files h4 {
  margin-bottom: 10px;
}

.progress {
  margin-top: 20px;
  text-align: center;
}

.progress p {
  margin-top: 10px;
  color: #909399;
}

/* 移动端适配 */
@media (max-width: 768px) {
  .cli-log-header {
    flex-direction: column;
    gap: 10px;
    align-items: flex-start;
  }
  
  .cli-log-header h4 {
    font-size: 14px;
  }
}
</style>