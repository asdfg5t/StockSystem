# Setup / 部署指南

## Environment / 环境

Use Python 3.11, Node.js 22.12+ and MySQL 8.0+. Install backend dependencies inside a fresh virtual environment. Use `npm ci` for the frontend. GPU training needs compatible PyTorch/CUDA; code falls back to CPU if CUDA is unavailable.

建议使用新虚拟环境。前端使用锁文件安装；不要混用不同 Python 安装目录。

## Configuration / 配置

Copy `.env.example` to `.env` at the repository root. The backend loads this exact path regardless of the working directory. Process environment variables take precedence.

- `DB_HOST`: MySQL host / 主机，默认 `127.0.0.1`。
- `DB_PORT`: port / 端口，默认 `3306`。
- `DB_USER`: account / 账号，默认 `root`。
- `DB_PASSWORD`: password / 密码，无内置密码。
- `DB_NAME`: database / 库名，默认 `stock_prediction`。
- `TUSHARE_TOKEN`: your own provider token / 自行申请的令牌。
- `TUSHARE_API_URL`: optional trusted gateway / 可选可信网关，留空使用 SDK 默认地址。

Never commit `.env`. Configuration page database records do not automatically override environment settings. Restart the backend after changes. Settings also apply to `startup.py`, `run_train.py` and `reset_and_collect.py`.

不要提交 `.env`；修改根目录配置后重启后端。系统配置页写入数据库的值不会自动应用到采集器。

## Database / 数据库

From `backend`, run `python startup.py initdb`. The account needs database/table creation privileges. Back up existing databases first: initialization can insert or update default records. The SQL template uses `stock_prediction`; the CLI substitutes the configured `DB_NAME` as a quoted identifier. There is no formal migration framework yet.

先执行初始化再操作业务页面。API 启动时的兼容性表检查不能替代完整初始化；已有数据应先备份。

## Running / 启动

From `backend`:

```sh
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

From `frontend`:

```sh
npm ci
npm run dev
npm run build
```

Development Vite proxies `/api` to `http://127.0.0.1:8000`. Production assets go to `frontend/dist`. Production hosting requires a static server, SPA fallback and `/api` reverse proxy. `vite preview` is a local preview without an API proxy configured here. Add authentication before public deployment.

生产构建不包含后端部署；静态服务器需要前端路由回退及 API 代理。当前系统以本地演示为主。

## Troubleshooting / 排错

- **Database access denied / 数据库拒绝访问**：检查 MySQL 状态、`.env` 与账号权限，注意环境变量优先级。
- **Missing tables / 缺表**：先执行 `startup.py initdb`。
- **Token or permissions / 令牌或权限错误**：填写自己的 Token 并重启，核对服务商接口权限与额度。
- **Insufficient data / 样本不足**：先采集基础信息和日线，再计算特征；窗口、步长与指标预热均消耗样本。
- **Out of memory / 内存不足**：缩小股票范围、批次或模型规模。
- **Frontend request failure / 前端请求失败**：确认后端 8000 端口、Vite 代理和数据库初始化。
- **Python startup failure / Python 启动异常**：使用独立 Python 3.11 创建新虚拟环境，避免 Anaconda 与其他解释器混用。

Logs are under root `logs/`. Remove credentials and personal information before sharing. 分享日志前请脱敏。
