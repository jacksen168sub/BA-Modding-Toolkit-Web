<template>
  <div class="crc-page">
    <el-card>
      <template #header>
        <span>{{ $t('crc.title') }}</span>
      </template>
      
      <el-alert type="info" :closable="false" style="margin-bottom: 20px;">
        <template #title>
          {{ $t('crc.description') }}
        </template>
      </el-alert>
      
      <el-form :model="form" label-position="top" size="default">
        <el-form-item :label="$t('crc.modifiedFile')" required>
          <div class="upload-area">
            <el-upload
              ref="modifiedUploadRef"
              :action="uploadUrl"
              :data="{ session_uuid: sessionUuid }"
              :on-success="onModifiedUploaded"
              :on-error="onUploadError"
              :before-upload="beforeUpload"
              :limit="1"
              :file-list="modifiedFileList"
              drag
            >
              <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
              <div class="el-upload__text">
                {{ $t('crc.modifiedFileHint') }}
              </div>
            </el-upload>
            <el-alert type="info" :closable="false" class="upload-hint">
              <span v-html="$t('crc.modifiedFileHintLabel')"></span>
            </el-alert>
          </div>
        </el-form-item>
        
        <el-form-item :label="$t('crc.originalFile')" required>
          <div class="upload-area">
            <el-upload
              ref="originalUploadRef"
              :action="uploadUrl"
              :data="{ session_uuid: sessionUuid }"
              :on-success="onOriginalUploaded"
              :on-error="onUploadError"
              :before-upload="beforeUpload"
              :limit="1"
              :file-list="originalFileList"
              drag
            >
              <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
              <div class="el-upload__text">
                {{ $t('crc.originalFileHint') }}
              </div>
            </el-upload>
            <el-alert type="info" :closable="false" class="upload-hint">
              <span v-html="$t('crc.originalFileHintLabel')"></span>
            </el-alert>
          </div>
        </el-form-item>
        
        <el-form-item>
          <el-button type="primary" @click="submitTask" :loading="submitting">
            {{ $t('common.submit') }}
          </el-button>
          <el-button @click="resetForm">{{ $t('common.clear') }}</el-button>
        </el-form-item>
      </el-form>
    </el-card>
    
    <TaskStatus v-if="currentTask" :task="currentTask" />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import TaskStatus from '@/components/TaskStatus.vue'
import { useSessionStore } from '@/stores/session'
import { useTasksStore } from '@/stores/tasks'
import { createCrcTask } from '@/api/tasks'

const { t } = useI18n()
const sessionStore = useSessionStore()
const tasksStore = useTasksStore()

// 响应式检测移动端
const windowWidth = ref(window.innerWidth)
const isMobile = computed(() => windowWidth.value < 768)

const modifiedUploadRef = ref()
const originalUploadRef = ref()
const submitting = ref(false)
const currentTask = ref(null)

const modifiedFile = ref(null)
const originalFile = ref(null)
const modifiedFileList = ref([])
const originalFileList = ref([])

const sessionUuid = computed(() => sessionStore.uuid)
const uploadUrl = '/api/files/upload'

const form = reactive({})

const allowedExtensions = ['.bundle']
const maxSize = 500 * 1024 * 1024 // 500MB

function beforeUpload(file) {
  const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase()
  
  if (!allowedExtensions.includes(ext)) {
    ElMessage.error(t('crc.unsupportedFileType'))
    return false
  }
  
  if (file.size > maxSize) {
    ElMessage.error(t('crc.fileTooLarge'))
    return false
  }
  
  return true
}

function onModifiedUploaded(response) {
  modifiedFile.value = response
  ElMessage.success(t('crc.fileUploaded'))
}

function onOriginalUploaded(response) {
  originalFile.value = response
  ElMessage.success(t('crc.fileUploaded'))
}

function onUploadError(error) {
  ElMessage.error(t('crc.uploadFailed'))
}

async function submitTask() {
  if (!modifiedFile.value) {
    ElMessage.warning(t('crc.pleaseUploadModified'))
    return
  }
  
  if (!originalFile.value) {
    ElMessage.warning(t('crc.pleaseUploadOriginal'))
    return
  }
  
  submitting.value = true
  
  try {
    const task = await createCrcTask({
      session_uuid: sessionStore.uuid,
      modified_file_id: modifiedFile.value.id,
      original_file_id: originalFile.value.id
    })
    
    currentTask.value = task
    ElMessage.success(t('crc.taskSubmitted'))
    
    // 立即清空已上传文件，让用户可以开始下一个任务的上传
    modifiedFile.value = null
    originalFile.value = null
    modifiedFileList.value = []
    originalFileList.value = []
    modifiedUploadRef.value?.clearFiles()
    originalUploadRef.value?.clearFiles()
    submitting.value = false
    
    await tasksStore.pollTask(task.id, 3000, 200)
    currentTask.value = tasksStore.currentTask
    
    if (currentTask.value?.status === 'completed') {
      ElMessage.success(t('crc.taskCompleted'))
    } else if (currentTask.value?.status === 'failed') {
      ElMessage.error(t('crc.taskFailed'))
    }
    
  } catch (e) {
    ElMessage.error(t('crc.taskSubmitFailed'))
    submitting.value = false
  }
}

function resetForm() {
  modifiedFile.value = null
  originalFile.value = null
  modifiedFileList.value = []
  originalFileList.value = []
  currentTask.value = null
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
.crc-page {
  max-width: 800px;
  margin: 0 auto;
}

.upload-area {
  width: 100%;
}

:deep(.el-upload) {
  width: 100%;
}

:deep(.el-upload-dragger) {
  width: 100%;
}

.upload-hint {
  margin-top: 12px;
}

.upload-hint :deep(.el-alert__content) {
  padding: 0;
}

.upload-hint :deep(code) {
  background-color: rgba(0, 0, 0, 0.06);
  padding: 2px 5px;
  border-radius: 3px;
  font-family: monospace;
}

/* 移动端适配 */
@media (max-width: 768px) {
  .crc-page {
    padding: 0 4px;
  }
}
</style>