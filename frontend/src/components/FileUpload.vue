<template>
  <el-upload
    ref="uploadRef"
    :action="uploadUrl"
    :data="{ session_uuid: sessionUuid }"
    :on-success="handleSuccess"
    :on-error="handleError"
    :on-progress="handleProgress"
    :before-upload="beforeUpload"
    :limit="1"
    :auto-upload="autoUpload"
    drag
  >
    <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
    <div class="el-upload__text">
      拖拽文件到此处或 <em>点击上传</em>
    </div>
    <template #tip>
      <div class="el-upload__tip">
        支持 .bundle, .png, .skel, .atlas 文件，最大 500MB
      </div>
    </template>
  </el-upload>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { useSessionStore } from '@/stores/session'

const props = defineProps({
  autoUpload: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['success', 'error', 'progress'])

const sessionStore = useSessionStore()
const uploadRef = ref()

const sessionUuid = computed(() => sessionStore.uuid)
const uploadUrl = '/api/files/upload'

const allowedExtensions = ['.bundle', '.png', '.skel', '.atlas']
const maxSize = 500 * 1024 * 1024 // 500MB

function beforeUpload(file) {
  const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase()
  
  if (!allowedExtensions.includes(ext)) {
    ElMessage.error(`不支持的文件类型: ${ext}`)
    return false
  }
  
  if (file.size > maxSize) {
    ElMessage.error('文件大小超过 500MB 限制')
    return false
  }
  
  return true
}

function handleSuccess(response) {
  ElMessage.success('上传成功')
  emit('success', response)
}

function handleError(error) {
  ElMessage.error('上传失败: ' + error.message)
  emit('error', error)
}

function handleProgress(event) {
  emit('progress', event.percent)
}

function submit() {
  uploadRef.value?.submit()
}

defineExpose({ submit })
</script>

<style scoped>
.el-upload {
  width: 100%;
}

:deep(.el-upload-dragger) {
  width: 100%;
}
</style>
