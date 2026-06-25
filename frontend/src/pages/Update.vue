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

        <!-- Match preview for batch mode -->
        <el-form-item v-if="matchPreview.length > 1" :label="$t('update.matchPreview')">
          <el-table :data="matchPreview" size="small" border stripe>
            <el-table-column type="index" width="50" />
            <el-table-column :label="$t('update.oldMod')" prop="oldName" min-width="200" show-overflow-tooltip />
            <el-table-column width="60" align="center">
              <template #default>
                <el-icon><Right /></el-icon>
              </template>
            </el-table-column>
            <el-table-column :label="$t('update.targetBundle')" prop="targetName" min-width="200" show-overflow-tooltip />
          </el-table>
          <div v-if="unmatchedOld.length || unmatchedTarget.length" class="unmatched-warning">
            <el-alert type="warning" :closable="false">
              <template #title>
                <span v-if="unmatchedOld.length">
                  {{ $t('update.unmatchedOld') }}: {{ unmatchedOld.map(f => f.name).join(', ') }}
                </span>
                <span v-if="unmatchedTarget.length" style="margin-left: 12px;">
                  {{ $t('update.unmatchedTarget') }}: {{ unmatchedTarget.map(f => f.name).join(', ') }}
                </span>
              </template>
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
import { UploadFilled, Right } from '@element-plus/icons-vue'
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

// Extract character name from bundle filename (mirrors backend logic)
function extractCharName(filename) {
  if (!filename) return 'unknown'
  const patterns = [
    /spinelobbies-([a-zA-Z0-9_-]+?)-_mxdependency/,
    /spinecharacters-([a-zA-Z0-9_-]+?)-_mxprolog/,
    /spinebackground-([a-zA-Z0-9_-]+?)-_mxdependency/,
    /assets-_mx-spinecharacters-([a-zA-Z0-9_-]+?)-_mxdependency/,
  ]
  for (const pattern of patterns) {
    const match = filename.match(pattern)
    if (match) {
      const name = match[1]
      const idx = name.lastIndexOf('_')
      if (idx > 0) return `${name.slice(0, idx)}(${name.slice(idx + 1)})`
      return name
    }
  }
  return 'unknown'
}

// Extract sort key (filename without CRC) for matching
function extractSortKey(filename) {
  const name = filename.replace(/\.[^.]+$/, '') // Remove extension
  const match = name.match(/^(.+)_(\d+)$/)
  return match ? match[1] : name
}

// Compute matched pairs for preview
const matchPreview = computed(() => {
  if (oldModFiles.value.length <= 1 && targetFiles.value.length <= 1) {
    return []
  }
  
  // Group by character name
  const oldByChar = {}
  for (const f of oldModFiles.value) {
    const char = extractCharName(f.name)
    const sortKey = extractSortKey(f.name)
    if (!oldByChar[char]) oldByChar[char] = []
    oldByChar[char].push({ sortKey, file: f })
  }
  
  const targetByChar = {}
  for (const f of targetFiles.value) {
    const char = extractCharName(f.name)
    const sortKey = extractSortKey(f.name)
    if (!targetByChar[char]) targetByChar[char] = []
    targetByChar[char].push({ sortKey, file: f })
  }
  
  const pairs = []
  const chars = [...new Set([...Object.keys(oldByChar), ...Object.keys(targetByChar)])].sort()
  
  for (const char of chars) {
    const oldList = (oldByChar[char] || []).sort((a, b) => a.sortKey.localeCompare(b.sortKey))
    const targetList = (targetByChar[char] || []).sort((a, b) => a.sortKey.localeCompare(b.sortKey))
    const maxLen = Math.max(oldList.length, targetList.length)
    for (let i = 0; i < maxLen; i++) {
      pairs.push({
        oldName: oldList[i]?.file.name || '—',
        targetName: targetList[i]?.file.name || '—',
      })
    }
  }
  
  return pairs
})

const unmatchedOld = computed(() => {
  if (oldModFiles.value.length <= 1 && targetFiles.value.length <= 1) return []
  const matchedOldNames = new Set(matchPreview.value.filter(p => p.oldName !== '—').map(p => p.oldName))
  return oldModFiles.value.filter(f => !matchedOldNames.has(f.name))
})

const unmatchedTarget = computed(() => {
  if (oldModFiles.value.length <= 1 && targetFiles.value.length <= 1) return []
  const matchedTargetNames = new Set(matchPreview.value.filter(p => p.targetName !== '—').map(p => p.targetName))
  return targetFiles.value.filter(f => !matchedTargetNames.has(f.name))
})

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
    let payload
    if (oldModFiles.value.length === 1 && targetFiles.value.length === 1) {
      // Single mode
      payload = {
        session_uuid: sessionStore.uuid,
        old_bundle_file_id: oldModFiles.value[0].id,
        target_file_id: targetFiles.value[0].id,
        crc_correction: form.crc_correction,
        asset_types: form.asset_types,
        strategy: form.strategy,
        compression: form.compression
      }
    } else {
      // Batch mode
      payload = {
        session_uuid: sessionStore.uuid,
        old_bundle_file_ids: oldModFiles.value.map(f => f.id),
        target_file_ids: targetFiles.value.map(f => f.id),
        crc_correction: form.crc_correction,
        asset_types: form.asset_types,
        strategy: form.strategy,
        compression: form.compression
      }
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

.unmatched-warning {
  margin-top: 8px;
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
