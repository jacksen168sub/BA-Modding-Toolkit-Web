<template>
  <div class="navbar">
    <!-- PC Layout -->
    <div v-if="!isMobile" class="navbar-pc">
      <div class="navbar-brand" @click="router.push('/')">
        <span class="brand-text">BAMTW</span>
      </div>
      <div class="navbar-links">
        <router-link to="/" class="nav-link" :class="{ active: route.path === '/' }">
          <el-icon><HomeFilled /></el-icon>
          <span>{{ $t('nav.home') }}</span>
        </router-link>
        <el-dropdown trigger="hover" @command="handleToolSelect">
          <span class="nav-link" :class="{ active: isToolActive }">
            <el-icon><Tools /></el-icon>
            <span>{{ $t('nav.tools') }}</span>
            <el-icon class="arrow-icon"><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="/update" :class="{ 'is-active-tool': route.path === '/update' }">
                <el-icon class="feature-icon"><Refresh /></el-icon>
                {{ $t('home.features.update') }}
              </el-dropdown-item>
              <el-dropdown-item command="/pack" :class="{ 'is-active-tool': route.path === '/pack' }">
                <el-icon class="feature-icon"><Box /></el-icon>
                {{ $t('home.features.pack') }}
              </el-dropdown-item>
              <el-dropdown-item command="/extract" :class="{ 'is-active-tool': route.path === '/extract' }">
                <el-icon class="feature-icon"><FolderOpened /></el-icon>
                {{ $t('home.features.extract') }}
              </el-dropdown-item>
              <el-dropdown-item command="/crc" :class="{ 'is-active-tool': route.path === '/crc' }">
                <el-icon class="feature-icon"><Key /></el-icon>
                {{ $t('home.features.crc') }}
              </el-dropdown-item>
              <el-dropdown-item command="/split" :class="{ 'is-active-tool': route.path === '/split' }">
                <el-icon class="feature-icon"><Scissor /></el-icon>
                {{ $t('home.features.split') }}
              </el-dropdown-item>
              <el-dropdown-item command="/merge" :class="{ 'is-active-tool': route.path === '/merge' }">
                <el-icon class="feature-icon"><Connection /></el-icon>
                {{ $t('home.features.merge') }}
              </el-dropdown-item>
              <el-dropdown-item command="/spine-preview" :class="{ 'is-active-tool': route.path === '/spine-preview' }">
                <el-icon class="feature-icon"><VideoPlay /></el-icon>
                {{ $t('home.features.spinePreview') }}
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <router-link to="/tasks" class="nav-link" :class="{ active: route.path === '/tasks' }">
          <el-icon><List /></el-icon>
          <span>{{ $t('nav.tasks') }}</span>
        </router-link>
      </div>
      <div class="navbar-actions">
        <el-dropdown trigger="hover" @command="handleLocaleSelect">
          <span class="nav-link">
            <el-icon><Platform /></el-icon>
            <span>{{ currentLocaleLabel }}</span>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item
                v-for="loc in availableLocales"
                :key="loc.value"
                :command="loc.value"
                :class="{ 'is-active-locale': currentLocale === loc.value }"
              >
                {{ loc.label }}
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <router-link to="/settings" class="nav-link" :class="{ active: route.path === '/settings' }">
          <el-icon><Setting /></el-icon>
        </router-link>
      </div>
    </div>

    <!-- Mobile Layout -->
    <div v-else class="navbar-mobile">
      <div class="navbar-brand" @click="router.push('/')">
        <span class="brand-text">BAMTW</span>
      </div>
      <div class="mobile-actions">
        <router-link to="/settings" class="mobile-icon-btn">
          <el-icon :size="20"><Setting /></el-icon>
        </router-link>
        <button class="hamburger-btn" @click="drawerVisible = true">
          <el-icon :size="22"><Menu /></el-icon>
        </button>
      </div>
    </div>

    <!-- Mobile Drawer -->
    <el-drawer
      v-model="drawerVisible"
      direction="rtl"
      :show-close="false"
      size="260px"
      class="mobile-drawer"
    >
      <template #header>
        <span class="drawer-title">BAMTW</span>
      </template>
      <div class="drawer-content">
        <div class="drawer-section">
          <router-link to="/" class="drawer-link" :class="{ active: route.path === '/' }" @click="drawerVisible = false">
            <el-icon><HomeFilled /></el-icon>
            <span>{{ $t('nav.home') }}</span>
          </router-link>
        </div>

        <div class="drawer-section">
          <div class="drawer-section-title">{{ $t('nav.tools') }}</div>
          <router-link to="/update" class="drawer-link" :class="{ active: route.path === '/update' }" @click="drawerVisible = false">
            <el-icon class="feature-icon"><Refresh /></el-icon>
            <span>{{ $t('home.features.update') }}</span>
          </router-link>
          <router-link to="/pack" class="drawer-link" :class="{ active: route.path === '/pack' }" @click="drawerVisible = false">
            <el-icon class="feature-icon"><Box /></el-icon>
            <span>{{ $t('home.features.pack') }}</span>
          </router-link>
          <router-link to="/extract" class="drawer-link" :class="{ active: route.path === '/extract' }" @click="drawerVisible = false">
            <el-icon class="feature-icon"><FolderOpened /></el-icon>
            <span>{{ $t('home.features.extract') }}</span>
          </router-link>
          <router-link to="/crc" class="drawer-link" :class="{ active: route.path === '/crc' }" @click="drawerVisible = false">
            <el-icon class="feature-icon"><Key /></el-icon>
            <span>{{ $t('home.features.crc') }}</span>
          </router-link>
          <router-link to="/split" class="drawer-link" :class="{ active: route.path === '/split' }" @click="drawerVisible = false">
            <el-icon class="feature-icon"><Scissor /></el-icon>
            <span>{{ $t('home.features.split') }}</span>
          </router-link>
          <router-link to="/merge" class="drawer-link" :class="{ active: route.path === '/merge' }" @click="drawerVisible = false">
            <el-icon class="feature-icon"><Connection /></el-icon>
            <span>{{ $t('home.features.merge') }}</span>
          </router-link>
          <router-link to="/spine-preview" class="drawer-link" :class="{ active: route.path === '/spine-preview' }" @click="drawerVisible = false">
            <el-icon class="feature-icon"><VideoPlay /></el-icon>
            <span>{{ $t('home.features.spinePreview') }}</span>
          </router-link>
        </div>

        <div class="drawer-section">
          <router-link to="/tasks" class="drawer-link" :class="{ active: route.path === '/tasks' }" @click="drawerVisible = false">
            <el-icon><List /></el-icon>
            <span>{{ $t('nav.tasks') }}</span>
          </router-link>
          <router-link to="/settings" class="drawer-link" :class="{ active: route.path === '/settings' }" @click="drawerVisible = false">
            <el-icon><Setting /></el-icon>
            <span>{{ $t('nav.settings') }}</span>
          </router-link>
        </div>

        <div class="drawer-section">
          <div class="drawer-section-title">{{ $t('lang.switch') }}</div>
          <div class="locale-grid">
            <button
              v-for="loc in availableLocales"
              :key="loc.value"
              class="locale-btn"
              :class="{ active: currentLocale === loc.value }"
              @click="handleLocaleSelect(loc.value)"
            >
              {{ loc.label }}
            </button>
          </div>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { HomeFilled, Tools, List, Platform, Setting, ArrowDown, Refresh, Box, FolderOpened, Key, Scissor, Connection, VideoPlay, Menu } from '@element-plus/icons-vue'
import { setLocale, getLocale } from '@/i18n'
import i18n from '@/i18n'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const currentLocale = computed(() => i18n.global.locale.value)
const drawerVisible = ref(false)

const windowWidth = ref(window.innerWidth)
const isMobile = computed(() => windowWidth.value < 768)

const toolPaths = ['/update', '/pack', '/extract', '/crc', '/split', '/merge', '/spine-preview']
const isToolActive = computed(() => toolPaths.includes(route.path))

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

const currentLocaleLabel = computed(() => {
  const loc = availableLocales.find(l => l.value === currentLocale.value)
  return loc ? loc.label : 'Language'
})

function handleLocaleSelect(locale) {
  setLocale(locale)
  drawerVisible.value = false
}

function handleToolSelect(command) {
  router.push(command)
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
.navbar {
  width: 100%;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  position: sticky;
  top: 0;
  z-index: 100;
}

/* ===== PC Layout ===== */
.navbar-pc {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  height: 56px;
  padding: 0 24px;
  gap: 8px;
}

.navbar-brand {
  cursor: pointer;
  flex-shrink: 0;
  margin-right: 16px;
}

.brand-text {
  font-size: 20px;
  font-weight: 700;
  color: #409eff;
  letter-spacing: 1px;
}

.navbar-links {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 1;
}

.nav-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 8px 14px;
  border-radius: 6px;
  color: #606266;
  font-size: 14px;
  cursor: pointer;
  text-decoration: none;
  transition: all 0.2s;
  white-space: nowrap;
}

.nav-link:hover {
  color: #409eff;
  background: #ecf5ff;
}

.nav-link.active {
  color: #409eff;
  background: #ecf5ff;
  font-weight: 500;
}

.arrow-icon {
  font-size: 12px;
  margin-left: -2px;
}

.navbar-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}



/* ===== Mobile Layout ===== */
.navbar-mobile {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 50px;
  padding: 0 16px;
}

.mobile-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.mobile-icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  color: #606266;
  text-decoration: none;
  transition: all 0.2s;
}

.mobile-icon-btn:active {
  background: #ecf5ff;
  color: #409eff;
}

.hamburger-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: none;
  background: none;
  border-radius: 8px;
  color: #606266;
  cursor: pointer;
  transition: all 0.2s;
}

.hamburger-btn:active {
  background: #ecf5ff;
  color: #409eff;
}

/* ===== Drawer ===== */
.drawer-title {
  font-size: 18px;
  font-weight: 700;
  color: #409eff;
}

.drawer-content {
  padding: 0 4px;
}

.drawer-section {
  margin-bottom: 20px;
}

.drawer-section-title {
  font-size: 12px;
  color: #909399;
  text-transform: uppercase;
  letter-spacing: 1px;
  padding: 0 12px;
  margin-bottom: 8px;
}

.drawer-link {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 8px;
  color: #303133;
  font-size: 14px;
  text-decoration: none;
  transition: all 0.2s;
}

.drawer-link:active {
  background: #ecf5ff;
  color: #409eff;
}

.drawer-link.active {
  background: #ecf5ff;
  color: #409eff;
  font-weight: 500;
}

.locale-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  padding: 0 8px;
}

.locale-btn {
  padding: 8px 4px;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  background: #fff;
  color: #606266;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  text-align: center;
}

.locale-btn:active {
  border-color: #409eff;
  color: #409eff;
}

.locale-btn.active {
  border-color: #409eff;
  background: #ecf5ff;
  color: #409eff;
  font-weight: 500;
}
</style>

<style>
/* 全局样式：el-dropdown-menu 通过 teleport 渲染到 body，scoped 样式无法作用 */
.is-active-locale {
  color: #409eff !important;
  font-weight: 500;
}

.is-active-tool {
  color: #409eff !important;
  font-weight: 500;
}
</style>
