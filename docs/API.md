# 智能旅游助手 API 文档

> Base URL: `http://localhost:5000`
> 交互式文档: `GET /api/docs`

---

## 📋 目录

- [认证 (Auth)](#认证)
- [用户 (User)](#用户)
- [景点 (Destinations)](#景点)
- [搜索 (Search)](#搜索)
- [收藏 (Favorites)](#收藏)
- [评论 (Reviews)](#评论)
- [推荐 (Recommendations)](#推荐)
- [行程 (Trips)](#行程)
- [地图 (Map)](#地图)
- [附近 (Nearby)](#附近)
- [天气/美食 (Weather & Food)](#天气美食)
- [AI 助手 (Assistant)](#ai-助手)
- [AI 管理 (AI Management)](#ai-管理)
- [安全 (Security)](#安全)
- [后台管理 (Admin)](#后台管理)
- [系统 (System)](#系统)
- [调试 (Debug)](#调试)
- [v2 接口](#v2-接口)

---

## 认证

### POST `/api/register`
用户注册 (邮箱)

**Body:** `{ "username": "string", "email": "string", "password": "string", "confirm_password": "string" }`
**Response:** `{ "success": true, "message": "注册成功" }`

### POST `/api/register/phone`
用户注册 (手机号)

**Body:** `{ "phone": "string", "code": "string", "username": "string", "password": "string" }`
**Response:** `{ "success": true }`

### POST `/api/login`
密码登录

**Body:** `{ "username": "string", "password": "string", "remember": false }`
**Response:** `{ "success": true, "user": {...} }`

### POST `/api/login/code`
验证码登录

**Body:** `{ "phone": "string", "code": "string" }`
**Response:** `{ "success": true, "user": {...} }`

### POST `/api/logout`
退出登录

**Response:** `{ "success": true }`

### POST `/api/send_code`
发送验证码

**Body:** `{ "phone": "string" }`
**Response:** `{ "success": true, "debug_code": "123456" }`

### GET `/auth/<provider>`
社交登录跳转 (wechat/qq/weibo)

### GET `/auth/wechat/callback`
### GET `/auth/qq/callback`
### GET `/auth/weibo/callback`
社交登录回调

---

## 用户

### GET `/api/user/status`
获取当前登录状态

**Response:** `{ "logged_in": true, "user": { "id": 1, "username": "xxx" } }`

### GET `/api/user/stats`
获取用户统计 (收藏数、浏览数等)

**Response:** `{ "favorites": 10, "views": 50, "reviews": 5 }`

### POST `/api/user/profile/update`
更新用户资料

**Body:** `{ "nickname": "string", "avatar": "string", "bio": "string" }`

### POST `/api/user/password/change`
修改密码

**Body:** `{ "old_password": "string", "new_password": "string" }`

### POST `/api/user/behavior`
记录用户行为

**Body:** `{ "action": "view", "dest_id": 1, "duration": 30 }`

### GET `/api/user/liked-destinations`
获取用户点赞的景点列表

### GET `/api/user/checkins`
获取用户签到记录

### GET `/api/user/following`
获取关注列表

### GET `/api/user/followers`
获取粉丝列表

### POST `/api/users/<user_id>/follow`
关注/取消关注用户

### GET `/api/users/<user_id>/profile`
获取用户公开资料

### GET `/api/user/export`
导出用户数据 (JSON)

---

## 景点

### GET `/`
首页 (支持分页/筛选)

**Query:** `?page=1&province=北京&category=历史古迹&sort=rating&view=hot`

### GET `/dest/<dest_id>`
景点详情页

### GET `/api/destinations/<dest_id>`
景点详情 API

**Response:** `{ "id": 1, "name": "故宫", "city": "北京", ... }`

### POST `/api/destinations/<dest_id>/like`
点赞景点

### POST `/api/destinations/<dest_id>/checkin`
签到景点

### GET `/api/destinations/<dest_id>/checkins`
获取景点签到列表

---

## 搜索

### GET `/api/search`
搜索景点

**Query:** `?q=故宫&page=1&limit=20`
**Response:** `{ "results": [...], "total": 100, "page": 1 }`

### GET `/api/search/suggestions`
搜索建议 (支持拼音)

**Query:** `?q=gugong&limit=8`
**Response:** `{ "suggestions": [{ "type": "destination", "name": "故宫", ... }] }`

### GET `/api/search/history`
获取搜索历史

### POST `/api/search/history/clear`
清空搜索历史

### POST `/api/search/history/remove`
删除单条搜索历史

**Body:** `{ "query": "故宫" }`

### GET `/api/click/history`
获取浏览历史

### POST `/api/click/history/clear`
清空浏览历史

---

## 收藏

### POST `/api/favorite/add`
添加收藏

**Body:** `{ "dest_id": 1 }`

### POST `/api/favorite/remove`
取消收藏

**Body:** `{ "dest_id": 1 }`

### GET `/api/favorite/list`
获取收藏列表

**Query:** `?page=1&limit=20`

### GET `/api/favorite/check/<dest_id>`
检查是否已收藏

**Response:** `{ "favorited": true }`

### POST `/api/favorite/batch`
批量收藏操作

**Body:** `{ "action": "add", "dest_ids": [1, 2, 3] }`

---

## 评论

### GET `/api/reviews/<dest_id>`
获取景点评论

**Query:** `?page=1&limit=10&sort=newest`

### POST `/api/reviews/<dest_id>/add`
添加评论

**Body:** `{ "content": "非常好!", "rating": 5 }`

### POST `/api/reviews/<dest_id>/edit`
编辑评论

**Body:** `{ "content": "修改后的内容", "rating": 4 }`

### GET `/reviews/<dest_id>`
评论页

---

## 推荐

### GET `/api/recommendations/personalized`
个性化推荐

**Query:** `?limit=10`

### GET `/api/recommendations/collaborative`
协同过滤推荐

**Query:** `?limit=10`

### GET `/api/recommendations/hot`
热门推荐

**Query:** `?limit=10&category=自然景观`

### GET `/api/recommendations/similar/<dest_id>`
相似景点推荐

**Query:** `?limit=5`

---

## 行程

### GET `/api/trips`
获取行程列表

### POST `/api/trips`
创建行程

**Body:** `{ "title": "北京三日游", "start_date": "2024-05-01", "end_date": "2024-05-03", "destinations": [1, 2, 3] }`

### GET `/api/trips/<trip_id>`
获取行程详情

### PUT `/api/trips/<trip_id>`
更新行程

### DELETE `/api/trips/<trip_id>`
删除行程

### POST `/api/trips/<trip_id>/items`
添加行程项

**Body:** `{ "dest_id": 1, "day": 1, "start_time": "09:00", "end_time": "12:00", "notes": "早上去" }`

### PUT `/api/trips/<trip_id>/items/<item_id>`
更新行程项

### DELETE `/api/trips/<trip_id>/items/<item_id>`
删除行程项

### GET `/api/trips/share/<share_code>`
获取分享的行程

### POST `/api/trips/<trip_id>/share`
生成分享链接

### POST `/api/trips/recommend`
AI 推荐行程

**Body:** `{ "city": "北京", "days": 3, "preferences": ["历史", "美食"] }`

### GET `/api/trips/<trip_id>/export/pdf`
导出行程 PDF

### GET `/api/trips/<trip_id>/export/image`
导出行程图片

---

## 地图

### GET `/api/map/destinations`
获取景点坐标列表

**Query:** `?province=北京&category=历史古迹`

### POST `/api/map/route`
规划路线

**Body:** `{ "origin": [116.4, 39.9], "destination": [116.5, 39.8], "mode": "driving" }`

### GET `/api/map/nearby`
地图附近景点

**Query:** `?lng=116.4&lat=39.9&radius=5000`

### POST `/api/map/geocode`
地址转坐标

**Body:** `{ "address": "北京市故宫" }`

### POST `/api/map/reverse-geocode`
坐标转地址

**Body:** `{ "lng": 116.4, "lat": 39.9 }`

---

## 附近

### GET `/api/nearby/search`
附近搜索

**Query:** `?lng=116.4&lat=39.9&radius=5000&category=美食&page=1`

### GET `/api/nearby/categories`
附近分类列表

### GET `/api/nearby/destination/<dest_id>`
景点附近信息

---

## 天气美食

### GET `/api/weather/<city>`
获取城市天气

### GET `/api/weather/forecast/<city>`
获取天气预报 (7天)

### GET `/api/food/<city>`
获取城市美食

### GET `/api/food/search`
搜索美食

**Query:** `?q=火锅&city=北京`

---

## AI 助手

### POST `/api/assistant`
对话接口

**Body:** `{ "message": "北京有哪些景点?", "session_id": "abc123" }`
**Response:** `{ "reply": "北京有很多著名景点...", "suggestions": ["故宫", "长城"] }`

### POST `/api/assistant/stream`
流式对话 (SSE)

**Body:** `{ "message": "介绍一下故宫", "session_id": "abc123" }`
**Response:** `text/event-stream`

### GET `/api/assistant/history/<session_id>`
获取对话历史

### GET `/api/assistant/tools`
获取可用工具列表

### POST `/api/assistant/context`
设置对话上下文

**Body:** `{ "session_id": "abc123", "context": {...} }`

---

## AI 管理

### GET `/api/ai/status`
AI 服务状态

**Response:** `{ "enabled": true, "provider": "deepseek", "available": true }`

### POST `/api/ai/toggle`
开关 AI 模式

**Body:** `{ "enabled": true }`

### GET `/api/ai/providers`
获取可用 AI 提供商列表

### POST `/api/ai/switch-provider`
切换 AI 提供商

**Body:** `{ "provider": "deepseek" }`

### POST `/api/ai/test`
测试 AI 连接

**Body:** `{ "provider": "deepseek" }`

### POST `/api/ai/stream-test`
测试 AI 流式输出

### GET `/api/ai/config`
获取 AI 配置 (脱敏)

---

## 安全

### POST `/api/security/check-password`
检查密码强度

**Body:** `{ "password": "string" }`
**Response:** `{ "strength": "strong", "score": 85, "suggestions": [] }`

### POST `/api/security/validate-csrf`
验证 CSRF Token

### GET `/api/security/login-attempts`
获取登录尝试次数

### POST `/api/login/secure`
安全登录 (带频率限制)

### POST `/api/security/sanitize-input`
输入消毒测试

### GET `/api/security/rate-limit-check`
检查速率限制状态

---

## 后台管理

### GET/POST `/admin/login`
管理员登录

### GET `/admin/logout`
管理员登出

### GET `/admin`
后台首页 (仪表盘)

### GET `/admin/destinations`
景点管理页

### GET `/admin/users`
用户管理页

### GET `/api/admin/destinations`
获取景点列表 (后台)

**Query:** `?page=1&limit=20&search=故宫`

### POST `/api/admin/destinations`
创建景点

### GET `/api/admin/destinations/<dest_id>`
获取景点详情

### PUT `/api/admin/destinations/<dest_id>`
更新景点

### DELETE `/api/admin/destinations/<dest_id>`
删除景点

### GET `/api/admin/users`
获取用户列表 (后台)

### GET `/api/admin/users/<user_id>`
获取用户详情

### PUT `/api/admin/users/<user_id>`
更新用户

### DELETE `/api/admin/users/<user_id>`
删除用户

### GET `/admin/reset-admin`
重置管理员账号

---

## 系统

### GET `/api/system/health`
健康检查

**Response:** `{ "status": "ok", "uptime": 86400, "db": "ok", "ai": "ok" }`

### GET `/api/mobile/config`
移动端配置

### GET `/api/performance/stats`
性能统计

### GET `/api/random-background`
随机背景图片

### GET `/api/backgrounds/batch`
批量获取背景图片

**Query:** `?count=4`

---

## 调试

> ⚠️ 仅在 DEBUG_MODE=true 时可用

### GET `/api/debug/images`
图片资源调试

### GET `/api/debug/stats`
系统统计

### GET `/api/debug/users`
用户列表调试

### POST `/api/debug/create-test-user`
创建测试用户

### POST `/api/debug/create-frontend-admin`
创建前端管理员

### GET `/api/test/assistant`
测试助手接口

### GET `/api/test/tools`
测试工具列表

### GET `/api/test/stream`
测试流式输出

### GET `/api/test/destination-detail`
测试景点详情

### GET `/test-login`
测试登录页面

---

## v2 接口

### GET `/api/v2/site/info`
站点信息

### GET `/api/v2/nav/header`
头部导航

### GET `/api/v2/nav/footer`
底部导航

### GET `/api/v2/home/data`
首页数据 (聚合接口)

---

## 错误码

| 状态码 | 含义 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 401 | 未登录 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 429 | 请求过于频繁 |
| 500 | 服务器内部错误 |
