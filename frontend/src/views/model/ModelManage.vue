<template>
  <div class="page-container">
    <div class="page-header">
      <h2>模型管理</h2>
      <el-button type="primary" @click="loadConfigs">刷新配置</el-button>
    </div>

    <div class="card-box">
      <h3 class="section-title">模型配置</h3>
      <el-table v-loading="configsLoading" :data="configs" stripe border style="width: 100%">
        <el-table-column prop="model_name" label="模型名称" min-width="120" />
        <el-table-column prop="model_type" label="模型类型" width="130" />
        <el-table-column prop="params" label="参数" min-width="200" show-overflow-tooltip />
        <el-table-column prop="description" label="描述" min-width="160" show-overflow-tooltip />
        <el-table-column prop="is_active" label="启用" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="openEdit(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="card-box">
      <div class="files-toolbar">
        <h3 class="section-title">模型文件</h3>
        <el-select
          v-model="filesModelType"
          placeholder="按模型类型筛选"
          clearable
          style="width: 200px"
          @change="onFilesFilterChange"
        >
          <el-option label="全部" value="" />
          <el-option label="TFT" value="TFT" />
          <el-option label="Transformer" value="Transformer" />
          <el-option label="BiLSTM" value="BiLSTM" />
        </el-select>
      </div>
      <el-table v-loading="filesLoading" :data="fileItems" stripe border style="width: 100%">
        <el-table-column prop="model_type" label="模型类型" width="120" />
        <el-table-column prop="ts_code" label="股票代码" width="150">
          <template #default="{ row }">
            <el-tag v-if="row.ts_code === 'smart_universal'" type="success" size="small" effect="plain">智能通用</el-tag>
            <el-tag v-else-if="row.ts_code === 'universal'" type="warning" size="small" effect="plain">通用模型</el-tag>
            <span v-else>{{ row.ts_code }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="predict_steps" label="预测步长" width="100" align="center" />
        <el-table-column prop="is_best" label="最优" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_best ? 'success' : 'info'" size="small">
              {{ row.is_best ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="file_size" label="文件大小" width="110">
          <template #default="{ row }">{{ formatFileSize(row.file_size) }}</template>
        </el-table-column>
        <el-table-column prop="metrics" label="指标" min-width="180" show-overflow-tooltip />
        <el-table-column prop="created_at" label="创建时间" min-width="170" />
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button type="danger" link @click="onDeleteFile(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="filesPage"
          v-model:page-size="filesPageSize"
          :total="filesTotal"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          background
          @current-change="loadFiles"
          @size-change="onFilesPageSizeChange"
        />
      </div>
    </div>

    <el-dialog v-model="editVisible" title="编辑模型配置" width="560px" destroy-on-close @closed="resetEditForm">
      <el-form ref="editFormRef" :model="editForm" label-width="100px">
        <el-form-item label="模型名称">
          <el-input v-model="editForm.model_name" />
        </el-form-item>
        <el-form-item label="参数(JSON)">
          <el-input v-model="editForm.params" type="textarea" :rows="6" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="editForm.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="editForm.is_active" :active-value="1" :inactive-value="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="editSubmitting" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { modelApi } from '@/api/index.js'

const configs = ref([])
const configsLoading = ref(false)
const filesLoading = ref(false)
const fileItems = ref([])
const filesTotal = ref(0)
const filesPage = ref(1)
const filesPageSize = ref(20)
const filesModelType = ref('')
const editVisible = ref(false)
const editSubmitting = ref(false)
const editFormRef = ref(null)
const editForm = reactive({
  id: null,
  model_name: '',
  params: '',
  description: '',
  is_active: 1,
})

const formatFileSize = (bytes) => {
  if (bytes == null || bytes === '') return '-'
  const n = Number(bytes)
  if (Number.isNaN(n)) return '-'
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(2)} MB`
}

const loadConfigs = async () => {
  configsLoading.value = true
  try {
    const res = await modelApi.getConfigs()
    configs.value = res.data || []
  } finally {
    configsLoading.value = false
  }
}

const loadFiles = async () => {
  filesLoading.value = true
  try {
    const params = {
      page: filesPage.value,
      page_size: filesPageSize.value,
    }
    if (filesModelType.value) params.model_type = filesModelType.value
    const res = await modelApi.getFiles(params)
    const payload = res.data || {}
    fileItems.value = payload.items || []
    filesTotal.value = payload.total || 0
  } finally {
    filesLoading.value = false
  }
}

const onFilesFilterChange = () => {
  filesPage.value = 1
  loadFiles()
}

const onFilesPageSizeChange = () => {
  filesPage.value = 1
  loadFiles()
}

const openEdit = (row) => {
  editForm.id = row.id
  editForm.model_name = row.model_name || ''
  editForm.params = row.params || ''
  editForm.description = row.description || ''
  editForm.is_active = row.is_active ? 1 : 0
  editVisible.value = true
}

const resetEditForm = () => {
  editForm.id = null
  editForm.model_name = ''
  editForm.params = ''
  editForm.description = ''
  editForm.is_active = 1
}

const submitEdit = async () => {
  if (!editForm.id) return
  editSubmitting.value = true
  try {
    await modelApi.updateConfig(editForm.id, {
      model_name: editForm.model_name,
      params: editForm.params,
      description: editForm.description,
      is_active: editForm.is_active,
    })
    ElMessage.success('保存成功')
    editVisible.value = false
    await loadConfigs()
  } finally {
    editSubmitting.value = false
  }
}

const onDeleteFile = (row) => {
  ElMessageBox.confirm('确定删除该模型文件？', '提示', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  })
    .then(async () => {
      await modelApi.deleteFile(row.id)
      ElMessage.success('已删除')
      await loadFiles()
    })
    .catch(() => {})
}

onMounted(() => {
  loadConfigs()
  loadFiles()
})
</script>

<style lang="scss" scoped>
.section-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 16px;
  color: #303133;
}

.files-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;

  .section-title {
    margin-bottom: 0;
  }
}

.pagination-wrap {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
