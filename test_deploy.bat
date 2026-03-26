@echo off
echo 测试开始...
echo.
echo 1. 检查当前目录
cd
echo.
echo 2. 检查Node.js
node --version
echo.
echo 3. 检查wrangler
wrangler --version
echo.
echo 4. 检查登录状态
wrangler whoami
echo.
echo 测试完成，按任意键退出...
pause