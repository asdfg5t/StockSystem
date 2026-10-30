<template>
  <div class="page-container">
    <div class="page-header">
      <h2>模型评估结果</h2>
    </div>
    <div class="card-box">
      <el-form :inline="true" @submit.prevent="loadData">
        <el-form-item label="模型类型">
          <el-select v-model="filters.model_type" clearable placeholder="全部" style="width: 140px">
            <el-option label="TFT" value="TFT" />
            <el-option label="Transformer" value="Transformer" />
            <el-option label="BiLSTM" value="BiLSTM" />
          </el-select>
        </el-form-item>
        <el-form-item label="股票代码">
          <el-input v-model="filters.ts_code" clearable placeholder="ts_code" style="width: 140px" />
        </el-form-item>
        <el-form-item label="预测步长">
          <el-select v-model="filters.predict_steps" clearable placeholder="全部" style="width: 100px">
            <el-option label="1" :value="1" />
            <el-option label="3" :value="3" />
            <el-option label="5" :value="5" />
          </el-select>
        </el-form-item>
        <el-form-item label="数据集">
          <el-select v-model="filters.dataset_type" style="width: 120px">
            <el-option label="测试集" value="test" />
            <el-option label="验证集" value="val" />
            <el-option label="训练集" value="train" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">查询</el-button>
        </el-form-item>
      </el-form>

      <el-table
        v-loading="loading"
        :data="tableData"
        border
        stripe
        highlight-current-row
        style="width: 100%"
        @row-click="onRowClick"
      >
        <el-table-column prop="model_type" label="模型" width="100" fixed="left" />
        <el-table-column prop="ts_code" label="股票" width="130">
          <template #default="{ row }">
            <el-tag v-if="row.ts_code === 'smart_universal'" type="success" size="small" effect="plain">智能通用</el-tag>
            <el-tag v-else-if="row.ts_code === 'universal'" type="warning" size="small" effect="plain">通用模型</el-tag>
            <span v-else>{{ row.ts_code }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="predict_steps" label="步长" width="70" align="center" />
        <el-table-column prop="dataset_type" label="数据集" width="80" align="center" />
        <el-table-column label="回归指标">
          <el-table-column prop="mae" label="MAE" width="95" align="right">
            <template #default="{ row }">{{ fmtNum(row.mae) }}</template>
          </el-table-column>
          <el-table-column prop="rmse" label="RMSE" width="95" align="right">
            <template #default="{ row }">{{ fmtNum(row.rmse) }}</template>
          </el-table-column>
          <el-table-column prop="mse" label="MSE" width="95" align="right">
            <template #default="{ row }">{{ fmtNum(row.mse) }}</template>
          </el-table-column>
          <el-table-column prop="mape" label="MAPE%" width="90" align="right">
            <template #default="{ row }">{{ fmtNum(row.mape) }}</template>
          </el-table-column>
          <el-table-column prop="smape" label="SMAPE%" width="95" align="right">
            <template #default="{ row }">{{ fmtNum(row.smape) }}</template>
          </el-table-column>
          <el-table-column prop="max_error" label="最大误差" width="95" align="right">
            <template #default="{ row }">{{ fmtNum(row.max_error) }}</template>
          </el-table-column>
          <el-table-column prop="median_ae" label="中位误差" width="95" align="right">
            <template #default="{ row }">{{ fmtNum(row.median_ae) }}</template>
          </el-table-column>
        </el-table-column>
        <el-table-column label="拟合指标">
          <el-table-column prop="r2" label="R²" width="85" align="right">
            <template #default="{ row }">{{ fmtNum(row.r2) }}</template>
          </el-table-column>
          <el-table-column prop="explained_variance" label="解释方差" width="95" align="right">
            <template #default="{ row }">{{ fmtNum(row.explained_variance) }}</template>
          </el-table-column>
          <el-table-column prop="pearson_corr" label="皮尔逊" width="90" align="right">
            <template #default="{ row }">{{ fmtNum(row.pearson_corr) }}</template>
          </el-table-column>
        </el-table-column>
        <el-table-column label="准确率">
          <el-table-column prop="accuracy_1pct" label="1%内" width="80" align="right">
            <template #default="{ row }">{{ fmtNum(row.accuracy_1pct) }}</template>
          </el-table-column>
          <el-table-column prop="accuracy_3pct" label="3%内" width="80" align="right">
            <template #default="{ row }">{{ fmtNum(row.accuracy_3pct) }}</template>
          </el-table-column>
          <el-table-column prop="accuracy_5pct" label="5%内" width="80" align="right">
            <template #default="{ row }">{{ fmtNum(row.accuracy_5pct) }}</template>
          </el-table-column>
        </el-table-column>
        <el-table-column label="交易指标">
          <el-table-column prop="win_rate" label="胜率%" width="85" align="right">
            <template #default="{ row }">{{ fmtNum(row.win_rate) }}</template>
          </el-table-column>
          <el-table-column prop="profit_factor" label="盈利因子" width="95" align="right">
            <template #default="{ row }">{{ fmtNum(row.profit_factor) }}</template>
          </el-table-column>
          <el-table-column prop="sharpe_ratio" label="夏普" width="85" align="right">
            <template #default="{ row }">{{ fmtNum(row.sharpe_ratio) }}</template>
          </el-table-column>
          <el-table-column prop="max_drawdown" label="最大回撤%" width="100" align="right">
            <template #default="{ row }">{{ fmtNum(row.max_drawdown) }}</template>
          </el-table-column>
        </el-table-column>
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click.stop="openDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.page_size"
        :total="pagination.total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        style="margin-top: 16px; justify-content: flex-end"
        @size-change="loadData"
        @current-change="loadData"
      />
    </div>

    <el-dialog v-model="detailVisible" title="评估详情" width="85%" top="3vh" destroy-on-close>
      <div v-if="detailRow" class="detail-content">
        <div class="detail-header">
          <span class="detail-tag">{{ detailRow.model_type }}</span>
          <span class="detail-tag">{{ detailRow.ts_code }}</span>
          <span class="detail-tag">步长 {{ detailRow.predict_steps }} 天</span>
          <span class="detail-tag">{{ detailRow.dataset_type }} 集</span>
        </div>

        <div class="metrics-grid">
          <div class="metrics-group">
            <h4>回归指标</h4>
            <div class="metrics-row">
              <div class="metric-item"><span class="label">MAE</span><span class="value">{{ fmtNum(detailRow.mae) }}</span></div>
              <div class="metric-item"><span class="label">RMSE</span><span class="value">{{ fmtNum(detailRow.rmse) }}</span></div>
              <div class="metric-item"><span class="label">MSE</span><span class="value">{{ fmtNum(detailRow.mse) }}</span></div>
              <div class="metric-item"><span class="label">MAPE%</span><span class="value">{{ fmtNum(detailRow.mape) }}</span></div>
              <div class="metric-item"><span class="label">SMAPE%</span><span class="value">{{ fmtNum(detailRow.smape) }}</span></div>
              <div class="metric-item"><span class="label">最大误差</span><span class="value">{{ fmtNum(detailRow.max_error) }}</span></div>
              <div class="metric-item"><span class="label">中位误差</span><span class="value">{{ fmtNum(detailRow.median_ae) }}</span></div>
            </div>
          </div>
          <div class="metrics-group">
            <h4>拟合指标</h4>
            <div class="metrics-row">
              <div class="metric-item highlight"><span class="label">R²</span><span class="value">{{ fmtNum(detailRow.r2) }}</span></div>
              <div class="metric-item"><span class="label">解释方差</span><span class="value">{{ fmtNum(detailRow.explained_variance) }}</span></div>
              <div class="metric-item"><span class="label">皮尔逊相关</span><span class="value">{{ fmtNum(detailRow.pearson_corr) }}</span></div>
            </div>
          </div>
          <div class="metrics-group">
            <h4>准确率</h4>
            <div class="metrics-row">
              <div class="metric-item highlight"><span class="label">1% 内</span><span class="value">{{ fmtNum(detailRow.accuracy_1pct) }}%</span></div>
              <div class="metric-item highlight"><span class="label">3% 内</span><span class="value">{{ fmtNum(detailRow.accuracy_3pct) }}%</span></div>
              <div class="metric-item highlight"><span class="label">5% 内</span><span class="value">{{ fmtNum(detailRow.accuracy_5pct) }}%</span></div>
            </div>
          </div>
          <div class="metrics-group">
            <h4>交易模拟</h4>
            <div class="metrics-row">
              <div class="metric-item"><span class="label">胜率%</span><span class="value">{{ fmtNum(detailRow.win_rate) }}</span></div>
              <div class="metric-item"><span class="label">盈利因子</span><span class="value">{{ fmtNum(detailRow.profit_factor) }}</span></div>
              <div class="metric-item"><span class="label">夏普比率</span><span class="value">{{ fmtNum(detailRow.sharpe_ratio) }}</span></div>
              <div class="metric-item"><span class="label">最大回撤%</span><span class="value">{{ fmtNum(detailRow.max_drawdown) }}</span></div>
            </div>
          </div>
        </div>
      </div>

      <div class="chart-area">
        <LineChart
          v-if="chartSeries.length"
          title="实际值 vs 预测值"
          :x-data="chartX"
          :series="chartSeries"
          height="460px"
          :colors="['#3DD0B6', '#36CFC9']"
        />
        <el-empty v-else description="暂无图表数据" />
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, reactive } from 'vue'
import { evaluateApi } from '@/api/index.js'
import LineChart from '@/components/charts/LineChart.vue'

const loading = ref(false)
const tableData = ref([])
const detailVisible = ref(false)
const detailRow = ref(null)
const chartX = ref([])
const chartSeries = ref([])

const filters = reactive({
  model_type: '',
  ts_code: '',
  predict_steps: null,
  dataset_type: 'test',
})

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0,
})

const fmtNum = (v) => (v == null || v === '' ? '—' : Number(v).toFixed(4))

const parseArr = (raw) => {
  if (raw == null || raw === '') return []
  if (Array.isArray(raw)) return raw.map(Number)
  try {
    const p = JSON.parse(raw)
    return Array.isArray(p) ? p.map(Number) : []
  } catch {
    return []
  }
}

const buildChartFromDetail = (d) => {
  const actual = parseArr(d.actual_values)
  const predicted = parseArr(d.predicted_values)
  const n = Math.max(actual.length, predicted.length)
  if (!n) {
    chartX.value = []
    chartSeries.value = []
    return
  }
  chartX.value = Array.from({ length: n }, (_, i) => `${i + 1}`)
  chartSeries.value = [
    { name: '实际值', data: actual.length ? actual : Array(n).fill(null) },
    { name: '预测值', data: predicted.length ? predicted : Array(n).fill(null) },
  ]
}

const loadData = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.page_size,
      dataset_type: filters.dataset_type || 'test',
    }
    if (filters.model_type) params.model_type = filters.model_type
    if (filters.ts_code) params.ts_code = filters.ts_code.trim()
    if (filters.predict_steps) params.predict_steps = filters.predict_steps
    const res = await evaluateApi.getResults(params)
    const payload = res.data || {}
    tableData.value = payload.items || []
    pagination.total = payload.total || 0
  } finally {
    loading.value = false
  }
}

const openDetail = async (row) => {
  if (!row?.id) return
  const res = await evaluateApi.getDetail(row.id)
  const d = res.data
  if (d) {
    detailRow.value = d
    buildChartFromDetail(d)
  }
  detailVisible.value = true
}

const onRowClick = (row) => {
  openDetail(row)
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.detail-content {
  margin-bottom: 20px;
}

.detail-header {
  display: flex;
  gap: 10px;
  margin-bottom: 18px;
}

.detail-tag {
  padding: 4px 14px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  background: #E8F8F4;
  color: #3DD0B6;
}

.metrics-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.metrics-group h4 {
  font-size: 13px;
  font-weight: 600;
  color: #86909C;
  margin-bottom: 10px;
  padding-bottom: 6px;
  border-bottom: 1px solid #F0F2F5;
}

.metrics-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.metric-item {
  flex: 0 0 auto;
  padding: 8px 14px;
  border-radius: 8px;
  background: #F7F8FA;
  border: 1px solid #E8ECF0;
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 90px;
}

.metric-item.highlight {
  background: #E8F8F4;
  border-color: #B3EDE3;
}

.metric-item .label {
  font-size: 11px;
  color: #86909C;
  margin-bottom: 4px;
}

.metric-item .value {
  font-size: 15px;
  font-weight: 600;
  color: #1D2129;
}

.metric-item.highlight .value {
  color: #3DD0B6;
}

.chart-area {
  background: #FAFBFC;
  border-radius: 10px;
  padding: 16px;
  border: 1px solid #E8ECF0;
}
</style>
