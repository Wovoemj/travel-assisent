# 移动端访问指南 - 解决手机无法访问问题

## 当前状态确认

从服务器日志看到：
- ✅ 服务器正在运行在 http://10.108.25.171:5000
- ✅ 服务器监听所有网络接口 (0.0.0.0)
- ⚠️ 移动设备(10.108.25.240)访问时出现SSL错误

## 问题诊断

### 1. 检查服务器状态
```powershell
# 检查服务器是否正在运行
netstat -an | findstr :5000

# 应该看到类似输出：
# TCP    0.0.0.0:5000           0.0.0.0:0              LISTENING
```

### 2. 检查网络连接
```powershell
# 检查本机IP地址
ipconfig | findstr "IPv4"

# 测试网络连通性
ping 10.108.25.171
```

### 3. 检查防火墙
```powershell
# 检查防火墙规则
netsh advfirewall firewall show rule name="Flask Travel App"
```

## 解决方案

### 方案1：使用HTTP而非HTTPS

从日志看到SSL错误，说明移动设备可能在尝试HTTPS连接。请确保：

1. **使用HTTP访问**：`http://10.108.25.171:5000`（不是https）
2. **避免浏览器自动跳转HTTPS**：
   - 清除浏览器缓存
   - 使用隐私模式访问
   - 尝试其他浏览器

### 方案2：配置防火墙（管理员权限）

```powershell
# 以管理员身份运行PowerShell，然后执行：
netsh advfirewall firewall add rule name="Flask Travel App" dir=in action=allow protocol=TCP localport=5000
```

### 方案3：临时禁用防火墙（仅测试）

```powershell
# 临时禁用防火墙（测试用）
netsh advfirewall set allprofiles state off

# 测试完成后重新启用
netsh advfirewall set allprofiles state on
```

### 方案4：检查移动设备网络设置

1. **确保在同一WiFi网络**：
   - 手机和电脑连接同一个WiFi
   - 检查手机IP地址是否在同一网段

2. **检查手机网络设置**：
   - 确保手机没有使用VPN
   - 关闭手机的数据流量，只使用WiFi
   - 尝试忘记WiFi重新连接

### 方案5：使用本地网络诊断工具

运行我们创建的诊断工具：
```batch
# 右键以管理员身份运行
diagnose_network.bat
```

## 移动端访问步骤

### 步骤1：确认服务器正在运行
```powershell
# 在电脑上检查
curl http://127.0.0.1:5000
```

### 步骤2：获取正确的IP地址
```powershell
# 查看所有网络接口
ipconfig /all
```

### 步骤3：在手机上访问
1. 打开手机浏览器
2. 输入地址：`http://10.108.25.171:5000`
3. 确保使用HTTP（不是HTTPS）

## 常见问题解决

### 问题1：连接超时
**解决方案**：
- 检查防火墙设置
- 确认设备在同一网络
- 尝试重启路由器

### 问题2：SSL错误
**解决方案**：
- 使用HTTP而非HTTPS
- 清除浏览器缓存
- 尝试其他浏览器

### 问题3：页面无法加载
**解决方案**：
- 检查静态文件路径
- 确认JavaScript文件加载正常
- 查看浏览器控制台错误信息

## 网络配置检查

### 检查本机网络配置
```powershell
# 查看详细网络信息
Get-NetIPAddress | Where-Object {$_.AddressFamily -eq "IPv4"}

# 检查路由表
Get-NetRoute -AddressFamily IPv4
```

### 检查移动设备连接
```powershell
# 查看连接的设备
arp -a | findstr "10.108.25"
```

## 测试脚本

### 创建测试页面访问脚本
```powershell
# 测试HTTP访问
Invoke-WebRequest -Uri "http://127.0.0.1:5000" -UseBasicParsing

# 测试从其他IP访问
Invoke-WebRequest -Uri "http://10.108.25.171:5000" -UseBasicParsing
```

## 联系支持

如果以上方法都无法解决问题，请提供以下信息：

1. **错误信息**：
   - 手机浏览器显示的具体错误
   - 服务器日志中的错误信息

2. **网络配置**：
   - 电脑IP地址：`ipconfig`输出
   - 手机IP地址
   - 网络类型（家庭/公司/公共WiFi）

3. **设备信息**：
   - 手机型号和操作系统版本
   - 浏览器类型和版本
   - 是否使用VPN或代理

## 快速解决步骤

1. **确认服务器运行**：`netstat -an | findstr :5000`
2. **检查防火墙**：以管理员身份运行`diagnose_network.bat`
3. **测试访问**：在手机浏览器输入`http://10.108.25.171:5000`
4. **清除缓存**：清除手机浏览器缓存，使用隐私模式
5. **检查网络**：确保手机和电脑在同一WiFi网络

如果问题仍然存在，请将错误信息和网络配置发送给技术支持。