// Frontend mirror of the backend UploadRuleService.
// Fetches the active rules from /api/files/upload-rules once and caches them,
// then validates filenames locally so we can reject bad files before they
// hit the network. The backend ALWAYS re-validates, so this is best-effort.

import { getUploadRules } from '@/api/files'

let _cache = null // { mode, caseSensitive, compiled: [{ re, description, raw }] }
let _loading = null // Promise while in-flight

/**
 * Load (and cache) the active upload rules from the backend.
 * Subsequent calls return the cached snapshot unless `force` is true.
 */
export async function loadUploadRules(force = false) {
  if (_cache && !force) return _cache
  if (_loading && !force) return _loading
  _loading = (async () => {
    try {
      const data = await getUploadRules()
      const compiled = (data.rules || []).map(r => {
        let re = null
        try {
          re = new RegExp(r.pattern, data.case_sensitive ? '' : 'i')
        } catch (e) {
          // Skip invalid regex; backend will reject anyway.
          console.warn('[uploadRules] invalid regex skipped:', r.pattern, e)
        }
        return { re, description: r.description || r.pattern, raw: r.pattern }
      }).filter(r => r.re !== null)
      _cache = {
        mode: data.mode || 'whitelist',
        caseSensitive: !!data.case_sensitive,
        source: data.source || 'default',
        compiled,
      }
      return _cache
    } catch (e) {
      // If we can't fetch rules, fall back to permissive (let backend decide).
      // Using a single catch-all whitelist rule so uploads are NOT blocked
      // solely because the rules endpoint is unreachable.
      console.warn('[uploadRules] failed to load rules, backend will enforce:', e)
      _cache = {
        mode: 'whitelist',
        caseSensitive: false,
        source: 'fetch-failed',
        compiled: [{ re: /^.*$/, description: 'rules unavailable — backend enforces', raw: '.*' }],
      }
      return _cache
    } finally {
      _loading = null
    }
  })()
  return _loading
}

/**
 * Validate a filename against the cached rules.
 * Returns { ok: true } on success, or { ok: false, key, params } on failure,
 * where `key` is an i18n message key (under the `uploadRules` namespace) and
 * `params` are the named interpolation values. The caller is responsible for
 * translating via `t(key, params)`.
 */
export async function validateFilename(filename) {
  const rules = await loadUploadRules()
  if (!filename) return { ok: false, key: 'uploadRules.emptyName', params: {} }

  let matched = null
  for (const r of rules.compiled) {
    if (r.re.test(filename)) {
      matched = r
      break
    }
  }

  if (rules.mode === 'whitelist') {
    if (matched) return { ok: true }
    return {
      ok: false,
      key: 'uploadRules.whitelistBlocked',
      params: { name: filename },
    }
  }
  // blacklist
  if (!matched) return { ok: true }
  return {
    ok: false,
    key: 'uploadRules.blacklistBlocked',
    params: { name: filename, rule: "BlackList" },
  }
}
