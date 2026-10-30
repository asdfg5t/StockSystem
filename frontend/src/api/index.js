import request from './request'

export const dashboardApi = {
  getStats: () => request.get('/dashboard/stats'),
  getModelSummary: () => request.get('/dashboard/model_summary'),
  stockHealth: () => request.get('/dashboard/stock_health'),
}

export const stockApi = {
  getList: (params) => request.get('/stock/list', { params }),
  getIndustries: () => request.get('/stock/industries'),
  getDetail: (tsCode) => request.get(`/stock/detail/${tsCode}`),
  getDaily: (tsCode, params) => request.get(`/stock/daily/${tsCode}`, { params }),
  getKline: (tsCode, params) => request.get(`/stock/kline/${tsCode}`, { params }),
}

export const collectApi = {
  create: (data) => request.post('/collect/create', data),
  start: (taskId) => request.post(`/collect/start/${taskId}`),
  getProgress: (taskId) => request.get(`/collect/progress/${taskId}`),
  getTasks: (params) => request.get('/collect/tasks', { params }),
  getLogs: (taskId, params) => request.get(`/collect/logs/${taskId}`, { params }),
  deleteTask: (taskId) => request.delete(`/collect/task/${taskId}`),
}

export const featureApi = {
  compute: (data) => request.post('/feature/compute', data),
  getColumns: () => request.get('/feature/columns'),
  getData: (tsCode, params) => request.get(`/feature/data/${tsCode}`, { params }),
  getStats: (tsCode, params) => request.get(`/feature/stats/${tsCode}`, { params }),
}

export const modelApi = {
  getConfigs: (params) => request.get('/model/configs', { params }),
  updateConfig: (id, data) => request.put(`/model/config/${id}`, data),
  getFiles: (params) => request.get('/model/files', { params }),
  deleteFile: (id) => request.delete(`/model/file/${id}`),
}

export const trainApi = {
  create: (data) => request.post('/train/create', data),
  start: (taskId) => request.post(`/train/start/${taskId}`),
  getTasks: (params) => request.get('/train/tasks', { params }),
  getTask: (taskId) => request.get(`/train/task/${taskId}`),
  getMetrics: (taskId) => request.get(`/train/metrics/${taskId}`),
  compareMetrics: (params) => request.get('/train/compare_metrics', { params }),
  getSmartResults: () => request.get('/train/smart_results'),
  deleteTask: (taskId) => request.delete(`/train/task/${taskId}`),
}

export const predictApi = {
  create: (data) => request.post('/predict/create', data),
  start: (taskId) => request.post(`/predict/start/${taskId}`),
  quickPredict: (data) => request.post('/predict/quick', data),
  getTasks: (params) => request.get('/predict/tasks', { params }),
  getResults: (params) => request.get('/predict/results', { params }),
  getCompare: (params) => request.get('/predict/compare', { params }),
  deleteTask: (taskId) => request.delete(`/predict/task/${taskId}`),
  getConfidence: (params) => request.get('/predict/confidence', { params }),
  backfillActual: (params) => request.post('/predict/backfill_actual', null, { params }),
}

export const evaluateApi = {
  getResults: (params) => request.get('/evaluate/results', { params }),
  getCompare: (params) => request.get('/evaluate/compare', { params }),
  getStepsCompare: (params) => request.get('/evaluate/steps_compare', { params }),
  getDetail: (id) => request.get(`/evaluate/detail/${id}`),
}

export const backtestApi = {
  run: (params) => request.get('/backtest/run', { params }),
}

export const analysisApi = {
  getPcaImportance: (params) => request.get('/analysis/pca_importance', { params }),
  getCorrelation: (params) => request.get('/analysis/feature_correlation', { params }),
  getMultiStockEval: (params) => request.get('/analysis/multi_stock_eval', { params }),
  getPortfolioSuggest: (params) => request.get('/analysis/portfolio_suggest', { params }),
  getErrorDistribution: (params) => request.get('/analysis/error_distribution', { params }),
  getWhatIf: (params) => request.get('/analysis/whatif', { params }),
  getModelFeatures: (params) => request.get('/analysis/model_features', { params }),
}

export const systemApi = {
  getConfigs: () => request.get('/system/configs'),
  updateConfig: (key, data) => request.put(`/system/config/${key}`, data),
  getLogs: (params) => request.get('/system/logs', { params }),
  getLogFiles: () => request.get('/system/log_files'),
  getLogContent: (filename, params) => request.get(`/system/log_content/${filename}`, { params }),
}
