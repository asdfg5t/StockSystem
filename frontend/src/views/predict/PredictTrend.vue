<template>
  <div class="page-container">
    <div class="card-box">
      <div style="display: flex; flex-wrap: wrap; gap: 16px; align-items: center; margin-bottom: 16px">
        <span style="font-weight: 600">股票：{{ tsCode || '—' }}</span>
        <el-form :inline="true" style="margin: 0">
          <el-form-item label="预测步长">
            <el-select v-model="predictSteps" style="width: 100px" @change="loadAll">
              <el-option label="1" :value="1" />
              <el-option label="3" :value="3" />
              <el-option label="5" :value="5" />
            </el-select>
          </el-form-item>
          <el-form-item label="模型">
            <el-select v-model="modelFilter" style="width: 140px" @change="loadAll">
              <el-option label="全部（三模型）" value="" />
              <el-option label="TFT" value="TFT" />
              <el-option label="Transformer" value="Transformer" />
              <el-option label="BiLSTM" value="BiLSTM" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="loadAll">刷新</el-button>
          </el-form-item>
        </el-form>
      </div>
      <LineChart
        v-if="chartX.length"
        title="历史收盘与多模型预测对比"
        :x-data="chartX"
        :series="chartSeries"
        height="460px"
      />
      <el-empty v-else-if="!loading" description="暂无数据" />
      <div v-loading="loading" style="min-height: 200px" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { stockApi, predictApi } from '@/api/index.js'
import LineChart from '@/components/charts/LineChart.vue'

const route = useRoute()
const loading = ref(false)
const klineList = ref([])
const predRows = ref([])
const predictSteps = ref(1)
const modelFilter = ref('')

const tsCode = computed(() => route.params.tsCode || '')

const MODELS = ['TFT', 'Transformer', 'BiLSTM']

const buildChart = () => {
  const code = tsCode.value
  if (!code) return { sorted: [], series: [] }
  const closeByDate = new Map()
  klineList.value.forEach((k) => {
    const d = k.date || k.trade_date
    if (d != null) closeByDate.set(String(d), k.close)
  })
  const predByModel = new Map()
  MODELS.forEach((m) => predByModel.set(m, new Map()))
  predRows.value.forEach((r) => {
    if (!r.target_date || r.model_type == null) return
    const m = r.model_type
    if (!predByModel.has(m)) return
    predByModel.get(m).set(String(r.target_date), r.predicted_close)
  })
  const dates = new Set(closeByDate.keys())
  predByModel.forEach((m) => {
    m.forEach((_, d) => dates.add(d))
  })
  const sorted = Array.from(dates).sort()
  const hist = sorted.map((d) => (closeByDate.has(d) ? closeByDate.get(d) : null))
  const series = [{ name: '历史收盘', data: hist }]
  const activeModels = modelFilter.value ? [modelFilter.value] : MODELS
  const colors = ['#3DD0B6', '#409EFF', '#E6A23C', '#F56C6C']
  activeModels.forEach((m) => {
    const pm = predByModel.get(m)
    if (!pm) return
    series.push({
      name: `${m} 预测`,
      data: sorted.map((d) => (pm.has(d) ? pm.get(d) : null)),
    })
  })
  return { sorted, series }
}

const chartX = ref([])
const chartSeries = ref([])

const loadAll = async () => {
  const code = tsCode.value
  if (!code) return
  loading.value = true
  try {
    const [kRes, pRes] = await Promise.all([
      stockApi.getKline(code, {}),
      predictApi.getResults({
        ts_code: code,
        predict_steps: predictSteps.value,
        page: 1,
        page_size: 200,
      }),
    ])
    klineList.value = kRes.data || []
    predRows.value = pRes.data || []
    const built = buildChart()
    chartX.value = built?.sorted || []
    chartSeries.value = built?.series || []
  } finally {
    loading.value = false
  }
}

watch(
  () => route.params.tsCode,
  () => {
    loadAll()
  }
)

onMounted(() => {
  loadAll()
})
</script>
