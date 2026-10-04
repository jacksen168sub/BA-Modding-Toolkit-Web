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
        <el-form-item required>
          <template #label>
            {{ $t('update.oldMod') }}
            <el-tag type="success" size="small" class="upload-badge">{{ $t('common.batchSupported') }}</el-tag>
          </template>
          <div class="upload-area">
            <el-upload
              ref="oldModUploadRef"
              :action="uploadUrl"
              :data="{ session_uuid: sessionUuid }"
              :on-success="onOldModUploaded"
              :on-error="onUploadError"
              :on-remove="onOldModRemoved"
              :before-upload="beforeUpload"
              :file-list="oldModFileList"
              multiple
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
        
        <el-form-item required>
          <template #label>
            {{ $t('update.targetBundle') }}
            <el-tag type="success" size="small" class="upload-badge">{{ $t('common.batchSupported') }}</el-tag>
          </template>
          <div class="upload-area">
            <el-upload
              ref="targetUploadRef"
              :action="uploadUrl"
              :data="{ session_uuid: sessionUuid }"
              :on-success="onTargetUploaded"
              :on-error="onUploadError"
              :on-remove="onTargetRemoved"
              :before-upload="beforeUpload"
              :file-list="targetFileList"
              multiple
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
        
        <el-form-item :label="$t('update.strategy')">
          <el-select v-model="form.strategy" style="width: 100%;">
            <el-option label="Path ID" value="path_id" />
            <el-option label="Container + Name + Type" value="cont_name_type" />
            <el-option label="Name + Type" value="name_type" />
          </el-select>
          <div class="strategy-hint">
            <p>{{ $t('update.strategyHintLine1') }}</p>
            <p>{{ $t('update.strategyHintLine2') }}</p>
            <p>{{ $t('update.strategyHintLine3') }}</p>
          </div>
        </el-form-item>

        <el-form-item :label="$t('update.compression')">
          <el-select v-model="form.compression" style="width: 100%;">
            <el-option label="LZMA" value="lzma" />
            <el-option label="LZ4" value="lz4" />
            <el-option label="Original" value="original" />
            <el-option label="None" value="none" />
          </el-select>
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
import { validateFilename } from '@/utils/uploadRules'
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

const oldModFiles = ref([])
const targetFiles = ref([])
const oldModFileList = ref([])
const targetFileList = ref([])

const sessionUuid = computed(() => sessionStore.uuid)
const uploadUrl = '/api/files/upload'

const form = reactive({
  crc_correction: true,
  asset_types: ['Texture2D', 'TextAsset', 'Mesh'],
  strategy: 'path_id',
  compression: 'lzma'
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

  // Filename black/whitelist (regex). Awaited so el-upload aborts on false.
  return validateFilename(file.name).then(verdict => {
    if (!verdict.ok) {
      ElMessage.error(t(verdict.key, verdict.params))
      return false
    }
    return true
  })
}

function onOldModUploaded(response) {
  oldModFiles.value.push({ id: response.id, name: response.original_name || response.name })
  ElMessage.success(t('update.oldModUploaded'))
}

function onOldModRemoved(file) {
  const idx = oldModFiles.value.findIndex(f => f.id === (file.response?.id))
  if (idx > -1) oldModFiles.value.splice(idx, 1)
}

function onTargetUploaded(response) {
  targetFiles.value.push({ id: response.id, name: response.original_name || response.name })
  ElMessage.success(t('update.targetUploaded'))
}

function onTargetRemoved(file) {
  const idx = targetFiles.value.findIndex(f => f.id === (file.response?.id))
  if (idx > -1) targetFiles.value.splice(idx, 1)
}

function onUploadError(error) {
  ElMessage.error(t('update.uploadFailed'))
}

async function submitTask() {
  if (oldModFiles.value.length === 0) {
    ElMessage.warning(t('update.pleaseUploadOldMod'))
    return
  }
  
  if (targetFiles.value.length === 0) {
    ElMessage.warning(t('update.pleaseUploadTarget'))
    return
  }
  
  submitting.value = true
  
  try {
    // One pooled N-to-N run: every old file is a source, every target receives the pool.
    const payload = {
      session_uuid: sessionStore.uuid,
      old_bundle_file_ids: oldModFiles.value.map(f => f.id),
      target_file_ids: targetFiles.value.map(f => f.id),
      crc_correction: form.crc_correction,
      asset_types: form.asset_types,
      strategy: form.strategy,
      compression: form.compression
    }

    const task = await createUpdateTask(payload)
    
    currentTask.value = task
    ElMessage.success(t('update.taskSubmitted'))
    
    // 立即清空已上传文件，让用户可以开始下一个任务的上传
    oldModFiles.value = []
    targetFiles.value = []
    oldModFileList.value = []
    targetFileList.value = []
    oldModUploadRef.value?.clearFiles()
    targetUploadRef.value?.clearFiles()
    submitting.value = false
    
    await tasksStore.pollTask(task.id, 3000, 200)
    currentTask.value = tasksStore.currentTask
    
    if (currentTask.value?.status === 'completed') {
      ElMessage.success(t('update.taskCompleted'))
    } else if (currentTask.value?.status === 'failed') {
      ElMessage.error(t('update.taskFailed'))
    }
    
  } catch (e) {
    ElMessage.error(t('update.taskSubmitFailed'))
    submitting.value = false
  }
}

function resetForm() {
  oldModFiles.value = []
  targetFiles.value = []
  oldModFileList.value = []
  targetFileList.value = []
  currentTask.value = null
  form.crc_correction = true
  form.asset_types = ['Texture2D', 'TextAsset', 'Mesh']
  form.strategy = 'path_id'
  form.compression = 'lzma'
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

.upload-badge {
  margin-left: 6px;
  vertical-align: middle;
}

.strategy-hint {
  margin-top: 6px;
  font-size: 12px;
  color: #909399;
  line-height: 1.6;
}

.strategy-hint p {
  margin: 0;
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
