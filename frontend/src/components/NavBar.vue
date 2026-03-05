<template>
  <div class="navbar">
    <el-menu
      :default-active="activeIndex"
      mode="horizontal"
      background-color="#409eff"
      text-color="#fff"
      active-text-color="#ffd04b"
      :collapse="isMobile"
      class="navbar-menu"
      @select="handleMenuSelect"
    >
      <el-menu-item index="/">
        <el-icon><HomeFilled /></el-icon>
        <span class="menu-text">{{ $t('nav.home') }}</span>
      </el-menu-item>
      
      <el-sub-menu index="tools" :popper-class="isMobile ? 'mobile-submenu' : ''">
        <template #title>
          <el-icon><Tools /></el-icon>
          <span class="menu-text">{{ $t('nav.tools') }}</span>
        </template>
        <el-menu-item index="/update">{{ $t('home.features.update') }}</el-menu-item>
        <el-menu-item index="/pack">{{ $t('home.features.pack') }}</el-menu-item>
        <el-menu-item index="/extract">{{ $t('home.features.extract') }}</el-menu-item>
        <el-menu-item index="/crc">{{ $t('home.features.crc') }}</el-menu-item>
      </el-sub-menu>
      
      <el-menu-item index="/tasks">
        <el-icon><List /></el-icon>
        <span class="menu-text">{{ $t('nav.tasks') }}</span>
      </el-menu-item>
      
      <!-- 语言切换 -->
      <el-sub-menu index="lang" class="lang-switcher">
        <template #title>
          <el-icon><Platform /></el-icon>
          <span class="menu-text">{{ $t('lang.switch') }}</span>
        </template>
        <el-menu-item 
          v-for="loc in availableLocales" 
          :key="loc.value" 
          :index="'lang-' + loc.value"
          :class="{ 'is-active': currentLocale === loc.value }"
        >
          {{ loc.label }}
        </el-menu-item>
      </el-sub-menu>
    </el-menu>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { HomeFilled, Tools, List, Platform } from '@element-plus/icons-vue'
import { setLocale, getLocale, getAvailableLocales } from '@/i18n'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const activeIndex = computed(() => route.path)
const currentLocale = ref(getLocale())

// 响应式检测移动端
const windowWidth = ref(window.innerWidth)
const isMobile = computed(() => windowWidth.value < 768)

// 可用语言列表
const availableLocales = [
  { value: 'zh-CN', label: '简体中文' },
  { value: 'en-US', label: 'English' }
]

function changeLocale(locale) {
  if (setLocale(locale)) {
    currentLocale.value = locale
  }
}

function handleMenuSelect(index) {
  // 如果是语言切换，不进行路由跳转
  if (index.startsWith('lang-')) {
    const locale = index.replace('lang-', '')
    changeLocale(locale)
    return
  }
  // 其他菜单项进行路由跳转
  router.push(index)
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
}

.navbar-menu {
  padding: 0 20px;
  display: flex;
  justify-content: center;
  flex-wrap: wrap;
}

.lang-switcher {
  margin-left: auto;
}

/* 桌面端默认显示文字 */
.menu-text {
  display: inline;
  margin-left: 5px;
}

/* 移动端适配 */
@media (max-width: 768px) {
  .navbar-menu {
    padding: 0 10px;
    justify-content: space-around;
  }
  
  .navbar-menu :deep(.menu-text) {
    display: none;
  }
  
  .lang-switcher {
    margin-left: 0;
  }
}
</style>
