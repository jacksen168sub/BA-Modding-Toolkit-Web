import { createI18n } from 'vue-i18n'
import zhCN from './locales/zh-CN.json'
import enUS from './locales/en-US.json'

const messages = {
  'zh-CN': zhCN,
  'en-US': enUS
}

// 获取浏览器语言
function getBrowserLocale() {
  const navigatorLocale = 
    navigator.languages !== undefined
      ? navigator.languages[0]
      : navigator.language

  if (!navigatorLocale) {
    return 'en-US'
  }

  // 标准化语言代码
  const trimmedLocale = navigatorLocale.trim()
  
  // 匹配完整的语言代码 (如 zh-CN, en-US)
  if (messages[trimmedLocale]) {
    return trimmedLocale
  }
  
  // 匹配语言前缀 (如 zh, en)
  const languagePart = trimmedLocale.split('-')[0]
  if (languagePart === 'zh') {
    return 'zh-CN'
  }
  if (languagePart === 'en') {
    return 'en-US'
  }
  
  // 默认返回英语
  return 'en-US'
}

// 从 localStorage 获取保存的语言设置，否则使用浏览器语言
function getDefaultLocale() {
  const savedLocale = localStorage.getItem('locale')
  if (savedLocale && messages[savedLocale]) {
    return savedLocale
  }
  return getBrowserLocale()
}

const i18n = createI18n({
  legacy: false, // 使用 Composition API
  locale: getDefaultLocale(),
  fallbackLocale: 'en-US',
  messages
})

export default i18n

// 导出切换语言的工具函数
export function setLocale(locale) {
  if (messages[locale]) {
    i18n.global.locale.value = locale
    localStorage.setItem('locale', locale)
    document.documentElement.setAttribute('lang', locale)
    return true
  }
  return false
}

export function getLocale() {
  return i18n.global.locale.value
}

export function getAvailableLocales() {
  return Object.keys(messages)
}
