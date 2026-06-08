<template>
  <div class="spine-preview-page">
    <!-- Upload Section -->
    <el-card v-if="!playerLoaded">
      <template #header>
        <span>{{ $t('spinePreview.title') }}</span>
      </template>

      <el-alert type="info" :closable="false" style="margin-bottom: 20px;">
        <template #title>
          {{ $t('spinePreview.description') }}
        </template>
      </el-alert>

      <el-form :model="form" label-position="top" size="default">
        <el-form-item required>
          <template #label>
            {{ $t('spinePreview.bundleFile') }}
            <el-tag type="success" size="small" class="upload-badge">{{ $t('common.batchSupported') }}</el-tag>
          </template>
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
                {{ $t('spinePreview.bundleFileHint') }}
              </div>
            </el-upload>
          </div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="startPreview" :loading="loading" :disabled="bundleFiles.length === 0">
            {{ $t('spinePreview.startPreview') }}
          </el-button>
          <el-button @click="resetForm">{{ $t('common.clear') }}</el-button>
        </el-form-item>
      </el-form>

      <!-- Progress -->
      <el-steps v-if="loading" :active="currentStep" align-center style="margin-top: 20px;">
        <el-step :title="$t('spinePreview.stepUpload')" />
        <el-step :title="$t('spinePreview.stepExtract')" />
        <el-step :title="$t('spinePreview.stepDownload')" />
        <el-step :title="$t('spinePreview.stepLoad')" />
      </el-steps>

      <el-progress v-if="downloadProgress > 0 && downloadProgress < 100" :percentage="downloadProgress" style="margin-top: 16px;" />
    </el-card>

    <!-- Player Section -->
    <el-card v-if="playerLoaded" class="player-card">
      <template #header>
        <div class="player-header">
          <span>{{ $t('spinePreview.title') }}</span>
          <el-button type="danger" size="small" @click="closePlayer">{{ $t('spinePreview.close') }}</el-button>
        </div>
      </template>

      <div class="player-layout">
        <!-- Left: Controls -->
        <div class="controls-panel">
          <el-form label-position="top" size="default">
            <el-form-item v-if="characters.length > 1" :label="$t('spinePreview.character')">
              <el-select v-model="currentCharacterIndex" @change="onCharacterChange" style="width: 100%;">
                <el-option v-for="(ch, idx) in characters" :key="idx" :label="ch.name" :value="idx" />
              </el-select>
            </el-form-item>

            <el-form-item :label="$t('spinePreview.animations')">
              <el-select v-model="currentAnimation" @change="onAnimationChange" style="width: 100%;">
                <el-option v-for="anim in animations" :key="anim" :label="anim" :value="anim" />
              </el-select>
            </el-form-item>

            <el-form-item :label="$t('spinePreview.loop')">
              <el-switch v-model="loopAnimation" @change="onLoopChange" />
            </el-form-item>

            <el-form-item :label="$t('spinePreview.playbackSpeed')">
              <el-slider v-model="playbackSpeed" :min="0.1" :max="3" :step="0.1" :format-tooltip="v => v + 'x'" @change="onSpeedChange" />
            </el-form-item>

            <el-form-item :label="$t('spinePreview.zoom')">
              <el-slider v-model="zoomLevel" :min="0.2" :max="5" :step="0.1" :format-tooltip="v => v.toFixed(1) + 'x'" @change="onZoomChange" />
            </el-form-item>

            <el-form-item :label="$t('spinePreview.offsetX')">
              <el-slider v-model="offsetX" :min="-500" :max="500" :step="10" @change="onOffsetChange" />
            </el-form-item>

            <el-form-item :label="$t('spinePreview.offsetY')">
              <el-slider v-model="offsetY" :min="-500" :max="500" :step="10" @change="onOffsetChange" />
            </el-form-item>

            <el-form-item>
              <div class="action-buttons">
                <el-button size="small" @click="resetViewport">{{ $t('spinePreview.resetViewport') }}</el-button>
                <el-button type="primary" size="small" @click="saveImage">{{ $t('spinePreview.saveImage') }}</el-button>
              </div>
            </el-form-item>
          </el-form>
        </div>

        <!-- Right: Spine Player -->
        <div class="spine-container-wrapper">
          <div ref="spineContainerRef" class="spine-container"></div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { useSessionStore } from '@/stores/session'
import { useTasksStore } from '@/stores/tasks'
import { createExtractTask } from '@/api/tasks'
import { getDownloadUrl } from '@/api/files'
import JSZip from 'jszip'
import { SpinePlayer } from '@esotericsoftware/spine-player'
import '@esotericsoftware/spine-player/dist/spine-player.css'

const { t } = useI18n()
const sessionStore = useSessionStore()
const tasksStore = useTasksStore()

const bundleUploadRef = ref()
const bundleFiles = ref([])
const bundleFileList = ref([])
const loading = ref(false)
const currentStep = ref(0)
const downloadProgress = ref(0)
const playerLoaded = ref(false)
const spineContainerRef = ref()
const animations = ref([])
const currentAnimation = ref('')
const loopAnimation = ref(true)
const playbackSpeed = ref(1)
const zoomLevel = ref(1)
const offsetX = ref(0)
const offsetY = ref(0)
const characters = ref([])
const currentCharacterIndex = ref(0)

let player = null
let baseViewport = null

const sessionUuid = computed(() => sessionStore.uuid)
const uploadUrl = '/api/files/upload'

const allowedExtensions = ['.bundle']
const maxSize = 500 * 1024 * 1024

// --- Upload handlers ---
function beforeUpload(file) {
  const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase()
  if (!allowedExtensions.includes(ext)) {
    ElMessage.error(t('spinePreview.unsupportedFileType'))
    return false
  }
  if (file.size > maxSize) {
    ElMessage.error(t('spinePreview.fileTooLarge'))
    return false
  }
  return true
}

function onBundleUploaded(response) {
  bundleFiles.value.push(response)
}

function onBundleRemoved(file) {
  const index = bundleFiles.value.findIndex(f => f.id === file.response?.id)
  if (index > -1) bundleFiles.value.splice(index, 1)
}

function onUploadError() {
  ElMessage.error(t('spinePreview.uploadFailed'))
}

// --- Extract character name from .skel filename ---
function extractCharacterName(assets) {
  const skelFile = Object.keys(assets).find(f => f.endsWith('.skel') || f.endsWith('.json'))
  if (!skelFile) return 'Unknown'
  // Remove extension, then remove trailing _Idle_01, _Attack_01 etc.
  const base = skelFile.replace(/\.(skel|json)$/i, '')
  return base.replace(/_[A-Za-z]+_\d+$/, '') || base
}

// --- Main preview flow ---
async function startPreview() {
  if (bundleFiles.value.length === 0) {
    ElMessage.warning(t('spinePreview.pleaseUploadBundle'))
    return
  }

  loading.value = true
  currentStep.value = 1

  try {
    // Step 1: Extract
    currentStep.value = 1
    const task = await createExtractTask({
      session_uuid: sessionStore.uuid,
      bundle_file_ids: bundleFiles.value.map(f => f.id),
      asset_types: ['Texture2D', 'TextAsset', 'Mesh'],
      unpack_atlas: false
    })

    await tasksStore.pollTask(task.id, 3000, 200)
    const completedTask = tasksStore.currentTask

    if (completedTask?.status !== 'completed' || !completedTask.files?.length) {
      throw new Error(t('spinePreview.extractFailed'))
    }

    // Step 2: Download & Unzip, group by character
    currentStep.value = 2
    const charList = []

    for (const outputFile of completedTask.files) {
      const zipBuffer = await downloadFile(outputFile.id)
      const assets = await unzipToAssets(zipBuffer)
      const skelFile = Object.keys(assets).find(f => f.endsWith('.skel') || f.endsWith('.json'))
      if (!skelFile) continue
      charList.push({
        name: extractCharacterName(assets),
        assets
      })
    }

    if (charList.length === 0) {
      throw new Error(t('spinePreview.noSpineAssets'))
    }

    characters.value = charList
    currentCharacterIndex.value = 0

    // Step 3: Load player
    currentStep.value = 3
    playerLoaded.value = true

    await nextTick()
    await loadCharacter(0)
  } catch (e) {
    ElMessage.error(e.message || t('spinePreview.previewFailed'))
    loading.value = false
  }
}

async function loadCharacter(index) {
  const ch = characters.value[index]
  if (!ch) return

  // Dispose old player
  if (player) {
    player.dispose()
    player = null
  }
  baseViewport = null

  // Reset viewport controls
  zoomLevel.value = 1
  offsetX.value = 0
  offsetY.value = 0

  // Clear container
  if (spineContainerRef.value) {
    spineContainerRef.value.innerHTML = ''
  }

  await nextTick()

  const rawDataURIs = buildRawDataURIs(ch.assets)
  const skelFile = Object.keys(ch.assets).find(f => f.endsWith('.skel') || f.endsWith('.json'))
  const atlasFile = Object.keys(ch.assets).find(f => f.endsWith('.atlas'))

  if (!skelFile || !atlasFile) return

  const isBinary = skelFile.endsWith('.skel')

  return new Promise((resolve) => {
    player = new SpinePlayer(spineContainerRef.value, {
      binaryUrl: isBinary ? skelFile : undefined,
      jsonUrl: isBinary ? undefined : skelFile,
      atlasUrl: atlasFile,
      rawDataURIs: rawDataURIs,
      animation: 'Idle_01',
      showControls: false,
      alpha: true,
      premultipliedAlpha: false,
      preserveDrawingBuffer: true,
      backgroundColor: '#00000000',
      viewport: {
        padLeft: '10%',
        padRight: '10%',
        padTop: '10%',
        padBottom: '10%'
      },
      success: (p) => {
        const skeletonData = p.skeleton?.data
        const animNames = skeletonData?.animations?.map(a => a.name) || []
        animations.value = animNames

        const defaultAnim = animNames.includes('Idle_01') ? 'Idle_01' : (animNames[0] || '')
        currentAnimation.value = defaultAnim

        if (defaultAnim) {
          p.animationState.setAnimation(0, defaultAnim, true)
        }

        setTimeout(() => {
          if (p.currentViewport) {
            baseViewport = {
              x: p.currentViewport.x,
              y: p.currentViewport.y,
              width: p.currentViewport.width,
              height: p.currentViewport.height
            }
          }
        }, 100)

        loading.value = false
        currentStep.value = 4
        resolve()
      },
      error: (p, reason) => {
        ElMessage.error(reason || t('spinePreview.playerError'))
        loading.value = false
        resolve()
      }
    })
  })
}

function onCharacterChange(index) {
  loadCharacter(index)
}

function onAnimationChange(name) {
  if (player?.animationState) {
    player.animationState.setAnimation(0, name, loopAnimation.value)
  }
}

function onLoopChange(val) {
  if (player?.animationState && currentAnimation.value) {
    player.animationState.setAnimation(0, currentAnimation.value, val)
  }
}

function onSpeedChange(val) {
  if (player?.animationState) {
    player.animationState.timeScale = val
  }
}

function applyViewport() {
  if (!player?.currentViewport || !baseViewport) return
  const vp = player.currentViewport
  const newWidth = baseViewport.width / zoomLevel.value
  const newHeight = baseViewport.height / zoomLevel.value
  const centerX = baseViewport.x + baseViewport.width / 2
  const centerY = baseViewport.y + baseViewport.height / 2
  vp.x = centerX - newWidth / 2 + offsetX.value
  vp.y = centerY - newHeight / 2 + offsetY.value
  vp.width = newWidth
  vp.height = newHeight
}

function onZoomChange() {
  applyViewport()
}

function onOffsetChange() {
  applyViewport()
}

function resetViewport() {
  zoomLevel.value = 1
  offsetX.value = 0
  offsetY.value = 0
  if (player?.currentViewport && baseViewport) {
    const vp = player.currentViewport
    vp.x = baseViewport.x
    vp.y = baseViewport.y
    vp.width = baseViewport.width
    vp.height = baseViewport.height
  }
}

function saveImage() {
  const canvas = spineContainerRef.value?.querySelector('canvas')
  if (!canvas) {
    ElMessage.warning(t('spinePreview.saveImageFailed'))
    return
  }
  const link = document.createElement('a')
  const ch = characters.value[currentCharacterIndex.value]
  const chName = ch?.name || 'spine'
  const animName = currentAnimation.value || 'animation'
  link.download = `${chName}_${animName}.png`
  link.href = canvas.toDataURL('image/png')
  link.click()
}

function buildRawDataURIs(assets) {
  const uris = {}
  for (const [name, { data, mimeType }] of Object.entries(assets)) {
    uris[name] = arrayBufferToDataURI(data, mimeType)
  }
  return uris
}

async function downloadFile(fileId) {
  downloadProgress.value = 0
  const url = getDownloadUrl(fileId)

  const response = await fetch(url)
  if (!response.ok) throw new Error('Download failed')

  const contentLength = response.headers.get('content-length')
  const total = contentLength ? parseInt(contentLength) : 0
  let loaded = 0

  const reader = response.body.getReader()
  const chunks = []

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    chunks.push(value)
    loaded += value.length
    if (total > 0) {
      downloadProgress.value = Math.round((loaded / total) * 100)
    }
  }

  downloadProgress.value = 100
  const buffer = new Uint8Array(loaded)
  let offset = 0
  for (const chunk of chunks) {
    buffer.set(chunk, offset)
    offset += chunk.length
  }
  return buffer.buffer
}

async function unzipToAssets(arrayBuffer) {
  const zip = await JSZip.loadAsync(arrayBuffer)
  const assets = {}

  const mimeMap = {
    '.skel': 'application/octet-stream',
    '.json': 'application/json',
    '.atlas': 'text/plain',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.webp': 'image/webp'
  }

  const fileNames = Object.keys(zip.files).filter(name => !zip.files[name].dir)

  for (const fileName of fileNames) {
    const baseName = fileName.split('/').pop()
    const ext = baseName.substring(baseName.lastIndexOf('.')).toLowerCase()
    const mimeType = mimeMap[ext]
    if (!mimeType) continue

    const data = await zip.files[fileName].async('arraybuffer')
    assets[baseName] = { data, mimeType }
  }

  return assets
}

function arrayBufferToDataURI(buffer, mimeType) {
  const bytes = new Uint8Array(buffer)
  let binary = ''
  const chunkSize = 8192
  for (let i = 0; i < bytes.length; i += chunkSize) {
    const chunk = bytes.subarray(i, i + chunkSize)
    binary += String.fromCharCode.apply(null, chunk)
  }
  return `data:${mimeType};base64,${btoa(binary)}`
}

function closePlayer() {
  if (player) {
    player.dispose()
    player = null
  }
  playerLoaded.value = false
  animations.value = []
  currentAnimation.value = ''
  characters.value = []
  currentCharacterIndex.value = 0
  resetForm()
}

function resetForm() {
  bundleFiles.value = []
  bundleFileList.value = []
  bundleUploadRef.value?.clearFiles()
  loading.value = false
  currentStep.value = 0
  downloadProgress.value = 0
}

onUnmounted(() => {
  if (player) {
    player.dispose()
    player = null
  }
})
</script>

<style scoped>
.spine-preview-page {
  max-width: 1000px;
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

.player-card {
  overflow: hidden;
}

.player-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.player-layout {
  display: flex;
  gap: 20px;
  min-height: 450px;
}

.controls-panel {
  width: 220px;
  flex-shrink: 0;
  border-right: 1px solid #ebeef5;
  padding-right: 20px;
}

.controls-panel :deep(.el-form-item) {
  margin-bottom: 8px;
}

.controls-panel :deep(.el-form-item__label) {
  padding-bottom: 2px;
}

.action-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.spine-container-wrapper {
  flex: 1;
  min-width: 0;
}

.spine-container {
  width: 100%;
  height: 450px;
}

/* Mobile */
@media (max-width: 768px) {
  .spine-preview-page {
    padding: 0 4px;
  }

  .player-layout {
    flex-direction: column;
  }

  .controls-panel {
    width: 100%;
    border-right: none;
    border-bottom: 1px solid #ebeef5;
    padding-right: 0;
    padding-bottom: 12px;
  }

  .spine-container {
    height: 350px;
  }
}
</style>
