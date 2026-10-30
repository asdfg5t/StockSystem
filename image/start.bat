@echo off
chcp 65001 >nul
echo ============================================
echo   基于深度学习的股票预测系统 - 启动脚本
echo ============================================
echo.

echo [步骤1] 初始化数据库...
cd /d "%~dp0backend"
python startup.py initdb
if %errorlevel% neq 0 (
    echo 数据库初始化失败!
    pause
    exit /b 1
)

echo.
echo [步骤2] 启动后端API服务 (后台运行)...
start "StockSystem-Backend" cmd /k "cd /d "%~dp0backend" && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
timeout /t 3 >nul

echo.
echo [步骤3] 启动前端开发服务...
start "StockSystem-Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"
timeout /t 3 >nul

echo.
echo ============================================
echo   系统已启动!
echo   后端地址: http://localhost:8000
echo   前端地址: http://localhost:5173
echo   API文档:  http://localhost:8000/docs
echo ============================================
echo.
echo 启动后请在浏览器访问 http://localhost:5173
echo.
pause
