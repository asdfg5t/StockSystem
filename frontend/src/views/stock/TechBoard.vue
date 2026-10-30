<template>
  <div class="page-container">
    <div class="page-header">
      <h2>技术分析看板 — {{ tsCode }}</h2>
      <el-button @click="$router.back()">返回</el-button>
    </div>

    <div class="card-box">
      <h3 class="sec-title">K线 + 成交量</h3>
      <div ref="klineRef" style="width: 100%; height: 500px;"></div>
    </div>

    <div class="tech-grid">
      <div class="card-box"><h3 class="sec-title">MACD</h3><div ref="macdRef" style="width: 100%; height: 260px;"></div></div>
      <div class="card-box"><h3 class="sec-title">KDJ</h3><div ref="kdjRef" style="width: 100%; height: 260px;"></div></div>
      <div class="card-box"><h3 class="sec-title">RSI</h3><div ref="rsiRef" style="width: 100%; height: 260px;"></div></div>
      <div class="card-box"><h3 class="sec-title">BOLL</h3><div ref="bollRef" style="width: 100%; height: 260px;"></div></div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import * as echarts from 'echarts'
import { stockApi } from '@/api/index.js'

const route = useRoute()
const tsCode = computed(() => route.params.tsCode || '000001.SZ')

const klineRef = ref(null)
const macdRef = ref(null)
const kdjRef = ref(null)
const rsiRef = ref(null)
const bollRef = ref(null)
const charts = []

const initChart = (el) => { const c = echarts.init(el); charts.push(c); return c }

onMounted(async () => {
  const res = await stockApi.getKline(tsCode.value)
  const data = res.data || []
  if (!data.length) return

  const dates = data.map(d => d.date)
  const ohlc = data.map(d => [d.open, d.close, d.low, d.high])
  const vols = data.map(d => d.vol)
  const closes = data.map(d => d.close)
  const highs = data.map(d => d.high)
  const lows = data.map(d => d.low)

  const ma = (arr, n) => arr.map((_, i) => i < n - 1 ? null : arr.slice(i - n + 1, i + 1).reduce((a, b) => a + b, 0) / n)
  const ema = (arr, n) => { const r = []; const k = 2 / (n + 1); arr.forEach((v, i) => { r.push(i === 0 ? v : v * k + r[i - 1] * (1 - k)) }); return r }

  const ma5 = ma(closes, 5), ma20 = ma(closes, 20)
  const ema12 = ema(closes, 12), ema26 = ema(closes, 26)
  const dif = ema12.map((v, i) => v - ema26[i])
  const dea = ema(dif, 9)
  const macdHist = dif.map((v, i) => (v - dea[i]) * 2)

  const rsv = closes.map((c, i) => {
    if (i < 8) return 50
    const lo = Math.min(...lows.slice(i - 8, i + 1))
    const hi = Math.max(...highs.slice(i - 8, i + 1))
    return hi === lo ? 50 : (c - lo) / (hi - lo) * 100
  })
  const kv = ema(rsv, 3), dv = ema(kv, 3), jv = kv.map((k, i) => 3 * k - 2 * dv[i])

  const delta = closes.map((v, i) => i === 0 ? 0 : v - closes[i - 1])
  const rsiCalc = (period) => {
    const gains = delta.map(d => d > 0 ? d : 0)
    const losses = delta.map(d => d < 0 ? -d : 0)
    const avgG = ma(gains, period)
    const avgL = ma(losses, period)
    return avgG.map((g, i) => g == null || avgL[i] == null ? null : 100 - 100 / (1 + g / (avgL[i] + 1e-8)))
  }
  const rsi6 = rsiCalc(6), rsi12 = rsiCalc(12)

  const bollMid = ma(closes, 20)
  const bollStd = closes.map((_, i) => {
    if (i < 19) return null
    const slice = closes.slice(i - 19, i + 1)
    const m = slice.reduce((a, b) => a + b, 0) / 20
    return Math.sqrt(slice.reduce((a, b) => a + (b - m) ** 2, 0) / 20)
  })
  const bollUp = bollMid.map((m, i) => m == null ? null : m + 2 * (bollStd[i] || 0))
  const bollLo = bollMid.map((m, i) => m == null ? null : m - 2 * (bollStd[i] || 0))

  const dataZoom = [{ type: 'inside', start: 70, end: 100 }, { type: 'slider', start: 70, end: 100 }]
  const grid = { left: '6%', right: '3%', top: '8%', bottom: '18%', containLabel: true }

  if (klineRef.value) {
    const c = initChart(klineRef.value)
    c.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
      legend: { data: ['K线', 'MA5', 'MA20'], top: 0 },
      grid: [{ left: '6%', right: '3%', top: '8%', bottom: '34%' }, { left: '6%', right: '3%', top: '72%', bottom: '8%' }],
      xAxis: [
        { type: 'category', data: dates, gridIndex: 0, axisLabel: { show: false } },
        { type: 'category', data: dates, gridIndex: 1 },
      ],
      yAxis: [{ type: 'value', scale: true, gridIndex: 0 }, { type: 'value', gridIndex: 1, splitNumber: 3 }],
      dataZoom: [{ type: 'inside', xAxisIndex: [0, 1], start: 70, end: 100 }, { type: 'slider', xAxisIndex: [0, 1], start: 70, end: 100 }],
      series: [
        { name: 'K线', type: 'candlestick', data: ohlc, xAxisIndex: 0, yAxisIndex: 0, itemStyle: { color: '#F5222D', color0: '#52C41A', borderColor: '#F5222D', borderColor0: '#52C41A' } },
        { name: 'MA5', type: 'line', data: ma5, xAxisIndex: 0, yAxisIndex: 0, smooth: true, lineStyle: { width: 1 }, symbol: 'none' },
        { name: 'MA20', type: 'line', data: ma20, xAxisIndex: 0, yAxisIndex: 0, smooth: true, lineStyle: { width: 1 }, symbol: 'none' },
        { name: '成交量', type: 'bar', data: vols, xAxisIndex: 1, yAxisIndex: 1, itemStyle: { color: (p) => ohlc[p.dataIndex][1] >= ohlc[p.dataIndex][0] ? '#F5222D' : '#52C41A' } },
      ],
    })
  }

  const miniOpt = (title, series) => ({ tooltip: { trigger: 'axis' }, legend: { top: 0 }, grid, xAxis: { type: 'category', data: dates }, yAxis: { type: 'value', scale: true }, dataZoom, series })

  if (macdRef.value) {
    const c = initChart(macdRef.value)
    c.setOption(miniOpt('MACD', [
      { name: 'DIF', type: 'line', data: dif.map(v => v.toFixed(3)), symbol: 'none', lineStyle: { width: 1 } },
      { name: 'DEA', type: 'line', data: dea.map(v => v.toFixed(3)), symbol: 'none', lineStyle: { width: 1 } },
      { name: 'MACD', type: 'bar', data: macdHist.map(v => v.toFixed(3)), itemStyle: { color: (p) => p.data >= 0 ? '#F5222D' : '#52C41A' } },
    ]))
  }
  if (kdjRef.value) {
    const c = initChart(kdjRef.value)
    c.setOption(miniOpt('KDJ', [
      { name: 'K', type: 'line', data: kv.map(v => v.toFixed(2)), symbol: 'none', lineStyle: { width: 1 } },
      { name: 'D', type: 'line', data: dv.map(v => v.toFixed(2)), symbol: 'none', lineStyle: { width: 1 } },
      { name: 'J', type: 'line', data: jv.map(v => v.toFixed(2)), symbol: 'none', lineStyle: { width: 1 } },
    ]))
  }
  if (rsiRef.value) {
    const c = initChart(rsiRef.value)
    c.setOption(miniOpt('RSI', [
      { name: 'RSI6', type: 'line', data: rsi6, symbol: 'none', lineStyle: { width: 1 } },
      { name: 'RSI12', type: 'line', data: rsi12, symbol: 'none', lineStyle: { width: 1 } },
    ]))
  }
  if (bollRef.value) {
    const c = initChart(bollRef.value)
    c.setOption(miniOpt('BOLL', [
      { name: '上轨', type: 'line', data: bollUp, symbol: 'none', lineStyle: { width: 1, type: 'dashed' } },
      { name: '中轨', type: 'line', data: bollMid, symbol: 'none', lineStyle: { width: 1 } },
      { name: '下轨', type: 'line', data: bollLo, symbol: 'none', lineStyle: { width: 1, type: 'dashed' } },
      { name: '收盘', type: 'line', data: closes, symbol: 'none', lineStyle: { width: 1.5 } },
    ]))
  }
})

onUnmounted(() => charts.forEach(c => c?.dispose()))
</script>

<style scoped>
.sec-title { font-size: 15px; font-weight: 600; color: #1D2129; margin-bottom: 8px; }
.tech-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
</style>
