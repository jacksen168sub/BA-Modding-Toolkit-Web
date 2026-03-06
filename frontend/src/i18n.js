import { createI18n } from 'vue-i18n'
import zhCN from './locales/zh-CN.json'
import enUS from './locales/en-US.json'
import zhTW from './locales/zh-TW.json'
import jaJP from './locales/ja-JP.json'
import koKR from './locales/ko-KR.json'
import esES from './locales/es-ES.json'
import frFR from './locales/fr-FR.json'
import ruRU from './locales/ru-RU.json'
import arSA from './locales/ar-SA.json'
import hiIN from './locales/hi-IN.json'
import bnBD from './locales/bn-BD.json'
import thTH from './locales/th-TH.json'

const messages = {
  'zh-CN': zhCN,
  'en-US': enUS,
  'zh-TW': zhTW,
  'ja-JP': jaJP,
  'ko-KR': koKR,
  'es-ES': esES,
  'fr-FR': frFR,
  'ru-RU': ruRU,
  'ar-SA': arSA,
  'hi-IN': hiIN,
  'bn-BD': bnBD,
  'th-TH': thTH
}

// 语言映射表
const localeMap = {
  'zh': 'zh-CN',
  'zh-cn': 'zh-CN',
  'zh-tw': 'zh-TW',
  'zh-hk': 'zh-TW',
  'en': 'en-US',
  'ja': 'ja-JP',
  'ko': 'ko-KR',
  'es': 'es-ES',
  'fr': 'fr-FR',
  'ru': 'ru-RU',
  'ar': 'ar-SA',
  'hi': 'hi-IN',
  'bn': 'bn-BD',
  'th': 'th-TH'
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
  const trimmedLocale = navigatorLocale.trim().toLowerCase()
  
  // 匹配完整的语言代码 (如 zh-CN, en-US)
  if (messages[trimmedLocale]) {
    return trimmedLocale
  }
  
  // 通过映射表匹配
  if (localeMap[trimmedLocale]) {
    return localeMap[trimmedLocale]
  }
  
  // 匹配语言前缀
  const languagePart = trimmedLocale.split('-')[0]
  if (localeMap[languagePart]) {
    return localeMap[languagePart]
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