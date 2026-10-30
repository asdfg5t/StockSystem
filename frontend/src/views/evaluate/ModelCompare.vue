<template>
  <div class="page-container">
    <div class="page-header">
      <h2>模型对比分析</h2>
    </div>
    <div class="card-box">
      <el-form :inline="true" @submit.prevent="loadCompare">
        <el-form-item label="股票代码" required>
          <el-input v-model="compareFilters.ts_code" clearable placeholder="如 000001.SZ 或留空用通用模型" style="width: 240px" />
        </el-form-item>
        <el-form-item label="预测步长">
          <el-select v-model="compareFilters.predict_steps" clearable placeholder="最新记录" style="width: 120px">
            <el-option label="不限" :value="0" />
            <el-option label="1" :value="1" />
            <el-option label="3" :value="3" />
            <el-option label="5" :value="5" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadCompare">对比</el-button>
        </el-form-item>
      </el-form>

      <el-table v-loading="loadingCompare" :data="compareRows" border stripe style="width: 100%; margin-bottom: 20px">
        <el-table-column prop="model_type" label="模型" width="110" fixed="left" />
        <el-table-column label="回归指标">
          <el-table-column prop="mae" label="MAE" width="90" align="right">
            <template #default="{ row }">{{ fmt(row.mae) }}</template>
          </el-table-column>
          <el-table-column prop="rmse" label="RMSE" width="90" align="right">
            <template #default="{ row }">{{ fmt(row.rmse) }}</template>
          </el-table-column>
          <el-table-column prop="mape" label="MAPE%" width="85" align="right">
            <template #default="{ row }">{{ fmt(row.mape) }}</template>
          </el-table-column>
          <el-table-column prop="max_error" label="最大误差" width="90" align="right">
            <template #default="{ row }">{{ fmt(row.max_error) }}</template>
          </el-table-column>
          <el-table-column prop="median_ae" label="中位误差" width="90" align="right">
            <template #default="{ row }">{{ fmt(row.median_ae) }}</template>
          </el-table-column>
        </el-table-column>
        <el-table-column label="拟合指标">
          <el-table-column prop="r2" label="R²" width="85" align="right">
            <template #default="{ row }">{{ fmt(row.r2) }}</template>
          </el-table-column>
          <el-table-column prop="explained_variance" label="解释方差" width="90" align="right">
            <template #default="{ row }">{{ fmt(row.explained_variance) }}</template>
          </el-table-column>
          <el-table-column prop="pearson_corr" label="皮尔逊" width="85" align="right">
            <template #default="{ row }">{{ fmt(row.pearson_corr) }}</template>
          </el-table-column>
        </el-table-column>
        <el-table-column label="准确率">
          <el-table-column prop="accuracy_1pct" label="1%内" width="75" align="right">
            <template #default="{ row }">{{ fmt(row.accuracy_1pct) }}</template>
          </el-table-column>
          <el-table-column prop="accuracy_3pct" label="3%内" width="75" align="right">
            <template #default="{ row }">{{ fmt(row.accuracy_3pct) }}</template>
          </el-table-column>
          <el-table-column prop="accuracy_5pct" label="5%内" width="75" align="right">
            <template #default="{ row }">{{ fmt(row.accuracy_5pct) }}</template>
          </el-table-column>
        </el-table-column>
        <el-table-column label="交易指标">
          <el-table-column prop="win_rate" label="胜率%" width="80" align="right">
            <template #default="{ row }">{{ fmt(row.win_rate) }}</template>
          </el-table-column>
          <el-table-column prop="profit_factor" label="盈利因子" width="90" align="right">
            <template #default="{ row }">{{ fmt(row.profit_factor) }}</template>
          </el-table-column>
          <el-table-column prop="sharpe_ratio" label="夏普" width="85" align="right">
            <template #default="{ row }">{{ fmt(row.sharpe_ratio) }}</template>
          </el-table-column>
          <el-table-column prop="max_drawdown" label="回撤%" width="80" align="right">
            <template #default="{ row }">{{ fmt(row.max_drawdown) }}</template>
          </el-table-column>
        </el-table-column>
      </el-table>

      <div v-if="compareAttempted && compareRaw && barSeries.length" style="display: flex; gap: 16px; flex-wrap: wrap;">
        <div style="flex: 1; min-width: 400px;">
          <BarChart
            title="回归指标对比"
            :x-data="regressionBarX"
            :series="regressionBarSeries"
            height="380px"
          />
        </div>
        <div style="flex: 1; min-width: 400px;">
          <BarChart
            title="交易指标对比"
            :x-data="tradingBarX"
            :series="tradingBarSeries"
            height="380px"
          />
        </div>
      </div>
      <el-empty v-else-if="compareAttempted && !loadingCompare" description="暂无对比数据" />
    </div>

    <div class="page-header" style="margin-top: 8px">
      <h2>步长对比（1日 / 3日 / 5日）</h2>
    </div>
    <div class="card-box">
      <el-form :inline="true" @submit.prevent="loadSteps">
        <el-form-item label="股票代码" required>
          <el-input v-model="stepsFilters.ts_code" clearable placeholder="如 000001.SZ 或留空用通用模型" style="width: 240px" />
        </el-form-item>
        <el-form-item label="模型类型">
          <el-select v-model="stepsFilters.model_type" clearable placeholder="全部模型" style="width: 140px">
            <el-option label="TFT" value="TFT" />
            <el-option label="Transformer" value="Transformer" />
            <el-option label="BiLSTM" value="BiLSTM" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadSteps">加载</el-button>
        </el-form-item>
      </el-form>
      <el-table v-loading="loadingSteps" :data="stepsTableRows" border stripe style="width: 100%">
        <el-table-column prop="model_type" label="模型" width="120" fixed="left" />
        <el-table-column label="步长 1">
          <template #default="{ row }">{{ stepCell(row, 1) }}</template>
        </el-table-column>
        <el-table-column label="步长 3">
          <template #default="{ row }">{{ stepCell(row, 3) }}</template>
        </el-table-column>
        <el-table-column label="步长 5">
          <template #default="{ row }">{{ stepCell(row, 5) }}</template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { evaluateApi } from '@/api/index.js'
import BarChart from '@/components/charts/BarChart.vue'

const MODEL_ORDER = ['TFT', 'Transformer', 'BiLSTM']

const REGRESSION_KEYS = [
  { key: 'mae', label: 'MAE' },
  { key: 'rmse', label: 'RMSE' },
  { key: 'mape', label: 'MAPE' },
  { key: 'r2', label: 'R²' },
  { key: 'explained_variance', label: '解释方差' },
  { key: 'pearson_corr', label: '皮尔逊' },
]

const TRADING_KEYS = [
  { key: 'win_rate', label: '胜率' },
  { key: 'profit_factor', label: '盈利因子' },
  { key: 'sharpe_ratio', label: '夏普比率' },
  { key: 'max_drawdown', label: '最大回撤' },
]

const loadingCompare = ref(false)
const loadingSteps = ref(false)
const compareAttempted = ref(false)
const compareRows = ref([])
const compareRaw = ref(null)
const stepsData = ref(null)

const compareFilters = reactive({
  ts_code: '',
  predict_steps: 0,
})

const stepsFilters = reactive({
  ts_code: '',
  model_type: '',
})

const fmt = (v) => (v == null || v === '' ? '—' : Number(v).toFixed(4))

const pickLatest = (arr) => {
  if (!arr || !arr.length) return null
  return arr[0]
}

const regressionBarX = computed(() => REGRESSION_KEYS.map((m) => m.label))
const tradingBarX = computed(() => TRADING_KEYS.map((m) => m.label))

const buildBarSeries = (keys) => {
  if (!compareRaw.value) return []
  return MODEL_ORDER.map((mt) => {
    const row = pickLatest(compareRaw.value[mt] || [])
    return {
      name: mt,
      data: keys.map((m) => (row && row[m.key] != null ? Number(row[m.key]) : 0)),
    }
  })
}

const barSeries = computed(() => buildBarSeries([...REGRESSION_KEYS, ...TRADING_KEYS]))
const regressionBarSeries = computed(() => buildBarSeries(REGRESSION_KEYS))
const tradingBarSeries = computed(() => buildBarSeries(TRADING_KEYS))

const stepsTableRows = computed(() => {
  if (!stepsData.value) return []
  const types = stepsFilters.model_type ? [stepsFilters.model_type] : MODEL_ORDER
  return types.map((mt) => ({
    model_type: mt,
    steps: stepsData.value[mt] || {},
  }))
})

const stepCell = (row, step) => {
  const cell = row.steps?.[step]
  if (!cell) return '—'
  const parts = [
    `RMSE ${fmt(cell.rmse)}`,
    `MAE ${fmt(cell.mae)}`,
    `R² ${fmt(cell.r2)}`,
    `胜率 ${fmt(cell.win_rate)}%`,
    `夏普 ${fmt(cell.sharpe_ratio)}`,
  ]
  return parts.join(' | ')
}

const loadCompare = async () => {
  const code = compareFilters.ts_code?.trim() || 'smart_universal'
  compareAttempted.value = true
  loadingCompare.value = true
  try {
    const params = { ts_code: code }
    if (compareFilters.predict_steps > 0) params.predict_steps = compareFilters.predict_steps
    const res = await evaluateApi.getCompare(params)
    compareRaw.value = res.data || {}
    compareRows.value = MODEL_ORDER.map((mt) => {
      const row = pickLatest(compareRaw.value[mt] || [])
      return row ? { model_type: mt, ...row } : { model_type: mt }
    })
  } finally {
    loadingCompare.value = false
  }
}

const loadSteps = async () => {
  const code = stepsFilters.ts_code?.trim() || 'smart_universal'
  loadingSteps.value = true
  try {
    const params = { ts_code: code }
    if (stepsFilters.model_type) params.model_type = stepsFilters.model_type
    const res = await evaluateApi.getStepsCompare(params)
    stepsData.value = res.data || {}
  } finally {
    loadingSteps.value = false
  }
}

onMounted(() => {
  if (compareFilters.ts_code) loadCompare()
})
</script>
