<template>
  <div class="update-page">
    <el-card>
      <template #header>
        <span>{{ $t('update.title') }}</span>
      </template>
      
      <el-alert type="info" :closable="false" style="margin-bottom: 20px;">
        <template #title>
          {{ $t('update.description') }}
        </template>
      </el-alert>
      
      <el-form :model="form" label-position="top" size="default">
        <el-form-item :label="$t('update.oldMod')" required>
          <div class="upload-area">
            <el-upload
              ref="oldModUploadRef"
              :action="uploadUrl"
              :data="{ session_uuid: sessionUuid }"
              :on-success="onOldModUploaded"
              :on-error="onUploadError"
              :before-upload="beforeUpload"
              :limit="1"
              :file-list="oldModFileList"
              drag
            >
              <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
              <div class="el-upload__text">
                {{ $t('update.oldModHint') }}
              </div>
            </el-upload>
            <el-alert type="info" :closable="false" class="upload-hint">
              <span v-html="$t('update.oldModHintLabel')"></span>
            </el-alert>
          </div>
        </el-form-item>
        
        <el-form-item :label="$t('update.targetBundle')" required>
          <div class="upload-area">
            <el-upload
              ref="targetUploadRef"
              :action="uploadUrl"
              :data="{ session_uuid: sessionUuid }"
              :on-success="onTargetUploaded"
              :on-error="onUploadError"
              :before-upload="beforeUpload"
              :limit="1"
              :file-list="targetFileList"
              drag
            >
              <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
              <div class="el-upload__text">
                {{ $t('update.targetBundleHint') }}
              </div>
            </el-upload>
            <el-alert type="info" :closable="false" class="upload-hint">
              <span v-html="$t('update.targetBundleHintLabel')"></span>
            </el-alert>
          </div>
        </el-form-item>
        
        <el-form-item :label="$t('update.crcCorrection')">
          <el-switch v-model="form.crc_correction" />
          <span class="form-tip">{{ $t('update.crcCorrectionDesc') }}</span>
        </el-form-item>
        
        <el-form-item :label="$t('update.assetTypes')">
          <el-checkbox-group v-model="form.asset_types">
            <el-checkbox label="Texture2D">{{ $t('update.assetTypeTexture') }}</el-checkbox>
            <el-checkbox label="TextAsset">{{ $t('update.assetTypeText') }}</el-checkbox>
            <el-checkbox label="Mesh">{{ $t('update.assetTypeMesh') }}</el-checkbox>
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
import { createUpdateTask } from '@/api/tasks'

const { t } = useI18n()
const sessionStore = useSessionStore()
const tasksStore = useTasksStore()

// 响应式检测移动端
const windowWidth = ref(window.innerWidth)
const isMobile = computed(() => windowWidth.value < 768)

const oldModUploadRef = ref()
const targetUploadRef = ref()
const submitting = ref(false)
const currentTask = ref(null)

const oldModFile = ref(null)
const targetFile = ref(null)
const oldModFileList = ref([])
const targetFileList = ref([])

const sessionUuid = computed(() => sessionStore.uuid)
const uploadUrl = '/api/files/upload'

const form = reactive({
  crc_correction: true,
  asset_types: ['Texture2D', 'TextAsset', 'Mesh']
})

const allowedExtensions = ['.bundle']
const maxSize = 500 * 1024 * 1024 // 500MB

function beforeUpload(file) {
  const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase()
  
  if (!allowedExtensions.includes(ext)) {
    ElMessage.error(t('update.unsupportedFileType'))
    return false
  }
  
  if (file.size > maxSize) {
    ElMessage.error(t('update.fileTooLarge'))
    return false
  }
  
  return true
}

function onOldModUploaded(response) {
  oldModFile.value = response
  ElMessage.success(t('update.oldModUploaded'))
}

function onTargetUploaded(response) {
  targetFile.value = response
  ElMessage.success(t('update.targetUploaded'))
}

function onUploadError(error) {
  ElMessage.error(t('update.uploadFailed'))
}

async function submitTask() {
  if (!oldModFile.value) {
    ElMessage.warning(t('update.pleaseUploadOldMod'))
    return
  }
  
  if (!targetFile.value) {
    ElMessage.warning(t('update.pleaseUploadTarget'))
    return
  }
  
  submitting.value = true
  
  try {
    const task = await createUpdateTask({
      session_uuid: sessionStore.uuid,
      old_bundle_file_id: oldModFile.value.id,
      target_file_id: targetFile.value.id,
      crc_correction: form.crc_correction,
      asset_types: form.asset_types
    })
    
    currentTask.value = task
    ElMessage.success(t('update.taskSubmitted'))
    
    await tasksStore.pollTask(task.id, 3000, 200)
    currentTask.value = tasksStore.currentTask
    
    if (currentTask.value?.status === 'completed') {
      ElMessage.success(t('update.taskCompleted'))
    } else if (currentTask.value?.status === 'failed') {
      ElMessage.error(t('update.taskFailed'))
    }
    
  } catch (e) {
    ElMessage.error(t('update.taskSubmitFailed'))
  } finally {
    submitting.value = false
  }
}

function resetForm() {
  oldModFile.value = null
  targetFile.value = null
  oldModFileList.value = []
  targetFileList.value = []
  currentTask.value = null
  form.crc_correction = true
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
.update-page {
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
  .update-page {
    padding: 0 4px;
  }
  
  .form-tip {
    display: block;
    margin-left: 0;
    margin-top: 5px;
  }
}
</style>
