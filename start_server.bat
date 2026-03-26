@echo off
chcp 65001 >nul
echo ========================================
echo 智能旅游助手 - 服务器启动脚本
echo ========================================
echo.

echo 正在检查Python环境...
python --version
if %errorlevel% neq 0 (
    echo [错误] Python未安装或未添加到PATH
    pause
    exit /b 1
)

echo.
echo 正在检查依赖包...
pip list | findstr flask >nul
if %errorlevel% neq 0 (
    echo [警告] Flask未安装，正在安装...
    pip install flask flask-sqlalchemy flask-socketio flask-caching flask-compress
)

echo.
echo 正在启动服务器...
echo.
echo ========================================
echo 🌐 服务器访问地址：
echo    本地访问: http://127.0.0.1:5000
echo    网络访问: http://0.0.0.0:5000
echo.
echo 📱 移动设备访问：
echo    请查看上方显示的IP地址
echo    例如: http://192.168.1.100:5000
echo ========================================
echo.
echo 按 Ctrl+C 停止服务器
echo.

python app.py
pause