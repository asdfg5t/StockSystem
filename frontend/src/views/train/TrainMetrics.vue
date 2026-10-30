<template>
  <div class="page-container">
    <div v-loading="taskLoading" class="card-box task-info-card">
      <template v-if="task">
        <h2 class="task-title">任务信息</h2>
        <el-descriptions :column="3" border>
          <el-descriptions-item label="任务名称">{{ task.task_name }}</el-descriptions-item>
          <el-descriptions-item label="模型类型">{{ task.model_type }}</el-descriptions-item>
          <el-descriptions-item label="股票代码">{{ task.ts_code }}</el-descriptions-item>
          <el-descriptions-item label="预测步长">{{ task.predict_steps }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusTagType(task.status)" size="small">{{ statusText(task.status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="进度">{{ task.current_epoch ?? 0 }} / {{ task.epochs ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="最优验证损失">
            {{ task.best_val_loss != null ? Number(task.best_val_loss).toFixed(6) : '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="训练起止" :span="2">
            {{ task.train_start_date || '-' }} ~ {{ task.train_end_date || '-' }}
          </el-descriptions-item>
        </el-descriptions>
      </template>
      <el-empty v-else-if="!taskLoading" description="未找到任务" />
    </div>

    <template v-if="metrics.length">
      <div class="card-box">
        <LineChart
          title="训练与验证损失对比"
          :x-data="epochLabels"
          :series="lossCompareSeries"
          :colors="chartColors"
          height="360px"
        />
      </div>
      <div class="card-box">
        <LineChart title="MAE 对比" :x-data="epochLabels" :series="maeSeries" :colors="chartColors" height="360px" />
      </div>
      <div class="card-box">
        <LineChart title="RMSE 对比" :x-data="epochLabels" :series="rmseSeries" :colors="chartColors" height="360px" />
      </div>
      <div class="card-box">
        <LineChart title="学习率" :x-data="epochLabels" :series="lrSeries" :colors="['#E6A23C']" height="300px" />
      </div>
    </template>
    <div v-else-if="!metricsLoading && task" class="card-box">
      <el-empty description="暂无指标数据" />
    </div>

    <div v-loading="metricsLoading" class="card-box">
      <h3 class="section-title">指标明细</h3>
      <el-table :data="metrics" stripe border style="width: 100%" max-height="480">
        <el-table-column prop="epoch" label="轮次" width="80" align="center" fixed="left" />
        <el-table-column prop="train_loss" label="训练Loss" align="right" width="120">
          <template #default="{ row }">{{ formatNum(row.train_loss) }}</template>
        </el-table-column>
        <el-table-column prop="val_loss" label="验证Loss" align="right" width="120">
          <template #default="{ row }">{{ formatNum(row.val_loss) }}</template>
        </el-table-column>
        <el-table-column prop="train_mae" label="训练MAE" align="right" width="120">
          <template #default="{ row }">{{ formatNum(row.train_mae) }}</template>
        </el-table-column>
        <el-table-column prop="val_mae" label="验证MAE" align="right" width="120">
          <template #default="{ row }">{{ formatNum(row.val_mae) }}</template>
        </el-table-column>
        <el-table-column prop="train_rmse" label="训练RMSE" align="right" width="120">
          <template #default="{ row }">{{ formatNum(row.train_rmse) }}</template>
        </el-table-column>
        <el-table-column prop="val_rmse" label="验证RMSE" align="right" width="120">
          <template #default="{ row }">{{ formatNum(row.val_rmse) }}</template>
        </el-table-column>
        <el-table-column prop="learning_rate" label="学习率" align="right" width="130">
          <template #default="{ row }">{{ formatNum(row.learning_rate) }}</template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, reactive, computed } from 'vue'
import { useRoute } from 'vue-router'
import LineChart from '@/components/charts/LineChart.vue'
import { trainApi } from '@/api/index.js'

const route = useRoute()
const chartColors = reactive(['#3DD0B6', '#409EFF', '#E6A23C', '#F56C6C'])
const task = ref(null)
const taskLoading = ref(false)
const metrics = ref([])
const metricsLoading = ref(false)

const taskId = computed(() => Number(route.params.taskId))

const statusText = (s) => {
  const map = {
    pending: '待执行',
    running: '训练中',
    completed: '已完成',
    failed: '失败',
  }
  return map[s] || s || '-'
}

const statusTagType = (s) => {
  const map = {
    pending: 'info',
    running: 'warning',
    completed: 'success',
    failed: 'danger',
  }
  return map[s] || 'info'
}

const formatNum = (v) => (v != null && v !== '' ? Number(v).toFixed(6) : '-')

const epochLabels = computed(() => metrics.value.map((m) => String(m.epoch)))

const lossCompareSeries = computed(() => [
  { name: '训练损失', data: metrics.value.map((m) => m.train_loss) },
  { name: '验证损失', data: metrics.value.map((m) => m.val_loss) },
])

const maeSeries = computed(() => [
  { name: '训练MAE', data: metrics.value.map((m) => m.train_mae) },
  { name: '验证MAE', data: metrics.value.map((m) => m.val_mae) },
])

const rmseSeries = computed(() => [
  { name: '训练RMSE', data: metrics.value.map((m) => m.train_rmse) },
  { name: '验证RMSE', data: metrics.value.map((m) => m.val_rmse) },
])

const lrSeries = computed(() => [
  { name: '学习率', data: metrics.value.map((m) => m.learning_rate) },
])

const loadTask = async () => {
  if (!taskId.value || Number.isNaN(taskId.value)) return
  taskLoading.value = true
  try {
    const res = await trainApi.getTask(taskId.value)
    task.value = res.data || null
  } catch {
    task.value = null
  } finally {
    taskLoading.value = false
  }
}

const loadMetrics = async () => {
  if (!taskId.value || Number.isNaN(taskId.value)) return
  metricsLoading.value = true
  try {
    const res = await trainApi.getMetrics(taskId.value)
    metrics.value = res.data || []
  } finally {
    metricsLoading.value = false
  }
}

onMounted(() => {
  loadTask()
  loadMetrics()
})
</script>

<style lang="scss" scoped>
.task-info-card {
  .task-title {
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 16px;
    color: #303133;
  }
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 16px;
  color: #303133;
}
</style>
