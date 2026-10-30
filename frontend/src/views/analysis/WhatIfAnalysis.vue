<template>
  <div class="page-container">
    <div class="page-header"><h2>What-If 情景分析</h2></div>
    <div class="card-box">
      <el-form :inline="true" @submit.prevent="loadData">
        <el-form-item label="股票代码"><el-input v-model="form.ts_code" placeholder="000001.SZ" style="width: 140px" /></el-form-item>
        <el-form-item label="模型">
          <el-select v-model="form.model_type" style="width: 130px">
            <el-option label="BiLSTM" value="BiLSTM" /><el-option label="Transformer" value="Transformer" /><el-option label="TFT" value="TFT" />
          </el-select>
        </el-form-item>
        <el-form-item label="步长">
          <el-select v-model="form.predict_steps" style="width: 80px">
            <el-option :label="1" :value="1" /><el-option :label="3" :value="3" /><el-option :label="5" :value="5" />
          </el-select>
        </el-form-item>
        <el-form-item label="调整特征">
          <el-select v-model="form.feature_name" filterable :loading="featureLoading" style="width: 160px">
            <el-option v-for="f in featureOptions" :key="f" :label="f" :value="f" />
          </el-select>
        </el-form-item>
        <el-form-item><el-button type="primary" :loading="loading" @click="loadData">分析敏感度</el-button></el-form-item>
      </el-form>
      <div v-if="modelScope" class="model-hint">
        当前命中模型：<el-tag size="small" effect="plain" :type="isUniversal ? 'success' : 'info'">{{ modelScope }}</el-tag>
        <span class="muted"> · 仅展示该模型实际使用的 {{ featureOptions.length }} 个特征</span>
      </div>
      <div v-else-if="!featureLoading && featureOptions.length === 0" class="model-hint warn">
        未找到对应模型，请先训练。当前下拉列表使用全量特征，仅供参考
      </div>
    </div>

    <template v-if="data">
      <div class="card-box">
        <h3 class="sec-title">特征「{{ data.feature_name }}」敏感度分析 <span class="sub">基准值: {{ data.base_value }}</span></h3>
        <div ref="chartRef" style="width: 100%; height: 380px;"></div>
      </div>
      <div class="card-box">
        <h3 class="sec-title">情景明细</h3>
        <el-table :data="data.scenarios" stripe border>
          <el-table-column prop="multiplier" label="倍数" width="80" align="center">
            <template #default="{ row }">{{ row.multiplier }}x</template>
          </el-table-column>
          <el-table-column prop="feature_value" label="特征值" width="120" />
          <el-table-column label="预测价格">
            <template #default="{ row }">
              <span v-for="(p, i) in row.predicted_prices" :key="i" class="price-tag">¥{{ p }}</span>
            </template>
          </el-table-column>
          <el-table-column label="vs 基准变化">
            <template #default="{ row }">
              <span v-if="basePrice" :style="{ color: row.predicted_prices[0] > basePrice ? '#52C41A' : '#F5222D' }">
                {{ ((row.predicted_prices[0] - basePrice) / basePrice * 100).toFixed(2) }}%
              </span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </template>
    <div v-else-if="!loading" class="card-box"><el-empty description="选择特征并分析其对预测的影响" /></div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { analysisApi, featureApi } from '@/api/index.js'

const loading = ref(false)
const featureLoading = ref(false)
const form = reactive({ ts_code: '000001.SZ', model_type: 'BiLSTM', predict_steps: 1, feature_name: 'vol' })
const data = ref(null)
const featureOptions = ref([])
const modelScope = ref('')
const isUniversal = ref(false)
const chartRef = ref(null)
let chart = null

const basePrice = computed(() => {
  if (!data.value) return null
  const base = data.value.scenarios.find(s => s.multiplier === 1.0)
  return base ? base.predicted_prices[0] : null
})

const loadFeatureOptions = async () => {
  featureLoading.value = true
  try {
    const res = await analysisApi.getModelFeatures({
      ts_code: form.ts_code,
      model_type: form.model_type,
      predict_steps: form.predict_steps,
    })
    const feats = res.data?.features || []
    if (feats.length > 0) {
      featureOptions.value = feats
      modelScope.value = res.data.model_scope || ''
      isUniversal.value = !!res.data.is_universal
    } else {
      // 无对应模型时回退到全量特征列表
      const all = await featureApi.getColumns()
      featureOptions.value = all.data || []
      modelScope.value = ''
      isUniversal.value = false
    }
    if (!featureOptions.value.includes(form.feature_name)) {
      form.feature_name = featureOptions.value[0] || ''
    }
  } finally {
    featureLoading.value = false
  }
}

onMounted(loadFeatureOptions)

watch(() => [form.ts_code, form.model_type, form.predict_steps], () => {
  if (form.ts_code && form.ts_code.length >= 6) loadFeatureOptions()
})

const loadData = async () => {
  if (!form.feature_name) {
    ElMessage.warning('请先选择一个调整特征')
    return
  }
  loading.value = true
  try {
    const res = await analysisApi.getWhatIf({
      ...form,
      multipliers: '0.5,0.7,0.8,0.9,1.0,1.1,1.2,1.3,1.5,2.0',
    })
    data.value = res.data
    await nextTick()
    renderChart()
  } catch (err) {
    // 拦截器已弹过提示；这里把后端返回的 available_features 同步到下拉框
    const avail = err?.payload?.data?.available_features
    if (Array.isArray(avail) && avail.length) {
      featureOptions.value = avail
      modelScope.value = err.payload.data.model_scope || modelScope.value
      if (!avail.includes(form.feature_name)) {
        form.feature_name = avail[0]
      }
    }
  } finally { loading.value = false }
}

const renderChart = () => {
  if (!chartRef.value || !data.value) return
  if (chart) chart.dispose()
  chart = echarts.init(chartRef.value)
  const scenarios = data.value.scenarios
  chart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: '8%', right: '4%', bottom: '10%', top: '10%', containLabel: true },
    xAxis: { type: 'category', data: scenarios.map(s => `${s.multiplier}x`), name: `${data.value.feature_name} 倍数` },
    yAxis: { type: 'value', name: '预测价格 (¥)', scale: true },
    series: [{
      name: '预测价格',
      type: 'line',
      data: scenarios.map(s => s.predicted_prices[0]),
      smooth: true,
      symbol: 'circle',
      symbolSize: 8,
      itemStyle: { color: '#3DD0B6' },
      areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(79,110,247,0.2)' }, { offset: 1, color: 'rgba(79,110,247,0)' }] } },
      markLine: { data: [{ name: '基准(1x)', xAxis: scenarios.findIndex(s => s.multiplier === 1.0) }], lineStyle: { color: '#86909C', type: 'dashed' } },
    }],
  })
}

onUnmounted(() => { chart?.dispose() })
</script>

<style scoped>
.sec-title { font-size: 15px; font-weight: 600; color: #1D2129; margin-bottom: 12px; }
.sec-title .sub { font-size: 12px; color: #86909C; font-weight: 400; margin-left: 8px; }
.price-tag { display: inline-block; margin-right: 8px; padding: 2px 8px; background: #E8F8F4; border-radius: 4px; font-size: 13px; color: #3DD0B6; font-weight: 500; }
.model-hint { margin-top: 6px; font-size: 12px; color: #4E5969; display: flex; align-items: center; gap: 6px; }
.model-hint.warn { color: #F5A623; }
.model-hint .muted { color: #86909C; }
</style>
