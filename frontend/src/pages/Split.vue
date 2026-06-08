<template>
  <div class="split-page">
    <el-card>
      <template #header>
        <span>{{ $t('split.title') }}</span>
      </template>

      <el-alert type="info" :closable="false" style="margin-bottom: 20px;">
        <template #title>
          {{ $t('split.description') }}
        </template>
      </el-alert>

      <el-form :model="form" label-position="top" size="default">
        <el-form-item :label="$t('split.legacyFile')" required>
          <div class="upload-area">
            <el-upload
              ref="legacyUploadRef"
              :action="uploadUrl"
              :data="{ session_uuid: sessionUuid }"
              :on-success="onLegacyUploaded"
              :on-error="onUploadError"
              :before-upload="beforeUpload"
              :limit="1"
              :file-list="legacyFileList"
              drag
            >
              <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
              <div class="el-upload__text">
                {{ $t('split.legacyFileHint') }}
              </div>
            </el-upload>
          </div>
        </el-form-item>

        <el-form-item required>
          <template #label>
            {{ $t('split.modernFiles') }}
            <el-tag type="primary" size="small" class="upload-badge">{{ $t('common.multiSelect') }}</el-tag>
          </template>
          <div class="upload-area">
            <el-upload
              ref="modernUploadRef"
              :action="uploadUrl"
              :data="{ session_uuid: sessionUuid }"
              :on-success="onModernUploaded"
              :on-error="onUploadError"
              :on-remove="onModernRemoved"
              :before-upload="beforeUpload"
              :file-list="modernFileList"
              multiple
              drag
            >
              <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
              <div class="el-upload__text">
                {{ $t('split.modernFilesHint') }}
              </div>
            </el-upload>
          </div>
        </el-form-item>

        <el-form-item :label="$t('split.assetTypes')">
          <el-checkbox-group v-model="form.asset_types">
            <el-checkbox label="Texture2D">{{ $t('split.assetTypeTexture') }}</el-checkbox>
            <el-checkbox label="TextAsset">{{ $t('split.assetTypeText') }}</el-checkbox>
            <el-checkbox label="Mesh">{{ $t('split.assetTypeMesh') }}</el-checkbox>
          </el-checkbox-group>
        </el-form-item>

        <el-form-item :label="$t('split.compression')">
          <el-select v-model="form.compression">
            <el-option label="LZ4" value="lz4" />
            <el-option label="LZMA" value="lzma" />
          </el-select>
        </el-form-item>

        <el-form-item :label="$t('split.crcCorrection')">
          <el-switch v-model="form.crc_correction" />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="submitTask" :loading="submitting">
            {{ $t('split.submit') }}
          </el-button>
          <el-button @click="resetForm">{{ $t('common.clear') }}</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <TaskStatus v-if="currentTask" :task="currentTask" />
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import TaskStatus from '@/components/TaskStatus.vue'
import { useSessionStore } from '@/stores/session'
import { useTasksStore } from '@/stores/tasks'
import { createSplitTask } from '@/api/tasks'

const { t } = useI18n()
const sessionStore = useSessionStore()
const tasksStore = useTasksStore()

const legacyUploadRef = ref()
const modernUploadRef = ref()
const submitting = ref(false)
const currentTask = ref(null)

const legacyFile = ref(null)
const modernFiles = ref([])
const legacyFileList = ref([])
const modernFileList = ref([])

const sessionUuid = computed(() => sessionStore.uuid)
const uploadUrl = '/api/files/upload'

const form = reactive({
  asset_types: ['Texture2D', 'TextAsset', 'Mesh'],
  compression: 'lzma',
  crc_correction: true
})

const allowedExtensions = ['.bundle']
const maxSize = 500 * 1024 * 1024

function beforeUpload(file) {
  const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase()
  if (!allowedExtensions.includes(ext)) {
    ElMessage.error(t('split.unsupportedFileType'))
    return false
  }
  if (file.size > maxSize) {
    ElMessage.error(t('split.fileTooLarge'))
    return false
  }
  return true
}

function onLegacyUploaded(response) {
  legacyFile.value = response
  ElMessage.success(t('split.legacyFileUploaded'))
}

function onModernUploaded(response) {
  modernFiles.value.push(response)
  ElMessage.success(t('split.modernFileUploaded'))
}

function onModernRemoved(file) {
  const index = modernFiles.value.findIndex(f => f.id === file.response?.id)
  if (index > -1) modernFiles.value.splice(index, 1)
}

function onUploadError() {
  ElMessage.error(t('split.uploadFailed'))
}

async function submitTask() {
  if (!legacyFile.value) {
    ElMessage.warning(t('split.pleaseUploadLegacy'))
    return
  }
  if (modernFiles.value.length === 0) {
    ElMessage.warning(t('split.pleaseUploadModern'))
    return
  }

  submitting.value = true

  try {
    const task = await createSplitTask({
      session_uuid: sessionStore.uuid,
      legacy_file_id: legacyFile.value.id,
      modern_file_ids: modernFiles.value.map(f => f.id),
      asset_types: form.asset_types,
      compression: form.compression,
      no_crc: !form.crc_correction
    })

    currentTask.value = task
    ElMessage.success(t('split.taskSubmitted'))

    legacyFile.value = null
    modernFiles.value = []
    legacyFileList.value = []
    modernFileList.value = []
    legacyUploadRef.value?.clearFiles()
    modernUploadRef.value?.clearFiles()
    submitting.value = false

    await tasksStore.pollTask(task.id, 3000, 200)
    currentTask.value = tasksStore.currentTask

    if (currentTask.value?.status === 'completed') {
      ElMessage.success(t('split.taskCompleted'))
    } else if (currentTask.value?.status === 'failed') {
      ElMessage.error(t('split.taskFailed'))
    }
  } catch (e) {
    ElMessage.error(t('split.taskSubmitFailed'))
    submitting.value = false
  }
}

function resetForm() {
  legacyFile.value = null
  modernFiles.value = []
  legacyFileList.value = []
  modernFileList.value = []
  currentTask.value = null
  form.asset_types = ['Texture2D', 'TextAsset', 'Mesh']
  form.compression = 'lzma'
  form.crc_correction = true
}
</script>

<style scoped>
.split-page {
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

.upload-badge {
  margin-left: 6px;
  vertical-align: middle;
}

@media (max-width: 768px) {
  .split-page {
    padding: 0 4px;
  }
}
</style>
