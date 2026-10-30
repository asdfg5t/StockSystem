<template>
  <div class="page-container">
    <div class="page-header">
      <h2>回测模拟交易</h2>
    </div>

    <div class="card-box">
      <el-form :inline="true" @submit.prevent="runBacktest">
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
        <el-form-item label="初始资金">
          <el-input-number v-model="form.initial_capital" :min="10000" :step="10000" style="width: 150px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="runBacktest">开始回测</el-button>
        </el-form-item>
      </el-form>
    </div>

    <template v-if="result">
      <div class="stats-row">
        <div v-for="(item, idx) in statCards" :key="idx" class="stat-card">
          <div class="stat-value" :class="item.color">{{ item.value }}</div>
          <div class="stat-label">{{ item.label }}</div>
        </div>
      </div>

      <div class="card-box">
        <h3 class="section-title">累计收益曲线</h3>
        <LineChart :x-data="result.dates" :series="equitySeries" height="380px" :colors="['#3DD0B6', '#86909C']" />
      </div>

      <div class="card-box">
        <h3 class="section-title">回撤曲线</h3>
        <LineChart :x-data="result.dates" :series="drawdownSeries" height="260px" :colors="['#F5222D']" />
      </div>

      <div class="card-box">
        <h3 class="section-title">交易记录</h3>
        <el-table :data="result.trades" stripe border max-height="400">
          <el-table-column prop="date" label="日期" width="120" />
          <el-table-column prop="action" label="方向" width="80">
            <template #default="{ row }">
              <el-tag :type="row.action === 'buy' ? 'success' : 'danger'" size="small">
                {{ row.action === 'buy' ? '买入' : '卖出' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="price" label="价格" width="100" />
          <el-table-column prop="shares" label="数量(股)" width="100" />
          <el-table-column prop="pnl" label="盈亏" width="120">
            <template #default="{ row }">
              <span :style="{ color: row.pnl > 0 ? '#52C41A' : row.pnl < 0 ? '#F5222D' : '' }">
                {{ row.pnl }}
              </span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </template>
    <div v-else-if="!loading" class="card-box">
      <el-empty description="请选择参数并点击开始回测" />
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { backtestApi } from '@/api/index.js'
import LineChart from '@/components/charts/LineChart.vue'

const loading = ref(false)
const result = ref(null)
const form = reactive({
  ts_code: '000001.SZ',
  model_type: 'BiLSTM',
  predict_steps: 1,
  initial_capital: 100000,
})

const statCards = computed(() => {
  if (!result.value) return []
  const s = result.value.stats
  return [
    { label: '最终市值', value: `¥${s.final_value?.toLocaleString()}`, color: '' },
    { label: '总收益率', value: `${s.total_return}%`, color: s.total_return > 0 ? 'green' : 'red' },
    { label: '基准收益', value: `${s.benchmark_return}%`, color: '' },
    { label: '年化收益', value: `${s.annual_return}%`, color: s.annual_return > 0 ? 'green' : 'red' },
    { label: '夏普比率', value: s.sharpe_ratio, color: '' },
    { label: '最大回撤', value: `${s.max_drawdown}%`, color: 'red' },
    { label: '交易次数', value: s.total_trades, color: '' },
    { label: '胜率', value: `${s.win_rate}%`, color: '' },
  ]
})

const equitySeries = computed(() => {
  if (!result.value) return []
  return [
    { name: '策略资金', data: result.value.equity_curve },
    { name: '基准(持有)', data: result.value.benchmark_curve },
  ]
})

const drawdownSeries = computed(() => {
  if (!result.value) return []
  return [{ name: '回撤%', data: result.value.drawdown_curve }]
})

const runBacktest = async () => {
  loading.value = true
  try {
    const res = await backtestApi.run(form)
    result.value = res.data
  } catch (e) {
    result.value = null
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}
.stat-card {
  background: #fff;
  border-radius: 10px;
  padding: 18px;
  text-align: center;
  border: 1px solid #E8ECF0;
}
.stat-value { font-size: 22px; font-weight: 700; color: #1D2129; }
.stat-value.green { color: #52C41A; }
.stat-value.red { color: #F5222D; }
.stat-label { font-size: 12px; color: #86909C; margin-top: 4px; }
.section-title { font-size: 15px; font-weight: 600; color: #1D2129; margin-bottom: 12px; }
</style>
