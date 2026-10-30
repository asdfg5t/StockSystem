<template>
  <div class="page-container">
    <div class="page-header">
      <h2>系统日志</h2>
    </div>
    <div class="card-box">
      <h3 style="margin-bottom: 12px; font-size: 15px">日志文件</h3>
      <el-table
        :data="logFiles"
        border
        stripe
        highlight-current-row
        max-height="240"
        style="width: 100%; margin-bottom: 20px"
        @row-click="onFileRowClick"
      >
        <el-table-column prop="name" label="文件名" min-width="200" />
        <el-table-column prop="size" label="大小（字节）" width="120" />
        <el-table-column prop="modified" label="修改时间" width="180" />
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button type="primary" link @click.stop="loadFileContent(row.name)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="selectedFile" style="margin-bottom: 24px">
        <div style="margin-bottom: 8px; font-weight: 600">文件内容：{{ selectedFile }}</div>
        <pre class="log-pre"><code>{{ fileContent }}</code></pre>
      </div>
    </div>
    <div class="page-header" style="margin-top: 8px">
      <h2>数据库日志</h2>
    </div>
    <div class="card-box">
      <el-form :inline="true" @submit.prevent="loadDbLogs">
        <el-form-item label="模块">
          <el-input v-model="dbFilters.module" clearable placeholder="模块" style="width: 140px" />
        </el-form-item>
        <el-form-item label="级别">
          <el-input v-model="dbFilters.level" clearable placeholder="如 INFO" style="width: 120px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadDbLogs">查询</el-button>
        </el-form-item>
      </el-form>
      <el-table v-loading="dbLoading" :data="dbItems" border stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="module" label="模块" width="140" />
        <el-table-column prop="level" label="级别" width="90" />
        <el-table-column prop="message" label="消息" min-width="200" show-overflow-tooltip />
        <el-table-column prop="detail" label="详情" min-width="160" show-overflow-tooltip />
        <el-table-column prop="created_at" label="时间" width="170" />
      </el-table>
      <el-pagination
        v-model:current-page="dbPage.page"
        v-model:page-size="dbPage.page_size"
        :total="dbPage.total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        style="margin-top: 16px; justify-content: flex-end"
        @size-change="loadDbLogs"
        @current-change="loadDbLogs"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { systemApi } from '@/api/index.js'

const logFiles = ref([])
const selectedFile = ref('')
const fileContent = ref('')

const dbLoading = ref(false)
const dbItems = ref([])

const dbFilters = reactive({
  module: '',
  level: '',
})

const dbPage = reactive({
  page: 1,
  page_size: 50,
  total: 0,
})

const loadLogFiles = async () => {
  const res = await systemApi.getLogFiles()
  logFiles.value = res.data || []
}

const loadFileContent = async (filename) => {
  if (!filename) return
  selectedFile.value = filename
  try {
    const res = await systemApi.getLogContent(filename, { lines: 500 })
    fileContent.value = res.data?.content ?? ''
  } catch {
    fileContent.value = ''
    ElMessage.error('无法读取该文件内容')
  }
}

const onFileRowClick = (row) => {
  loadFileContent(row.name)
}

const loadDbLogs = async () => {
  dbLoading.value = true
  try {
    const params = {
      page: dbPage.page,
      page_size: dbPage.page_size,
    }
    if (dbFilters.module?.trim()) params.module = dbFilters.module.trim()
    if (dbFilters.level?.trim()) params.level = dbFilters.level.trim()
    const res = await systemApi.getLogs(params)
    const payload = res.data || {}
    dbItems.value = payload.items || []
    dbPage.total = payload.total ?? 0
  } finally {
    dbLoading.value = false
  }
}

onMounted(() => {
  loadLogFiles()
  loadDbLogs()
})
</script>

<style scoped>
.log-pre {
  margin: 0;
  padding: 12px;
  background: #1e1e1e;
  color: #d4d4d4;
  border-radius: 8px;
  max-height: 360px;
  overflow: auto;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
}
.log-pre code {
  font-family: Consolas, 'Courier New', monospace;
  color: inherit;
}
</style>
