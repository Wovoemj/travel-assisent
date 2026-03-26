# Cloudflare Workers 详细部署指南

## 🎯 为什么选择Cloudflare Workers

- ✅ **完全免费**：无需信用卡，每天10万次请求
- ✅ **全球网络**：200+数据中心，访问速度极快
- ✅ **企业级稳定**：Cloudflare是全球知名CDN服务商
- ✅ **自动HTTPS**：免费SSL证书
- ✅ **简单易用**：30分钟完成部署

## 📋 部署前准备

### 需要的账号
1. Cloudflare账号（免费）
2. GitHub账号（免费）

### 需要的工具
1. Node.js（用于安装Wrangler CLI）
2. Git（用于代码管理）

## 🚀 详细部署步骤

### 步骤1：注册Cloudflare账号

1. 访问 https://dash.cloudflare.com/sign-up
2. 输入邮箱和密码
3. 验证邮箱
4. 登录成功

**注意**：完全免费，无需信用卡！

### 步骤2：安装Node.js

1. 访问 https://nodejs.org/
2. 下载LTS版本
3. 安装Node.js
4. 验证安装：
```bash
node --version
npm --version
```

### 步骤3：安装Wrangler CLI

```bash
# 安装Wrangler（Cloudflare Workers CLI）
npm install -g wrangler

# 验证安装
wrangler --version
```

### 步骤4：登录Cloudflare

```bash
# 登录Cloudflare账号
wrangler login
```

这会打开浏览器，授权Wrangler访问您的Cloudflare账号。

### 步骤5：准备项目代码

#### 5.1 创建wrangler.toml配置文件

```toml
name = "travel-assistant"
main = "src/worker.js"
compatibility_date = "2024-01-01"

[vars]
SECRET_KEY = "your-secret-key-here"

[site]
bucket = "./static"
```

#### 5.2 创建src目录结构

```bash
# 创建目录
mkdir -p src
mkdir -p static
```

#### 5.3 创建Worker入口文件

创建 `src/worker.js`：

```javascript
// Cloudflare Worker 入口文件
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    
    // 处理静态文件
    if (url.pathname.startsWith('/static/')) {
      return handleStaticFile(request, env);
    }
    
    // 处理API请求
    if (url.pathname.startsWith('/api/')) {
      return handleAPI(request, env);
    }
    
    // 处理页面请求
    return handlePage(request, env);
  }
};

// 处理静态文件
async function handleStaticFile(request, env) {
  const url = new URL(request.url);
  const path = url.pathname;
  
  // 从KV存储或静态资源获取文件
  const asset = await env.ASSETS.get(path);
  if (asset) {
    const contentType = getContentType(path);
    return new Response(asset, {
      headers: { 'Content-Type': contentType }
    });
  }
  
  return new Response('Not Found', { status: 404 });
}

// 处理API请求
async function handleAPI(request, env) {
  const url = new URL(request.url);
  const path = url.pathname;
  
  // 景点搜索API
  if (path === '/api/search') {
    const query = url.searchParams.get('q') || '';
    const results = await searchDestinations(query, env);
    return Response.json({ success: true, results });
  }
  
  // 天气API
  if (path.startsWith('/api/weather/')) {
    const city = path.split('/').pop();
    const weather = await getWeather(city);
    return Response.json({ success: true, weather });
  }
  
  // 其他API...
  return Response.json({ error: 'API not found' }, { status: 404 });
}

// 处理页面请求
async function handlePage(request, env) {
  // 返回主页面HTML
  const html = await getMainPage(env);
  return new Response(html, {
    headers: { 'Content-Type': 'text/html; charset=utf-8' }
  });
}

// 搜索景点
async function searchDestinations(query, env) {
  // 从KV存储获取景点数据
  const data = await env.DESTINATIONS.get('all', 'json') || [];
  
  if (!query) {
    return data.slice(0, 20);
  }
  
  return data.filter(dest => 
    dest.name.includes(query) || 
    dest.city.includes(query) ||
    dest.description.includes(query)
  ).slice(0, 20);
}

// 获取天气
async function getWeather(city) {
  // 模拟天气数据
  const conditions = ['晴', '多云', '阴', '小雨'];
  return {
    city: city,
    temperature: `${Math.floor(Math.random() * 15 + 15)}°C`,
    condition: conditions[Math.floor(Math.random() * conditions.length)],
    humidity: `${Math.floor(Math.random() * 40 + 40)}%`
  };
}

// 获取主页面
async function getMainPage(env) {
  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>智能旅游助手</title>
    <link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
    <div id="app">
        <header>
            <h1>智能旅游助手</h1>
            <nav>
                <a href="/">首页</a>
                <a href="/chat">智能助手</a>
                <a href="/about">关于</a>
            </nav>
        </header>
        <main>
            <section class="hero">
                <h2>发现中国最美风景</h2>
                <p>您的智能旅行伙伴</p>
                <div class="search-box">
                    <input type="text" id="searchInput" placeholder="搜索景点...">
                    <button onclick="search()">搜索</button>
                </div>
            </section>
            <section class="features">
                <div class="feature">
                    <i class="icon">🔍</i>
                    <h3>智能搜索</h3>
                    <p>快速找到您想去的景点</p>
                </div>
                <div class="feature">
                    <i class="icon">🌤️</i>
                    <h3>天气查询</h3>
                    <p>实时天气信息</p>
                </div>
                <div class="feature">
                    <i class="icon">🗺️</i>
                    <h3>行程规划</h3>
                    <p>智能行程推荐</p>
                </div>
            </section>
            <section class="popular">
                <h3>热门景点</h3>
                <div id="destinations" class="destinations-grid">
                    <!-- 动态加载景点 -->
                </div>
            </section>
        </main>
        <footer>
            <p>© 2024 智能旅游助手</p>
        </footer>
    </div>
    <script src="/static/js/app.js"></script>
</body>
</html>`;
}

// 获取内容类型
function getContentType(path) {
  const ext = path.split('.').pop();
  const types = {
    'html': 'text/html',
    'css': 'text/css',
    'js': 'application/javascript',
    'json': 'application/json',
    'png': 'image/png',
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'gif': 'image/gif',
    'svg': 'image/svg+xml'
  };
  return types[ext] || 'application/octet-stream';
}
```

### 步骤6：创建静态资源

#### 6.1 创建CSS文件

创建 `static/css/style.css`：

```css
/* 基础样式 */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  line-height: 1.6;
  color: #333;
}

/* 头部 */
header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 1rem 2rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

header h1 {
  font-size: 1.5rem;
}

nav a {
  color: white;
  text-decoration: none;
  margin-left: 1.5rem;
}

/* 主内容 */
main {
  max-width: 1200px;
  margin: 0 auto;
  padding: 2rem;
}

/* 英雄区域 */
.hero {
  text-align: center;
  padding: 4rem 0;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-radius: 10px;
  margin-bottom: 2rem;
}

.hero h2 {
  font-size: 2.5rem;
  margin-bottom: 1rem;
}

.search-box {
  display: flex;
  justify-content: center;
  gap: 1rem;
  margin-top: 2rem;
}

.search-box input {
  padding: 1rem;
  font-size: 1rem;
  border: none;
  border-radius: 25px;
  width: 300px;
}

.search-box button {
  padding: 1rem 2rem;
  font-size: 1rem;
  background: #ff6b6b;
  color: white;
  border: none;
  border-radius: 25px;
  cursor: pointer;
}

/* 功能区 */
.features {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 2rem;
  margin: 3rem 0;
}

.feature {
  text-align: center;
  padding: 2rem;
  border: 1px solid #eee;
  border-radius: 10px;
  transition: transform 0.3s;
}

.feature:hover {
  transform: translateY(-5px);
  box-shadow: 0 10px 30px rgba(0,0,0,0.1);
}

.icon {
  font-size: 3rem;
  margin-bottom: 1rem;
  display: block;
}

/* 景点网格 */
.destinations-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1.5rem;
}

.dest-card {
  background: white;
  border-radius: 10px;
  overflow: hidden;
  box-shadow: 0 4px 15px rgba(0,0,0,0.1);
  transition: transform 0.3s;
}

.dest-card:hover {
  transform: translateY(-5px);
}

.dest-card img {
  width: 100%;
  height: 200px;
  object-fit: cover;
}

.dest-info {
  padding: 1rem;
}

.dest-info h4 {
  margin-bottom: 0.5rem;
  color: #333;
}

.dest-info p {
  color: #666;
  font-size: 0.9rem;
}

/* 底部 */
footer {
  text-align: center;
  padding: 2rem;
  background: #f5f5f5;
  margin-top: 3rem;
}

/* 响应式 */
@media (max-width: 768px) {
  header {
    flex-direction: column;
    text-align: center;
  }
  
  nav {
    margin-top: 1rem;
  }
  
  .hero h2 {
    font-size: 1.8rem;
  }
  
  .search-box {
    flex-direction: column;
    align-items: center;
  }
  
  .search-box input {
    width: 100%;
    max-width: 300px;
  }
}
```

#### 6.2 创建JavaScript文件

创建 `static/js/app.js`：

```javascript
// 主应用逻辑
document.addEventListener('DOMContentLoaded', function() {
    loadPopularDestinations();
});

// 搜索景点
function search() {
    const query = document.getElementById('searchInput').value;
    if (!query) {
        alert('请输入搜索关键词');
        return;
    }
    
    fetch(`/api/search?q=${encodeURIComponent(query)}`)
        .then(response => response.json())
        .then(data => {
            displayDestinations(data.results);
        })
        .catch(error => {
            console.error('搜索失败:', error);
            alert('搜索失败，请稍后重试');
        });
}

// 加载热门景点
function loadPopularDestinations() {
    fetch('/api/search')
        .then(response => response.json())
        .then(data => {
            displayDestinations(data.results);
        })
        .catch(error => {
            console.error('加载失败:', error);
        });
}

// 显示景点
function displayDestinations(destinations) {
    const container = document.getElementById('destinations');
    if (!container) return;
    
    container.innerHTML = '';
    
    destinations.forEach(dest => {
        const card = document.createElement('div');
        card.className = 'dest-card';
        card.innerHTML = `
            <img src="${dest.cover_image || '/static/images/placeholder.jpg'}" 
                 alt="${dest.name}" 
                 onerror="this.src='/static/images/placeholder.jpg'">
            <div class="dest-info">
                <h4>${dest.name}</h4>
                <p>${dest.city} · ${dest.category}</p>
                <p>⭐ ${dest.rating}分</p>
            </div>
        `;
        
        card.onclick = () => {
            window.location.href = `/dest/${dest.id}`;
        };
        
        container.appendChild(card);
    });
}

// 回车搜索
document.getElementById('searchInput')?.addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        search();
    }
});
```

### 步骤7：配置wrangler.toml

```toml
name = "travel-assistant"
main = "src/worker.js"
compatibility_date = "2024-01-01"

# 环境变量
[vars]
SECRET_KEY = "your-secret-key-change-this"

# KV存储（用于存储数据）
[[kv_namespaces]]
binding = "DESTINATIONS"
id = "your-kv-namespace-id"

[[kv_namespaces]]
binding = "USERS"
id = "your-users-kv-id"

[[kv_namespaces]]
binding = "ASSETS"
id = "your-assets-kv-id"

# 静态资源配置
[site]
bucket = "./static"
exclude-pattern = ["node_modules/", "src/"]
```

### 步骤8：创建KV存储

```bash
# 创建景点数据KV存储
wrangler kv:namespace create DESTINATIONS

# 创建用户数据KV存储
wrangler kv:namespace create USERS

# 创建静态资源KV存储
wrangler kv:namespace create ASSETS
```

记录返回的namespace ID，更新到wrangler.toml中。

### 步骤9：上传数据到KV存储

```bash
# 上传景点数据
wrangler kv:key put --binding DESTINATIONS "all" --path destinations.json

# 上传静态资源
wrangler kv:key put --binding ASSETS "static/css/style.css" --path static/css/style.css
wrangler kv:key put --binding ASSETS "static/js/app.js" --path static/js/app.js
```

### 步骤10：部署到Cloudflare Workers

```bash
# 部署
wrangler deploy
```

**部署成功后会显示访问地址**：
```
Published travel-assistant (x.xx sec)
  https://travel-assistant.你的用户名.workers.dev
```

## 🔧 配置自定义域名（可选）

### 步骤1：添加域名到Cloudflare

1. 登录Cloudflare Dashboard
2. 点击"添加站点"
3. 输入您的域名
4. 按照提示修改DNS

### 步骤2：配置Workers路由

在wrangler.toml中添加：

```toml
[env.production]
route = "travel.yourdomain.com/*"
```

### 步骤3：重新部署

```bash
wrangler deploy --env production
```

## 🧪 测试部署

### 测试访问
```bash
# 测试主页
curl https://travel-assistant.你的用户名.workers.dev

# 测试API
curl https://travel-assistant.你的用户名.workers.dev/api/search?q=故宫
```

### 检查日志
```bash
# 实时查看日志
wrangler tail
```

## 📊 监控和维护

### 查看统计
- 登录Cloudflare Dashboard
- 进入Workers & Pages
- 查看请求数、错误率等

### 更新代码
```bash
# 修改代码后重新部署
wrangler deploy
```

### 查看日志
```bash
# 查看实时日志
wrangler tail

# 查看特定时间的日志
wrangler tail --since 1h
```

## ⚠️ 注意事项

### 免费额度
- 每天10万次请求
- 每次请求最长30秒执行时间
- 内存限制128MB

### 性能优化
- 使用KV存储缓存数据
- 静态资源使用CDN
- 避免长时间运行的任务

### 安全考虑
- 不要在客户端暴露敏感信息
- 使用环境变量存储密钥
- 定期更新SECRET_KEY

## 🎉 部署完成

**恭喜！您的智能旅游助手已成功部署到Cloudflare Workers！**

### 访问地址
`https://travel-assistant.你的用户名.workers.dev`

### 主要特点
- ✅ 完全免费
- ✅ 全球CDN加速
- ✅ 自动HTTPS
- ✅ 24/7稳定运行
- ✅ 全球任何网络都能访问

### 下一步
1. 测试所有功能
2. 上传更多景点数据
3. 配置自定义域名（可选）
4. 分享给朋友使用

**现在您的网站可以24/7全球访问了！**