#!/usr/bin/env python3
"""
数据迁移脚本
将 python 硬编码数据迁移到数据库
用法: python migrate_data.py
"""
import sys
import os
import json
import random

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# 创建临时 Flask 应用
app = Flask(__name__)
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'travel_destinations.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ============ 模型定义（与 models_extended.py 一致） ============

class Province(db.Model):
    __tablename__ = 'province'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    code = db.Column(db.String(10))
    description = db.Column(db.Text)
    cover_image = db.Column(db.String(500))
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: __import__('datetime').datetime.now())
    updated_at = db.Column(db.DateTime, default=lambda: __import__('datetime').datetime.now())

class City(db.Model):
    __tablename__ = 'city'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    province_id = db.Column(db.Integer, db.ForeignKey('province.id'))
    province_name = db.Column(db.String(50))
    city_type = db.Column(db.String(20), default='地级市')
    description = db.Column(db.Text)
    cover_image = db.Column(db.String(500))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: __import__('datetime').datetime.now())
    updated_at = db.Column(db.DateTime, default=lambda: __import__('datetime').datetime.now())

class Food(db.Model):
    __tablename__ = 'food'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    city = db.Column(db.String(100))
    province = db.Column(db.String(50))
    description = db.Column(db.Text)
    price_range = db.Column(db.String(100))
    restaurants = db.Column(db.Text)
    cover_image = db.Column(db.String(500))
    category = db.Column(db.String(50))
    rating = db.Column(db.Float, default=4.5)
    popularity_score = db.Column(db.Float, default=50.0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: __import__('datetime').datetime.now())
    updated_at = db.Column(db.DateTime, default=lambda: __import__('datetime').datetime.now())

class TripPlan(db.Model):
    __tablename__ = 'trip_plan'
    id = db.Column(db.Integer, primary_key=True)
    city = db.Column(db.String(100), nullable=False)
    province = db.Column(db.String(50))
    title = db.Column(db.String(200), nullable=False)
    days = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text)
    itinerary = db.Column(db.Text)
    budget_estimate = db.Column(db.String(100))
    best_season = db.Column(db.String(100))
    cover_image = db.Column(db.String(500))
    is_default = db.Column(db.Boolean, default=False)
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: __import__('datetime').datetime.now())
    updated_at = db.Column(db.DateTime, default=lambda: __import__('datetime').datetime.now())

class Review(db.Model):
    __tablename__ = 'review'
    id = db.Column(db.Integer, primary_key=True)
    destination_id = db.Column(db.Integer)  # 移除外键约束，destination 表已在 app.py 中定义
    user_id = db.Column(db.Integer)
    username = db.Column(db.String(80), nullable=False)
    rating = db.Column(db.Float, nullable=False)
    content = db.Column(db.Text, nullable=False)
    images = db.Column(db.Text, default='[]')
    likes = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='approved')
    created_at = db.Column(db.DateTime, default=lambda: __import__('datetime').datetime.now())
    updated_at = db.Column(db.DateTime, default=lambda: __import__('datetime').datetime.now())

class SiteConfig(db.Model):
    __tablename__ = 'site_config'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)
    value_type = db.Column(db.String(20), default='string')
    group = db.Column(db.String(50), default='general')
    label = db.Column(db.String(200))
    description = db.Column(db.Text)
    is_public = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: __import__('datetime').datetime.now())
    updated_at = db.Column(db.DateTime, default=lambda: __import__('datetime').datetime.now())

class Banner(db.Model):
    __tablename__ = 'banner'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    image_url = db.Column(db.String(500), nullable=False)
    link_url = db.Column(db.String(500))
    link_type = db.Column(db.String(20), default='url')
    link_id = db.Column(db.Integer)
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=lambda: __import__('datetime').datetime.now())
    updated_at = db.Column(db.DateTime, default=lambda: __import__('datetime').datetime.now())

class Navigation(db.Model):
    __tablename__ = 'navigation'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(500))
    icon = db.Column(db.String(100))
    parent_id = db.Column(db.Integer)  # 移除自引用外键
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    position = db.Column(db.String(20), default='header')
    created_at = db.Column(db.DateTime, default=lambda: __import__('datetime').datetime.now())
    updated_at = db.Column(db.DateTime, default=lambda: __import__('datetime').datetime.now())

# ============ 导入数据 ============
from data.china_locations import (
    ALL_PROVINCES, ALL_CITIES, COUNTY_CITIES,
    FOOD_DATABASE, TRIP_PLANS, DEFAULT_TRIP_PLANS,
    WEATHER_DATA, CITY_MAPPING, CITY_TO_PROVINCE
)


def migrate_provinces():
    """迁移省份数据"""
    print("\n📍 迁移省份数据...")
    count = 0
    for i, name in enumerate(ALL_PROVINCES):
        if not Province.query.filter_by(name=name).first():
            p = Province(name=name, sort_order=i, is_active=True)
            db.session.add(p)
            count += 1
    db.session.commit()
    print(f"   ✅ 导入 {count} 个省份（共 {Province.query.count()} 个）")
    return Province.query.all()


def migrate_cities(provinces):
    """迁移城市数据"""
    print("\n🏙️ 迁移城市数据...")
    province_map = {p.name: p.id for p in provinces}
    count = 0

    # 直辖市
    direct_cities = ['北京', '上海', '天津', '重庆']

    for city_name in ALL_CITIES:
        clean_name = city_name.replace('市', '').replace('地区', '').replace('林区', '')

        if City.query.filter_by(name=clean_name).first():
            continue

        # 查找省份
        prov_name = CITY_TO_PROVINCE.get(city_name, '')

        # 判断城市类型
        if city_name in direct_cities:
            city_type = '直辖市'
            prov_name = city_name
        elif '自治州' in city_name:
            city_type = '自治州'
        elif '地区' in city_name:
            city_type = '地区'
        else:
            city_type = '地级市'

        prov_id = province_map.get(prov_name)

        c = City(
            name=clean_name,
            province_id=prov_id,
            province_name=prov_name,
            city_type=city_type,
            is_active=True
        )
        db.session.add(c)
        count += 1

        if count % 50 == 0:
            db.session.commit()
            print(f"   ⏳ 已导入 {count} 个城市...")

    # 县级市
    for city_name in COUNTY_CITIES:
        clean_name = city_name.replace('市', '')
        if City.query.filter_by(name=clean_name).first():
            continue

        prov_name = CITY_TO_PROVINCE.get(city_name, '')
        prov_id = province_map.get(prov_name)

        c = City(
            name=clean_name,
            province_id=prov_id,
            province_name=prov_name,
            city_type='县级市',
            is_active=True
        )
        db.session.add(c)
        count += 1

    db.session.commit()
    print(f"   ✅ 导入 {count} 个城市（共 {City.query.count()} 个）")


def migrate_foods():
    """迁移美食数据"""
    print("\n🍜 迁移美食数据...")
    count = 0

    # 分类关键词
    category_keywords = {
        '小吃': ['面', '包', '粉', '饼', '串', '汤', '豆腐', '凉皮', '凉粉'],
        '甜品': ['奶', '糖', '糕', '甜', '酥'],
        '饮品': ['茶', '酒', '饮', '汁', '奶'],
        '正餐': []
    }

    def guess_category(name):
        for cat, keywords in category_keywords.items():
            for kw in keywords:
                if kw in name:
                    return cat
        return '正餐'

    for location, foods in FOOD_DATABASE.items():
        for food_data in foods:
            if Food.query.filter_by(name=food_data['name'], city=location).first():
                continue

            restaurants = food_data.get('restaurants', [])
            f = Food(
                name=food_data['name'],
                city=location,
                province=location if location in ALL_PROVINCES else '',
                description=food_data.get('description', ''),
                price_range=food_data.get('price', ''),
                restaurants=json.dumps(restaurants, ensure_ascii=False),
                category=guess_category(food_data['name']),
                rating=round(random.uniform(4.0, 5.0), 1),
                popularity_score=round(random.uniform(40, 90), 1),
                is_active=True
            )
            db.session.add(f)
            count += 1

            if count % 20 == 0:
                db.session.commit()

    db.session.commit()
    print(f"   ✅ 导入 {count} 条美食（共 {Food.query.count()} 条）")


def migrate_trip_plans():
    """迁移行程模板"""
    print("\n🗺️ 迁移行程模板...")
    count = 0

    for city, plans in TRIP_PLANS.items():
        for day_key, items in plans.items():
            # 解析天数
            days = 1
            for d in range(1, 8):
                if f'{d}日游' in day_key:
                    days = d
                    break

            if TripPlan.query.filter_by(city=city, title=day_key).first():
                continue

            tp = TripPlan(
                city=city,
                province=CITY_TO_PROVINCE.get(city, ''),
                title=f'{city}{day_key}',
                days=days,
                description=f'{city}{day_key}推荐行程',
                itinerary=json.dumps(items, ensure_ascii=False),
                is_default=False,
                is_active=True
            )
            db.session.add(tp)
            count += 1

    # 默认行程模板
    for day_key, items in DEFAULT_TRIP_PLANS.items():
        days = 1
        for d in range(1, 8):
            if f'{d}日游' in day_key:
                days = d
                break

        if TripPlan.query.filter_by(city='通用', title=day_key, is_default=True).first():
            continue

        tp = TripPlan(
            city='通用',
            title=f'通用{day_key}',
            days=days,
            description=f'通用{day_key}模板',
            itinerary=json.dumps(items, ensure_ascii=False),
            is_default=True,
            is_active=True
        )
        db.session.add(tp)
        count += 1

    db.session.commit()
    print(f"   ✅ 导入 {count} 条行程模板（共 {TripPlan.query.count()} 条）")


def migrate_site_config():
    """初始化站点配置"""
    print("\n⚙️ 初始化站点配置...")
    configs = [
        {'key': 'site_name', 'value': '智能旅游助手', 'label': '站点名称', 'group': 'general', 'is_public': True},
        {'key': 'site_description', 'value': '您的智能旅行伙伴，提供景点查询、行程规划、天气查询等一站式旅游服务', 'label': '站点描述', 'group': 'general', 'is_public': True},
        {'key': 'site_keywords', 'value': '旅游,景点,行程规划,天气查询,美食推荐', 'label': 'SEO关键词', 'group': 'general', 'is_public': True},
        {'key': 'site_logo', 'value': '/static/images/logo.png', 'label': '站点Logo', 'group': 'ui', 'is_public': True},
        {'key': 'site_favicon', 'value': '/static/images/favicon.ico', 'label': 'Favicon', 'group': 'ui', 'is_public': True},
        {'key': 'contact_email', 'value': 'admin@travel.com', 'label': '联系邮箱', 'group': 'general', 'is_public': True},
        {'key': 'contact_phone', 'value': '400-123-4567', 'label': '联系电话', 'group': 'general', 'is_public': True},
        {'key': 'icp_number', 'value': '', 'label': 'ICP备案号', 'group': 'general', 'is_public': True},
        {'key': 'enable_register', 'value': 'true', 'value_type': 'bool', 'label': '开放注册', 'group': 'general'},
        {'key': 'enable_social_login', 'value': 'true', 'value_type': 'bool', 'label': '社交登录', 'group': 'general'},
        {'key': 'enable_chat', 'value': 'true', 'value_type': 'bool', 'label': '智能助手', 'group': 'general'},
        {'key': 'enable_review', 'value': 'true', 'value_type': 'bool', 'label': '评论功能', 'group': 'general'},
        {'key': 'enable_weather', 'value': 'true', 'value_type': 'bool', 'label': '天气查询', 'group': 'general'},
        {'key': 'default_page_size', 'value': '12', 'value_type': 'int', 'label': '默认每页条数', 'group': 'ui'},
        {'key': 'hot_destinations_count', 'value': '10', 'value_type': 'int', 'label': '热门景点数量', 'group': 'ui'},
        {'key': 'seniverse_api_key', 'value': 'SlwyrUvFR5pMbWwOg', 'label': '心知天气API Key', 'group': 'api'},
        {'key': 'gaode_api_key', 'value': 'c819cfec11f53d9fa4e022a8fb1b5c48', 'label': '高德API Key', 'group': 'api'},
        {'key': 'ai_mode_enabled', 'value': 'false', 'value_type': 'bool', 'label': 'AI大模型模式', 'group': 'api'},
        {'key': 'default_ai_provider', 'value': 'deepseek', 'label': '默认AI提供商', 'group': 'api'},
    ]

    count = 0
    for cfg in configs:
        if not SiteConfig.query.filter_by(key=cfg['key']).first():
            sc = SiteConfig(
                key=cfg['key'],
                value=cfg['value'],
                value_type=cfg.get('value_type', 'string'),
                group=cfg.get('group', 'general'),
                label=cfg.get('label', cfg['key']),
                is_public=cfg.get('is_public', False)
            )
            db.session.add(sc)
            count += 1

    db.session.commit()
    print(f"   ✅ 导入 {count} 条配置（共 {SiteConfig.query.count()} 条）")


def migrate_navigations():
    """初始化导航菜单"""
    print("\n📋 初始化导航菜单...")
    navs = [
        {'name': '首页', 'url': '/', 'icon': '🏠', 'sort_order': 1, 'position': 'header'},
        {'name': '热门景点', 'url': '/?view=hot', 'icon': '🔥', 'sort_order': 2, 'position': 'header'},
        {'name': '智能助手', 'url': '/chat', 'icon': '🤖', 'sort_order': 3, 'position': 'header'},
        {'name': '关于我们', 'url': '/about', 'icon': 'ℹ️', 'sort_order': 4, 'position': 'header'},
        {'name': '后台管理', 'url': '/admin', 'icon': '⚙️', 'sort_order': 5, 'position': 'header'},
        {'name': '隐私政策', 'url': '/privacy', 'icon': '', 'sort_order': 1, 'position': 'footer'},
        {'name': '使用条款', 'url': '/terms', 'icon': '', 'sort_order': 2, 'position': 'footer'},
        {'name': '联系我们', 'url': '/contact', 'icon': '', 'sort_order': 3, 'position': 'footer'},
    ]

    count = 0
    for nav in navs:
        if not Navigation.query.filter_by(name=nav['name']).first():
            n = Navigation(
                name=nav['name'],
                url=nav['url'],
                icon=nav.get('icon', ''),
                sort_order=nav.get('sort_order', 0),
                position=nav.get('position', 'header'),
                is_active=True
            )
            db.session.add(n)
            count += 1

    db.session.commit()
    print(f"   ✅ 导入 {count} 条导航（共 {Navigation.query.count()} 条）")


def migrate_reviews():
    """为景点生成评论数据"""
    print("\n💬 迁移评论数据...")

    from sqlalchemy import text
    # 直接用 SQL 查询 destination 表
    try:
        result = db.session.execute(text("SELECT id, name FROM destination LIMIT 20"))
        destinations = [{'id': r[0], 'name': r[1]} for r in result.fetchall()]
    except Exception as e:
        print(f"   ⚠️ 查询 destination 表失败: {e}，跳过评论迁移")
        return

    review_templates = [
        "非常值得一去的景点，景色优美，环境整洁，服务态度也很好。",
        "性价比很高，门票价格合理，里面的设施也很完善。",
        "人有点多，但是景色确实不错，拍照很出片。",
        "交通便利，停车方便，适合全家出游。",
        "风景如画，空气清新，是个放松身心的好地方。",
        "历史底蕴深厚，导游讲解很详细，学到了很多知识。",
        "餐饮价格略贵，但景点本身很棒，推荐大家来看看。",
        "最佳旅游季节来玩的，景色果然名不虚传。",
        "景区管理规范，卫生状况良好，体验很不错。",
        "带父母来的，他们非常喜欢，拍了很多照片。",
        "孩子特别喜欢，玩得很开心，下次还会再来。",
        "建议避开节假日，人太多了，影响体验。",
        "景色很美，但景区内指示牌不够清晰，容易迷路。",
    ]

    usernames = ["旅行者", "背包客", "摄影师", "美食家", "探险家",
                 "自由行", "徒步者", "自驾游", "度假达人", "风景控"]

    count = 0
    for dest in destinations:
        # 检查是否已有评论
        existing = Review.query.filter_by(destination_id=dest['id']).count()
        if existing > 0:
            continue

        num_reviews = random.randint(3, 8)
        for _ in range(num_reviews):
            r = Review(
                destination_id=dest['id'],
                username=random.choice(usernames) + str(random.randint(1, 99)),
                rating=round(random.uniform(3.5, 5.0), 1),
                content=random.choice(review_templates),
                likes=random.randint(0, 30),
                status='approved'
            )
            db.session.add(r)
            count += 1

        if count % 50 == 0:
            db.session.commit()

    db.session.commit()
    print(f"   ✅ 导入 {count} 条评论（共 {Review.query.count()} 条）")


def migrate_banners():
    """初始化轮播图"""
    print("\n🖼️ 初始化轮播图...")
    banners = [
        {'title': '探索中国美景', 'image_url': '/static/images/banner1.jpg', 'sort_order': 1},
        {'title': '智能行程规划', 'image_url': '/static/images/banner2.jpg', 'sort_order': 2},
        {'title': '发现特色美食', 'image_url': '/static/images/banner3.jpg', 'sort_order': 3},
    ]

    count = 0
    for b in banners:
        if not Banner.query.filter_by(title=b['title']).first():
            banner = Banner(
                title=b['title'],
                image_url=b['image_url'],
                sort_order=b['sort_order'],
                is_active=True
            )
            db.session.add(banner)
            count += 1

    db.session.commit()
    print(f"   ✅ 导入 {count} 条轮播图（共 {Banner.query.count()} 条）")


# ============ 主流程 ============

def main():
    print("=" * 60)
    print("🚀 数据迁移脚本启动")
    print("=" * 60)

    with app.app_context():
        # 确认数据库文件路径
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'travel_destinations.db')
        print(f"\n📁 数据库路径: {db_path}")
        print(f"   文件存在: {os.path.exists(db_path)}")

        # 创建新表
        print("\n📦 创建新表...")
        db.create_all()
        print("   ✅ 表创建完成")

        # 执行迁移
        provinces = migrate_provinces()
        migrate_cities(provinces)
        migrate_foods()
        migrate_trip_plans()
        migrate_site_config()
        migrate_navigations()
        migrate_reviews()
        migrate_banners()

        # 汇总
        print("\n" + "=" * 60)
        print("📊 迁移完成汇总")
        print("=" * 60)
        tables_info = [
            ('Province', Province),
            ('City', City),
            ('Food', Food),
            ('TripPlan', TripPlan),
            ('Review', Review),
            ('SiteConfig', SiteConfig),
            ('Navigation', Navigation),
            ('Banner', Banner),
        ]
        for name, model in tables_info:
            count = model.query.count()
            print(f"   {name:15s}: {count:>6d} 条")
        print("=" * 60)
        print("✅ 全部迁移完成！")


if __name__ == '__main__':
    main()
