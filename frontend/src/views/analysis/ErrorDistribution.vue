<template>
  <div class="page-container">
    <div class="page-header"><h2>预测误差分布分析</h2></div>
    <div class="card-box">
      <el-form :inline="true" @submit.prevent="loadData">
        <el-form-item label="股票代码">
          <el-input v-model="form.ts_code" placeholder="000001.SZ" style="width: 150px" />
        </el-form-item>
        <el-form-item label="步长">
          <el-select v-model="form.predict_steps" style="width: 90px">
            <el-option :label="1" :value="1" /><el-option :label="3" :value="3" /><el-option :label="5" :value="5" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="loadData">加载分析</el-button>
        </el-form-item>
      </el-form>
    </div>

    <template v-if="Object.keys(modelData).length">
      <div v-for="(info, mt) in modelData" :key="mt" class="card-box">
        <h3 class="sec-title">{{ mt }} 误差分布</h3>
        <div class="stats-grid">
          <div class="stat-item" v-for="(val, key) in info.stats" :key="key">
            <span class="stat-label">{{ statLabels[key] || key }}</span>
            <span class="stat-val">{{ val }}</span>
          </div>
        </div>
        <div :ref="el => setChartRef(mt, el)" style="width: 100%; height: 320px; margin-top: 16px;"></div>
      </div>
    </template>
    <div v-else-if="!loading" class="card-box"><el-empty description="选择参数加载误差分析" /></div>
  </div>
</template>

<script setup>
import { ref, reactive, nextTick, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { analysisApi } from '@/api/index.js'

const loading = ref(false)
const form = reactive({ ts_code: '000001.SZ', predict_steps: 1 })
const modelData = ref({})
const charts = {}
const chartRefs = {}
const statLabels = { mean: '均值', std: '标准差', median: '中位数', skewness: '偏度', kurtosis: '峰度', q25: 'Q25%', q75: 'Q75%', min_pct: '最小%', max_pct: '最大%' }

const setChartRef = (mt, el) => { if (el) chartRefs[mt] = el }

const loadData = async () => {
  loading.value = true
  try {
    const res = await analysisApi.getErrorDistribution(form)
    modelData.value = res.data || {}
    await nextTick()
    Object.entries(modelData.value).forEach(([mt, info]) => renderHistogram(mt, info))
  } finally { loading.value = false }
}

const renderHistogram = (mt, info) => {
  const el = chartRefs[mt]
  if (!el) return
  if (charts[mt]) charts[mt].dispose()
  charts[mt] = echarts.init(el)
  const h = info.histogram
  const labels = h.edges.slice(0, -1).map((e, i) => `${e.toFixed(1)}~${h.edges[i + 1].toFixed(1)}%`)
  charts[mt].setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: '6%', right: '4%', bottom: '12%', top: '10%', containLabel: true },
    xAxis: { type: 'category', data: labels, axisLabel: { rotate: 45, fontSize: 10 } },
    yAxis: { type: 'value', name: '频次' },
    series: [{ type: 'bar', data: h.counts, itemStyle: { color: '#3DD0B6', borderRadius: [4, 4, 0, 0] } }],
  })
}

onUnmounted(() => Object.values(charts).forEach(c => c?.dispose()))
</script>

<style scoped>
.sec-title { font-size: 15px; font-weight: 600; color: #1D2129; margin-bottom: 12px; }
.stats-grid { display: flex; flex-wrap: wrap; gap: 10px; }
.stat-item { background: #F7F8FA; border-radius: 8px; padding: 8px 14px; border: 1px solid #E8ECF0; text-align: center; min-width: 90px; }
.stat-label { display: block; font-size: 11px; color: #86909C; }
.stat-val { display: block; font-size: 14px; font-weight: 600; color: #1D2129; }
</style>
