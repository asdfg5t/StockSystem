<template>
  <div class="page-container">
    <div class="page-header">
      <h2>指定日期快速预测</h2>
      <span class="page-sub">
        选择股票、模型、起始基准日和预测步长（1/3/5 天）→ 立刻看到每一天的预测值，并通过 Tushare 自动获取已公布的实际收盘价进行对比。
      </span>
    </div>

    <div class="card-box">
      <el-form :inline="true" :model="form" label-width="90px" class="quick-form">
        <el-form-item label="股票代码">
          <el-input v-model="form.ts_code" placeholder="如 000001.SZ" style="width: 170px" clearable />
        </el-form-item>
        <el-form-item label="模型">
          <el-select v-model="form.model_type" style="width: 150px">
            <el-option label="TFT（推荐）" value="TFT" />
            <el-option label="Transformer" value="Transformer" />
            <el-option label="BiLSTM" value="BiLSTM" />
          </el-select>
        </el-form-item>
        <el-form-item label="起始基准日">
          <el-date-picker
            v-model="form.base_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="从哪天开始预测（可选，默认最新）"
            style="width: 220px"
          />
        </el-form-item>
        <el-form-item label="预测步长">
          <el-radio-group v-model="form.predict_steps">
            <el-radio-button :value="1">1 天</el-radio-button>
            <el-radio-button :value="3">3 天</el-radio-button>
            <el-radio-button :value="5">5 天</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="handlePredict">立即预测</el-button>
          <el-button @click="resetForm">重置</el-button>
        </el-form-item>
      </el-form>
      <div class="form-tip">
        <el-icon><InfoFilled /></el-icon>
        将从 <b>起始基准日</b>（不含当天）起，预测连续 <b>{{ form.predict_steps }} 个交易日</b> 的收盘价；
        如果对应交易日的行情已公布，系统会自动通过 Tushare 拉取实际值进行对比。
      </div>
    </div>

    <el-row v-if="result" :gutter="16" class="result-row">
      <el-col :xs="12" :sm="6">
        <div class="result-card">
          <div class="result-label">基准日 / 收盘</div>
          <div class="result-value">
            <template v-if="result.base_close != null">{{ formatPrice(result.base_close) }}</template>
            <span v-else class="muted">—</span>
          </div>
          <div class="result-sub">{{ result.base_date }}</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6">
        <div class="result-card primary">
          <div class="result-label">使用模型</div>
          <div class="result-value model-name">{{ result.model_type }}</div>
          <div class="result-sub">step{{ result.model_step }} · {{ result.is_universal_model ? '通用模型' : '单股模型' }}</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6">
        <div class="result-card">
          <div class="result-label">已验证 / 总步数</div>
          <div class="result-value">
            <span class="text-green">{{ result.verified_count }}</span>
            <span class="muted" style="font-size: 18px"> / {{ result.steps_total }}</span>
          </div>
          <div class="result-sub">已通过 Tushare 校验</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6">
        <div class="result-card">
          <div class="result-label">平均误差</div>
          <div class="result-value" :class="avgErrorClass">
            <template v-if="avgErrorPct != null">
              {{ avgErrorPct > 0 ? '+' : '' }}{{ avgErrorPct.toFixed(2) }}%
            </template>
            <span v-else class="muted">待验证</span>
          </div>
          <div class="result-sub">已验证步长平均偏差</div>
        </div>
      </el-col>
    </el-row>

    <div v-if="result" class="card-box">
      <div class="section-title">
        <span>预测明细（共 {{ result.steps_total }} 个交易日）</span>
        <el-tag size="small" type="info">基准 {{ result.base_date }}</el-tag>
        <el-tag v-if="result.actual_source === 'tushare'" size="small" type="success">
          含 Tushare 实时数据
        </el-tag>
      </div>
      <el-table :data="result.all_steps" stripe border style="width: 100%">
        <el-table-column prop="step_index" label="第几日" width="80" align="center">
          <template #default="{ row }">
            <el-tag size="small" round>+{{ row.step_index }}d</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="target_date" label="对应交易日" width="140" align="center" />
        <el-table-column label="预测收盘价" width="140" align="right">
          <template #default="{ row }">
            <span class="price-text">{{ formatPrice(row.predicted_close) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="预测涨跌" width="120" align="right">
          <template #default="{ row }">
            <span v-if="row.change_pct != null" :class="row.change_pct >= 0 ? 'text-red' : 'text-green'">
              {{ row.change_pct > 0 ? '+' : '' }}{{ row.change_pct.toFixed(2) }}%
            </span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="实际收盘价" width="160" align="right">
          <template #default="{ row }">
            <template v-if="row.actual_close != null">
              <span class="actual-price">{{ formatPrice(row.actual_close) }}</span>
              <el-tag
                size="small"
                :type="row.actual_source === 'tushare' ? 'success' : 'info'"
                effect="plain"
                round
                style="margin-left: 6px"
              >
                {{ row.actual_source === 'tushare' ? 'Tushare' : '本地' }}
              </el-tag>
            </template>
            <span v-else class="muted">待公布</span>
          </template>
        </el-table-column>
        <el-table-column label="误差" width="120" align="right">
          <template #default="{ row }">
            <span v-if="row.error != null" :class="row.error > 0 ? 'text-red' : 'text-green'">
              {{ row.error > 0 ? '+' : '' }}{{ formatPrice(row.error) }}
            </span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="误差%" min-width="120" align="right">
          <template #default="{ row }">
            <el-tag
              v-if="row.error_pct != null"
              :type="errorPctTag(row.error_pct)"
              size="small"
              round
            >
              {{ row.error_pct > 0 ? '+' : '' }}{{ row.error_pct.toFixed(2) }}%
            </el-tag>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-empty v-if="!result && !loading" description="填写参数后点击「立即预测」开始" />
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { InfoFilled } from '@element-plus/icons-vue'
import { predictApi } from '@/api/index.js'

const loading = ref(false)
const result = ref(null)

const form = reactive({
  ts_code: '',
  model_type: 'TFT',
  base_date: '',
  predict_steps: 3,
})

const formatPrice = (v) => (v == null || isNaN(v) ? '—' : Number(v).toFixed(2))

const errorPctTag = (p) => {
  const a = Math.abs(p)
  if (a <= 1) return 'success'
  if (a <= 3) return 'warning'
  return 'danger'
}

const avgErrorPct = computed(() => {
  if (!result.value || !result.value.all_steps) return null
  const verified = result.value.all_steps.filter((s) => s.error_pct != null)
  if (!verified.length) return null
  return verified.reduce((sum, s) => sum + s.error_pct, 0) / verified.length
})

const avgErrorClass = computed(() => {
  if (avgErrorPct.value == null) return ''
  const a = Math.abs(avgErrorPct.value)
  if (a <= 1) return 'text-green'
  if (a <= 3) return 'text-orange'
  return 'text-red'
})

const handlePredict = async () => {
  if (!form.ts_code.trim()) {
    ElMessage.warning('请输入股票代码')
    return
  }
  loading.value = true
  result.value = null
  try {
    const payload = {
      ts_code: form.ts_code.trim(),
      model_type: form.model_type,
      predict_steps: form.predict_steps,
    }
    if (form.base_date) payload.base_date = form.base_date
    const res = await predictApi.quickPredict(payload)
    if (res.code === 200) {
      result.value = res.data
      const v = res.data.verified_count
      const total = res.data.steps_total
      if (v === total) {
        ElMessage.success(`预测完成，全部 ${total} 个交易日均已校验`)
      } else if (v > 0) {
        ElMessage.success(`预测完成，已校验 ${v}/${total}（其余等待行情公布）`)
      } else {
        ElMessage.info('预测完成，全部交易日尚未公布行情')
      }
    } else {
      ElMessage.error(res.message || '预测失败')
    }
  } finally {
    loading.value = false
  }
}

const resetForm = () => {
  form.ts_code = ''
  form.model_type = 'TFT'
  form.base_date = ''
  form.predict_steps = 3
  result.value = null
}
</script>

<style scoped>
.page-sub {
  display: block;
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  line-height: 1.6;
}

.quick-form {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}

.form-tip {
  margin-top: 6px;
  padding: 8px 12px;
  background: #F4F8FB;
  border-left: 3px solid #3DD0B6;
  border-radius: 4px;
  font-size: 12px;
  color: #5A6474;
  display: flex;
  align-items: center;
  gap: 6px;
}

.form-tip b {
  color: #2BBDA5;
}

.result-row {
  margin: 16px 0;
}

.result-card {
  background: #fff;
  padding: 18px 20px;
  border-radius: 12px;
  border: 1px solid #ECEEF1;
  height: 100%;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.03);
  transition: all 0.25s;
}

.result-card.primary {
  background: linear-gradient(135deg, #3DD0B6 0%, #2BB39F 100%);
  border: none;
}

.result-card.primary .result-label,
.result-card.primary .result-value,
.result-card.primary .result-sub {
  color: #fff;
}

.result-label {
  font-size: 13px;
  color: #86909C;
  margin-bottom: 8px;
}

.result-value {
  font-size: 26px;
  font-weight: 700;
  color: #1D2129;
  letter-spacing: 0.5px;
  line-height: 1.3;
}

.result-value.model-name {
  font-size: 22px;
  letter-spacing: 1px;
}

.result-sub {
  margin-top: 6px;
  font-size: 12px;
  color: #909399;
}

.muted {
  color: #C0C4CC;
  font-weight: 400;
  font-size: 14px;
}

.text-red {
  color: #F56C6C !important;
}

.text-green {
  color: #3DD0B6 !important;
}

.text-orange {
  color: #E6A23C !important;
}

.section-title {
  font-weight: 600;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.price-text {
  font-weight: 600;
  color: #2BBDA5;
}

.actual-price {
  font-weight: 600;
  color: #1D2129;
}
</style>
