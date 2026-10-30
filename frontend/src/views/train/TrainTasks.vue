<template>
  <div class="page-container">
    <div class="page-header">
      <h2>模型训练</h2>
      <el-button type="primary" @click="showCreate = true">新建训练任务</el-button>
    </div>

    <div class="card-box">
      <el-table :data="tasks" stripe>
        <el-table-column prop="task_name" label="任务名称" min-width="140" />
        <el-table-column prop="model_type" label="模型类型" width="120" />
        <el-table-column prop="ts_code" label="股票代码" width="110" />
        <el-table-column prop="predict_steps" label="预测步长" width="90" align="center" />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="训练进度" width="140">
          <template #default="{ row }">
            {{ row.current_epoch || 0 }} / {{ row.epochs }}
          </template>
        </el-table-column>
        <el-table-column label="最优验证损失" width="130">
          <template #default="{ row }">
            {{ row.best_val_loss != null ? row.best_val_loss.toFixed(6) : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" :disabled="row.status === 'running'" @click="startTask(row.id)">启动</el-button>
            <el-button size="small" @click="router.push('/train/metrics/' + row.id)">指标</el-button>
            <el-button size="small" type="danger" :disabled="row.status === 'running'" @click="deleteTask(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        style="margin-top: 16px; justify-content: flex-end;"
        @current-change="loadTasks"
      />
    </div>

    <el-dialog v-model="showCreate" title="新建训练任务" width="560px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="任务名称">
          <el-input v-model="form.task_name" placeholder="请输入任务名称" />
        </el-form-item>
        <el-form-item label="模型类型">
          <el-select v-model="form.model_type" style="width: 100%;">
            <el-option label="TFT" value="TFT" />
            <el-option label="Transformer" value="Transformer" />
            <el-option label="BiLSTM" value="BiLSTM" />
          </el-select>
        </el-form-item>
        <el-form-item label="股票代码">
          <el-input v-model="form.ts_code" placeholder="如 000001.SZ" />
        </el-form-item>
        <el-form-item label="预测步长">
          <el-select v-model="form.predict_steps" style="width: 100%;">
            <el-option :label="'1天'" :value="1" />
            <el-option :label="'3天'" :value="3" />
            <el-option :label="'5天'" :value="5" />
          </el-select>
        </el-form-item>
        <el-form-item label="回看窗口">
          <el-input-number v-model="form.lookback_window" :min="20" :max="200" />
        </el-form-item>
        <el-form-item label="训练轮数">
          <el-input-number v-model="form.epochs" :min="10" :max="500" />
        </el-form-item>
        <el-form-item label="批次大小">
          <el-input-number v-model="form.batch_size" :min="8" :max="256" />
        </el-form-item>
        <el-form-item label="学习率">
          <el-input-number v-model="form.learning_rate" :min="0.00001" :max="0.1" :step="0.0001" :precision="6" />
        </el-form-item>
        <el-form-item label="训练区间">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            value-format="YYYYMMDD"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            style="width: 100%;"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" @click="createTask">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { trainApi } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'

const router = useRouter()
const tasks = ref([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const showCreate = ref(false)
const dateRange = ref(null)

const form = reactive({
  task_name: '',
  model_type: 'TFT',
  ts_code: '',
  predict_steps: 1,
  lookback_window: 60,
  epochs: 100,
  batch_size: 32,
  learning_rate: 0.001,
})

const statusType = (s) => ({ completed: 'success', running: 'warning', pending: 'info', failed: 'danger' }[s] || 'info')
const statusText = (s) => ({ completed: '已完成', running: '运行中', pending: '待执行', failed: '失败' }[s] || s)

const loadTasks = async () => {
  const res = await trainApi.getTasks({ page: page.value, page_size: pageSize.value })
  tasks.value = res.data
  total.value = res.total
}

const createTask = async () => {
  const data = { ...form }
  if (dateRange.value) {
    data.train_start_date = dateRange.value[0]
    data.train_end_date = dateRange.value[1]
  }
  await trainApi.create(data)
  ElMessage.success('训练任务已创建')
  showCreate.value = false
  loadTasks()
}

const startTask = async (id) => {
  await trainApi.start(id)
  ElMessage.success('训练任务已启动')
  loadTasks()
}

const deleteTask = async (id) => {
  await ElMessageBox.confirm('确认删除该训练任务？', '提示', { type: 'warning' })
  await trainApi.deleteTask(id)
  ElMessage.success('删除成功')
  loadTasks()
}

onMounted(loadTasks)
</script>
