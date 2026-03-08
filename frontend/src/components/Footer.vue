<template>
  <div class="footer">
    <div class="footer-content">
      <p>
        <a href="https://github.com/jacksen168sub/BA-Modding-Toolkit-Web" target="_blank" class="repo-link">
          {{ $t('footer.repository') }}
        </a>
        <span v-if="version" class="version-info">| {{ $t('footer.version') }}: {{ version }}</span>
      </p>
      <p>
        <a href="https://github.com/Agent-0808/BA-Modding-Toolkit" target="_blank">
          {{ $t('footer.upstream') }}
        </a>
        Web Interface
      </p>
      <p class="session-info">
        {{ $t('footer.sessionId') }}: {{ sessionStore.uuid }}
        <span v-if="sessionStore.expiresAt">
          | {{ $t('footer.expiresAt') }}: {{ formatTime(sessionStore.expiresAt) }}
        </span>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSessionStore } from '@/stores/session'
import { getVersion } from '@/api/version'

const { t } = useI18n()
const sessionStore = useSessionStore()
const version = ref(null)

onMounted(async () => {
  try {
    const data = await getVersion()
    version.value = data.version
  } catch (e) {
    // Ignore version fetch errors
  }
})

function formatTime(time) {
  return new Date(time).toLocaleString()
}
</script>

<style scoped>
.footer {
  background-color: #fff;
  padding: 10px 20px;
}

.footer-content {
  text-align: center;
  color: #909399;
  font-size: 12px;
}

.footer-content p {
  margin: 5px 0;
}

.footer-content a {
  color: #409eff;
  text-decoration: none;
}

.footer-content a:hover {
  text-decoration: underline;
}

.session-info {
  font-family: monospace;
  color: #c0c4cc;
}

.version-info {
  margin-left: 8px;
}

/* 移动端适配 */
@media (max-width: 768px) {
  .footer {
    padding: 10px;
  }
  
  .session-info {
    font-size: 10px;
    word-break: break-all;
  }
}
</style>