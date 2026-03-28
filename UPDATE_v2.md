# 更新日志 - 数据库驱动架构升级

> 更新日期：2026-03-28

---

## 📋 本次更新概览

将项目从前端硬编码数据架构，升级为**全数据库驱动架构**，所有内容通过数据库存储、API 读写、后台管理。

---

## 🗄️ 新增数据库表（8 张）

| 表名 | 说明 | 记录数 | 核心字段 |
|------|------|--------|----------|
| `province` | 全国省份 | 34 | name, code, description, sort_order, is_active |
| `city` | 城市（地级市+县级市+直辖市） | 748 | name, province_name, city_type, latitude, longitude |
| `food` | 各地特色美食 | 97 | name, city, province, description, price_range, restaurants(JSON), category |
| `trip_plan` | 行程模板 | 700 | city, title, days, itinerary(JSON), budget_estimate, best_season |
| `review` | 景点评论（数据库版） | 109 | destination_id, username, rating, content, status |
| `site_config` | 站点配置 | 19 | key, value, value_type, group, label, is_public |
| `navigation` | 导航菜单 | 8 | name, url, icon, position(header/footer), sort_order |
| `banner` | 轮播图 | 3 | title, image_url, link_url, sort_order, is_active |

### 数据来源

- **省份/城市数据**：从 `data/china_locations.py` 的 `ALL_PROVINCES`、`ALL_CITIES`、`CITY_TO_PROVINCE` 迁移
- **美食数据**：从 `data/china_locations.py` 的 `FOOD_DATABASE` 迁移
- **行程模板**：从 `data/china_locations.py` 的 `TRIP_PLANS`、`DEFAULT_TRIP_PLANS` 迁移
- **评论数据**：为景点自动生成初始评论

---

## 🔌 新增 API 接口（45 个）

所有接口以 `/api/v2` 为前缀，遵循 RESTful 规范。

### 通用 CRUD 模式

每个资源都有以下接口：

```
GET    /api/v2/{resource}           → 列表（支持分页、搜索、筛选）
POST   /api/v2/{resource}           → 新增（需管理员权限）
GET    /api/v2/{resource}/<id>      → 详情
PUT    /api/v2/{resource}/<id>      → 更新（需管理员权限）
DELETE /api/v2/{resource}/<id>      → 删除（需管理员权限）
```

### 各资源接口详情

#### 省份 `/api/v2/provinces`

| 方法 | 路径 | 说明 | 参数 |
|------|------|------|------|
| GET | `/api/v2/provinces` | 省份列表 | page, per_page, keyword, is_active |
| POST | `/api/v2/provinces` | 创建省份 | name(必填), code, description, sort_order |
| GET | `/api/v2/provinces/<id>` | 省份详情 | - |
| PUT | `/api/v2/provinces/<id>` | 更新省份 | 任意字段 |
| DELETE | `/api/v2/provinces/<id>` | 删除省份 | - |

#### 城市 `/api/v2/cities`

| 方法 | 路径 | 说明 | 参数 |
|------|------|------|------|
| GET | `/api/v2/cities` | 城市列表 | page, per_page, keyword, province, type |
| POST | `/api/v2/cities` | 创建城市 | name(必填), province_name, city_type, lat, lng |
| GET | `/api/v2/cities/<id>` | 城市详情 | - |
| PUT | `/api/v2/cities/<id>` | 更新城市 | 任意字段 |
| DELETE | `/api/v2/cities/<id>` | 删除城市 | - |

#### 美食 `/api/v2/foods`

| 方法 | 路径 | 说明 | 参数 |
|------|------|------|------|
| GET | `/api/v2/foods` | 美食列表 | page, per_page, keyword, city, province, category |
| POST | `/api/v2/foods` | 创建美食 | name(必填), city, province, description, price_range, restaurants |
| GET | `/api/v2/foods/<id>` | 美食详情 | - |
| PUT | `/api/v2/foods/<id>` | 更新美食 | 任意字段 |
| DELETE | `/api/v2/foods/<id>` | 删除美食 | - |

#### 行程模板 `/api/v2/trip-plans`

| 方法 | 路径 | 说明 | 参数 |
|------|------|------|------|
| GET | `/api/v2/trip-plans` | 模板列表 | page, per_page, city, days, is_default |
| POST | `/api/v2/trip-plans` | 创建模板 | city, title, days(必填), itinerary(JSON) |
| GET | `/api/v2/trip-plans/<id>` | 模板详情 | - |
| PUT | `/api/v2/trip-plans/<id>` | 更新模板 | 任意字段 |
| DELETE | `/api/v2/trip-plans/<id>` | 删除模板 | - |

#### 评论 `/api/v2/reviews`

| 方法 | 路径 | 说明 | 参数 |
|------|------|------|------|
| GET | `/api/v2/reviews` | 评论列表 | page, per_page, destination_id, status, keyword |
| POST | `/api/v2/reviews` | 发表评论 | destination_id, content(必填), rating |
| GET | `/api/v2/reviews/<id>` | 评论详情 | - |
| PUT | `/api/v2/reviews/<id>` | 更新评论 | content, rating, status(管理员) |
| DELETE | `/api/v2/reviews/<id>` | 删除评论 | - |
| POST | `/api/v2/reviews/<id>/approve` | 审核评论 | status: approved/rejected |

#### 站点配置 `/api/v2/configs`

| 方法 | 路径 | 说明 | 参数 |
|------|------|------|------|
| GET | `/api/v2/configs` | 配置列表 | group, is_public |
| GET | `/api/v2/configs/public` | 公开配置（前端可调用） | - |
| POST | `/api/v2/configs` | 创建配置 | key(必填), value, value_type, group |
| GET | `/api/v2/configs/<key>` | 配置详情 | - |
| PUT | `/api/v2/configs/<key>` | 更新配置 | value 等 |
| DELETE | `/api/v2/configs/<key>` | 删除配置 | - |

#### 导航菜单 `/api/v2/navigations`

| 方法 | 路径 | 说明 | 参数 |
|------|------|------|------|
| GET | `/api/v2/navigations` | 导航列表 | position(header/footer/sidebar) |
| POST | `/api/v2/navigations` | 创建导航 | name(必填), url, icon, position |
| PUT | `/api/v2/navigations/<id>` | 更新导航 | 任意字段 |
| DELETE | `/api/v2/navigations/<id>` | 删除导航 | - |

#### 轮播图 `/api/v2/banners`

| 方法 | 路径 | 说明 | 参数 |
|------|------|------|------|
| GET | `/api/v2/banners` | 轮播图列表 | - |
| POST | `/api/v2/banners` | 创建轮播图 | image_url(必填), title, link_url |
| PUT | `/api/v2/banners/<id>` | 更新轮播图 | 任意字段 |
| DELETE | `/api/v2/banners/<id>` | 删除轮播图 | - |

### 聚合接口

| 路径 | 说明 | 返回内容 |
|------|------|----------|
| `/api/v2/home/data` | 首页聚合数据 | 热门景点、好评景点、省份、分类、轮播图、站点配置、统计 |
| `/api/v2/site/info` | 站点公开信息 | 站点名称、描述、联系方式等 |
| `/api/v2/nav/header` | 页头导航 | header 位置的导航列表 |
| `/api/v2/nav/footer` | 页脚导航 | footer 位置的导航列表 |
| `/api/v2/stats/database` | 数据库统计 | 各表记录数（需管理员权限） |
| `/api/v2/batch/update-status` | 批量操作 | 批量启用/禁用/删除 |

---

## 🖥️ 后台管理页面

### 数据管理中心 `/admin/data-manager`

新增统一的数据管理界面，功能包括：

- **统计面板**：顶部卡片展示各表记录数
- **Tab 切换**：省份 / 城市 / 美食 / 行程模板 / 评论 / 站点配置 / 导航 / 轮播图
- **搜索过滤**：关键词搜索
- **分页浏览**：数据表格 + 分页导航
- **新增**：弹窗表单，自动生成字段
- **编辑**：点击编辑按钮，表单回填数据
- **删除**：确认后删除
- **评论审核**：支持 approved / pending / rejected 状态切换

---

## 📁 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `models_extended.py` | 新增 | 8 个数据模型定义（工厂模式） |
| `api_routes_extended.py` | 新增 | 45 个 CRUD API 路由（Blueprint） |
| `migrate_data.py` | 新增 | 数据迁移脚本 |
| `templates/admin/data_manager.html` | 新增 | 后台数据管理页面 |
| `app.py` | 修改 | 集成扩展模型、注册 API 蓝图、新增管理路由 |
| `utils/social_login.py` | 修改 | 修复 redis_client 导入兼容 |

---

## 🔄 数据迁移

迁移脚本 `migrate_data.py` 已执行完毕，将以下数据从 Python 文件导入数据库：

```
Province:   34 条  ← ALL_PROVINCES
City:      748 条  ← ALL_CITIES + COUNTY_CITIES
Food:       97 条  ← FOOD_DATABASE
TripPlan:  700 条  ← TRIP_PLANS + DEFAULT_TRIP_PLANS
Review:    109 条  ← 自动生成
SiteConfig: 19 条  ← 手动初始化
Navigation:  8 条  ← 手动初始化
Banner:      3 条  ← 手动初始化
```

如需重新迁移（清空后重新导入），执行：

```bash
cd travel-assisent
# 删除新表后重新运行迁移
python3 migrate_data.py
```

---

## 🚀 启动方式

```bash
cd travel-assisent
pip install -r requirements.txt
python3 app.py
```

服务默认运行在 `http://0.0.0.0:5000`

---

## 📌 管理员账号

| 用户名 | 密码 | 说明 |
|--------|------|------|
| admin | admin123 | 超级管理员 |

登录地址：`http://localhost:5000/admin/login`

---

## 🔮 后续可扩展方向

- [ ] 前端页面对接 v2 API（替换硬编码）
- [ ] 省份/城市/美食的图片上传
- [ ] 评论的图片上传
- [ ] 数据导入/导出（CSV/Excel）
- [ ] 操作日志审计
- [ ] Redis 缓存层
- [ ] API 限流
