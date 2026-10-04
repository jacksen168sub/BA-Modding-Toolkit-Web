<!--
SPDX-License-Identifier: GPL-3.0-or-later
Copyright (C) 2026 jacksen168sub
-->
<template>
  <div class="status-page">
    <!-- Service banner -->
    <el-card class="banner-card">
      <div class="banner">
        <div class="banner-meta">
          <span class="service-name">{{ service.name || '—' }}</span>
          <span class="muted">{{ versionLabel }}</span>
        </div>
        <div class="banner-right">
          <div class="meta-item">
            <span class="muted">{{ $t('status.uptime') }}</span>
            <span class="meta-value">{{ formatUptime(service.uptime_seconds) }}</span>
          </div>
          <div class="meta-item">
            <span class="muted">{{ $t('status.serverTime') }}</span>
            <span class="meta-value">{{ formatTime(service.server_time) }}</span>
          </div>
          <el-button :loading="loading" @click="load()">
            <el-icon><Refresh /></el-icon>
            {{ $t('common.refresh') }}
          </el-button>
        </div>
      </div>
    </el-card>

    <el-alert
      v-if="error"
      type="error"
      :title="$t('status.loadFailed')"
      :description="error"
      show-icon
      :closable="false"
      class="error-alert"
    />

    <el-alert
      v-if="redacted.length"
      type="info"
      :title="$t('status.redactedNote', { sections: redactedLabels })"
      show-icon
      :closable="false"
      class="redacted-alert"
    />

    <!-- KPI row -->
    <div class="kpi-row">
      <el-card v-for="tile in kpiTiles" :key="tile.key" class="stat-tile" shadow="hover">
        <div class="stat-label">{{ tile.label }}</div>
        <div class="stat-value">{{ tile.value }}</div>
        <div class="stat-sub">{{ tile.sub }}</div>
      </el-card>
    </div>

    <el-row :gutter="16">
      <!-- Task status breakdown -->
      <el-col :xs="24" :md="12">
        <el-card class="panel" v-loading="loading && !loaded">
          <template #header>
            <span class="panel-title">{{ $t('status.tasks.statusTitle') }}</span>
          </template>

          <div class="stack" v-if="tasks.total > 0">
            <div
              v-for="seg in visibleSegments"
              :key="seg.key"
              class="stack-seg"
              :style="{ flexGrow: seg.count, background: seg.color }"
              :title="`${seg.label}: ${formatNumber(seg.count)}`"
            />
          </div>
          <div class="stack stack-empty" v-else />

          <div class="legend">
            <div v-for="seg in statusSegments" :key="seg.key" class="legend-item">
              <span class="legend-dot" :style="{ background: seg.color }" />
              <span class="legend-label">{{ seg.label }}</span>
              <span class="legend-value">{{ formatNumber(seg.count) }}</span>
            </div>
          </div>

          <div class="hero-facts">
            <div class="hero-fact">
              <span class="muted">{{ $t('status.tasks.successRate') }}</span>
              <span class="fact-value">{{ formatPercent(tasks.success_rate) }}</span>
            </div>
            <div class="hero-fact">
              <span class="muted">{{ $t('status.tasks.avgDuration') }}</span>
              <span class="fact-value">{{ formatDuration(tasks.avg_duration_seconds) }}</span>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- Task type breakdown -->
      <el-col :xs="24" :md="12">
        <el-card class="panel" v-loading="loading && !loaded">
          <template #header>
            <span class="panel-title">{{ $t('status.tasks.typeTitle') }}</span>
          </template>

          <div class="type-list">
            <div v-for="row in typeRows" :key="row.key" class="type-row">
              <span class="type-name">{{ row.label }}</span>
              <div class="type-track">
                <div class="type-fill" :style="{ width: `${row.pct}%` }" />
              </div>
              <span class="type-value">{{ formatNumber(row.count) }}</span>
            </div>
          </div>

          <el-divider class="tight-divider" />

          <div class="recent-title muted">{{ $t('status.tasks.recentTitle') }}</div>
          <div class="recent-row">
            <div v-for="item in recentItems" :key="item.key" class="recent-item">
              <span class="recent-value">{{ formatNumber(item.count) }}</span>
              <span class="recent-label muted">{{ item.label }}</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <!-- System load -->
      <el-col :xs="24" :md="12">
        <el-card class="panel" v-loading="loading && !loaded">
          <template #header>
            <div class="panel-header">
              <span class="panel-title">{{ $t('status.system.title') }}</span>
              <el-tag v-if="container.detected" size="small" type="info" effect="plain">
                {{ runtimeLabel }}
              </el-tag>
            </div>
          </template>

          <div v-if="container.detected" class="container-line muted">{{ containerLine }}</div>

          <div
            v-for="meter in meters"
            :key="meter.key"
            class="meter-row"
            :class="{ 'meter-sep': meter.separated }"
          >
            <div class="meter-head">
              <span class="meter-name">{{ meter.label }}</span>
              <span class="meter-detail muted">{{ meter.detail }}</span>
            </div>
            <el-progress
              v-if="meter.percent !== null && meter.percent !== undefined"
              :percentage="meterPercent(meter.percent)"
              :color="meterColor(meter.percent)"
              :stroke-width="10"
              :show-text="false"
            />
            <div v-else class="meter-unknown" />
            <span class="meter-value">{{ formatPercent(meter.percent) }}</span>
          </div>
        </el-card>
      </el-col>

      <!-- Storage, sessions, process -->
      <el-col :xs="24" :md="12">
        <el-card class="panel" v-loading="loading && !loaded">
          <template #header>
            <span class="panel-title">{{ $t('status.storage.title') }}</span>
          </template>

          <div class="fact">
            <span class="muted">{{ $t('status.storage.uploads') }}</span>
            <span class="fact-value">{{ storageLine(storage.uploads) }}</span>
          </div>
          <div class="fact">
            <span class="muted">{{ $t('status.storage.outputs') }}</span>
            <span class="fact-value">{{ storageLine(storage.outputs) }}</span>
          </div>
          <div class="fact">
            <span class="muted">{{ $t('status.storage.totalSize') }}</span>
            <span class="fact-value">{{ formatBytes(storage.total_size) }}</span>
          </div>
          <div class="fact">
            <span class="muted">{{ $t('status.storage.sessions') }}</span>
            <span class="fact-value">
              {{ $t('status.storage.sessionsValue', { active: formatNumber(sessions.active), total: formatNumber(sessions.total) }) }}
            </span>
          </div>
          <div class="fact">
            <span class="muted">{{ $t('status.storage.process') }}</span>
            <span class="fact-value">
              {{ system.process.pid ? $t('status.storage.processValue', { pid: system.process.pid, rss: formatBytes(system.process.memory_rss) }) : '—' }}
            </span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <div class="refresh-hint muted">{{ $t('status.autoRefresh', { seconds: refreshSeconds }) }}</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { Refresh } from '@element-plus/icons-vue'
import { getStatus } from '@/api/status'
const { t } = useI18n()

const refreshSeconds = 5
const loading = ref(false)
const loaded = ref(false)
const error = ref('')
const data = ref(null)
let refreshInterval = null

const EMPTY = {
  service: {},
  tasks: { total: 0, by_status: {}, by_type: {}, success_rate: null, avg_duration_seconds: null, recent: {} },
  queue: { pending: 0, processing: 0, length: 0, max_concurrent: 0, available_slots: 0, utilization: 0 },
  system: { container: {}, cpu: {}, memory: {}, disk: {}, process: {} },
  storage: { uploads: {}, outputs: {}, total_size: 0 },
  sessions: { total: 0, active: 0 },
  redacted: []
}

const service = computed(() => data.value?.service || {})
const tasks = computed(() => data.value?.tasks || EMPTY.tasks)
const queue = computed(() => data.value?.queue || EMPTY.queue)
const system = computed(() => data.value?.system || EMPTY.system)
const container = computed(() => system.value.container || EMPTY.system.container)
const storage = computed(() => data.value?.storage || EMPTY.storage)
const sessions = computed(() => data.value?.sessions || EMPTY.sessions)
const redacted = computed(() => data.value?.redacted || EMPTY.redacted)

const versionLabel = computed(() => {
  const parts = [service.value.version, service.value.commit].filter(Boolean)
  return parts.join(' · ') || '—'
})

// Sections blanked out by the deployment's STATUS_REDACT setting.
const redactedLabels = computed(() =>
  redacted.value.map(key => t(`status.redacted.${key}`)).join(', ')
)

// --- Formatters ---------------------------------------------------------

function formatNumber(value) {
  if (value === null || value === undefined) return '—'
  return Number(value).toLocaleString()
}

function formatPercent(value) {
  if (value === null || value === undefined) return '—'
  return `${Number(value).toFixed(1)}%`
}

function formatBytes(bytes) {
  if (bytes === null || bytes === undefined) return '—'
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
  const i = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)))
  const value = bytes / Math.pow(1024, i)
  const digits = i === 0 || value >= 100 ? 0 : 1
  return `${value.toFixed(digits)} ${units[i]}`
}

function formatTime(time) {
  return time ? new Date(time).toLocaleString() : '—'
}

function formatUptime(seconds) {
  if (seconds === null || seconds === undefined) return '—'
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)

  const parts = []
  if (days) parts.push(`${days}${t('status.units.days')}`)
  if (hours || days) parts.push(`${hours}${t('status.units.hours')}`)
  parts.push(`${minutes}${t('status.units.minutes')}`)
  return parts.join(' ')
}

function formatDuration(seconds) {
  if (seconds === null || seconds === undefined) return '—'
  if (seconds < 60) return `${Math.round(seconds)}${t('status.units.seconds')}`
  const minutes = Math.floor(seconds / 60)
  const rest = Math.round(seconds % 60)
  return `${minutes}${t('status.units.minutes')} ${rest}${t('status.units.seconds')}`
}

function meterPercent(value) {
  return Math.max(0, Math.min(100, Number(value) || 0))
}

// Meter colour doubles as a status cue, so every meter always shows its
// numeric value alongside it.
function meterColor(value) {
  if (value === null || value === undefined) return '#909399'
  if (value >= 90) return '#d03b3b'
  if (value >= 70) return '#fab219'
  return '#0ca30c'
}

// --- Derived view data --------------------------------------------------

// Ordering keeps the reddest and greenest segments apart so the stack stays
// readable under colour-vision deficiency.
const statusOrder = ['completed', 'pending', 'processing', 'failed']
const statusColors = {
  completed: '#0ca30c',
  pending: '#909399',
  processing: '#fab219',
  failed: '#d03b3b'
}

const statusSegments = computed(() => {
  const byStatus = tasks.value.by_status || {}
  return statusOrder.map(key => ({
    key,
    label: t(`tasks.statuses.${key}`),
    count: byStatus[key] || 0,
    color: statusColors[key]
  }))
})

const visibleSegments = computed(() => statusSegments.value.filter(seg => seg.count > 0))

const typeOrder = ['update', 'pack', 'extract', 'crc', 'split', 'merge']

const typeRows = computed(() => {
  const byType = tasks.value.by_type || {}
  const rows = typeOrder.map(key => ({
    key,
    label: t(`tasks.types.${key}`),
    count: byType[key] || 0
  }))
  const max = Math.max(1, ...rows.map(row => row.count))
  return rows.map(row => ({ ...row, pct: (row.count / max) * 100 }))
})

const recentItems = computed(() => {
  const recent = tasks.value.recent || {}
  return [
    { key: 'last_hour', label: t('status.tasks.lastHour'), count: recent.last_hour || 0 },
    { key: 'last_24h', label: t('status.tasks.last24h'), count: recent.last_24h || 0 },
    { key: 'last_7d', label: t('status.tasks.last7d'), count: recent.last_7d || 0 }
  ]
})

const cpuDetail = computed(() => {
  const cpu = system.value.cpu || {}
  const cores = cpu.cores ? t('status.system.cores', { cores: cpu.cores }) : ''
  const load = Array.isArray(cpu.load_avg) ? cpu.load_avg.join(' / ') : null
  const loadText = load ? t('status.system.loadAvg', { values: load }) : ''
  return [cores, loadText].filter(Boolean).join(' · ')
})

const memoryDetail = computed(() => {
  const memory = system.value.memory || {}
  if (!memory.total) return ''
  return t('status.system.memoryDetail', {
    used: formatBytes(memory.used),
    total: formatBytes(memory.total)
  })
})

const diskDetail = computed(() => {
  const disk = system.value.disk || {}
  if (!disk.total) return ''
  return t('status.system.diskDetail', {
    used: formatBytes(disk.used),
    total: formatBytes(disk.total)
  })
})

const workerDetail = computed(() =>
  t('status.queue.slots', { used: queue.value.processing, max: queue.value.max_concurrent })
)

// Every meter is a single ratio against a limit, so a percentage bar is the
// right form; the numeric value always rides alongside the colour.
const meters = computed(() => [
  {
    key: 'cpu',
    label: t('status.system.cpu'),
    detail: cpuDetail.value,
    percent: system.value.cpu?.percent ?? null
  },
  {
    key: 'memory',
    label: t('status.system.memory'),
    detail: memoryDetail.value,
    percent: system.value.memory?.percent ?? null
  },
  {
    key: 'disk',
    label: t('status.system.disk'),
    detail: diskDetail.value,
    percent: system.value.disk?.percent ?? null
  },
  {
    key: 'queue',
    label: t('status.queue.title'),
    detail: workerDetail.value,
    percent: queue.value.utilization ?? null,
    separated: true
  }
])

const runtimeLabel = computed(() => {
  switch (container.value.runtime) {
    case 'docker': return t('status.container.docker')
    case 'podman': return t('status.container.podman')
    case 'kubernetes': return t('status.container.kubernetes')
    default: return t('status.container.generic')
  }
})

const containerLine = computed(() => {
  const info = container.value
  const parts = []

  if (info.cgroup_version) parts.push(t('status.container.cgroup', { version: info.cgroup_version }))
  if (info.cpu_quota) parts.push(t('status.container.cpuLimit', { cores: info.cpu_quota }))
  if (info.memory_limit) parts.push(t('status.container.memoryLimit', { size: formatBytes(info.memory_limit) }))
  if (!info.cpu_quota && !info.memory_limit) parts.push(t('status.container.noLimits'))

  // Host totals only appear when the deployment has not redacted them.
  const hostCores = system.value.cpu?.host_cores
  const hostMemory = system.value.memory?.host_total
  if (hostCores && hostMemory) {
    parts.push(t('status.container.hostTotals', { cores: hostCores, memory: formatBytes(hostMemory) }))
  }

  return parts.join(' · ')
})

const kpiTiles = computed(() => [
  {
    key: 'total',
    label: t('status.kpi.totalTasks'),
    value: formatNumber(tasks.value.total),
    sub: t('status.kpi.totalTasksSub', { count: formatNumber(tasks.value.recent?.last_24h || 0) })
  },
  {
    key: 'queue',
    label: t('status.kpi.queueLength'),
    value: formatNumber(queue.value.length),
    sub: t('status.kpi.queueSub', { pending: queue.value.pending, processing: queue.value.processing })
  },
  {
    key: 'cpu',
    label: t('status.kpi.cpu'),
    value: formatPercent(system.value.cpu?.percent),
    sub: cpuDetail.value
  },
  {
    key: 'memory',
    label: t('status.kpi.memory'),
    value: formatPercent(system.value.memory?.percent),
    sub: memoryDetail.value
  }
])

function storageLine(bucket) {
  if (!bucket || bucket.count === null || bucket.count === undefined) return '—'
  return t('status.storage.bucket', {
    count: formatNumber(bucket.count),
    size: formatBytes(bucket.size)
  })
}

// --- Data loading -------------------------------------------------------

async function load(showLoading = true) {
  if (showLoading) loading.value = true
  try {
    data.value = await getStatus()
    error.value = ''
    loaded.value = true
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  load()
  refreshInterval = setInterval(() => load(false), refreshSeconds * 1000)
})

onUnmounted(() => {
  if (refreshInterval) clearInterval(refreshInterval)
})
</script>

<style scoped>
.status-page {
  --status-good: #0ca30c;
  --status-warning: #fab219;
  --status-neutral: #909399;
  --status-critical: #d03b3b;
  --series-1: #409eff;
  --ink-primary: #303133;
  --ink-secondary: #606266;
  --ink-muted: #909399;
  --hairline: #e4e7ed;

  max-width: 1000px;
  margin: 0 auto;
}

.muted {
  color: var(--ink-muted);
}

/* ===== Banner ===== */
.banner-card {
  margin-bottom: 16px;
}

.banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.banner-meta {
  display: flex;
  flex-direction: column;
  line-height: 1.4;
}

.service-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--ink-primary);
}

.banner-meta .muted {
  font-size: 12px;
}

.banner-right {
  display: flex;
  align-items: center;
  gap: 20px;
  flex-wrap: wrap;
}

.meta-item {
  display: flex;
  flex-direction: column;
  line-height: 1.4;
}

.meta-item .muted {
  font-size: 12px;
}

.meta-value {
  font-size: 14px;
  color: var(--ink-secondary);
}

.error-alert {
  margin-bottom: 16px;
}

.redacted-alert {
  margin-bottom: 16px;
}

/* ===== KPI row ===== */
.kpi-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}

.stat-tile {
  text-align: left;
}

.stat-label {
  font-size: 13px;
  color: var(--ink-muted);
  margin-bottom: 6px;
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
  line-height: 1.2;
  color: var(--ink-primary);
}

.stat-sub {
  margin-top: 6px;
  font-size: 12px;
  color: var(--ink-muted);
  min-height: 16px;
}

/* ===== Panels ===== */
.panel {
  margin-bottom: 16px;
  height: calc(100% - 16px);
}

.panel-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--ink-primary);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.container-line {
  font-size: 12px;
  margin-bottom: 16px;
  line-height: 1.5;
}

.tight-divider {
  margin: 16px 0 12px;
}

/* ===== Stacked status bar ===== */
.stack {
  display: flex;
  gap: 2px;
  height: 18px;
  border-radius: 4px;
  overflow: hidden;
  background: #f0f2f5;
}

.stack-seg {
  flex-basis: 0;
  min-width: 2px;
}

.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 20px;
  margin-top: 14px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 3px;
  flex-shrink: 0;
}

.legend-label {
  color: var(--ink-secondary);
}

.legend-value {
  color: var(--ink-primary);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

/* ===== Type bars ===== */
.type-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.type-row {
  display: grid;
  grid-template-columns: 88px 1fr 56px;
  align-items: center;
  gap: 10px;
}

.type-name {
  font-size: 13px;
  color: var(--ink-secondary);
}

.type-track {
  height: 10px;
  border-radius: 4px;
  background: #f0f2f5;
  overflow: hidden;
}

.type-fill {
  height: 100%;
  border-radius: 4px;
  background: var(--series-1);
  transition: width 0.3s ease;
}

.type-value {
  font-size: 13px;
  text-align: right;
  color: var(--ink-primary);
  font-variant-numeric: tabular-nums;
}

/* ===== Recent activity ===== */
.recent-title {
  font-size: 13px;
  margin-bottom: 8px;
}

.recent-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.recent-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 4px;
  border-radius: 6px;
  background: #f7f8fa;
}

.recent-value {
  font-size: 18px;
  font-weight: 600;
  color: var(--ink-primary);
}

.recent-label {
  font-size: 12px;
  margin-top: 2px;
  text-align: center;
}

/* ===== Meters ===== */
.meter-row {
  margin-bottom: 18px;
}

.meter-row:last-child {
  margin-bottom: 0;
}

/* Separates the worker-pool meter from the host resource meters. */
.meter-sep {
  border-top: 1px solid var(--hairline);
  padding-top: 16px;
}

/* Placeholder shown when a figure is hidden by the deployment policy. */
.meter-unknown {
  height: 10px;
  border-radius: 4px;
  background: repeating-linear-gradient(
    45deg,
    #f0f2f5,
    #f0f2f5 6px,
    #fafafa 6px,
    #fafafa 12px
  );
}

.meter-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 6px;
}

.meter-name {
  font-size: 14px;
  color: var(--ink-primary);
}

.meter-detail {
  font-size: 12px;
  text-align: right;
}

.meter-row :deep(.el-progress__text) {
  display: none;
}

.meter-value {
  display: block;
  margin-top: 4px;
  font-size: 13px;
  color: var(--ink-secondary);
  font-variant-numeric: tabular-nums;
}

/* ===== Facts list ===== */
.hero-facts {
  display: flex;
  gap: 32px;
  margin-top: 18px;
}

.hero-fact {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.hero-fact .muted {
  font-size: 12px;
}

.hero-fact .fact-value {
  font-size: 16px;
}

.fact {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid var(--hairline);
  font-size: 13px;
}

.fact:last-child {
  border-bottom: none;
}

.fact-value {
  color: var(--ink-primary);
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}

.refresh-hint {
  text-align: center;
  font-size: 12px;
  padding: 4px 0 12px;
}

/* ===== Responsive ===== */
@media (max-width: 768px) {
  .kpi-row {
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
  }

  .stat-value {
    font-size: 22px;
  }

  .banner {
    flex-direction: column;
    align-items: flex-start;
  }

  .banner-right {
    gap: 12px;
    width: 100%;
    justify-content: space-between;
  }

  .type-row {
    grid-template-columns: 72px 1fr 48px;
  }

  .hero-facts {
    gap: 16px;
  }
}
</style>
