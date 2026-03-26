# Cloudflare Dashboard 详细操作指南

## 🎯 如何找到KV存储标签

### 步骤1：登录Cloudflare Dashboard
1. 访问 https://dash.cloudflare.com/
2. 使用您的账号登录

### 步骤2：进入Workers & Pages
1. 在左侧菜单中找到 **"Workers & Pages"**
2. 点击进入

### 步骤3：创建或选择Worker
1. 如果还没有Worker，点击 **"Create application"**
2. 选择 **"Create Worker"**
3. 命名为 `travel-assistant`
4. 点击 **"Deploy"**

### 步骤4：找到KV标签
1. 在Worker详情页面
2. 点击 **"Settings"** 标签
3. 向下滚动找到 **"KV Namespace Bindings"**
4. 点击 **"Add binding"**

### 步骤5：创建KV存储
1. 在弹出的对话框中
2. Variable name: `DESTINATIONS`
3. KV namespace: 点击 **"Create a namespace"**
4. 命名空间名称: `travel-destinations`
5. 点击 **"Add"**

### 步骤6：重复创建第二个KV存储
1. 再次点击 **"Add binding"**
2. Variable name: `ASSETS`
3. KV namespace: 点击 **"Create a namespace"**
4. 命名空间名称: `travel-assets`
5. 点击 **"Add"**

## 📱 替代方案：使用GitHub + Render（推荐）

如果KV配置太复杂，推荐使用更简单的方案：

### 方案1：Render部署（最简单）
1. 访问 https://render.com
2. 注册账号
3. 点击 **"New +"** → **"Web Service"**
4. 连接GitHub仓库
5. 配置：
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python app.py`
   - **Plan**: Free
6. 点击 **"Create Web Service"**

### 方案2：Vercel部署（最快）
1. 访问 https://vercel.com
2. 注册账号
3. 点击 **"New Project"**
4. 上传项目文件
5. 自动部署完成

## 🔧 快速测试命令

### 测试当前配置
```bash
# 检查Wrangler是否正确配置
wrangler kv:namespace list

# 测试部署
wrangler dev
```

### 手动上传数据
```bash
# 上传景点数据
wrangler kv:key put --binding DESTINATIONS "all" --path destinations.json

# 上传静态资源
wrangler kv:key put --binding ASSETS "static/css/style.css" --path static/css/style.css
wrangler kv:key put --binding ASSETS "static/js/app.js" --path static/js/app.js
```

## 💡 推荐方案

### 最简单：GitHub + Render
1. **完全免费**
2. **无需复杂配置**
3. **自动部署**
4. **10分钟完成**

### 最快：Vercel
1. **5分钟部署**
2. **全球CDN**
3. **自动HTTPS**

## 🚀 立即行动

**推荐选择GitHub + Render方案**，最简单易用！

**访问 https://render.com 开始部署！**