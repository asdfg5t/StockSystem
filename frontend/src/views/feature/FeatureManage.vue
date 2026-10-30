<template>
  <div class="page-container">
    <div class="page-header">
      <h2>特征工程</h2>
    </div>

    <div class="card-box">
      <el-space wrap :size="12" alignment="center">
        <el-input v-model="tsCodeInput" placeholder="请输入股票代码，如 000001.SZ" clearable style="width: 220px" @keyup.enter="onTsCodeEnter" />
        <el-date-picker
          v-model="filterStart"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="数据开始日期（可选）"
          clearable
        />
        <el-date-picker
          v-model="filterEnd"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="数据结束日期（可选）"
          clearable
        />
        <el-button type="primary" :loading="computeLoading" :disabled="!tsCodeInput.trim()" @click="handleCompute">
          计算特征
        </el-button>
        <el-button :disabled="!tsCodeInput.trim()" @click="loadFeatureData">刷新数据</el-button>
      </el-space>
    </div>

    <div class="card-box">
      <div style="margin-bottom: 12px; font-weight: 600; color: #303133">可用特征列</div>
      <div class="feature-tags">
        <el-tag v-for="col in columns" :key="col" class="feature-tag" type="info" effect="plain">{{ col }}</el-tag>
      </div>
    </div>

    <div v-if="stats" class="card-box">
      <div style="margin-bottom: 12px; font-weight: 600; color: #303133">特征数据统计</div>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="股票代码">{{ stats.ts_code }}</el-descriptions-item>
        <el-descriptions-item label="版本">{{ stats.version }}</el-descriptions-item>
        <el-descriptions-item label="记录条数">{{ stats.count }}</el-descriptions-item>
        <el-descriptions-item label="特征维度数">{{ stats.feature_count }}</el-descriptions-item>
        <el-descriptions-item label="最早交易日">{{ stats.min_date || '—' }}</el-descriptions-item>
        <el-descriptions-item label="最晚交易日">{{ stats.max_date || '—' }}</el-descriptions-item>
      </el-descriptions>
    </div>

    <div class="card-box">
      <div style="margin-bottom: 12px; font-weight: 600; color: #303133">特征数据表</div>
      <el-table v-loading="tableLoading" :data="tableRows" stripe style="width: 100%">
        <el-table-column prop="trade_date" label="交易日" width="120" />
        <el-table-column prop="ts_code" label="股票代码" width="120" />
        <el-table-column prop="feature_version" label="版本" width="90" />
        <el-table-column label="特征数据" min-width="200">
          <template #default="{ row }">
            <el-popover placement="left" :width="480" trigger="click">
              <template #reference>
                <el-button link type="primary">查看详情</el-button>
              </template>
              <pre class="feature-json">{{ formatFeatureJson(row.feature_set) }}</pre>
            </el-popover>
          </template>
        </el-table-column>
      </el-table>
      <div style="margin-top: 16px; display: flex; justify-content: flex-end">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[20, 50, 100, 200]"
          layout="total, sizes, prev, pager, next"
          background
          @size-change="loadFeatureData"
          @current-change="loadFeatureData"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { featureApi } from '@/api/index.js'

const tsCodeInput = ref('')
const filterStart = ref('')
const filterEnd = ref('')
const computeLoading = ref(false)

const columns = ref([])
const stats = ref(null)

const tableLoading = ref(false)
const tableRows = ref([])
const pagination = reactive({ page: 1, pageSize: 50, total: 0 })

function formatFeatureJson(raw) {
  if (raw == null || raw === '') return ''
  try {
    const obj = typeof raw === 'string' ? JSON.parse(raw) : raw
    return JSON.stringify(obj, null, 2)
  } catch {
    return String(raw)
  }
}

async function loadColumns() {
  const res = await featureApi.getColumns()
  const list = res.data
  columns.value = Array.isArray(list) ? list : []
}

async function handleCompute() {
  const ts = tsCodeInput.value.trim()
  if (!ts) return
  computeLoading.value = true
  try {
    await featureApi.compute({
      ts_code: ts,
      start_date: filterStart.value || undefined,
      end_date: filterEnd.value || undefined,
      version: 'v1',
    })
    ElMessage.success('特征计算任务已启动，正在等待计算完成…')
    pollForData(ts)
  } catch {
    computeLoading.value = false
  }
}

let pollTimer = null
function pollForData(ts, attempt = 0) {
  const maxAttempts = 15
  const interval = 2000
  clearTimeout(pollTimer)
  if (attempt >= maxAttempts) {
    computeLoading.value = false
    ElMessage.info('计算可能仍在进行，请稍后手动刷新数据')
    return
  }
  pollTimer = setTimeout(async () => {
    try {
      const res = await featureApi.getStats(ts, { version: 'v1' })
      const count = res.data?.count ?? 0
      if (count > 0) {
        computeLoading.value = false
        ElMessage.success('特征计算完成')
        await loadFeatureData()
        return
      }
    } catch { /* ignore */ }
    pollForData(ts, attempt + 1)
  }, interval)
}

async function loadFeatureData() {
  const ts = tsCodeInput.value.trim()
  if (!ts) {
    ElMessage.warning('请先输入股票代码')
    return
  }
  tableLoading.value = true
  try {
    const [statsRes, dataRes] = await Promise.all([
      featureApi.getStats(ts, { version: 'v1' }),
      featureApi.getData(ts, {
        page: pagination.page,
        page_size: pagination.pageSize,
        start_date: filterStart.value || undefined,
        end_date: filterEnd.value || undefined,
        version: 'v1',
      }),
    ])
    stats.value = statsRes.data || null
    const block = dataRes.data || {}
    tableRows.value = block.items || []
    pagination.total = block.total ?? 0
  } finally {
    tableLoading.value = false
  }
}

onMounted(() => {
  loadColumns()
})

function onTsCodeEnter() {
  if (tsCodeInput.value.trim()) {
    loadFeatureData()
  }
}
</script>

<style scoped>
.feature-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.feature-tag {
  margin: 0;
}
.feature-json {
  margin: 0;
  max-height: 360px;
  overflow: auto;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
