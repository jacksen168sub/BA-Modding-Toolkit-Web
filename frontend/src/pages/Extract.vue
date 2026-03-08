<template>
  <div class="extract-page">
    <el-card>
      <template #header>
        <span>{{ $t('extract.title') }}</span>
      </template>
      
      <el-alert type="info" :closable="false" style="margin-bottom: 20px;">
        <template #title>
          {{ $t('extract.description') }}
        </template>
      </el-alert>
      
      <el-form :model="form" label-position="top" size="default">
        <el-form-item :label="$t('extract.bundleFile')" required>
          <div class="upload-area">
            <el-upload
              ref="bundleUploadRef"
              :action="uploadUrl"
              :data="{ session_uuid: sessionUuid }"
              :on-success="onBundleUploaded"
              :on-error="onUploadError"
              :on-remove="onBundleRemoved"
              :before-upload="beforeUpload"
              :file-list="bundleFileList"
              multiple
              drag
            >
              <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
              <div class="el-upload__text">
                {{ $t('extract.bundleFileHint') }}
              </div>
            </el-upload>
            <el-alert type="info" :closable="false" class="upload-hint">
              <span v-html="$t('extract.bundleFileHintLabel')"></span>
            </el-alert>
          </div>
        </el-form-item>
        
        <el-form-item :label="$t('extract.assetTypes')">
          <el-checkbox-group v-model="form.asset_types">
            <el-checkbox label="Texture2D">{{ $t('extract.assetTypeTexture') }}</el-checkbox>
            <el-checkbox label="TextAsset">{{ $t('extract.assetTypeText') }}</el-checkbox>
            <el-checkbox label="Mesh">{{ $t('extract.assetTypeMesh') }}</el-checkbox>
          </el-checkbox-group>
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
import { createExtractTask } from '@/api/tasks'

const { t } = useI18n()
const sessionStore = useSessionStore()
const tasksStore = useTasksStore()

// 响应式检测移动端
const windowWidth = ref(window.innerWidth)
const isMobile = computed(() => windowWidth.value < 768)

const bundleUploadRef = ref()
const submitting = ref(false)
const currentTask = ref(null)

const bundleFiles = ref([])
const bundleFileList = ref([])

const sessionUuid = computed(() => sessionStore.uuid)
const uploadUrl = '/api/files/upload'

const form = reactive({
  asset_types: ['Texture2D', 'TextAsset', 'Mesh']
})

const allowedExtensions = ['.bundle']
const maxSize = 500 * 1024 * 1024 // 500MB

function beforeUpload(file) {
  const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase()
  
  if (!allowedExtensions.includes(ext)) {
    ElMessage.error(t('extract.unsupportedFileType'))
    return false
  }
  
  if (file.size > maxSize) {
    ElMessage.error(t('extract.fileTooLarge'))
    return false
  }
  
  return true
}

function onBundleUploaded(response) {
  bundleFiles.value.push(response)
}

function onBundleRemoved(file) {
  const index = bundleFiles.value.findIndex(f => f.id === file.response?.id)
  if (index > -1) {
    bundleFiles.value.splice(index, 1)
  }
}

function onUploadError(error) {
  ElMessage.error(t('extract.uploadFailed'))
}

async function submitTask() {
  if (bundleFiles.value.length === 0) {
    ElMessage.warning(t('extract.pleaseUploadBundle'))
    return
  }
  
  submitting.value = true
  
  try {
    const task = await createExtractTask({
      session_uuid: sessionStore.uuid,
      bundle_file_ids: bundleFiles.value.map(f => f.id),
      asset_types: form.asset_types
    })
    
    currentTask.value = task
    ElMessage.success(t('extract.taskSubmitted'))
    
    await tasksStore.pollTask(task.id, 3000, 200)
    currentTask.value = tasksStore.currentTask
    
    if (currentTask.value?.status === 'completed') {
      ElMessage.success(t('extract.taskCompleted'))
    } else if (currentTask.value?.status === 'failed') {
      ElMessage.error(t('extract.taskFailed'))
    }
    
  } catch (e) {
    ElMessage.error(t('extract.taskSubmitFailed'))
  } finally {
    submitting.value = false
  }
}

function resetForm() {
  bundleFiles.value = []
  bundleFileList.value = []
  currentTask.value = null
  form.asset_types = ['Texture2D', 'TextAsset', 'Mesh']
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
.extract-page {
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
  .extract-page {
    padding: 0 4px;
  }
}
</style>