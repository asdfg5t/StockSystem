<template>
  <div class="page-container">
    <div class="page-header">
      <h2>股票列表</h2>
    </div>

    <div class="card-box search-bar">
      <el-form :inline="true" @submit.prevent="handleSearch">
        <el-form-item label="关键词">
          <el-input
            v-model="query.keyword"
            placeholder="代码 / 名称 / 拼音"
            clearable
            style="width: 220px"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item label="行业">
          <el-select
            v-model="query.industry"
            placeholder="全部行业"
            clearable
            filterable
            style="width: 200px"
          >
            <el-option
              v-for="item in industries"
              :key="item"
              :label="item"
              :value="item"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">搜索</el-button>
        </el-form-item>
      </el-form>
    </div>

    <div class="card-box" v-loading="loading">
      <el-table :data="list" stripe style="width: 100%">
        <el-table-column prop="ts_code" label="股票代码" width="120" />
        <el-table-column prop="name" label="名称" min-width="120" />
        <el-table-column prop="industry" label="行业" min-width="100" />
        <el-table-column prop="area" label="地区" width="100" />
        <el-table-column prop="market" label="市场" width="90" />
        <el-table-column prop="list_date" label="上市日期" width="120" />
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="goDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pager-wrap">
        <el-pagination
          v-model:current-page="query.page"
          v-model:page-size="query.page_size"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @size-change="loadList"
          @current-change="loadList"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { stockApi } from '@/api/index.js'

const router = useRouter()
const loading = ref(false)
const list = ref([])
const total = ref(0)
const industries = ref([])

const query = reactive({
  page: 1,
  page_size: 20,
  keyword: '',
  industry: '',
})

const loadIndustries = async () => {
  const res = await stockApi.getIndustries()
  industries.value = Array.isArray(res.data) ? res.data : []
}

const loadList = async () => {
  loading.value = true
  try {
    const res = await stockApi.getList({
      page: query.page,
      page_size: query.page_size,
      keyword: query.keyword || undefined,
      industry: query.industry || undefined,
    })
    list.value = res.data || []
    total.value = res.total ?? 0
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  query.page = 1
  loadList()
}

const goDetail = (row) => {
  router.push({ name: 'StockDetail', params: { tsCode: row.ts_code } })
}

onMounted(async () => {
  await loadIndustries()
  await loadList()
})
</script>

<style scoped lang="scss">
.search-bar {
  margin-bottom: 16px;
}

.pager-wrap {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
