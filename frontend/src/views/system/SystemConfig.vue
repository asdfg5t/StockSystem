<template>
  <div class="page-container">
    <div class="page-header">
      <h2>系统配置</h2>
      <el-button type="primary" @click="loadConfigs">刷新</el-button>
    </div>
    <div class="card-box">
      <el-table v-loading="loading" :data="tableData" border stripe style="width: 100%">
        <el-table-column prop="config_key" label="配置键" width="200" />
        <el-table-column prop="config_value" label="配置值" min-width="220">
          <template #default="{ row }">
            <el-input
              v-if="editingKey === row.config_key"
              v-model="editValue"
              type="textarea"
              :rows="2"
            />
            <span v-else>{{ row.config_value }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="config_type" label="类型" width="120" />
        <el-table-column prop="description" label="说明" min-width="200" show-overflow-tooltip />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <template v-if="editingKey === row.config_key">
              <el-button type="primary" link :loading="saving" @click="saveRow(row)">保存</el-button>
              <el-button link @click="cancelEdit">取消</el-button>
            </template>
            <el-button v-else type="primary" link @click="startEdit(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { systemApi } from '@/api/index.js'

const loading = ref(false)
const saving = ref(false)
const tableData = ref([])
const editingKey = ref('')
const editValue = ref('')

const loadConfigs = async () => {
  loading.value = true
  try {
    const res = await systemApi.getConfigs()
    tableData.value = res.data || []
  } finally {
    loading.value = false
  }
}

const startEdit = (row) => {
  editingKey.value = row.config_key
  editValue.value = row.config_value ?? ''
}

const cancelEdit = () => {
  editingKey.value = ''
  editValue.value = ''
}

const saveRow = async (row) => {
  saving.value = true
  try {
    await systemApi.updateConfig(row.config_key, { config_value: editValue.value })
    ElMessage.success('保存成功')
    row.config_value = editValue.value
    cancelEdit()
    loadConfigs()
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadConfigs()
})
</script>
