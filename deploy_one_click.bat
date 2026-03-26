@echo off
chcp 65001 >nul
title 智能旅游助手 - 一键部署脚本

echo ========================================
echo 🚀 智能旅游助手 - 一键部署脚本
echo ========================================
echo.

:: 检查Node.js
echo [1/5] 检查Node.js...
node --version
if %errorlevel% neq 0 (
    echo.
    echo ❌ Node.js未安装！
    echo 请访问 https://nodejs.org/ 下载安装Node.js
    echo 安装完成后重新运行此脚本
    echo.
    pause
    exit /b 1
)
echo ✅ Node.js已安装

:: 安装Wrangler CLI
echo.
echo [2/5] 安装Wrangler CLI...
wrangler --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 正在安装Wrangler CLI...
    npm install -g wrangler
    if %errorlevel% neq 0 (
        echo.
        echo ❌ Wrangler CLI安装失败！
        echo 请检查网络连接或以管理员身份运行
        echo.
        pause
        exit /b 1
    )
    echo ✅ Wrangler CLI安装成功
) else (
    echo ✅ Wrangler CLI已安装
)

:: 登录Cloudflare
echo.
echo [3/5] 登录Cloudflare...
wrangler whoami >nul 2>&1
if %errorlevel% neq 0 (
    echo 正在打开浏览器进行Cloudflare授权...
    echo 请在浏览器中完成授权操作
    wrangler login
    if %errorlevel% neq 0 (
        echo.
        echo ❌ Cloudflare登录失败！
        echo 请检查网络连接
        echo.
        pause
        exit /b 1
    )
    echo ✅ Cloudflare登录成功
) else (
    echo ✅ 已登录Cloudflare账号
)

:: 部署到Cloudflare Workers
echo.
echo [4/5] 部署到Cloudflare Workers...
echo 正在部署，请稍候...
wrangler deploy
if %errorlevel% neq 0 (
    echo.
    echo ❌ 部署失败！
    echo 请检查网络连接和权限
    echo.
    pause
    exit /b 1
)

:: 完成
echo.
echo [5/5] 部署完成！
echo.
echo ========================================
echo ✅ 部署成功！
echo ========================================
echo.
echo 📱 主要功能：
echo    • 景点搜索和详情
echo    • 天气查询
echo    • 行程规划
echo    • 美食推荐
echo    • 全球CDN加速
echo.
echo 💰 费用：完全免费
echo 🌍 访问：全球任何网络
echo ⏰ 可用性：24/7
echo.
echo 📝 请在Cloudflare Dashboard查看访问地址
echo    https://dash.cloudflare.com/
echo.
echo ========================================
echo 按任意键退出...
pause >nul
