<template>
  <div class="home-page">
    <el-row :gutter="20">
      <el-col :span="24">
        <el-card class="welcome-card">
          <h1>{{ $t('home.title') }}</h1>
          <p>{{ $t('home.subtitle') }}</p>
          <p class="session-info">
            {{ $t('home.sessionId') }}: <code>{{ sessionStore.uuid }}</code>
            <el-button type="primary" text @click="copyUUID">{{ $t('common.copy') || $t('common.copy') }}</el-button>
          </p>
        </el-card>
      </el-col>
    </el-row>
    
    <el-row :gutter="20" class="feature-cards">
      <el-col :xs="24" :sm="12" :md="6">
        <el-card class="feature-card" @click="$router.push('/update')">
          <el-icon class="feature-icon"><Refresh /></el-icon>
          <h3>{{ $t('home.features.update') }}</h3>
          <p>{{ $t('home.features.updateDesc') }}</p>
        </el-card>
      </el-col>
      
      <el-col :xs="24" :sm="12" :md="6">
        <el-card class="feature-card" @click="$router.push('/pack')">
          <el-icon class="feature-icon"><Box /></el-icon>
          <h3>{{ $t('home.features.pack') }}</h3>
          <p>{{ $t('home.features.packDesc') }}</p>
        </el-card>
      </el-col>
      
      <el-col :xs="24" :sm="12" :md="6">
        <el-card class="feature-card" @click="$router.push('/extract')">
          <el-icon class="feature-icon"><FolderOpened /></el-icon>
          <h3>{{ $t('home.features.extract') }}</h3>
          <p>{{ $t('home.features.extractDesc') }}</p>
        </el-card>
      </el-col>
      
      <el-col :xs="24" :sm="12" :md="6">
        <el-card class="feature-card" @click="$router.push('/crc')">
          <el-icon class="feature-icon"><Key /></el-icon>
          <h3>{{ $t('home.features.crc') }}</h3>
          <p>{{ $t('home.features.crcDesc') }}</p>
        </el-card>
      </el-col>
    </el-row>
    
    <el-row :gutter="20" class="info-section">
      <el-col :span="24">
        <el-card>
          <template #header>
            <span>{{ $t('home.instructions') }}</span>
          </template>
          <ol>
            <li>{{ $t('home.instruction1') }}</li>
            <li>{{ $t('home.instruction2') }}</li>
            <li>{{ $t('home.instruction3') }}</li>
            <li>{{ $t('home.instruction4') }}</li>
          </ol>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { Refresh, Box, FolderOpened, Key } from '@element-plus/icons-vue'
import { useSessionStore } from '@/stores/session'

const { t } = useI18n()
const sessionStore = useSessionStore()

onMounted(() => {
  sessionStore.fetchSession()
})

function copyUUID() {
  navigator.clipboard.writeText(sessionStore.uuid)
  ElMessage.success(t('home.copied'))
}
</script>

<style scoped>
.home-page {
  max-width: 1200px;
  margin: 0 auto;
}

.welcome-card {
  text-align: center;
  margin-bottom: 20px;
}

.welcome-card h1 {
  margin-bottom: 10px;
  color: #303133;
}

.welcome-card p {
  color: #606266;
}

.session-info {
  margin-top: 15px;
  padding: 10px;
  background-color: #f5f7fa;
  border-radius: 4px;
}

.session-info code {
  font-family: monospace;
  background-color: #e4e7ed;
  padding: 2px 6px;
  border-radius: 3px;
}

.feature-cards {
  margin-top: 20px;
}

.feature-cards .el-col {
  display: flex;
  margin-bottom: 20px;
}

.feature-card {
  text-align: center;
  padding: 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  width: 100%;
}

.feature-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.feature-icon {
  font-size: 48px;
  color: #409eff;
  margin-bottom: 15px;
}

.feature-card h3 {
  margin-bottom: 10px;
  color: #303133;
}

.feature-card p {
  color: #909399;
  font-size: 14px;
  margin: 0;
}

.info-section {
  margin-top: 20px;
}

.info-section ol {
  padding-left: 20px;
}

.info-section li {
  margin-bottom: 10px;
  color: #606266;
}

/* 移动端适配 */
@media (max-width: 768px) {
  .welcome-card h1 {
    font-size: 24px;
  }
  
  .feature-card {
    padding: 15px;
  }
  
  .feature-icon {
    font-size: 36px;
  }
  
  .feature-card h3 {
    font-size: 16px;
  }
}
</style>
