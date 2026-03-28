# 智能旅游助手 - 项目总结文档

## 📋 项目概述

基于 Flask + SQLAlchemy + SQLite 的智能旅游助手系统，提供景点查询、智能对话、行程规划等功能。支持后台管理对数据库的实时增删改查，数据变更即时推送到前端。

---

## 🗂️ 项目结构

```
travel-assisent/
├── app.py                    # 主应用入口（Flask 路由 + 数据库模型 + SocketIO）
├── config.py                 # 应用配置（数据库、密钥、AI设置）
├── requirements.txt          # Python 依赖
├── destinations.json         # 景点数据源（JSON）
├── gaode_api.py              # 高德地图 API 封装
├── ai_model_manager.py       # AI 大模型管理（OpenAI/Claude/文心等）
├── wiki_image_provider.py    # 维基百科图片获取
├── models_extended.py        # 扩展数据库模型（省份/城市/美食/配置等）
├── api_routes_extended.py    # 扩展 API 路由（v2 接口）
├── data/
│   └── china_locations.py    # 中国地理数据（省份/城市/美食/行程模板）
├── static/
│   ├── css/                  # 样式文件
│   ├── js/                   # JavaScript 文件
│   └── images/               # 静态图片（默认背景、占位图）
├── scenic_images/            # 景点图片库（1430+ 景点文件夹）
├── templates/
│   ├── base.html             # 前台基础模板
│   ├── index.html            # 首页（景点列表/搜索/筛选）
│   ├── dest_detail.html      # 景点详情页
│   ├── chat.html             # 智能助手对话页
│   ├── login.html            # 用户登录
│   ├── register.html         # 用户注册
│   ├── profile.html          # 个人中心
│   ├── reviews.html          # 评论页
│   ├── about.html            # 关于页
│   └── admin_new/            # 后台管理页面
│       ├── base.html         # 后台基础模板（侧边栏导航）
│       ├── login.html        # 管理员登录
│       ├── dashboard.html    # 仪表盘（数据概览）
│       ├── destinations.html # 景点 CRUD 管理
│       └── users.html        # 用户 CRUD 管理
├── utils/
│   ├── __init__.py
│   └── social_login.py       # 社交登录（微信/QQ/微博）
└── instance/                 # SQLite 数据库文件目录
```

---

## 🗄️ 数据库模型

### 核心模型

| 模型 | 表名 | 说明 |
|------|------|------|
| `Destination` | destination | 景点（名称/城市/省份/分类/评分/坐标等） |
| `User` | user | 用户（用户名/邮箱/密码/收藏/历史等） |
| `Conversation` | conversation | 对话记录（会话ID/消息历史/上下文） |
| `Admin` | admin | 管理员（用户名/密码/创建时间） |

### 扩展模型（models_extended.py）

| 模型 | 说明 |
|------|------|
| `Province` | 省份 |
| `City` | 城市 |
| `Food` | 美食 |
| `TripPlan` | 行程模板 |
| `Review` | 评论 |
| `SiteConfig` | 站点配置 |
| `Banner` | 轮播图 |
| `Navigation` | 导航菜单 |

---

## 🔌 API 接口

### 前台 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 首页（景点列表） |
| GET | `/dest/<id>` | 景点详情 |
| GET | `/chat` | 智能助手 |
| POST | `/api/register` | 用户注册 |
| POST | `/api/login` | 用户登录 |
| POST | `/api/logout` | 用户登出 |
| GET | `/api/search` | 搜索景点 |
| GET | `/api/search/suggestions` | 搜索建议（支持拼音） |
| POST | `/api/assistant` | 智能助手对话 |
| GET | `/api/weather/<city>` | 天气查询 |
| GET | `/api/food/<city>` | 美食查询 |
| POST | `/api/favorite/add` | 添加收藏 |
| POST | `/api/favorite/remove` | 取消收藏 |
| GET | `/api/favorite/list` | 收藏列表 |
| GET | `/api/reviews/<dest_id>` | 获取评论 |
| POST | `/api/reviews/<dest_id>/add` | 添加评论 |
| GET | `/api/destinations/<id>` | 景点详情 JSON |
| GET | `/api/recommendations/personalized` | 个性化推荐 |
| GET | `/api/recommendations/hot` | 热门推荐 |
| GET | `/api/recommendations/similar/<id>` | 相似推荐 |

### 后台管理 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | `/admin/login` | 管理员登录 |
| GET | `/admin` | 管理后台首页 |
| GET | `/admin/destinations` | 景点管理页面 |
| GET | `/admin/users` | 用户管理页面 |
| GET | `/api/admin/destinations` | 获取景点列表（分页/搜索/筛选） |
| POST | `/api/admin/destinations` | 创建景点 |
| GET | `/api/admin/destinations/<id>` | 获取单个景点 |
| PUT | `/api/admin/destinations/<id>` | 更新景点 |
| DELETE | `/api/admin/destinations/<id>` | 删除景点 |
| GET | `/api/admin/users` | 获取用户列表（分页/搜索） |
| GET | `/api/admin/users/<id>` | 获取单个用户 |
| PUT | `/api/admin/users/<id>` | 更新用户 |
| DELETE | `/api/admin/users/<id>` | 删除用户 |

### SocketIO 实时事件

| 事件 | 方向 | 说明 |
|------|------|------|
| `connect` | 客户端→服务端 | 连接时发送欢迎消息 |
| `user_message` | 客户端→服务端 | 用户发送消息 |
| `assistant_response` | 服务端→客户端 | 助手回复 |
| `assistant_typing` | 服务端→客户端 | 正在输入提示 |
| `data_updated` | 服务端→所有客户端 | 数据变更通知（景点/用户） |
| `request_refresh` | 客户端→服务端 | 请求刷新数据 |

---

## ⚙️ 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | Flask 2.x |
| 数据库 | SQLite + SQLAlchemy ORM |
| 实时通信 | Flask-SocketIO |
| 模板引擎 | Jinja2 |
| 前端框架 | Bootstrap 5 |
| 缓存 | Flask-Caching |
| 压缩 | Flask-Compress |
| 天气 API | 心知天气 |
| 地图 API | 高德地图 |
| AI 模型 | OpenAI / Claude / 文心一言 / 通义千问 / 智谱 |

---

## 🚀 启动方式

### 安装依赖
```bash
pip install -r requirements.txt
```

### 启动服务
```bash
python app.py
```

### 访问地址
- **前台**: http://localhost:5000
- **后台管理**: http://localhost:5000/admin/login
- **管理员账号**: admin / admin123

### 网络访问
启动时会自动显示本机 IP，移动设备可通过同一局域网访问：
```
http://<本机IP>:5000
```

---

## 🔄 数据交互流程

```
┌─────────────┐     HTTP/AJAX      ┌─────────────┐
│   前台页面   │ ◄────────────────► │  Flask API  │
│  (浏览器)    │                    │  (app.py)   │
└──────┬──────┘                    └──────┬──────┘
       │                                  │
       │  SocketIO (实时推送)              │
       │  ┌─────────────────────┐         │
       ├─►│  data_updated 事件  │ ◄───────┤
       │  │  - destinations     │         │
       │  │  - users            │         │
       │  └─────────────────────┘         │
       │                                  │
       │         ┌─────────────┐          │
       │         │   SQLite    │          │
       │         │  数据库     │ ◄────────┘
       │         └─────────────┘          │
       │                                  │
┌──────┴──────┐                    ┌──────┴──────┐
│  后台管理    │     CRUD API      │  SQLAlchemy │
│ (admin_new)  │ ─────────────────►│   ORM 层    │
└─────────────┘                    └─────────────┘
```

**实时更新机制：**
1. 管理员在后台执行增删改操作
2. Flask 处理请求并更新数据库
3. 通过 SocketIO 广播 `data_updated` 事件
4. 前台浏览器监听事件，自动刷新对应数据区域
5. 用户无需手动刷新页面即可看到最新数据

---

## 📝 关键配置（config.py）

| 配置项 | 说明 |
|--------|------|
| `SECRET_KEY` | Flask 密钥 |
| `SQLALCHEMY_DATABASE_URI` | 数据库连接（默认 SQLite） |
| `AI_MODE_ENABLED` | 是否启用 AI 大模型模式 |
| `OPENAI_API_KEY` | OpenAI API 密钥 |
| `CLAUDE_API_KEY` | Claude API 密钥 |

环境变量可通过 `.env` 文件配置。

---

## 🧹 已清理文件

以下文件因与核心功能无关已被删除：

| 文件/目录 | 原因 |
|-----------|------|
| `cloudflared.exe` | Cloudflare 隧道二进制，未使用 |
| `wrangler.toml` | Cloudflare Workers 配置，未使用 |
| `src/` | Cloudflare Workers 代码，未使用 |
| `local-mcps/` | MCP 配置目录，未使用 |
| `models.py` | 空壳兼容文件，未被引用 |
| `performance_config.py` | 性能配置，未被引用 |
| `config.yml` | YAML 配置，未被引用 |
| `migrate_data.py` | 一次性迁移脚本 |
| `images/` | 根目录重复图片，与 `scenic_images/` 冗余 |
| `__pycache__/` | Python 编译缓存 |
| 各种 `.md` 部署文档 | Cloudflare/Firewall/Network 等指南 |
| 各种 `.bat`/`.sh` 脚本 | 部署/诊断/启动脚本 |
| `Dockerfile`/`Procfile` | 容器/Heroku 配置 |
| `templates/admin/` | 旧版后台管理（已由 admin_new 替代） |
