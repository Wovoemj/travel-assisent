@echo off
chcp 65001 >nul
echo ========================================
echo 智能旅游助手 - 网络诊断工具
echo ========================================
echo.

echo 1. 检查服务器状态...
netstat -an | findstr :5000
echo.

echo 2. 检查本机IP地址...
ipconfig | findstr "IPv4"
echo.

echo 3. 检查防火墙规则...
netsh advfirewall firewall show rule name="Flask Travel App" 2>nul
if %errorlevel% neq 0 (
    echo [警告] 防火墙规则不存在
    echo 正在添加防火墙规则...
    netsh advfirewall firewall add rule name="Flask Travel App" dir=in action=allow protocol=TCP localport=5000
    if %errorlevel% equ 0 (
        echo [成功] 防火墙规则已添加
    ) else (
        echo [错误] 添加防火墙规则失败，请以管理员身份运行此脚本
    )
) else (
    echo [正常] 防火墙规则已存在
)
echo.

echo 4. 测试本地访问...
curl -s -o nul -w "HTTP状态码: %%{http_code}\n" http://127.0.0.1:5000/ 2>nul || echo 本地访问失败
echo.

echo 5. 网络连通性测试...
ping -n 1 10.108.25.171 >nul 2>&1
if %errorlevel% equ 0 (
    echo [正常] 本机IP可达
) else (
    echo [警告] 本机IP不可达
)
echo.

echo ========================================
echo 诊断完成！
echo.
echo 如果服务器正在运行，请尝试访问：
echo http://127.0.0.1:5000
echo http://10.108.25.171:5000
echo.
echo 如果仍然无法访问，请：
echo 1. 以管理员身份运行此脚本
echo 2. 检查杀毒软件设置
echo 3. 重启Flask服务器
echo ========================================
pause