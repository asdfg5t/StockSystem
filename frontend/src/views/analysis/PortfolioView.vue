<template>
  <div class="page-container">
    <div class="page-header">
      <h2>多股票组合分析</h2>
    </div>

    <div class="card-box">
      <el-form :inline="true" @submit.prevent="loadAll">
        <el-form-item label="模型">
          <el-select v-model="form.model_type" clearable placeholder="全部" style="width: 140px">
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
        <el-form-item label="推荐数量">
          <el-input-number v-model="form.top_n" :min="3" :max="20" style="width: 110px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="loadAll">加载分析</el-button>
        </el-form-item>
      </el-form>
    </div>

    <template v-if="portfolio">
      <div class="card-box">
        <h3 class="section-title">推荐投资组合 (Top {{ form.top_n }})</h3>
        <el-table :data="portfolio.suggestions" stripe border>
          <el-table-column prop="ts_code" label="代码" width="110" />
          <el-table-column prop="name" label="名称" width="100" />
          <el-table-column prop="industry" label="行业" width="100" />
          <el-table-column prop="r2" label="R²" width="80" align="right">
            <template #default="{ row }">{{ row.r2?.toFixed(4) ?? '—' }}</template>
          </el-table-column>
          <el-table-column prop="mape" label="MAPE%" width="90" align="right">
            <template #default="{ row }">{{ row.mape?.toFixed(2) ?? '—' }}</template>
          </el-table-column>
          <el-table-column prop="sharpe_ratio" label="夏普" width="80" align="right">
            <template #default="{ row }">{{ row.sharpe_ratio?.toFixed(4) ?? '—' }}</template>
          </el-table-column>
          <el-table-column prop="accuracy_3pct" label="3%准确率" width="100" align="right">
            <template #default="{ row }">{{ row.accuracy_3pct ? row.accuracy_3pct + '%' : '—' }}</template>
          </el-table-column>
          <el-table-column prop="score" label="综合得分" width="100" align="right">
            <template #default="{ row }">
              <span style="color: #3DD0B6; font-weight: 600;">{{ row.score?.toFixed(4) }}</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </template>

    <template v-if="evalData">
      <div class="card-box">
        <h3 class="section-title">行业维度模型表现</h3>
        <el-table :data="evalData.industry_summary" stripe border v-if="evalData.industry_summary?.length">
          <el-table-column prop="industry" label="行业" width="120" />
          <el-table-column prop="count" label="股票数" width="80" align="center" />
          <el-table-column prop="avg_r2" label="平均R²" width="100" align="right">
            <template #default="{ row }">{{ row.avg_r2?.toFixed(4) ?? '—' }}</template>
          </el-table-column>
          <el-table-column prop="avg_mape" label="平均MAPE%" width="110" align="right">
            <template #default="{ row }">{{ row.avg_mape?.toFixed(4) ?? '—' }}</template>
          </el-table-column>
          <el-table-column prop="avg_sharpe" label="平均夏普" width="100" align="right">
            <template #default="{ row }">{{ row.avg_sharpe?.toFixed(4) ?? '—' }}</template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="暂无多股票评估数据" />
      </div>

      <div v-if="evalData.stocks?.length > 1" class="card-box">
        <h3 class="section-title">风险-收益散点图</h3>
        <div ref="scatterRef" style="width: 100%; height: 400px;"></div>
      </div>
    </template>

    <div v-if="!portfolio && !loading" class="card-box">
      <el-empty description="选择参数加载组合分析" />
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, nextTick, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { analysisApi } from '@/api/index.js'

const loading = ref(false)
const form = reactive({ model_type: 'BiLSTM', predict_steps: 1, top_n: 5 })
const portfolio = ref(null)
const evalData = ref(null)
const scatterRef = ref(null)
let chart = null

const loadAll = async () => {
  loading.value = true
  try {
    const [portRes, evalRes] = await Promise.all([
      analysisApi.getPortfolioSuggest(form),
      analysisApi.getMultiStockEval({ model_type: form.model_type }),
    ])
    portfolio.value = portRes.data
    evalData.value = evalRes.data

    await nextTick()
    renderScatter()
  } finally {
    loading.value = false
  }
}

const renderScatter = () => {
  if (!scatterRef.value || !evalData.value?.stocks?.length) return
  if (chart) chart.dispose()
  chart = echarts.init(scatterRef.value)

  const data = evalData.value.stocks
    .filter(s => s.mape != null && s.sharpe_ratio != null)
    .map(s => ({
      value: [s.mape, s.sharpe_ratio],
      name: `${s.name || s.ts_code}`,
      symbolSize: Math.max(8, (s.r2 || 0) * 40),
    }))

  chart.setOption({
    tooltip: {
      formatter: (p) => `${p.data.name}<br/>MAPE: ${p.data.value[0]}%<br/>夏普: ${p.data.value[1]}`,
    },
    grid: { left: '10%', right: '6%', bottom: '12%', top: '8%' },
    xAxis: { type: 'value', name: 'MAPE% (风险 →)', nameLocation: 'middle', nameGap: 30 },
    yAxis: { type: 'value', name: '夏普比率 (收益 →)', nameLocation: 'middle', nameGap: 40 },
    series: [{
      type: 'scatter',
      data,
      itemStyle: { color: '#3DD0B6' },
      label: { show: data.length <= 20, formatter: (p) => p.data.name, position: 'top', fontSize: 10 },
    }],
  })
}

onUnmounted(() => { chart?.dispose() })
</script>

<style scoped>
.section-title { font-size: 15px; font-weight: 600; color: #1D2129; margin-bottom: 12px; }
</style>
