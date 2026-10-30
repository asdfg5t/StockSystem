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
  colors: { type: Array, default: () => ['#3DD0B6', '#409EFF', '#E6A23C', '#F56C6C'] },
  showLabel: { type: Boolean, default: false },
  labelFormatter: { type: Function, default: null },
  yAxisName: { type: String, default: '' },
  xAxisName: { type: String, default: '' },
  showLegend: { type: Boolean, default: true },
})

const chartRef = ref(null)
let chart = null
let resizeObserver = null

const renderChart = () => {
  if (!chart) return

  const seriesData = props.series.map((s, i) => ({
    name: s.name,
    type: 'bar',
    data: s.data,
    barMaxWidth: 40,
    itemStyle: {
      color: props.colors[i % props.colors.length],
      borderRadius: [4, 4, 0, 0],
    },
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
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: props.showLegend ? { data: props.series.map(s => s.name), top: props.title ? 30 : 10 } : undefined,
    grid: { left: '6%', right: '4%', bottom: props.xAxisName ? '12%' : '8%', top: props.title ? '18%' : '14%', containLabel: true },
    xAxis: { type: 'category', data: props.xData, name: props.xAxisName, nameLocation: 'middle', nameGap: 30 },
    yAxis: { type: 'value', name: props.yAxisName, scale: true },
    series: seriesData,
  }, true)
}

const handleResize = () => chart?.resize()

onMounted(() => {
  chart = echarts.init(chartRef.value)
  renderChart()
  nextTick(() => setTimeout(handleResize, 200))
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
