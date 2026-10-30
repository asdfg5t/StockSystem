<template>
  <div ref="chartRef" :style="{ width: '100%', height: height }"></div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  title: { type: String, default: '' },
  xData: { type: Array, default: () => [] },
  series: { type: Array, default: () => [] },
  height: { type: String, default: '400px' },
  colors: { type: Array, default: () => ['#3DD0B6', '#36CFC9', '#FAAD14', '#F5222D'] },
  showLegend: { type: Boolean, default: true },
  showLabel: { type: Boolean, default: false },
  labelFormatter: { type: Function, default: null },
  xAxisName: { type: String, default: '' },
  yAxisName: { type: String, default: '' },
  symbols: { type: Array, default: () => [] },
})

const chartRef = ref(null)
let chart = null
let resizeObserver = null

const renderChart = () => {
  if (!chart) return

  const seriesData = props.series.map((s, i) => ({
    name: s.name,
    type: 'line',
    data: s.data,
    smooth: true,
    symbol: props.symbols[i] || 'circle',
    symbolSize: props.showLabel ? 8 : 4,
    lineStyle: { width: 2 },
    itemStyle: { color: props.colors[i % props.colors.length] },
    label: props.showLabel ? {
      show: true,
      position: 'top',
      fontSize: 11,
      color: '#1D2129',
      formatter: props.labelFormatter
        ? (p) => props.labelFormatter(p.value)
        : (p) => p.value,
    } : { show: false },
    ...s.extra,
  }))

  chart.setOption({
    title: props.title ? { text: props.title, left: 'center', textStyle: { fontSize: 14 } } : undefined,
    tooltip: { trigger: 'axis' },
    legend: props.showLegend ? { data: props.series.map(s => s.name), top: props.title ? 30 : 10 } : undefined,
    grid: { left: '6%', right: '4%', bottom: props.xAxisName ? '14%' : '12%', top: props.title ? '18%' : '14%', containLabel: true },
    xAxis: { type: 'category', data: props.xData, boundaryGap: false, name: props.xAxisName, nameLocation: 'middle', nameGap: 30 },
    yAxis: { type: 'value', scale: true, name: props.yAxisName },
    dataZoom: props.xData.length > 60 ? [
      { type: 'inside', start: 60, end: 100 },
      { type: 'slider', start: 60, end: 100 },
    ] : undefined,
    series: seriesData,
  }, true)
}

const handleResize = () => chart?.resize()

onMounted(() => {
  chart = echarts.init(chartRef.value)
  renderChart()

  nextTick(() => setTimeout(handleResize, 300))

  resizeObserver = new ResizeObserver(handleResize)
  resizeObserver.observe(chartRef.value)
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  resizeObserver?.disconnect()
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
})

watch(() => [props.xData, props.series], () => {
  renderChart()
  nextTick(() => setTimeout(handleResize, 100))
}, { deep: true })
</script>
