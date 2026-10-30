<template>
  <div class="page-container">
    <div class="page-header"><h2>模型训练对比看板</h2></div>

    <div v-if="loading" class="card-box"><el-skeleton :rows="6" animated /></div>

    <template v-else-if="hasData">
      <!-- 关键测试指标对比（参考图 5 张） -->
      <div class="card-box">
        <h3 class="sec-title">不同预测步长下各模型 MAE 对比</h3>
        <BarChart
          :x-data="stepLabels" :series="series.mae"
          :colors="palette" height="360px"
          show-label :label-formatter="fmt4"
          x-axis-name="预测步长（天）" y-axis-name="MAE"
        />
      </div>
      <div class="card-box">
        <h3 class="sec-title">不同预测步长下各模型 RMSE 对比</h3>
        <BarChart
          :x-data="stepLabels" :series="series.rmse"
          :colors="palette" height="360px"
          show-label :label-formatter="fmt4"
          x-axis-name="预测步长（天）" y-axis-name="RMSE"
        />
      </div>
      <div class="card-box">
        <h3 class="sec-title">不同预测步长下各模型 MAPE 变化趋势</h3>
        <LineChart
          :x-data="stepLabels" :series="series.mape"
          :colors="palette" :symbols="['circle', 'rect', 'diamond']"
          height="360px" show-label :label-formatter="fmtPct"
          x-axis-name="预测步长（天）" y-axis-name="MAPE（%）"
        />
      </div>
      <div class="card-box">
        <h3 class="sec-title">不同预测步长下各模型 R² 变化趋势</h3>
        <LineChart
          :x-data="stepLabels" :series="series.r2"
          :colors="palette" :symbols="['circle', 'rect', 'diamond']"
          height="360px" show-label :label-formatter="fmt4"
          x-axis-name="预测步长（天）" y-axis-name="R²"
        />
      </div>
      <div class="card-box">
        <h3 class="sec-title">不同预测步长下各模型 1% 准确率对比</h3>
        <BarChart
          :x-data="stepLabels" :series="series.acc1"
          :colors="palette" height="360px"
          show-label :label-formatter="fmt1"
          x-axis-name="预测步长（天）" y-axis-name="1% 准确率（%）"
        />
      </div>

      <!-- 详细汇总表 -->
      <div class="card-box">
        <h3 class="sec-title">汇总指标</h3>
        <el-table :data="tableRows" size="small" border stripe>
          <el-table-column prop="model_type" label="模型" width="120">
            <template #default="{ row }">
              <el-tag :type="modelTagType(row.model_type)" size="small">{{ row.model_type }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="predict_steps" label="步长" width="80" />
          <el-table-column prop="num_stocks" label="股票数" width="90" />
          <el-table-column prop="epochs_trained" label="训练轮数" width="100" />
          <el-table-column label="MAE" width="100">
            <template #default="{ row }">{{ fmt4(row.test_evaluation?.mae) }}</template>
          </el-table-column>
          <el-table-column label="RMSE" width="100">
            <template #default="{ row }">{{ fmt4(row.test_evaluation?.rmse) }}</template>
          </el-table-column>
          <el-table-column label="MAPE" width="100">
            <template #default="{ row }">{{ fmtPct(row.test_evaluation?.mape) }}</template>
          </el-table-column>
          <el-table-column label="R²" width="100">
            <template #default="{ row }">{{ fmt4(row.test_evaluation?.r2) }}</template>
          </el-table-column>
          <el-table-column label="1% 准确率" width="110">
            <template #default="{ row }">{{ fmtPct1(row.test_evaluation?.accuracy_1pct) }}</template>
          </el-table-column>
          <el-table-column label="3% 准确率" width="110">
            <template #default="{ row }">{{ fmtPct1(row.test_evaluation?.accuracy_3pct) }}</template>
          </el-table-column>
          <el-table-column label="5% 准确率" width="110">
            <template #default="{ row }">{{ fmtPct1(row.test_evaluation?.accuracy_5pct) }}</template>
          </el-table-column>
          <el-table-column label="最优 val_loss" min-width="120">
            <template #default="{ row }">{{ fmt6(row.best_val_loss) }}</template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 训练 epoch 曲线对比（按 step 切换） -->
      <div class="card-box">
        <div class="epoch-head">
          <h3 class="sec-title" style="margin: 0">训练过程曲线对比（按步长查看）</h3>
          <el-radio-group v-model="curStep" size="small">
            <el-radio-button :value="1">1 日</el-radio-button>
            <el-radio-button :value="3">3 日</el-radio-button>
            <el-radio-button :value="5">5 日</el-radio-button>
          </el-radio-group>
        </div>
      </div>
      <div class="card-box"><h4 class="sub-title">val_loss</h4>
        <LineChart :x-data="epochLabels" :series="epochSeries('val_loss')" :colors="palette" height="320px" />
      </div>
      <div class="card-box"><h4 class="sub-title">val_mae</h4>
        <LineChart :x-data="epochLabels" :series="epochSeries('val_mae')" :colors="palette" height="320px" />
      </div>
      <div class="card-box"><h4 class="sub-title">val_rmse</h4>
        <LineChart :x-data="epochLabels" :series="epochSeries('val_rmse')" :colors="palette" height="320px" />
      </div>
    </template>

    <div v-else class="card-box"><el-empty description="未读取到 smart_results 训练结果" /></div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { trainApi } from '@/api/index.js'
import BarChart from '@/components/charts/BarChart.vue'
import LineChart from '@/components/charts/LineChart.vue'

const loading = ref(false)
const items = ref([])
const curStep = ref(1)

const models = ['BiLSTM', 'Transformer', 'TFT']
const palette = ['#3B82F6', '#EF4444', '#22C55E']
const stepLabels = ['1天', '3天', '5天']
const stepValues = [1, 3, 5]

const hasData = computed(() => items.value.length > 0)

const find = (mt, step) =>
  items.value.find(x => x.model_type === mt && x.predict_steps === step)

const seriesByMetric = (key) =>
  models.map(mt => ({
    name: mt,
    data: stepValues.map(s => {
      const it = find(mt, s)
      const v = it?.test_evaluation?.[key]
      return v == null ? null : Number(v)
    }),
  }))

const series = computed(() => ({
  mae: seriesByMetric('mae'),
  rmse: seriesByMetric('rmse'),
  mape: seriesByMetric('mape'),
  r2: seriesByMetric('r2'),
  acc1: seriesByMetric('accuracy_1pct'),
}))

const tableRows = computed(() => {
  const rows = []
  for (const mt of models) {
    for (const s of stepValues) {
      const it = find(mt, s)
      if (it) rows.push(it)
    }
  }
  return rows
})

const modelTagType = (m) => ({
  BiLSTM: 'primary',
  Transformer: 'danger',
  TFT: 'success',
}[m] || '')

const epochCount = computed(() => {
  const lens = items.value
    .filter(it => it.predict_steps === curStep.value)
    .map(it => it.epoch_metrics?.length || 0)
  return lens.length ? Math.max(...lens) : 0
})
const epochLabels = computed(() =>
  Array.from({ length: epochCount.value }, (_, i) => String(i + 1))
)

const epochSeries = (field) =>
  models
    .map(mt => {
      const it = find(mt, curStep.value)
      if (!it?.epoch_metrics?.length) return null
      return { name: mt, data: it.epoch_metrics.map(m => m[field]) }
    })
    .filter(Boolean)

const fmt4 = (v) => (v == null ? '—' : Number(v).toFixed(4))
const fmt6 = (v) => (v == null ? '—' : Number(v).toFixed(6))
const fmt1 = (v) => (v == null ? '—' : Number(v).toFixed(1))
const fmtPct = (v) => (v == null ? '—' : `${Number(v).toFixed(2)}%`)
const fmtPct1 = (v) => (v == null ? '—' : `${Number(v).toFixed(1)}%`)

const load = async () => {
  loading.value = true
  try {
    const res = await trainApi.getSmartResults()
    items.value = res.data?.items || []
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.sec-title { font-size: 15px; font-weight: 600; color: #1D2129; margin-bottom: 12px; }
.sub-title { font-size: 13px; font-weight: 600; color: #4E5969; margin-bottom: 8px; }
.epoch-head { display: flex; justify-content: space-between; align-items: center; }
</style>
