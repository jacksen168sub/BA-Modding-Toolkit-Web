<template>
  <div class="pack-page">
    <el-card>
      <template #header>
        <span>{{ $t('pack.title') }}</span>
      </template>
      
      <el-alert type="info" :closable="false" style="margin-bottom: 20px;">
        <template #title>
          {{ $t('pack.description') }}
        </template>
      </el-alert>
      
      <el-form :model="form" label-position="top" size="default">
        <el-form-item :label="$t('pack.assetFolder')" required>
          <div class="upload-area">
            <el-upload
              ref="assetUploadRef"
              :action="uploadUrl"
              :data="{ session_uuid: sessionUuid }"
              :on-success="onAssetUploaded"
              :on-error="onUploadError"
              :on-remove="onAssetRemoved"
              :before-upload="beforeUploadAsset"
              :file-list="assetFileList"
              multiple
              drag
            >
              <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
              <div class="el-upload__text">
                {{ $t('pack.assetFolderHint') }}
              </div>
            </el-upload>
            <el-alert type="info" :closable="false" class="upload-hint">
              <span v-html="$t('pack.assetFolderHintLabel')"></span>
            </el-alert>
          </div>
        </el-form-item>
        
        <el-form-item :label="$t('pack.targetBundle')" required>
          <div class="upload-area">
            <el-upload
              ref="targetUploadRef"
              :action="uploadUrl"
              :data="{ session_uuid: sessionUuid }"
              :on-success="onTargetUploaded"
              :on-error="onUploadError"
              :before-upload="beforeUploadBundle"
              :limit="1"
              :file-list="targetFileList"
              drag
            >
              <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
              <div class="el-upload__text">
                {{ $t('pack.targetBundleHint') }}
              </div>
            </el-upload>
            <el-alert type="info" :closable="false" class="upload-hint">
              <span v-html="$t('pack.targetBundleHintLabel')"></span>
            </el-alert>
          </div>
        </el-form-item>
        
        <el-form-item :label="$t('pack.crcCorrection')">
          <el-switch v-model="form.crc_correction" />
          <span class="form-tip">{{ $t('pack.crcCorrectionDesc') }}</span>
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
import { createPackTask } from '@/api/tasks'

const { t } = useI18n()
const sessionStore = useSessionStore()
const tasksStore = useTasksStore()

// 响应式检测移动端
const windowWidth = ref(window.innerWidth)
const isMobile = computed(() => windowWidth.value < 768)

const assetUploadRef = ref()
const targetUploadRef = ref()
const submitting = ref(false)
const currentTask = ref(null)

const assetFiles = ref([])
const targetFile = ref(null)
const assetFileList = ref([])
const targetFileList = ref([])

const sessionUuid = computed(() => sessionStore.uuid)
const uploadUrl = '/api/files/upload'

const form = reactive({
  crc_correction: true
})

const assetExtensions = ['.png', '.skel', '.atlas']
const bundleExtensions = ['.bundle']
const maxSize = 500 * 1024 * 1024 // 500MB

function beforeUploadAsset(file) {
  const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase()
  
  if (!assetExtensions.includes(ext)) {
    ElMessage.error(t('pack.unsupportedFileType'))
    return false
  }
  
  if (file.size > maxSize) {
    ElMessage.error(t('pack.fileTooLarge'))
    return false
  }
  
  return true
}

function beforeUploadBundle(file) {
  const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase()
  
  if (!bundleExtensions.includes(ext)) {
    ElMessage.error(t('pack.unsupportedFileType'))
    return false
  }
  
  if (file.size > maxSize) {
    ElMessage.error(t('pack.fileTooLarge'))
    return false
  }
  
  return true
}

function onAssetUploaded(response) {
  assetFiles.value.push(response)
}

function onAssetRemoved(file) {
  const index = assetFiles.value.findIndex(f => f.id === file.response?.id)
  if (index > -1) {
    assetFiles.value.splice(index, 1)
  }
}

function onTargetUploaded(response) {
  targetFile.value = response
  ElMessage.success(t('pack.targetUploaded'))
}

function onUploadError(error) {
  ElMessage.error(t('pack.uploadFailed'))
}

async function submitTask() {
  if (assetFiles.value.length === 0) {
    ElMessage.warning(t('pack.pleaseUploadAssets'))
    return
  }
  
  if (!targetFile.value) {
    ElMessage.warning(t('pack.pleaseUploadTarget'))
    return
  }
  
  submitting.value = true
  
  try {
    const task = await createPackTask({
      session_uuid: sessionStore.uuid,
      asset_folder_files: assetFiles.value.map(f => f.id),
      target_bundle_file_id: targetFile.value.id,
      crc_correction: form.crc_correction
    })
    
    currentTask.value = task
    ElMessage.success(t('pack.taskSubmitted'))
    
    // 立即清空已上传文件，让用户可以开始下一个任务的上传
    assetFiles.value = []
    targetFile.value = null
    assetFileList.value = []
    targetFileList.value = []
    assetUploadRef.value?.clearFiles()
    targetUploadRef.value?.clearFiles()
    submitting.value = false
    
    await tasksStore.pollTask(task.id, 3000, 200)
    currentTask.value = tasksStore.currentTask
    
    if (currentTask.value?.status === 'completed') {
      ElMessage.success(t('pack.taskCompleted'))
    } else if (currentTask.value?.status === 'failed') {
      ElMessage.error(t('pack.taskFailed'))
    }
    
  } catch (e) {
    ElMessage.error(t('pack.taskSubmitFailed'))
    submitting.value = false
  }
}

function resetForm() {
  assetFiles.value = []
  targetFile.value = null
  assetFileList.value = []
  targetFileList.value = []
  currentTask.value = null
  form.crc_correction = true
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
.pack-page {
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

.form-tip {
  margin-left: 10px;
  color: #909399;
  font-size: 12px;
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
  .pack-page {
    padding: 0 4px;
  }
  
  .form-tip {
    display: block;
    margin-left: 0;
    margin-top: 5px;
  }
}
</style>