<template>
  <div class="page-container">
    <div v-loading="loading">
      <el-row :gutter="16" class="stat-row">
        <el-col :xs="24" :sm="12" :md="6">
          <div class="stat-card stock-card" @click="checkStockHealth">
            <div class="stat-value">{{ stats.stock_count }}</div>
            <div class="stat-label">股票数量</div>
            <div v-if="health.unique_ts_code" class="stat-sub">
              唯一 {{ health.unique_ts_code }} · 在市 {{ health.by_status?.L ?? '—' }}
              <span v-if="health.has_duplicate_ts_code" class="text-danger">⚠ 发现重复</span>
              <span v-else class="text-ok">✓ 无重复</span>
            </div>
            <div v-else class="stat-sub muted">点击体检</div>
          </div>
        </el-col>
        <el-col :xs="24" :sm="12" :md="6">
          <div class="stat-card">
            <div class="stat-value">{{ stats.daily_data_count }}</div>
            <div class="stat-label">日线数据量</div>
          </div>
        </el-col>
        <el-col :xs="24" :sm="12" :md="6">
          <div class="stat-card">
            <div class="stat-value">{{ stats.model_count }}</div>
            <div class="stat-label">模型数量</div>
          </div>
        </el-col>
        <el-col :xs="24" :sm="12" :md="6">
          <div class="stat-card">
            <div class="stat-value">{{ stats.predict_count }}</div>
            <div class="stat-label">预测记录数</div>
          </div>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <el-col :xs="24" :md="12">
          <div class="card-box">
            <div class="card-title">最新采集任务</div>
            <template v-if="stats.latest_collect_task">
              <el-descriptions :column="1" size="small" border>
                <el-descriptions-item label="任务名称">{{ stats.latest_collect_task.task_name }}</el-descriptions-item>
                <el-descriptions-item label="任务类型">{{ stats.latest_collect_task.task_type }}</el-descriptions-item>
                <el-descriptions-item label="状态">
                  <el-tag :type="statusTagType(stats.latest_collect_task.status)" size="small">
                    {{ statusLabel(stats.latest_collect_task.status) }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="进度">{{ stats.latest_collect_task.progress }}%</el-descriptions-item>
                <el-descriptions-item label="成功/总数">
                  {{ stats.latest_collect_task.success_count }} / {{ stats.latest_collect_task.total_count }}
                </el-descriptions-item>
                <el-descriptions-item label="创建时间">{{ stats.latest_collect_task.created_at || '—' }}</el-descriptions-item>
              </el-descriptions>
            </template>
            <el-empty v-else description="暂无采集任务" :image-size="80" />
          </div>
        </el-col>
        <el-col :xs="24" :md="12">
          <div class="card-box">
            <div class="card-title">最新训练任务</div>
            <template v-if="stats.latest_train_task">
              <el-descriptions :column="1" size="small" border>
                <el-descriptions-item label="任务名称">{{ stats.latest_train_task.task_name }}</el-descriptions-item>
                <el-descriptions-item label="模型类型">{{ stats.latest_train_task.model_type }}</el-descriptions-item>
                <el-descriptions-item label="股票代码">{{ stats.latest_train_task.ts_code }}</el-descriptions-item>
                <el-descriptions-item label="状态">
                  <el-tag :type="statusTagType(stats.latest_train_task.status)" size="small">
                    {{ statusLabel(stats.latest_train_task.status) }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="轮次">
                  {{ stats.latest_train_task.current_epoch }} / {{ stats.latest_train_task.epochs }}
                </el-descriptions-item>
                <el-descriptions-item label="最佳验证损失">
                  {{ stats.latest_train_task.best_val_loss != null ? stats.latest_train_task.best_val_loss : '—' }}
                </el-descriptions-item>
                <el-descriptions-item label="创建时间">{{ stats.latest_train_task.created_at || '—' }}</el-descriptions-item>
              </el-descriptions>
            </template>
            <el-empty v-else description="暂无训练任务" :image-size="80" />
          </div>
        </el-col>
      </el-row>

      <div class="card-box">
        <div class="card-title">最近预测</div>
        <el-table :data="stats.recent_predictions" stripe style="width: 100%">
          <el-table-column prop="ts_code" label="股票代码" width="110" />
          <el-table-column prop="model_type" label="模型类型" width="100" />
          <el-table-column prop="predict_steps" label="预测步数" width="90" />
          <el-table-column prop="base_date" label="基准日" width="110" />
          <el-table-column prop="target_date" label="目标日" width="110" />
          <el-table-column prop="predicted_close" label="预测收盘" width="100">
            <template #default="{ row }">{{ formatNum(row.predicted_close) }}</template>
          </el-table-column>
          <el-table-column prop="actual_close" label="实际收盘" width="100">
            <template #default="{ row }">{{ row.actual_close != null ? formatNum(row.actual_close) : '—' }}</template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" min-width="160" />
        </el-table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { dashboardApi } from '@/api/index.js'

const loading = ref(false)
const stats = reactive({
  stock_count: 0,
  daily_data_count: 0,
  model_count: 0,
  predict_count: 0,
  latest_collect_task: null,
  latest_train_task: null,
  recent_predictions: [],
})

const health = reactive({
  unique_ts_code: 0,
  total_rows: 0,
  has_duplicate_ts_code: false,
  by_status: null,
  by_market: null,
  duplicate_by_name_total: 0,
  duplicate_by_name: [],
})

const statusMap = {
  pending: '待处理',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
}

const statusLabel = (s) => statusMap[s] || s || '—'

const statusTagType = (s) => {
  if (s === 'completed') return 'success'
  if (s === 'failed') return 'danger'
  if (s === 'running') return 'warning'
  return 'info'
}

const formatNum = (n) => (n != null && n !== '' ? Number(n).toFixed(4) : '—')

const load = async () => {
  loading.value = true
  try {
    const res = await dashboardApi.getStats()
    const d = res.data || {}
    stats.stock_count = d.stock_count ?? 0
    stats.daily_data_count = d.daily_data_count ?? 0
    stats.model_count = d.model_count ?? 0
    stats.predict_count = d.predict_count ?? 0
    stats.latest_collect_task = d.latest_collect_task ?? null
    stats.latest_train_task = d.latest_train_task ?? null
    stats.recent_predictions = d.recent_predictions ?? []
  } finally {
    loading.value = false
  }
  loadHealthSilent()
}

const loadHealthSilent = async () => {
  try {
    const res = await dashboardApi.stockHealth()
    Object.assign(health, res.data || {})
  } catch (e) {
    // 静默失败：体检接口失败不影响主面板
  }
}

const checkStockHealth = async () => {
  try {
    const res = await dashboardApi.stockHealth()
    const d = res.data || {}
    Object.assign(health, d)
    const dupNameLines = (d.duplicate_by_name || [])
      .slice(0, 10)
      .map(x => `${x.name} × ${x.count}`)
      .join('，')
    const html = `
      <div style="line-height:1.9;font-size:13px;">
        <div><b>总记录数：</b>${d.total_rows}</div>
        <div><b>唯一 ts_code：</b>${d.unique_ts_code} ${d.has_duplicate_ts_code ? '⚠ 检测到重复！' : '✓ 无重复'}</div>
        <div><b>唯一 symbol：</b>${d.unique_symbol}</div>
        <div><b>按上市状态：</b>${Object.entries(d.by_status || {}).map(([k, v]) => `${k}=${v}`).join('，') || '—'}</div>
        <div><b>按交易所：</b>${Object.entries(d.by_market || {}).map(([k, v]) => `${k}=${v}`).join('，') || '—'}</div>
        <div><b>同名不同代码：</b>${d.duplicate_by_name_total} 组${dupNameLines ? '<br><span style="color:#909399;font-size:12px;">' + dupNameLines + (d.duplicate_by_name_total > 10 ? '…' : '') + '</span>' : ''}</div>
      </div>`
    ElMessageBox.alert(html, '股票表健康体检', {
      dangerouslyUseHTMLString: true,
      confirmButtonText: '知道了',
    })
  } catch (e) {
    ElMessage.error('体检失败：' + (e.message || e))
  }
}

onMounted(load)
</script>

<style scoped lang="scss">
.stat-row {
  margin-bottom: 8px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #ebeef5;
}

.stock-card {
  cursor: pointer;
  position: relative;
}

.stock-card::after {
  content: '点击体检 ›';
  position: absolute;
  top: 12px;
  right: 14px;
  font-size: 11px;
  color: #C0C4CC;
  opacity: 0;
  transition: opacity 0.2s;
}

.stock-card:hover::after {
  opacity: 1;
}

.stat-sub {
  margin-top: 6px;
  font-size: 11px;
  color: #909399;
  line-height: 1.5;

  &.muted {
    color: #C0C4CC;
  }
}

.text-ok {
  color: #3DD0B6;
  font-weight: 600;
  margin-left: 6px;
}

.text-danger {
  color: #F56C6C;
  font-weight: 600;
  margin-left: 6px;
}
</style>
