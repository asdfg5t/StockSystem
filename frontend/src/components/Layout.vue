<template>
  <el-container class="layout-container">
    <el-aside :width="isCollapse ? '64px' : '240px'" class="sidebar">
      <div class="logo-area">
        <div class="logo-icon">
          <el-icon :size="22"><TrendCharts /></el-icon>
        </div>
        <transition name="fade">
          <div v-show="!isCollapse" class="logo-info">
            <span class="logo-title">股票预测系统</span>
            <span class="logo-sub">Stock Prediction</span>
          </div>
        </transition>
      </div>

      <el-menu
        :default-active="currentRoute"
        :collapse="isCollapse"
        :collapse-transition="false"
        router
        class="sidebar-menu"
      >
        <el-menu-item index="/dashboard">
          <el-icon><Odometer /></el-icon>
          <template #title>总览面板</template>
        </el-menu-item>

        <div v-show="!isCollapse" class="menu-group-label">数据</div>
        <el-menu-item index="/stock/list">
          <el-icon><List /></el-icon>
          <template #title>股票列表</template>
        </el-menu-item>
        <el-menu-item index="/collect/tasks">
          <el-icon><Download /></el-icon>
          <template #title>数据采集</template>
        </el-menu-item>
        <el-menu-item index="/feature/manage">
          <el-icon><Operation /></el-icon>
          <template #title>特征工程</template>
        </el-menu-item>

        <div v-show="!isCollapse" class="menu-group-label">模型</div>
        <el-menu-item index="/model/manage">
          <el-icon><Files /></el-icon>
          <template #title>模型管理</template>
        </el-menu-item>
        <el-menu-item index="/train/tasks">
          <el-icon><Cpu /></el-icon>
          <template #title>模型训练</template>
        </el-menu-item>
        <el-menu-item index="/train/compare">
          <el-icon><Histogram /></el-icon>
          <template #title>训练对比</template>
        </el-menu-item>
        <el-menu-item index="/evaluate/results">
          <el-icon><DataAnalysis /></el-icon>
          <template #title>评估结果</template>
        </el-menu-item>
        <el-menu-item index="/evaluate/compare">
          <el-icon><ScaleToOriginal /></el-icon>
          <template #title>模型对比</template>
        </el-menu-item>

        <div v-show="!isCollapse" class="menu-group-label">预测</div>
        <el-menu-item index="/predict/quick">
          <el-icon><Calendar /></el-icon>
          <template #title>指定日期预测</template>
        </el-menu-item>
        <el-menu-item index="/predict/results">
          <el-icon><Tickets /></el-icon>
          <template #title>预测结果</template>
        </el-menu-item>
        <el-menu-item index="/backtest">
          <el-icon><TrendCharts /></el-icon>
          <template #title>回测模拟</template>
        </el-menu-item>

        <div v-show="!isCollapse" class="menu-group-label">分析</div>
        <el-menu-item index="/analysis/features">
          <el-icon><PieChart /></el-icon>
          <template #title>特征重要性</template>
        </el-menu-item>
        <el-menu-item index="/analysis/errors">
          <el-icon><WarnTriangleFilled /></el-icon>
          <template #title>误差分布</template>
        </el-menu-item>
        <el-menu-item index="/analysis/whatif">
          <el-icon><MagicStick /></el-icon>
          <template #title>情景分析</template>
        </el-menu-item>
        <el-menu-item index="/analysis/portfolio">
          <el-icon><Briefcase /></el-icon>
          <template #title>组合分析</template>
        </el-menu-item>

        <div v-show="!isCollapse" class="menu-group-label">系统</div>
        <el-menu-item index="/system/config">
          <el-icon><Setting /></el-icon>
          <template #title>系统配置</template>
        </el-menu-item>
        <el-menu-item index="/system/logs">
          <el-icon><Document /></el-icon>
          <template #title>运行日志</template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="main-header">
        <div class="header-left">
          <el-icon class="collapse-btn" @click="isCollapse = !isCollapse" :size="18">
            <Fold v-if="!isCollapse" />
            <Expand v-else />
          </el-icon>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item>{{ $route.meta.title || '' }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <el-tag effect="plain" round size="small" type="info">v1.0</el-tag>
          <span class="system-title">基于深度学习的股票预测系统</span>
        </div>
      </el-header>

      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const isCollapse = ref(false)
const currentRoute = computed(() => route.path)
</script>

<style lang="scss" scoped>
.layout-container {
  height: 100vh;
}

.sidebar {
  background: #fff;
  border-right: 1px solid #E8ECF0;
  overflow-y: auto;
  overflow-x: hidden;
  transition: width 0.3s;
}

.logo-area {
  height: 60px;
  display: flex;
  align-items: center;
  padding: 0 16px;
  gap: 10px;
  border-bottom: 1px solid #E8ECF0;
}

.logo-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: #3DD0B6;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
}

.logo-info {
  display: flex;
  flex-direction: column;
  line-height: 1.3;
}

.logo-title {
  font-size: 16px;
  font-weight: 700;
  color: #1D2129;
  letter-spacing: 0.5px;
}

.logo-sub {
  font-size: 11px;
  color: #86909C;
}

.menu-group-label {
  padding: 16px 20px 6px;
  font-size: 11px;
  font-weight: 600;
  color: #C0C4CC;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.sidebar-menu {
  border-right: none;
  padding: 4px 8px;

  :deep(.el-menu-item) {
    height: 42px;
    line-height: 42px;
    margin: 2px 0;
    border-radius: 8px;
    color: #5A6474;
    font-size: 13.5px;

    &:hover {
      background: #E8F8F4;
      color: #3DD0B6;
    }

    &.is-active {
      background: #E8F8F4 !important;
      color: #2BBDA5 !important;
      font-weight: 600;
      border-right: none;
    }

    .el-icon {
      font-size: 17px;
    }
  }
}

.main-header {
  height: 56px;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  border-bottom: 1px solid #E8ECF0;
  z-index: 10;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.collapse-btn {
  cursor: pointer;
  color: #86909C;
  padding: 4px;
  border-radius: 6px;
  transition: all 0.2s;

  &:hover {
    color: #3DD0B6;
    background: #E8F8F4;
  }
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;

  .system-title {
    font-size: 13px;
    color: #86909C;
  }
}

.main-content {
  background: #F0F2F5;
  overflow-y: auto;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
