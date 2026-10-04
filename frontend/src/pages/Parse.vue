<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
<!-- Copyright (C) 2026 jacksen168sub -->
<template>
  <div class="parse-page">
    <el-card>
      <template #header>
        <span>{{ $t('parse.title') }}</span>
      </template>

      <el-alert type="info" :closable="false" style="margin-bottom: 20px;">
        <template #title>
          {{ $t('parse.description') }}
        </template>
      </el-alert>

      <el-form label-position="top" size="default">
        <el-form-item :label="$t('parse.filenames')">
          <el-input
            v-model="input"
            type="textarea"
            :rows="6"
            :placeholder="$t('parse.filenamesPlaceholder')"
          />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="submit" :loading="loading">
            {{ $t('common.submit') }}
          </el-button>
          <el-button @click="reset">{{ $t('common.clear') }}</el-button>
        </el-form-item>
      </el-form>

      <el-table v-if="results.length" :data="results" border style="width: 100%">
        <el-table-column prop="filename" :label="$t('taskDetail.fileName')" min-width="280" show-overflow-tooltip />
        <el-table-column prop="category" label="category" width="150" />
        <el-table-column prop="core" label="core" min-width="150" />
        <el-table-column prop="display_name" label="display_name" min-width="150" />
        <el-table-column prop="res_type" label="res_type" width="140" />
        <el-table-column prop="date" label="date" width="120" />
        <el-table-column prop="crc" label="crc" width="140" />
        <el-table-column prop="prefix" label="prefix" min-width="240" show-overflow-tooltip />
      </el-table>

      <el-collapse v-if="raw" style="margin-top: 16px;">
        <el-collapse-item :title="$t('taskDetail.cliLog')" name="raw">
          <pre class="raw">{{ raw }}</pre>
        </el-collapse-item>
      </el-collapse>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { parseFilenames } from '@/api/files'

const { t } = useI18n()

const input = ref('')
const loading = ref(false)
const results = ref([])
const raw = ref('')

/** Accept one filename per line, or several separated by commas. */
function splitInput(text) {
  return text.split(/[\n,]+/).map(s => s.trim()).filter(Boolean)
}

async function submit() {
  const filenames = splitInput(input.value)
  if (!filenames.length) {
    ElMessage.warning(t('parse.pleaseEnterFilenames'))
    return
  }

  loading.value = true
  try {
    const response = await parseFilenames(filenames)
    results.value = response.results || []
    raw.value = response.raw || ''
  } catch (e) {
    ElMessage.error(t('parse.parseFailed'))
  } finally {
    loading.value = false
  }
}

function reset() {
  input.value = ''
  results.value = []
  raw.value = ''
}
</script>

<style scoped>
.parse-page {
  max-width: 1100px;
  margin: 0 auto;
}

.raw {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: monospace;
  font-size: 12px;
}

/* 移动端适配 */
@media (max-width: 768px) {
  .parse-page {
    padding: 0 4px;
  }
}
</style>
