# 防火墙配置指南 - 解决网址无法访问问题

## 问题诊断

您的Flask应用正在运行并监听5000端口，但外部无法访问。这通常是由于Windows防火墙阻止了入站连接。

## 解决方案

### 方法1：手动添加防火墙规则（推荐）

1. **以管理员身份运行PowerShell或命令提示符**
   - 右键点击"开始"菜单
   - 选择"Windows PowerShell(管理员)"或"命令提示符(管理员)"

2. **执行以下命令添加防火墙规则**：
   ```powershell
   netsh advfirewall firewall add rule name="Flask Travel App" dir=in action=allow protocol=TCP localport=5000
   ```

3. **验证规则是否添加成功**：
   ```powershell
   netsh advfirewall firewall show rule name="Flask Travel App"
   ```

### 方法2：通过Windows防火墙GUI配置

1. **打开Windows Defender防火墙**
   - 按 `Win + R`，输入 `wf.msc`，按回车

2. **添加入站规则**
   - 点击左侧的"入站规则"
   - 点击右侧的"新建规则"
   - 选择"端口"，点击"下一步"
   - 选择"TCP"，选择"特定本地端口"，输入"5000"
   - 选择"允许连接"，点击"下一步"
   - 保持所有配置文件选中，点击"下一步"
   - 名称输入"Flask Travel App"，点击"完成"

### 方法3：临时禁用防火墙（仅用于测试）

**⚠️ 警告：这会降低系统安全性，仅用于测试**

1. **以管理员身份运行PowerShell**
2. **临时禁用防火墙**：
   ```powershell
   netsh advfirewall set allprofiles state off
   ```
3. **测试完成后重新启用**：
   ```powershell
   netsh advfirewall set allprofiles state on
   ```

## 验证配置

配置完成后，尝试从其他设备访问：
```
http://10.108.25.171:5000
```

## 其他可能的问题

### 1. 网络连接问题
确保您的设备和其他设备在同一网络中：
```powershell
ipconfig
```

### 2. 服务器绑定问题
检查app.py中的服务器配置，确保绑定到所有接口：
```python
# 当前配置应该是这样
socketio.run(app, debug=False, port=5000, host='0.0.0.0', allow_unsafe_werkzeug=True)
```

### 3. 端口被占用
检查5000端口是否被其他程序占用：
```powershell
netstat -ano | findstr :5000
```

## 快速测试脚本

创建一个批处理文件 `setup_firewall.bat`：
```batch
@echo off
echo 正在配置防火墙规则...
netsh advfirewall firewall add rule name="Flask Travel App" dir=in action=allow protocol=TCP localport=5000
echo 防火墙规则已添加
echo 验证规则：
netsh advfirewall firewall show rule name="Flask Travel App"
pause
```

右键以管理员身份运行此脚本即可。

## 故障排除

如果问题仍然存在：

1. **检查网络连接**：确保其他设备可以ping通您的IP
2. **检查防火墙日志**：在事件查看器中查看防火墙日志
3. **尝试不同端口**：将端口改为8080或其他常用端口
4. **检查杀毒软件**：某些杀毒软件也有自己的防火墙功能

## 联系支持

如果以上方法都无法解决问题，请提供以下信息：
- Windows版本
- 错误信息
- 网络配置（ipconfig输出）
- 防火墙状态