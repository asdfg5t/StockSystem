import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    component: () => import('@/components/Layout.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/Index.vue'),
        meta: { title: '首页总览' },
      },
      {
        path: 'stock/list',
        name: 'StockList',
        component: () => import('@/views/stock/StockList.vue'),
        meta: { title: '股票数据管理' },
      },
      {
        path: 'stock/detail/:tsCode',
        name: 'StockDetail',
        component: () => import('@/views/stock/StockDetail.vue'),
        meta: { title: '个股详情' },
      },
      {
        path: 'collect/tasks',
        name: 'CollectTasks',
        component: () => import('@/views/collect/CollectTasks.vue'),
        meta: { title: '数据采集任务' },
      },
      {
        path: 'feature/manage',
        name: 'FeatureManage',
        component: () => import('@/views/feature/FeatureManage.vue'),
        meta: { title: '特征工程管理' },
      },
      {
        path: 'model/manage',
        name: 'ModelManage',
        component: () => import('@/views/model/ModelManage.vue'),
        meta: { title: '模型管理' },
      },
      {
        path: 'train/tasks',
        name: 'TrainTasks',
        component: () => import('@/views/train/TrainTasks.vue'),
        meta: { title: '模型训练' },
      },
      {
        path: 'train/metrics/:taskId',
        name: 'TrainMetrics',
        component: () => import('@/views/train/TrainMetrics.vue'),
        meta: { title: '训练指标' },
      },
      {
        path: 'evaluate/results',
        name: 'EvaluateResults',
        component: () => import('@/views/evaluate/EvaluateResults.vue'),
        meta: { title: '模型评估' },
      },
      {
        path: 'evaluate/compare',
        name: 'ModelCompare',
        component: () => import('@/views/evaluate/ModelCompare.vue'),
        meta: { title: '模型对比分析' },
      },
      {
        path: 'predict/quick',
        name: 'QuickPredict',
        component: () => import('@/views/predict/QuickPredict.vue'),
        meta: { title: '指定日期预测' },
      },
      {
        path: 'predict/results',
        name: 'PredictResults',
        component: () => import('@/views/predict/PredictResults.vue'),
        meta: { title: '预测结果' },
      },
      {
        path: 'predict/trend/:tsCode',
        name: 'PredictTrend',
        component: () => import('@/views/predict/PredictTrend.vue'),
        meta: { title: '走势对比' },
      },
      {
        path: 'train/compare',
        name: 'TrainCompare',
        component: () => import('@/views/train/TrainCompare.vue'),
        meta: { title: '训练对比看板' },
      },
      {
        path: 'analysis/errors',
        name: 'ErrorDistribution',
        component: () => import('@/views/analysis/ErrorDistribution.vue'),
        meta: { title: '误差分布分析' },
      },
      {
        path: 'analysis/whatif',
        name: 'WhatIfAnalysis',
        component: () => import('@/views/analysis/WhatIfAnalysis.vue'),
        meta: { title: '情景分析' },
      },
      {
        path: 'stock/techboard/:tsCode',
        name: 'TechBoard',
        component: () => import('@/views/stock/TechBoard.vue'),
        meta: { title: '技术分析看板' },
      },
      {
        path: 'backtest',
        name: 'Backtest',
        component: () => import('@/views/backtest/BacktestView.vue'),
        meta: { title: '回测模拟交易' },
      },
      {
        path: 'analysis/features',
        name: 'FeatureAnalysis',
        component: () => import('@/views/analysis/FeatureAnalysis.vue'),
        meta: { title: '特征重要性分析' },
      },
      {
        path: 'analysis/portfolio',
        name: 'PortfolioView',
        component: () => import('@/views/analysis/PortfolioView.vue'),
        meta: { title: '多股票组合分析' },
      },
      {
        path: 'system/config',
        name: 'SystemConfig',
        component: () => import('@/views/system/SystemConfig.vue'),
        meta: { title: '系统配置' },
      },
      {
        path: 'system/logs',
        name: 'SystemLogs',
        component: () => import('@/views/system/SystemLogs.vue'),
        meta: { title: '日志查看' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
