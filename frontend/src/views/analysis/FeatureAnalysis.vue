<template>
  <div class="page-container">
    <div class="page-header">
      <h2>特征重要性分析</h2>
    </div>

    <div class="card-box">
      <el-form :inline="true" @submit.prevent="loadData">
        <el-form-item label="股票代码">
          <el-input v-model="form.ts_code" placeholder="000001.SZ" style="width: 150px" />
        </el-form-item>
        <el-form-item label="模型">
          <el-select v-model="form.model_type" style="width: 140px">
            <el-option label="BiLSTM" value="BiLSTM" />
            <el-option label="Transformer" value="Transformer" />
            <el-option label="TFT" value="TFT" />
          </el-select>
        </el-form-item>
        <el-form-item label="步长">
          <el-select v-model="form.predict_steps" style="width: 90px">
            <el-option :label="1" :value="1" />
            <el-option :label="3" :value="3" />
            <el-option :label="5" :value="5" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="loadData">加载分析</el-button>
        </el-form-item>
      </el-form>
    </div>

    <template v-if="pcaData">
      <div v-if="isFeatureSelectionMode" class="card-box info-banner">
        <el-icon><InfoFilled /></el-icon>
        <span>当前命中模型 <b>{{ pcaData.model_scope }}</b> 未使用 PCA，下方展示的是<b>互信息精选的 Top 特征</b>排序（共 {{ pcaData.selected_features?.length || 0 }} 个）</span>
      </div>

      <div class="card-box">
        <h3 class="section-title">
          {{ isFeatureSelectionMode ? `特征精选 (共 ${pcaData.total_components} 组)` : `PCA 方差解释比 (前${pcaData.total_components}个主成分, 累计 ${pcaData.total_variance_explained}%)` }}
        </h3>
        <div ref="pcaChartRef" style="width: 100%; height: 360px;"></div>
      </div>

      <div class="card-box">
        <h3 class="section-title">{{ isFeatureSelectionMode ? '各组 Top-5 精选特征' : '各主成分 Top-5 原始特征权重' }}</h3>
        <div class="components-grid">
          <div v-for="comp in pcaData.top_features_per_component" :key="comp.component" class="comp-card">
            <div class="comp-header">{{ isFeatureSelectionMode ? `组 ${comp.component}` : `PC${comp.component}` }} <span class="comp-pct">{{ comp.explained_ratio }}%</span></div>
            <div v-for="f in comp.top_features" :key="f.feature" class="feat-row">
              <span class="feat-name">{{ f.feature }}</span>
              <div class="feat-bar-bg">
                <div class="feat-bar" :style="{ width: Math.abs(f.weight) * 200 + '%' }"></div>
              </div>
              <span class="feat-val">{{ f.weight }}</span>
            </div>
          </div>
        </div>
      </div>
    </template>

    <div v-if="corrData" class="card-box">
      <h3 class="section-title">特征相关性矩阵 (前30个特征)</h3>
      <div ref="corrChartRef" style="width: 100%; height: 600px;"></div>
    </div>

    <div v-if="!pcaData && !loading" class="card-box">
      <el-empty description="选择参数并加载分析" />
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, nextTick, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { analysisApi } from '@/api/index.js'

const loading = ref(false)
const form = reactive({ ts_code: '000001.SZ', model_type: 'BiLSTM', predict_steps: 1 })
const pcaData = ref(null)
const corrData = ref(null)
const pcaChartRef = ref(null)
const corrChartRef = ref(null)
let pcaChart = null, corrChart = null

const isFeatureSelectionMode = computed(() => pcaData.value?.mode === 'feature_selection')

const loadData = async () => {
  loading.value = true
  try {
    const [pcaRes, corrRes] = await Promise.all([
      analysisApi.getPcaImportance(form).catch(() => ({ data: null })),
      analysisApi.getCorrelation({ ts_code: form.ts_code }).catch(() => ({ data: null })),
    ])
    pcaData.value = pcaRes.data
    corrData.value = corrRes.data
    await nextTick()
    renderPcaChart()
    renderCorrChart()
  } finally {
    loading.value = false
  }
}

const renderPcaChart = () => {
  if (!pcaChartRef.value || !pcaData.value) return
  if (pcaChart) pcaChart.dispose()
  pcaChart = echarts.init(pcaChartRef.value)
  const isSel = isFeatureSelectionMode.value
  const prefix = isSel ? '组' : 'PC'
  const labels = pcaData.value.explained_ratio.map((_, i) => `${prefix}${i + 1}`)
  pcaChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: [isSel ? '占比%' : '方差解释比%', '累积%'], top: 10 },
    grid: { left: '6%', right: '4%', bottom: '10%', top: '16%', containLabel: true },
    xAxis: { type: 'category', data: labels, axisLabel: { rotate: 45 } },
    yAxis: { type: 'value', name: '%' },
    series: [
      { name: isSel ? '占比%' : '方差解释比%', type: 'bar', data: pcaData.value.explained_ratio, itemStyle: { color: '#3DD0B6' } },
      { name: '累积%', type: 'line', data: pcaData.value.cumulative_ratio, itemStyle: { color: '#36CFC9' }, lineStyle: { width: 2 } },
    ],
  })
}

const renderCorrChart = () => {
  if (!corrChartRef.value || !corrData.value) return
  if (corrChart) corrChart.dispose()
  corrChart = echarts.init(corrChartRef.value)
  const features = corrData.value.features
  const matrix = corrData.value.matrix
  const data = []
  matrix.forEach((row, yi) => { row.forEach((val, xi) => { data.push([xi, yi, val]) }) })
  corrChart.setOption({
    tooltip: { formatter: (p) => `${features[p.data[0]]} & ${features[p.data[1]]}: ${p.data[2]}` },
    grid: { left: '14%', right: '12%', top: '2%', bottom: '14%' },
    xAxis: { type: 'category', data: features, axisLabel: { rotate: 60, fontSize: 10 } },
    yAxis: { type: 'category', data: features, axisLabel: { fontSize: 10 } },
    visualMap: { min: -1, max: 1, calculable: true, orient: 'vertical', right: '1%', top: 'center', inRange: { color: ['#3A56D4', '#E8F8F4', '#F5222D'] } },
    series: [{ type: 'heatmap', data, label: { show: false }, emphasis: { itemStyle: { shadowBlur: 6 } } }],
  })
}

onUnmounted(() => { pcaChart?.dispose(); corrChart?.dispose() })
</script>

<style scoped>
.section-title { font-size: 15px; font-weight: 600; color: #1D2129; margin-bottom: 12px; }
.components-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }
.comp-card { background: #F7F8FA; border-radius: 10px; padding: 14px; border: 1px solid #E8ECF0; }
.comp-header { font-weight: 600; font-size: 14px; color: #1D2129; margin-bottom: 10px; }
.comp-pct { font-size: 12px; color: #3DD0B6; margin-left: 6px; }
.feat-row { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; font-size: 12px; }
.feat-name { width: 100px; text-align: right; color: #4E5969; flex-shrink: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.feat-bar-bg { flex: 1; height: 8px; background: #E8ECF0; border-radius: 4px; overflow: hidden; }
.feat-bar { height: 100%; background: linear-gradient(90deg, #3DD0B6, #36CFC9); border-radius: 4px; max-width: 100%; }
.feat-val { width: 50px; text-align: right; color: #86909C; flex-shrink: 0; }
.info-banner { display: flex; align-items: center; gap: 8px; background: #E8F8F4; border: 1px solid #B7EBDC; color: #1F6F58; font-size: 13px; }
.info-banner b { color: #0E5C46; }
</style>
