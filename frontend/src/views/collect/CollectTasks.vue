<template>
  <div class="page-container">
    <div class="page-header">
      <h2>数据采集任务</h2>
      <el-button type="primary" @click="openCreateDialog">新建采集任务</el-button>
    </div>

    <div class="card-box">
      <el-table v-loading="loading" :data="tasks" stripe style="width: 100%">
        <el-table-column prop="task_name" label="任务名称" min-width="140" />
        <el-table-column prop="task_type" label="任务类型" width="120">
          <template #default="{ row }">
            {{ row.task_type === 'stock_basic' ? '股票基础' : row.task_type === 'daily' ? '日线行情' : row.task_type }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="进度" min-width="160">
          <template #default="{ row }">
            <el-progress :percentage="Math.min(100, Math.round(Number(row.progress) || 0))" :stroke-width="10" />
          </template>
        </el-table-column>
        <el-table-column label="统计" width="160">
          <template #default="{ row }">
            <span>总 {{ row.total_count ?? 0 }} / 成功 {{ row.success_count ?? 0 }} / 失败 {{ row.fail_count ?? 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" min-width="160" show-overflow-tooltip />
        <el-table-column prop="started_at" label="开始时间" min-width="160" show-overflow-tooltip />
        <el-table-column prop="finished_at" label="结束时间" min-width="160" show-overflow-tooltip />
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" :disabled="row.status === 'running'" @click="handleStart(row)">启动</el-button>
            <el-button link type="primary" @click="openLogs(row)">日志</el-button>
            <el-button link type="danger" :disabled="row.status === 'running'" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div style="margin-top: 16px; display: flex; justify-content: flex-end">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          background
          @size-change="loadTasks"
          @current-change="loadTasks"
        />
      </div>
    </div>

    <el-dialog v-model="createVisible" title="新建采集任务" width="520px" destroy-on-close @closed="resetCreateForm">
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-width="100px">
        <el-form-item label="任务名称" prop="task_name">
          <el-input v-model="createForm.task_name" placeholder="请输入任务名称" clearable />
        </el-form-item>
        <el-form-item label="任务类型" prop="task_type">
          <el-select v-model="createForm.task_type" placeholder="请选择" style="width: 100%">
            <el-option label="股票基础" value="stock_basic" />
            <el-option label="日线行情" value="daily" />
          </el-select>
        </el-form-item>
        <el-form-item label="股票代码">
          <el-input v-model="createForm.ts_code" placeholder="可选，如 000001.SZ" clearable />
        </el-form-item>
        <el-form-item label="开始日期">
          <el-date-picker
            v-model="createForm.start_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="可选"
            style="width: 100%"
            clearable
          />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-date-picker
            v-model="createForm.end_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="可选"
            style="width: 100%"
            clearable
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="createSubmitting" @click="submitCreate">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="logsVisible" :title="`采集日志 — ${currentTaskName}`" width="900px" destroy-on-close>
      <el-table v-loading="logsLoading" :data="logs" stripe max-height="420">
        <el-table-column prop="ts_code" label="股票代码" width="120" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="logStatusTagType(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="message" label="消息" min-width="200" show-overflow-tooltip />
        <el-table-column prop="retry_count" label="重试" width="70" />
        <el-table-column prop="created_at" label="时间" width="170" />
      </el-table>
      <div style="margin-top: 12px; display: flex; justify-content: flex-end">
        <el-pagination
          v-model:current-page="logPagination.page"
          v-model:page-size="logPagination.pageSize"
          :total="logPagination.total"
          :page-sizes="[20, 50, 100, 200]"
          layout="total, sizes, prev, pager, next"
          background
          @size-change="loadLogs"
          @current-change="loadLogs"
        />
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, reactive, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { collectApi } from '@/api/index.js'

const loading = ref(false)
const tasks = ref([])
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })

const createVisible = ref(false)
const createSubmitting = ref(false)
const createFormRef = ref(null)
const createForm = reactive({
  task_name: '',
  task_type: '',
  ts_code: '',
  start_date: '',
  end_date: '',
})

const createRules = {
  task_name: [{ required: true, message: '请输入任务名称', trigger: 'blur' }],
  task_type: [{ required: true, message: '请选择任务类型', trigger: 'change' }],
}

const logsVisible = ref(false)
const logsLoading = ref(false)
const logs = ref([])
const currentTaskId = ref(null)
const currentTaskName = ref('')
const logPagination = reactive({ page: 1, pageSize: 50, total: 0 })

let pollTimer = null

function statusLabel(status) {
  const map = { pending: '待执行', running: '运行中', completed: '已完成', failed: '失败' }
  return map[status] || status
}

function statusTagType(status) {
  if (status === 'completed') return 'success'
  if (status === 'running') return 'warning'
  if (status === 'pending') return 'info'
  if (status === 'failed') return 'danger'
  return 'info'
}

function logStatusTagType(status) {
  const s = String(status || '').toLowerCase()
  if (s.includes('success') || s === 'ok') return 'success'
  if (s.includes('fail') || s.includes('error')) return 'danger'
  return 'info'
}

async function loadTasks() {
  loading.value = true
  try {
    const res = await collectApi.getTasks({
      page: pagination.page,
      page_size: pagination.pageSize,
    })
    tasks.value = res.data || []
    pagination.total = res.total ?? 0
    setupPolling()
  } finally {
    loading.value = false
  }
}

function setupPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  const hasRunning = tasks.value.some((t) => t.status === 'running')
  if (hasRunning) {
    pollTimer = setInterval(() => {
      loadTasksQuiet()
    }, 4000)
  }
}

async function loadTasksQuiet() {
  try {
    const res = await collectApi.getTasks({
      page: pagination.page,
      page_size: pagination.pageSize,
    })
    tasks.value = res.data || []
    pagination.total = res.total ?? 0
    if (!tasks.value.some((t) => t.status === 'running') && pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  } catch {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }
}

function openCreateDialog() {
  resetCreateForm()
  createVisible.value = true
}

function resetCreateForm() {
  createForm.task_name = ''
  createForm.task_type = ''
  createForm.ts_code = ''
  createForm.start_date = ''
  createForm.end_date = ''
  createFormRef.value?.clearValidate?.()
}

async function submitCreate() {
  await createFormRef.value?.validate?.()
  createSubmitting.value = true
  try {
    const payload = {
      task_name: createForm.task_name,
      task_type: createForm.task_type,
      ts_code: createForm.ts_code || undefined,
      start_date: createForm.start_date || undefined,
      end_date: createForm.end_date || undefined,
    }
    await collectApi.create(payload)
    ElMessage.success('创建成功')
    createVisible.value = false
    await loadTasks()
  } finally {
    createSubmitting.value = false
  }
}

async function handleStart(row) {
  await collectApi.start(row.id)
  ElMessage.success('任务已启动')
  await loadTasks()
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确定删除任务「${row.task_name}」？`, '提示', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  })
  await collectApi.deleteTask(row.id)
  ElMessage.success('已删除')
  await loadTasks()
}

function openLogs(row) {
  currentTaskId.value = row.id
  currentTaskName.value = row.task_name
  logPagination.page = 1
  logsVisible.value = true
  loadLogs()
}

async function loadLogs() {
  if (!currentTaskId.value) return
  logsLoading.value = true
  try {
    const res = await collectApi.getLogs(currentTaskId.value, {
      page: logPagination.page,
      page_size: logPagination.pageSize,
    })
    logs.value = res.data || []
    logPagination.total = res.total ?? 0
  } finally {
    logsLoading.value = false
  }
}

onMounted(() => {
  loadTasks()
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>
