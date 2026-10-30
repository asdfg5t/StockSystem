CREATE DATABASE IF NOT EXISTS stock_prediction DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE stock_prediction;

-- 股票基础信息表
CREATE TABLE IF NOT EXISTS stock_basic (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL COMMENT '股票代码',
    symbol VARCHAR(10) NOT NULL COMMENT '股票简码',
    name VARCHAR(50) NOT NULL COMMENT '股票名称',
    area VARCHAR(20) DEFAULT NULL COMMENT '地区',
    industry VARCHAR(50) DEFAULT NULL COMMENT '所属行业',
    market VARCHAR(20) DEFAULT NULL COMMENT '市场类型',
    list_date VARCHAR(10) DEFAULT NULL COMMENT '上市日期',
    list_status VARCHAR(5) DEFAULT 'L' COMMENT '上市状态 L上市 D退市 P暂停',
    is_hs VARCHAR(5) DEFAULT NULL COMMENT '是否沪深港通 N否 H沪 S深',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_ts_code (ts_code),
    INDEX idx_industry (industry),
    INDEX idx_list_status (list_status)
) ENGINE=InnoDB COMMENT='股票基础信息表';

-- 日线行情数据表
CREATE TABLE IF NOT EXISTS stock_daily (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL COMMENT '股票代码',
    trade_date VARCHAR(10) NOT NULL COMMENT '交易日期',
    open DECIMAL(12,4) DEFAULT NULL COMMENT '开盘价',
    high DECIMAL(12,4) DEFAULT NULL COMMENT '最高价',
    low DECIMAL(12,4) DEFAULT NULL COMMENT '最低价',
    close DECIMAL(12,4) DEFAULT NULL COMMENT '收盘价',
    pre_close DECIMAL(12,4) DEFAULT NULL COMMENT '昨收价',
    `change` DECIMAL(12,4) DEFAULT NULL COMMENT '涨跌额',
    pct_chg DECIMAL(12,4) DEFAULT NULL COMMENT '涨跌幅',
    vol DECIMAL(18,4) DEFAULT NULL COMMENT '成交量(手)',
    amount DECIMAL(18,4) DEFAULT NULL COMMENT '成交额(千元)',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_code_date (ts_code, trade_date),
    INDEX idx_trade_date (trade_date),
    INDEX idx_ts_code (ts_code)
) ENGINE=InnoDB COMMENT='日线行情数据表';

-- 特征数据表
CREATE TABLE IF NOT EXISTS feature_data (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL COMMENT '股票代码',
    trade_date VARCHAR(10) NOT NULL COMMENT '交易日期',
    feature_set TEXT COMMENT '特征JSON数据',
    feature_version VARCHAR(20) DEFAULT 'v1' COMMENT '特征版本',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_code_date_ver (ts_code, trade_date, feature_version),
    INDEX idx_ts_code (ts_code)
) ENGINE=InnoDB COMMENT='特征数据表';

-- 数据采集任务表
CREATE TABLE IF NOT EXISTS collect_task (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    task_name VARCHAR(100) NOT NULL COMMENT '任务名称',
    task_type VARCHAR(30) NOT NULL COMMENT '任务类型: stock_basic/daily',
    ts_code VARCHAR(20) DEFAULT NULL COMMENT '股票代码(为空则全量)',
    start_date VARCHAR(10) DEFAULT NULL COMMENT '开始日期',
    end_date VARCHAR(10) DEFAULT NULL COMMENT '结束日期',
    status VARCHAR(20) DEFAULT 'pending' COMMENT 'pending/running/completed/failed/paused',
    total_count INT DEFAULT 0 COMMENT '总数量',
    success_count INT DEFAULT 0 COMMENT '成功数量',
    fail_count INT DEFAULT 0 COMMENT '失败数量',
    progress DECIMAL(5,2) DEFAULT 0 COMMENT '进度百分比',
    error_msg TEXT DEFAULT NULL COMMENT '错误信息',
    started_at DATETIME DEFAULT NULL,
    finished_at DATETIME DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_status (status),
    INDEX idx_task_type (task_type)
) ENGINE=InnoDB COMMENT='数据采集任务表';

-- 采集日志表
CREATE TABLE IF NOT EXISTS collect_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    task_id BIGINT NOT NULL COMMENT '关联任务ID',
    ts_code VARCHAR(20) DEFAULT NULL COMMENT '股票代码',
    status VARCHAR(20) NOT NULL COMMENT 'success/failed/retry',
    message TEXT DEFAULT NULL COMMENT '日志信息',
    retry_count INT DEFAULT 0 COMMENT '重试次数',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_task_id (task_id),
    INDEX idx_ts_code (ts_code)
) ENGINE=InnoDB COMMENT='采集日志表';

-- 模型配置表
CREATE TABLE IF NOT EXISTS model_config (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    model_name VARCHAR(50) NOT NULL COMMENT '模型名称: TFT/Transformer/BiLSTM',
    model_type VARCHAR(30) NOT NULL COMMENT '模型类型',
    params TEXT COMMENT '模型超参数JSON',
    description VARCHAR(200) DEFAULT NULL COMMENT '模型描述',
    is_active TINYINT DEFAULT 1 COMMENT '是否激活',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_model_type (model_type)
) ENGINE=InnoDB COMMENT='模型配置表';

-- 训练任务表
CREATE TABLE IF NOT EXISTS train_task (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    task_name VARCHAR(100) NOT NULL COMMENT '任务名称',
    model_type VARCHAR(30) NOT NULL COMMENT '模型类型: TFT/Transformer/BiLSTM',
    ts_code VARCHAR(20) NOT NULL COMMENT '股票代码',
    predict_steps INT NOT NULL DEFAULT 1 COMMENT '预测步长: 1/3/5',
    lookback_window INT DEFAULT 60 COMMENT '回看窗口',
    epochs INT DEFAULT 100 COMMENT '训练轮数',
    batch_size INT DEFAULT 32 COMMENT '批次大小',
    learning_rate DECIMAL(10,8) DEFAULT 0.001 COMMENT '学习率',
    train_start_date VARCHAR(10) DEFAULT NULL COMMENT '训练开始日期',
    train_end_date VARCHAR(10) DEFAULT NULL COMMENT '训练结束日期',
    val_ratio DECIMAL(3,2) DEFAULT 0.15 COMMENT '验证集比例',
    test_ratio DECIMAL(3,2) DEFAULT 0.15 COMMENT '测试集比例',
    status VARCHAR(20) DEFAULT 'pending' COMMENT 'pending/running/completed/failed',
    current_epoch INT DEFAULT 0 COMMENT '当前训练轮数',
    best_val_loss DECIMAL(12,6) DEFAULT NULL COMMENT '最优验证损失',
    model_path VARCHAR(500) DEFAULT NULL COMMENT '模型保存路径',
    error_msg TEXT DEFAULT NULL COMMENT '错误信息',
    started_at DATETIME DEFAULT NULL,
    finished_at DATETIME DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_model_type (model_type),
    INDEX idx_status (status),
    INDEX idx_ts_code (ts_code)
) ENGINE=InnoDB COMMENT='训练任务表';

-- 训练指标记录表
CREATE TABLE IF NOT EXISTS train_metric (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    task_id BIGINT NOT NULL COMMENT '训练任务ID',
    epoch INT NOT NULL COMMENT '轮数',
    train_loss DECIMAL(12,6) DEFAULT NULL COMMENT '训练损失',
    val_loss DECIMAL(12,6) DEFAULT NULL COMMENT '验证损失',
    train_mae DECIMAL(12,6) DEFAULT NULL,
    val_mae DECIMAL(12,6) DEFAULT NULL,
    train_rmse DECIMAL(12,6) DEFAULT NULL COMMENT '训练RMSE',
    val_rmse DECIMAL(12,6) DEFAULT NULL COMMENT '验证RMSE',
    learning_rate DECIMAL(12,8) DEFAULT NULL COMMENT '当前学习率',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_task_id (task_id),
    INDEX idx_epoch (epoch)
) ENGINE=InnoDB COMMENT='训练指标记录表';

-- 模型文件表
CREATE TABLE IF NOT EXISTS model_file (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    train_task_id BIGINT DEFAULT NULL COMMENT '训练任务ID',
    model_type VARCHAR(30) NOT NULL COMMENT '模型类型',
    ts_code VARCHAR(20) NOT NULL COMMENT '股票代码',
    predict_steps INT NOT NULL COMMENT '预测步长',
    file_path VARCHAR(500) NOT NULL COMMENT '模型文件路径',
    scaler_path VARCHAR(500) DEFAULT NULL COMMENT '标准化器路径',
    feature_config TEXT DEFAULT NULL COMMENT '特征配置JSON',
    metrics TEXT DEFAULT NULL COMMENT '评估指标JSON',
    is_best TINYINT DEFAULT 0 COMMENT '是否最优模型',
    file_size BIGINT DEFAULT 0 COMMENT '文件大小(bytes)',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_model_type (model_type),
    INDEX idx_ts_code (ts_code),
    INDEX idx_is_best (is_best)
) ENGINE=InnoDB COMMENT='模型文件表';

-- 预测任务表
CREATE TABLE IF NOT EXISTS predict_task (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    task_name VARCHAR(100) NOT NULL COMMENT '任务名称',
    model_type VARCHAR(30) NOT NULL COMMENT '模型类型',
    model_file_id BIGINT DEFAULT NULL COMMENT '模型文件ID',
    ts_code VARCHAR(20) NOT NULL COMMENT '股票代码',
    predict_steps INT NOT NULL DEFAULT 1 COMMENT '预测步长',
    predict_date VARCHAR(10) DEFAULT NULL COMMENT '预测日期(基准日)',
    status VARCHAR(20) DEFAULT 'pending' COMMENT 'pending/running/completed/failed',
    error_msg TEXT DEFAULT NULL COMMENT '错误信息',
    started_at DATETIME DEFAULT NULL,
    finished_at DATETIME DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_model_type (model_type),
    INDEX idx_ts_code (ts_code),
    INDEX idx_status (status)
) ENGINE=InnoDB COMMENT='预测任务表';

-- 预测结果表
CREATE TABLE IF NOT EXISTS predict_result (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    task_id BIGINT NOT NULL COMMENT '预测任务ID',
    model_type VARCHAR(30) NOT NULL COMMENT '模型类型',
    ts_code VARCHAR(20) NOT NULL COMMENT '股票代码',
    predict_steps INT NOT NULL COMMENT '预测步长',
    base_date VARCHAR(10) NOT NULL COMMENT '基准日期',
    target_date VARCHAR(10) NOT NULL COMMENT '目标日期',
    step_index INT NOT NULL COMMENT '步长序号(从1开始)',
    predicted_close DECIMAL(12,4) NOT NULL COMMENT '预测收盘价',
    actual_close DECIMAL(12,4) DEFAULT NULL COMMENT '实际收盘价',
    error DECIMAL(12,4) DEFAULT NULL COMMENT '误差',
    error_pct DECIMAL(8,4) DEFAULT NULL COMMENT '误差百分比',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_task_id (task_id),
    INDEX idx_ts_code (ts_code),
    INDEX idx_base_date (base_date),
    INDEX idx_model_type (model_type),
    INDEX idx_pred_lookup (model_type, ts_code, predict_steps, id DESC)
) ENGINE=InnoDB COMMENT='预测结果表';

-- 模型评估结果表
CREATE TABLE IF NOT EXISTS evaluate_result (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    train_task_id BIGINT DEFAULT NULL COMMENT '训练任务ID',
    model_type VARCHAR(30) NOT NULL COMMENT '模型类型',
    ts_code VARCHAR(20) NOT NULL COMMENT '股票代码',
    predict_steps INT NOT NULL COMMENT '预测步长',
    dataset_type VARCHAR(20) NOT NULL DEFAULT 'test' COMMENT 'train/val/test',
    mae DECIMAL(12,6) DEFAULT NULL,
    mse DECIMAL(12,6) DEFAULT NULL,
    rmse DECIMAL(12,6) DEFAULT NULL,
    mape DECIMAL(12,6) DEFAULT NULL,
    smape DECIMAL(12,6) DEFAULT NULL,
    r2 DECIMAL(12,6) DEFAULT NULL,
    direction_accuracy DECIMAL(8,4) DEFAULT NULL COMMENT '趋势方向准确率',
    max_error DECIMAL(12,6) DEFAULT NULL COMMENT '最大绝对误差',
    median_ae DECIMAL(12,6) DEFAULT NULL COMMENT '中位数绝对误差',
    explained_variance DECIMAL(12,6) DEFAULT NULL COMMENT '解释方差分数',
    pearson_corr DECIMAL(12,6) DEFAULT NULL COMMENT '皮尔逊相关系数',
    accuracy_1pct DECIMAL(8,4) DEFAULT NULL COMMENT '1%阈值准确率(%)',
    accuracy_3pct DECIMAL(8,4) DEFAULT NULL COMMENT '3%阈值准确率(%)',
    accuracy_5pct DECIMAL(8,4) DEFAULT NULL COMMENT '5%阈值准确率(%)',
    win_rate DECIMAL(8,4) DEFAULT NULL COMMENT '模拟交易胜率(%)',
    profit_factor DECIMAL(12,6) DEFAULT NULL COMMENT '盈利因子',
    sharpe_ratio DECIMAL(12,6) DEFAULT NULL COMMENT '夏普比率(年化)',
    max_drawdown DECIMAL(8,4) DEFAULT NULL COMMENT '最大回撤(%)',
    actual_values TEXT DEFAULT NULL COMMENT '实际值JSON',
    predicted_values TEXT DEFAULT NULL COMMENT '预测值JSON',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_model_type (model_type),
    INDEX idx_ts_code (ts_code),
    INDEX idx_dataset_type (dataset_type)
) ENGINE=InnoDB COMMENT='模型评估结果表';

-- 系统配置表
CREATE TABLE IF NOT EXISTS system_config (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    config_key VARCHAR(100) NOT NULL COMMENT '配置键',
    config_value TEXT NOT NULL COMMENT '配置值',
    config_type VARCHAR(20) DEFAULT 'string' COMMENT '值类型: string/int/float/json/bool',
    description VARCHAR(200) DEFAULT NULL COMMENT '配置描述',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_config_key (config_key)
) ENGINE=InnoDB COMMENT='系统配置表';

-- 系统日志表
CREATE TABLE IF NOT EXISTS system_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    module VARCHAR(50) NOT NULL COMMENT '模块名',
    level VARCHAR(10) NOT NULL COMMENT 'DEBUG/INFO/WARNING/ERROR/CRITICAL',
    message TEXT NOT NULL COMMENT '日志信息',
    detail TEXT DEFAULT NULL COMMENT '详细信息',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_module (module),
    INDEX idx_level (level),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB COMMENT='系统日志表';

-- 初始化系统配置
INSERT INTO system_config (config_key, config_value, config_type, description) VALUES
('tushare_token', '', 'string', 'Tushare API Token (configure in .env)'),
('tushare_api_url', '', 'string', 'Optional Tushare gateway (configure in .env)'),
('default_lookback_window', '60', 'int', '默认回看窗口'),
('default_epochs', '100', 'int', '默认训练轮数'),
('default_batch_size', '32', 'int', '默认批次大小'),
('default_learning_rate', '0.001', 'float', '默认学习率'),
('data_years', '3', 'int', '数据采集年限'),
('collect_batch_size', '50', 'int', '采集批次大小'),
('collect_retry_times', '3', 'int', '采集重试次数'),
('collect_retry_interval', '5', 'int', '采集重试间隔(秒)')
ON DUPLICATE KEY UPDATE updated_at = CURRENT_TIMESTAMP;

-- 初始化模型配置
INSERT INTO model_config (model_name, model_type, params, description) VALUES
('TFT-Default', 'TFT', '{"hidden_size":128,"num_heads":4,"num_encoder_layers":2,"num_decoder_layers":2,"dropout":0.1,"attention_dropout":0.1}', 'Temporal Fusion Transformer默认配置'),
('Transformer-Default', 'Transformer', '{"d_model":128,"nhead":4,"num_encoder_layers":3,"num_decoder_layers":3,"dim_feedforward":256,"dropout":0.1}', 'Transformer默认配置'),
('BiLSTM-Default', 'BiLSTM', '{"hidden_size":128,"num_layers":2,"dropout":0.2,"bidirectional":true}', 'BiLSTM默认配置');

DROP TABLE IF EXISTS system_log;

CREATE TABLE IF NOT EXISTS system_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    module VARCHAR(50) NOT NULL COMMENT '模块名',
    level VARCHAR(10) NOT NULL COMMENT 'DEBUG/INFO/WARNING/ERROR/CRITICAL',
    message TEXT NOT NULL COMMENT '日志信息',
    detail TEXT DEFAULT NULL COMMENT '详细信息',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_module (module),
    INDEX idx_level (level),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB COMMENT='系统日志表';
