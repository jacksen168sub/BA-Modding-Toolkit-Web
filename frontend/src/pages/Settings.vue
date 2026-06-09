<template>
  <div class="settings-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <el-icon :size="20"><Setting /></el-icon>
          <span>{{ $t('settings.title') }}</span>
        </div>
      </template>

      <!-- Session Section -->
      <div class="section">
        <h3 class="section-title">{{ $t('settings.session') }}</h3>
        <div class="session-row">
          <span class="label">{{ $t('settings.sessionId') }}</span>
          <div class="session-value">
            <code>{{ sessionStore.uuid }}</code>
            <el-button text type="primary" size="small" @click="copyUUID">
              <el-icon><CopyDocument /></el-icon>
            </el-button>
          </div>
        </div>
        <div v-if="sessionStore.expiresAt" class="session-row">
          <span class="label">{{ $t('settings.expiresAt') }}</span>
          <span class="value">{{ formatTime(sessionStore.expiresAt) }}</span>
        </div>
        <div class="session-actions">
          <el-button type="primary" @click="handleRefreshSession" :loading="refreshing">
            <el-icon><RefreshRight /></el-icon>
            {{ $t('settings.refreshSession') }}
          </el-button>
          <el-button type="danger" plain @click="handleResetSession">
            <el-icon><SwitchButton /></el-icon>
            {{ $t('settings.resetSession') }}
          </el-button>
        </div>
        <p class="hint">{{ $t('settings.sessionHint') }}</p>
      </div>

      <el-divider />

      <!-- Version Section -->
      <div class="section">
        <div class="session-row">
          <span class="label">{{ $t('settings.version') }}</span>
          <span class="value">{{ versionInfo.version || '—' }}</span>
        </div>
        <div v-if="versionInfo.commit" class="session-row">
          <span class="label">{{ $t('settings.commit') }}</span>
          <div class="session-value">
            {{ versionInfo.commit }}
            <el-button text type="primary" size="small" @click="copyCommit">
              <el-icon><CopyDocument /></el-icon>
            </el-button>
          </div>
        </div>
      </div>

      <el-divider />

      <!-- Language Section -->
      <div class="section">
        <h3 class="section-title">{{ $t('lang.switch') }}</h3>
        <div class="locale-list">
          <button
            v-for="loc in availableLocales"
            :key="loc.value"
            class="locale-option"
            :class="{ active: currentLocale === loc.value }"
            @click="changeLocale(loc.value)"
          >
            {{ loc.label }}
          </button>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Setting, CopyDocument, RefreshRight, SwitchButton } from '@element-plus/icons-vue'
import { useSessionStore } from '@/stores/session'
import { setSessionUUID, clearSessionUUID, generateUUID } from '@/utils/uuid'
import { setLocale, getLocale } from '@/i18n'
import { getVersion } from '@/api/version'

const { t } = useI18n()
const sessionStore = useSessionStore()
const versionInfo = ref({})
const refreshing = ref(false)
const currentLocale = ref(getLocale())

const availableLocales = [
  { value: 'zh-CN', label: '简体中文' },
  { value: 'zh-TW', label: '繁體中文' },
  { value: 'en-US', label: 'English' },
  { value: 'ja-JP', label: '日本語' },
  { value: 'ko-KR', label: '한국어' },
  { value: 'es-ES', label: 'Español' },
  { value: 'fr-FR', label: 'Français' },
  { value: 'ru-RU', label: 'Русский' },
  { value: 'ar-SA', label: 'العربية' },
  { value: 'hi-IN', label: 'हिन्दी' },
  { value: 'bn-BD', label: 'বাংলা' },
  { value: 'th-TH', label: 'ไทย' }
]

onMounted(async () => {
  try {
    const data = await getVersion()
    versionInfo.value = data
  } catch (e) {
    // Ignore
  }
})

function formatTime(time) {
  return new Date(time).toLocaleString()
}

function copyUUID() {
  navigator.clipboard.writeText(sessionStore.uuid)
  ElMessage.success(t('home.copied'))
}

function copyCommit() {
  navigator.clipboard.writeText(versionInfo.value.commit || '')
  ElMessage.success(t('home.copied'))
}

async function handleRefreshSession() {
  refreshing.value = true
  try {
    await sessionStore.refresh()
    ElMessage.success(t('settings.refreshSuccess'))
  } catch (e) {
    ElMessage.error(t('settings.refreshFailed'))
  } finally {
    refreshing.value = false
  }
}

async function handleResetSession() {
  try {
    await ElMessageBox.confirm(
      t('settings.resetConfirm'),
      t('settings.resetSession'),
      { confirmButtonText: t('common.confirm'), cancelButtonText: t('common.cancel'), type: 'warning' }
    )
    clearSessionUUID()
    const newUuid = generateUUID()
    setSessionUUID(newUuid)
    sessionStore.uuid = newUuid
    await sessionStore.fetchSession()
    ElMessage.success(t('settings.resetSuccess'))
  } catch {
    // Cancelled
  }
}

function changeLocale(locale) {
  if (setLocale(locale)) {
    currentLocale.value = locale
  }
}
</script>

<style scoped>
.settings-page {
  max-width: 700px;
  margin: 0 auto;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
}

.section {
  padding: 4px 0;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 16px;
}

.session-row {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
}

.session-row .label {
  color: #909399;
  font-size: 14px;
  min-width: 80px;
  flex-shrink: 0;
}

.session-row .value {
  color: #303133;
  font-size: 14px;
}

.session-value {
  display: flex;
  align-items: center;
  gap: 4px;
}

.session-value code {
  font-family: monospace;
  background: #f5f7fa;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 13px;
  color: #303133;
  word-break: break-all;
}

.session-actions {
  display: flex;
  gap: 10px;
  margin-top: 16px;
  flex-wrap: wrap;
}

.hint {
  margin-top: 12px;
  font-size: 12px;
  color: #c0c4cc;
  line-height: 1.6;
}

.locale-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.locale-option {
  padding: 8px 16px;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  background: #fff;
  color: #606266;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.locale-option:hover {
  border-color: #409eff;
  color: #409eff;
}

.locale-option.active {
  border-color: #409eff;
  background: #ecf5ff;
  color: #409eff;
  font-weight: 500;
}

@media (max-width: 768px) {
  .session-row {
    flex-direction: row;
    align-items: flex-start;
    justify-content: flex-start;
    gap: 4px;
  }

  .session-actions {
    flex-direction: column;
  }

  .session-actions .el-button {
    margin-left: unset;
  }

  .locale-option {
    padding: 6px 12px;
    font-size: 13px;
  }
}
</style>
