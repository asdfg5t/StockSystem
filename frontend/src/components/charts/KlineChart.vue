<template>
  <div ref="chartRef" :style="{ width: '100%', height: height }"></div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  data: { type: Array, default: () => [] },
  height: { type: String, default: '500px' },
})

const chartRef = ref(null)
let chart = null

const renderChart = () => {
  if (!chart || !props.data.length) return

  const dates = props.data.map(d => d.date)
  const ohlc = props.data.map(d => [d.open, d.close, d.low, d.high])
  const volumes = props.data.map(d => d.vol)

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
    },
    legend: { data: ['K线', '成交量'], top: 10 },
    grid: [
      { left: '8%', right: '4%', top: '12%', height: '55%' },
      { left: '8%', right: '4%', top: '74%', height: '18%' },
    ],
    xAxis: [
      { type: 'category', data: dates, gridIndex: 0, boundaryGap: true },
      { type: 'category', data: dates, gridIndex: 1, boundaryGap: true },
    ],
    yAxis: [
      { scale: true, gridIndex: 0 },
      { scale: true, gridIndex: 1, splitNumber: 3 },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 70, end: 100 },
      { type: 'slider', xAxisIndex: [0, 1], start: 70, end: 100, top: '95%' },
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: ohlc,
        xAxisIndex: 0,
        yAxisIndex: 0,
        itemStyle: {
          color: '#F56C6C',
          color0: '#3DD0B6',
          borderColor: '#F56C6C',
          borderColor0: '#3DD0B6',
        },
      },
      {
        name: '成交量',
        type: 'bar',
        data: volumes,
        xAxisIndex: 1,
        yAxisIndex: 1,
        itemStyle: {
          color: (params) => {
            const idx = params.dataIndex
            if (idx > 0 && props.data[idx].close >= props.data[idx].open) {
              return '#F56C6C'
            }
            return '#3DD0B6'
          },
        },
      },
    ],
  })
}

onMounted(() => {
  chart = echarts.init(chartRef.value)
  renderChart()
  window.addEventListener('resize', () => chart?.resize())
})

onUnmounted(() => {
  chart?.dispose()
  window.removeEventListener('resize', () => chart?.resize())
})

watch(() => props.data, renderChart, { deep: true })
</script>
