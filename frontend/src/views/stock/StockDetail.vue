<template>
  <div class="page-container">
    <div class="page-header">
      <h2>个股详情</h2>
      <el-button @click="router.back()">返回</el-button>
    </div>

    <div class="card-box" v-loading="detailLoading">
      <template v-if="basic">
        <el-descriptions title="基本信息" :column="3" border>
          <el-descriptions-item label="股票代码">{{ basic.ts_code }}</el-descriptions-item>
          <el-descriptions-item label="名称">{{ basic.name }}</el-descriptions-item>
          <el-descriptions-item label="简称">{{ basic.symbol }}</el-descriptions-item>
          <el-descriptions-item label="行业">{{ basic.industry || '—' }}</el-descriptions-item>
          <el-descriptions-item label="地区">{{ basic.area || '—' }}</el-descriptions-item>
          <el-descriptions-item label="市场">{{ basic.market || '—' }}</el-descriptions-item>
          <el-descriptions-item label="上市日期">{{ basic.list_date || '—' }}</el-descriptions-item>
          <el-descriptions-item label="上市状态">{{ basic.list_status || '—' }}</el-descriptions-item>
          <el-descriptions-item label="日线条数">{{ dailyTotalAll }}</el-descriptions-item>
        </el-descriptions>
      </template>
      <el-empty v-else-if="!detailLoading" description="未找到股票" />
    </div>

    <div class="card-box">
      <div class="filter-row">
        <span class="filter-label">日期范围</span>
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
          clearable
          @change="onRangeChange"
        />
      </div>
    </div>

    <div class="card-box" v-loading="klineLoading">
      <div class="chart-title">K 线图</div>
      <KlineChart v-if="klineData.length" :data="klineData" height="420px" />
      <el-empty v-else description="暂无 K 线数据" :image-size="80" />
    </div>

    <div class="card-box" v-loading="klineLoading">
      <div class="chart-title">历史收盘价</div>
      <LineChart
        v-if="lineXData.length"
        title=""
        :x-data="lineXData"
        :series="lineSeries"
        height="360px"
      />
      <el-empty v-else description="暂无收盘价数据" :image-size="80" />
    </div>

    <div class="card-box" v-loading="tableLoading">
      <div class="chart-title">日线数据</div>
      <el-table :data="dailyRows" stripe style="width: 100%">
        <el-table-column prop="trade_date" label="交易日期" width="120" />
        <el-table-column prop="open" label="开盘" width="100">
          <template #default="{ row }">{{ formatNum(row.open) }}</template>
        </el-table-column>
        <el-table-column prop="high" label="最高" width="100">
          <template #default="{ row }">{{ formatNum(row.high) }}</template>
        </el-table-column>
        <el-table-column prop="low" label="最低" width="100">
          <template #default="{ row }">{{ formatNum(row.low) }}</template>
        </el-table-column>
        <el-table-column prop="close" label="收盘" width="100">
          <template #default="{ row }">{{ formatNum(row.close) }}</template>
        </el-table-column>
        <el-table-column prop="pct_chg" label="涨跌幅%" width="100">
          <template #default="{ row }">{{ formatNum(row.pct_chg) }}</template>
        </el-table-column>
        <el-table-column prop="vol" label="成交量" min-width="110">
          <template #default="{ row }">{{ formatNum(row.vol) }}</template>
        </el-table-column>
        <el-table-column prop="amount" label="成交额" min-width="110">
          <template #default="{ row }">{{ formatNum(row.amount) }}</template>
        </el-table-column>
      </el-table>
      <div class="pager-wrap">
        <el-pagination
          v-model:current-page="dailyPager.page"
          v-model:page-size="dailyPager.page_size"
          :total="dailyTotal"
          :page-sizes="[20, 50, 100, 200]"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @size-change="loadDaily"
          @current-change="loadDaily"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, reactive, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { stockApi } from '@/api/index.js'
import KlineChart from '@/components/charts/KlineChart.vue'
import LineChart from '@/components/charts/LineChart.vue'

const route = useRoute()
const router = useRouter()

const detailLoading = ref(false)
const klineLoading = ref(false)
const tableLoading = ref(false)

const basic = ref(null)
const dailyTotalAll = ref(0)

const dateRange = ref(null)

const klineData = ref([])

const lineXData = computed(() => klineData.value.map((d) => d.date))
const lineSeries = computed(() => [
  { name: '收盘价', data: klineData.value.map((d) => d.close) },
])

const dailyRows = ref([])
const dailyTotal = ref(0)
const dailyPager = reactive({
  page: 1,
  page_size: 50,
})

const tsCode = () => route.params.tsCode

const rangeParams = () => {
  if (!dateRange.value || dateRange.value.length !== 2) {
    return { start_date: '', end_date: '' }
  }
  return { start_date: dateRange.value[0], end_date: dateRange.value[1] }
}

const formatNum = (n) => (n != null && n !== '' ? Number(n).toFixed(4) : '—')

const loadDetail = async () => {
  const code = tsCode()
  if (!code) return
  detailLoading.value = true
  basic.value = null
  dailyTotalAll.value = 0
  try {
    const res = await stockApi.getDetail(code)
    const d = res.data
    if (d && d.basic) {
      basic.value = d.basic
      dailyTotalAll.value = d.daily_count ?? 0
    }
  } catch {
    basic.value = null
  } finally {
    detailLoading.value = false
  }
}

const loadKline = async () => {
  const code = tsCode()
  if (!code) return
  klineLoading.value = true
  try {
    const p = rangeParams()
    const res = await stockApi.getKline(code, p)
    klineData.value = Array.isArray(res.data) ? res.data : []
  } finally {
    klineLoading.value = false
  }
}

const loadDaily = async () => {
  const code = tsCode()
  if (!code) return
  tableLoading.value = true
  try {
    const p = {
      ...rangeParams(),
      page: dailyPager.page,
      page_size: dailyPager.page_size,
    }
    const res = await stockApi.getDaily(code, p)
    dailyRows.value = res.data || []
    dailyTotal.value = res.total ?? 0
  } finally {
    tableLoading.value = false
  }
}

const refreshChartsAndTable = async () => {
  dailyPager.page = 1
  await loadKline()
  await loadDaily()
}

const onRangeChange = () => {
  refreshChartsAndTable()
}

const initPage = async () => {
  await loadDetail()
  await refreshChartsAndTable()
}

onMounted(initPage)

watch(
  () => route.params.tsCode,
  async (code, prev) => {
    if (!code || code === prev) return
    dateRange.value = null
    dailyPager.page = 1
    await loadDetail()
    await refreshChartsAndTable()
  }
)
</script>

<style scoped lang="scss">
.filter-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.filter-label {
  font-size: 14px;
  color: #606266;
  white-space: nowrap;
}

.chart-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 16px;
}

.pager-wrap {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
