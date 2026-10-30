<template>
  <div class="page-container">
    <div class="page-header"><h2>预测结果</h2></div>

    <!-- 筛选条件 -->
    <div class="card-box">
      <el-form :inline="true" @submit.prevent="loadResults">
        <el-form-item label="股票代码">
          <el-input v-model="filters.ts_code" placeholder="如 000001.SZ" clearable style="width: 160px" @keyup.enter="loadResults" />
        </el-form-item>
        <el-form-item label="模型类型">
          <el-select v-model="filters.model_type" clearable placeholder="全部" style="width: 130px">
            <el-option label="TFT" value="TFT" />
            <el-option label="Transformer" value="Transformer" />
            <el-option label="BiLSTM" value="BiLSTM" />
          </el-select>
        </el-form-item>
        <el-form-item label="预测步长">
          <el-select v-model="filters.predict_steps" clearable placeholder="全部" style="width: 110px">
            <el-option label="1 天" :value="1" />
            <el-option label="3 天" :value="3" />
            <el-option label="5 天" :value="5" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadResults">查询</el-button>
          <el-tooltip content="优先使用本地行情，DB 没有则通过 Tushare 实时拉取" placement="top">
            <el-button :loading="backfilling" type="success" plain @click="handleBackfill">
              <el-icon style="margin-right: 4px"><Refresh /></el-icon>
              Tushare 回填实际价格
            </el-button>
          </el-tooltip>
        </el-form-item>
      </el-form>
    </div>

    <!-- 统计概览 -->
    <el-row :gutter="16" class="stat-row" v-if="results.length">
      <el-col :xs="24" :sm="8">
        <div class="stat-card">
          <div class="stat-value">{{ total }}</div>
          <div class="stat-label">预测记录数</div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="8">
        <div class="stat-card">
          <div class="stat-value">{{ summaryStats.verifiedCount }}</div>
          <div class="stat-label">已验证</div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="8">
        <div class="stat-card">
          <div class="stat-value">{{ summaryStats.avgErrorPct }}</div>
          <div class="stat-label">平均误差%</div>
        </div>
      </el-col>
    </el-row>

    <!-- 数据表格 -->
    <div class="card-box">
      <el-table v-loading="loading" :data="results" stripe style="width: 100%">
        <el-table-column prop="model_type" label="模型" width="110" align="center">
          <template #default="{ row }">
            <el-tag size="small" effect="plain" round>{{ row.model_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="ts_code" label="股票代码" width="110" />
        <el-table-column prop="predict_steps" label="步长" width="70" align="center">
          <template #default="{ row }">{{ row.predict_steps }}天</template>
        </el-table-column>
        <el-table-column prop="base_date" label="基准日期" width="110" />
        <el-table-column prop="target_date" label="目标日期" width="110">
          <template #default="{ row }">{{ row.target_date || '—' }}</template>
        </el-table-column>
        <el-table-column prop="step_index" label="序号" width="60" align="center" />
        <el-table-column label="预测收盘价" width="120" align="right">
          <template #default="{ row }">
            <span class="price-text">{{ row.predicted_close?.toFixed(2) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="实际收盘价" width="120" align="right">
          <template #default="{ row }">
            <span v-if="row.actual_close != null">{{ row.actual_close.toFixed(2) }}</span>
            <span v-else class="text-muted">待验证</span>
          </template>
        </el-table-column>
        <el-table-column label="误差" width="100" align="right">
          <template #default="{ row }">
            <span v-if="row.error != null" :class="row.error > 0 ? 'text-red' : 'text-green'">
              {{ row.error > 0 ? '+' : '' }}{{ row.error.toFixed(2) }}
            </span>
            <span v-else class="text-muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="误差%" width="100" align="right">
          <template #default="{ row }">
            <template v-if="row.error_pct != null">
              <el-tag
                :type="Math.abs(row.error_pct) <= 1 ? 'success' : Math.abs(row.error_pct) <= 3 ? 'warning' : 'danger'"
                size="small" round
              >
                {{ row.error_pct > 0 ? '+' : '' }}{{ row.error_pct.toFixed(2) }}%
              </el-tag>
            </template>
            <span v-else class="text-muted">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" min-width="160">
          <template #default="{ row }">
            <span class="text-muted">{{ row.created_at }}</span>
          </template>
        </el-table-column>
      </el-table>

      <div style="margin-top: 16px; display: flex; justify-content: flex-end">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          background
          @size-change="loadResults"
          @current-change="loadResults"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { predictApi } from '@/api'

const loading = ref(false)
const backfilling = ref(false)
const results = ref([])
const page = ref(1)
const pageSize = ref(50)
const total = ref(0)

const filters = reactive({
  ts_code: '',
  model_type: '',
  predict_steps: null,
})

const summaryStats = computed(() => {
  // 只统计：实际收盘价 + 误差%都拿到了的记录，避免空值被当成 0 错入分子分母
  const verified = results.value.filter(
    r => r.actual_close != null && r.error_pct != null && Number.isFinite(r.error_pct),
  )
  const count = verified.length
  if (!count) {
    return { verifiedCount: 0, avgErrorPct: '—' }
  }
  const avgPct = verified.reduce((s, r) => s + Math.abs(r.error_pct), 0) / count
  return {
    verifiedCount: count,
    avgErrorPct: avgPct.toFixed(2) + '%',
  }
})

const loadResults = async () => {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (filters.ts_code) params.ts_code = filters.ts_code
    if (filters.model_type) params.model_type = filters.model_type
    if (filters.predict_steps) params.predict_steps = filters.predict_steps
    const res = await predictApi.getResults(params)
    results.value = res.data
    total.value = res.total
  } finally {
    loading.value = false
  }
}

const handleBackfill = async () => {
  backfilling.value = true
  try {
    const res = await predictApi.backfillActual({ use_tushare: true })
    const d = res.data || {}
    ElMessage.success(res.message || `回填完成：更新 ${d.updated} 条`)
    if (d.updated > 0) await loadResults()
  } finally {
    backfilling.value = false
  }
}

onMounted(loadResults)
</script>

<style scoped>
.stat-row {
  margin-bottom: 8px;
}

.price-text {
  color: #3DD0B6;
  font-weight: 600;
}

.text-muted {
  color: #C0C4CC;
  font-size: 12px;
}

.text-red {
  color: #F56C6C;
  font-weight: 500;
}

.text-green {
  color: #3DD0B6;
  font-weight: 500;
}
</style>
