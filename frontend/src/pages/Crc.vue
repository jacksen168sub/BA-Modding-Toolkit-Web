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
              ref="bundleUploadRef"
              :action="uploadUrl"
              :data="{ session_uuid: sessionUuid }"
              :on-success="onBundleUploaded"
              :on-error="onUploadError"
              :before-upload="beforeUpload"
              :limit="1"
              :file-list="bundleFileList"
              drag
            >
              <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
              <div class="el-upload__text">
                {{ $t('crc.modifiedFileHint') }}
              </div>
              <template #tip>
                <div class="el-upload__tip">.bundle</div>
              </template>
            </el-upload>
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

const bundleUploadRef = ref()
const submitting = ref(false)
const currentTask = ref(null)

const bundleFile = ref(null)
const bundleFileList = ref([])

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

function onBundleUploaded(response) {
  bundleFile.value = response
  ElMessage.success(t('crc.fileUploaded'))
}

function onUploadError(error) {
  ElMessage.error(t('crc.uploadFailed'))
}

async function submitTask() {
  if (!bundleFile.value) {
    ElMessage.warning(t('crc.pleaseUploadFile'))
    return
  }
  
  submitting.value = true
  
  try {
    const task = await createCrcTask({
      session_uuid: sessionStore.uuid,
      bundle_file_id: bundleFile.value.id
    })
    
    currentTask.value = task
    ElMessage.success(t('crc.taskSubmitted'))
    
    await tasksStore.pollTask(task.id, 3000, 200)
    currentTask.value = tasksStore.currentTask
    
    if (currentTask.value?.status === 'completed') {
      ElMessage.success(t('crc.taskCompleted'))
    } else if (currentTask.value?.status === 'failed') {
      ElMessage.error(t('crc.taskFailed'))
    }
    
  } catch (e) {
    ElMessage.error(t('crc.taskSubmitFailed'))
  } finally {
    submitting.value = false
  }
}

function resetForm() {
  bundleFile.value = null
  bundleFileList.value = []
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

/* 移动端适配 */
@media (max-width: 768px) {
  .crc-page {
    padding: 0 4px;
  }
}
</style>