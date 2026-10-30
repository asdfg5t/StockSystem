@echo off
chcp 65001 >nul
echo ============================================
echo   股票预测系统 - 完整流水线
echo   (初始化 → 采集数据 → 训练模型 → 预测)
echo ============================================
echo.

set STOCK_CODE=000001.SZ
if not "%1"=="" set STOCK_CODE=%1

echo 目标股票: %STOCK_CODE%
echo.

cd /d "%~dp0backend"
python startup.py all %STOCK_CODE%

echo.
echo 流水线执行完毕, 现在启动Web服务查看结果...
echo.

start "StockSystem-Backend" cmd /k "cd /d "%~dp0backend" && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
timeout /t 3 >nul

start "StockSystem-Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"
timeout /t 3 >nul

echo.
echo 请在浏览器访问: http://localhost:5173
echo.
pause
