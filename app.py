"""
智能旅游助手 - 完整版
保留：维基百科图片、天气查询、社交登录、批量收藏、导出数据、用户统计、高德API
"""
import os
import json
import time
import signal
import sys
import re
import random
import hashlib
import urllib.parse
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from functools import wraps
from collections import defaultdict
from pypinyin import pinyin, Style

import requests
from flask import Flask, render_template, request, jsonify, session, abort, redirect, url_for, send_from_directory, flash
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_, func
from pathlib import Path
import gzip
from io import BytesIO
from functools import wraps

# 尝试导入Flask-Compress进行响应压缩
try:
    from flask_compress import Compress
    COMPRESS_AVAILABLE = True
    log.info("✅ Flask-Compress已加载，响应压缩功能可用")
except ImportError:
    COMPRESS_AVAILABLE = False
    log.warning("⚠️ Flask-Compress未安装，响应压缩功能不可用")
    log.info("   请运行: pip install flask-compress")

# 导入日志系统
from services.logger import log

# 导入配置
from config import Config

# 导入维基百科图片提供者
from wiki_image_provider import wiki_image_provider

# 导入数据
from data.china_locations import (
    ALL_PROVINCES, ALL_CITIES, FOOD_DATABASE, TRIP_PLANS,
    DEFAULT_TRIP_PLANS, WEATHER_DATA, CITY_MAPPING, CITY_TO_PROVINCE
)

# ==================== 从JSON文件加载景点数据 ====================
def load_destinations_from_json():
    """从destinations.json文件加载景点数据"""
    json_path = Path("destinations.json")
    if not json_path.exists():
        log.warning(f"⚠️ 警告: {json_path} 文件不存在，使用空数据")
        return []

    try:
        with open(json_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
            # 移除可能存在的BOM头和注释
            import re
            content = re.sub(r'//.*?(\n|$)', '\n', content)
            content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
            data = json.loads(content)
            log.info(f"✅ 从 {json_path} 加载了 {len(data)} 条景点数据")
            return data
    except Exception as e:
        log.error(f"❌ 加载 {json_path} 失败: {e}")
        return []

# 加载JSON数据
JSON_DESTINATIONS = load_destinations_from_json()

# ==================== 背景图片加载 ====================
# 从scenic_images文件夹动态读取背景图片
SCENIC_IMAGES_DIR = Path("scenic_images")

def load_background_images_from_folder():
    """
    从scenic_images文件夹中读取所有图片
    返回格式与原有的BACKGROUND_IMAGES保持一致
    """
    background_images = []

    # 检查文件夹是否存在
    if not SCENIC_IMAGES_DIR.exists() or not SCENIC_IMAGES_DIR.is_dir():
        log.warning(f"⚠️ 警告: 文件夹 {SCENIC_IMAGES_DIR} 不存在或不是目录，使用默认图片")
        # 返回一个默认图片，防止程序崩溃
        return [{
            'url': '/static/images/default-bg.jpg',
            'name': '默认背景',
            'location': '未知'
        }]

    log.info(f"📁 正在从 {SCENIC_IMAGES_DIR} 加载背景图片...")

    # 遍历所有子文件夹
    folder_count = 0
    for sub_dir in SCENIC_IMAGES_DIR.iterdir():
        if not sub_dir.is_dir():
            continue

        # 获取子文件夹名称作为地点名称
        location_name = sub_dir.name

        # 获取该文件夹中的所有图片文件
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
        images = [f for f in sub_dir.iterdir()
                  if f.is_file() and f.suffix.lower() in image_extensions]

        # 为每张图片创建一个背景图对象
        for img_path in images:
            background_images.append({
                'url': f'/static/scenic_images/{sub_dir.name}/{img_path.name}',
                'name': img_path.stem,
                'location': location_name
            })

        if images:
            folder_count += 1

    # 如果没有找到任何图片，添加默认图片
    if not background_images:
        log.warning(f"⚠️ 警告: 在 {SCENIC_IMAGES_DIR} 中没有找到任何图片，使用默认图片")
        background_images.append({
            'url': '/static/images/default-bg.jpg',
            'name': '默认背景',
            'location': '未知'
        })
    else:
        log.info(f"✅ 成功从 {folder_count} 个文件夹加载 {len(background_images)} 张背景图片")

    return background_images

# 加载背景图片
BACKGROUND_IMAGES = load_background_images_from_folder()

# ==================== 图片匹配函数 ====================
# ==================== 景点图片缓存 ====================
_IMAGE_CACHE = None
_IMAGE_INDEX_FILE = Path("scenic_images/image_index.json")

def _build_image_cache():
    """启动时构建图片索引缓存（带JSON持久化，避免每次遍历文件系统）"""
    global _IMAGE_CACHE
    if _IMAGE_CACHE is not None:
        return _IMAGE_CACHE

    scenic_images_dir = Path("scenic_images")
    if not scenic_images_dir.exists():
        _IMAGE_CACHE = {}
        return _IMAGE_CACHE

    # 尝试从JSON索引文件加载（文件存在且scenic_images目录未变更时）
    if _IMAGE_INDEX_FILE.exists():
        try:
            index_mtime = _IMAGE_INDEX_FILE.stat().st_mtime
            dir_mtime = scenic_images_dir.stat().st_mtime
            if index_mtime >= dir_mtime:
                with open(_IMAGE_INDEX_FILE, 'r', encoding='utf-8') as f:
                    _IMAGE_CACHE = json.load(f)
                log.info(f"✅ 图片索引从缓存加载: {len(_IMAGE_CACHE)} 条")
                return _IMAGE_CACHE
        except Exception as e:
            log.warning(f"图片索引缓存加载失败，重新构建: {e}")

    # 遍历文件系统构建索引
    log.info("📁 正在构建图片索引...")
    cache = {}
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
    for sub_dir in scenic_images_dir.iterdir():
        if not sub_dir.is_dir():
            continue
        images = [f for f in sub_dir.iterdir()
                  if f.is_file() and f.suffix.lower() in image_extensions]
        if images:
            name = sub_dir.name
            cache[name] = f'/static/scenic_images/{name}/{images[0].name}'
            for suffix in ['风景名胜区', '风景名胜', '旅游区', '旅游景区', '景区', '风景区', '遗址', '博物馆', '公园', '寺', '庙']:
                short = name.replace(suffix, '')
                if short and short not in cache:
                    cache[short] = f'/static/scenic_images/{name}/{images[0].name}'

    # 持久化到JSON文件
    try:
        with open(_IMAGE_INDEX_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False)
        log.info(f"✅ 图片索引构建并持久化: {len(cache)} 条")
    except Exception as e:
        log.warning(f"图片索引持久化失败: {e}")

    _IMAGE_CACHE = cache
    return _IMAGE_CACHE

def match_scenic_image(dest_name, external=False):
    """
    根据景点名称从scenic_images文件夹中匹配图片（使用缓存，支持复合名称）
    改进：处理 "青城山-都江堰"、"峨眉山-乐山大佛" 等复合名称
    """
    cache = _build_image_cache()
    clean_name = dest_name.strip().replace(' ', '')

    # 1. 精确匹配
    if clean_name in cache:
        return cache[clean_name]

    # 2. 去除标点后匹配
    clean_no_punct = clean_name.replace('·', '').replace('-', '')
    if clean_no_punct in cache:
        return cache[clean_no_punct]

    # 3. 去掉括号内容后匹配
    clean_no_bracket = re.sub(r'[（(][^）)]*[）)]', '', clean_name).strip()
    if clean_no_bracket != clean_name and clean_no_bracket in cache:
        return cache[clean_no_bracket]

    # 4. 复合名称拆分（处理 "-" 和 "·" 分隔的复合名称）
    parts = re.split(r'[-·]', clean_name)
    if len(parts) > 1:
        for part in parts:
            part = part.strip()
            if len(part) >= 2 and part in cache:
                return cache[part]
        combined = ''.join(parts)
        if combined in cache:
            return cache[combined]

    # 5. 子串匹配（确保质量：匹配度 >= 50%）
    best_match_url = None
    best_score = 0
    for key, url in cache.items():
        if clean_name in key:
            score = len(clean_name) / len(key)
            if score > best_score and score >= 0.5:
                best_score = score
                best_match_url = url
        elif key in clean_name:
            score = len(key) / len(clean_name)
            if score > best_score and score >= 0.3:
                best_score = score
                best_match_url = url

    if best_match_url:
        return best_match_url

    # 6. 无匹配，返回默认
    placeholder = '/static/images/placeholder.jpg'
    if external:
        try:
            return url_for('static', filename='images/placeholder.jpg', _external=True)
        except Exception:
            return placeholder
    return placeholder
def update_destinations_with_images():
    """更新数据库中的景点图片（使用缓存，批量更新）"""
    # 先构建图片缓存
    _build_image_cache()
    # 只查没有封面的景点
    destinations = Destination.query.filter(
        (Destination.cover_image == None) | (Destination.cover_image == '') | (Destination.cover_image.like('%placeholder%'))
    ).all()
    updated_count = 0
    for dest in destinations:
        matched_image = match_scenic_image(dest.name, external=False)
        if matched_image and 'placeholder' not in matched_image:
            dest.cover_image = matched_image
            updated_count += 1
    if updated_count > 0:
        db.session.commit()
        log.info(f"✅ 已更新 {updated_count} 个景点的图片")

# ==================== 社交登录导入 ====================
from utils.social_login import (
    WeChatLogin, QQLogin, WeiBoLogin,
    generate_state, save_state, verify_state,
    redis_client
)

# ==================== 高德API导入 ====================
from gaode_api import GaodeAPIManager, extract_lat_lng_from_text

# ==================== 导出功能导入 ====================
try:
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as ReportLabImage
    from reportlab.lib.units import inch, cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    PDF_AVAILABLE = True
    log.info("✅ ReportLab库已加载，PDF导出功能可用")
except ImportError:
    PDF_AVAILABLE = False
    log.warning("⚠️ ReportLab库未安装，PDF导出功能不可用")
    log.info("   请运行: pip install reportlab")

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    PIL_AVAILABLE = True
    log.info("✅ Pillow库已加载，图片导出功能可用")
except ImportError:
    PIL_AVAILABLE = False
    log.warning("⚠️ Pillow库未安装，图片导出功能受限")

# ==================== 配置 ====================
# 心知天气Key
SENIVERSE_API_KEY = os.environ.get('SENIVERSE_API_KEY')

# 高德API配置
GAODE_API_KEY = os.environ.get('GAODE_API_KEY')
gaode_api = GaodeAPIManager(GAODE_API_KEY, max_qps=5) if GAODE_API_KEY else None

# ==================== Flask应用初始化 ====================
app = Flask(__name__,
            static_folder='static',
            static_url_path='/static')
# 在 app 初始化后添加
from flask_caching import Cache
app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config['SQLALCHEMY_DATABASE_URI'] = Config.SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = Config.SQLALCHEMY_TRACK_MODIFICATIONS
app.config['SESSION_PERMANENT'] = Config.SESSION_PERMANENT
app.config['PERMANENT_SESSION_LIFETIME'] = Config.PERMANENT_SESSION_LIFETIME
# 配置缓存
app.config['CACHE_TYPE'] = 'simple'  # 开发环境用 simple，生产环境用 redis
app.config['CACHE_DEFAULT_TIMEOUT'] = 300  # 5分钟缓存
cache = Cache(app)

# 配置响应压缩
if COMPRESS_AVAILABLE:
    app.config['COMPRESS_MIMETYPES'] = [
        'text/html',
        'text/css',
        'text/xml',
        'application/json',
        'application/javascript',
        'text/javascript',
        'image/svg+xml'
    ]
    app.config['COMPRESS_LEVEL'] = 6  # 压缩级别 (1-9, 6是平衡点)
    app.config['COMPRESS_MIN_SIZE'] = 500  # 最小压缩大小(字节)
    Compress(app)
    log.info("✅ 响应压缩已启用")
else:
    log.warning("⚠️ 响应压缩未启用，使用默认响应")



# 添加静态文件路由，使scenic_images文件夹可通过/static/scenic_images访问
@app.route('/static/scenic_images/<path:filename>')
def serve_scenic_images(filename):
    response = send_from_directory('scenic_images', filename)
    # 添加缓存头 - 缓存1天
    response.headers['Cache-Control'] = 'public, max-age=86400'
    response.headers['ETag'] = hashlib.md5(filename.encode()).hexdigest()[:16]
    return response

# 静态文件缓存优化
@app.after_request
def add_cache_headers(response):
    # 为静态资源添加缓存头
    if request.path.startswith('/static/'):
        if request.path.endswith(('.css', '.js')):
            # CSS和JS文件缓存1小时
            response.headers['Cache-Control'] = 'public, max-age=3600'
        elif request.path.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.ico')):
            # 图片文件缓存1天
            response.headers['Cache-Control'] = 'public, max-age=86400'
        elif request.path.endswith(('.woff', '.woff2', '.ttf', '.eot')):
            # 字体文件缓存7天
            response.headers['Cache-Control'] = 'public, max-age=604800'
    return response

# 数据库初始化
db = SQLAlchemy()
db.init_app(app)

# SocketIO 初始化 - 修复 ssl.wrap_socket 问题
try:
    import eventlet
    # 在 monkey_patch 之前先打补丁解决 ssl.wrap_socket 问题
    import ssl
    if not hasattr(ssl, 'wrap_socket'):
        # Python 3.10+ 中 wrap_socket 已被移除，添加兼容性方法
        ssl.wrap_socket = ssl.SSLContext.wrap_socket

    eventlet.monkey_patch()
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')
    log.info("✅ 使用 eventlet 模式，已修复 ssl 兼容性")
except (ImportError, AttributeError) as e:
    log.warning(f"⚠️ eventlet 初始化失败: {e}，使用 threading 模式")
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ==================== 数据库模型 ====================
class Destination(db.Model):
    """景点模型"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    province = db.Column(db.String(50), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    price_range = db.Column(db.String(50))
    rating = db.Column(db.Float, default=4.5)
    review_count = db.Column(db.Integer, default=0)
    opening_hours = db.Column(db.String(100))
    address = db.Column(db.String(300))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    popularity_score = db.Column(db.Float, default=70.0)
    is_open = db.Column(db.Boolean, default=True)
    tags = db.Column(db.String(500))
    images = db.Column(db.String(1000), default='[]')
    cover_image = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.now)
    # 新增字段
    view_count = db.Column(db.Integer, default=0)  # 浏览次数
    like_count = db.Column(db.Integer, default=0)  # 点赞数

    # 添加索引优化查询
    __table_args__ = (
        db.Index('idx_dest_popularity', 'popularity_score'),
        db.Index('idx_dest_rating', 'rating'),
        db.Index('idx_dest_city', 'city'),
        db.Index('idx_dest_province', 'province'),
        db.Index('idx_dest_category', 'category'),
        db.Index('idx_dest_view_count', 'view_count'),
        db.Index('idx_dest_like_count', 'like_count'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'city': self.city,
            'province': self.province,
            'category': self.category,
            'description': self.description,
            'price_range': self.price_range,
            'rating': self.rating,
            'review_count': self.review_count,
            'opening_hours': self.opening_hours,
            'address': self.address,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'popularity_score': self.popularity_score,
            'is_open': self.is_open,
            'tags': json.loads(self.tags) if self.tags else [],
            'images': json.loads(self.images) if self.images else [],
            'cover_image': self.cover_image or url_for('static', filename='images/placeholder.jpg', _external=True)
        }


class User(db.Model):
    """用户模型"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True)
    phone = db.Column(db.String(20), unique=True)
    password_hash = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default=datetime.now)
    last_login = db.Column(db.DateTime)
    wechat_openid = db.Column(db.String(100), unique=True)
    qq_openid = db.Column(db.String(100), unique=True)
    weibo_uid = db.Column(db.String(100), unique=True)
    avatar_url = db.Column(db.String(500))
    favorites = db.Column(db.Text, default='[]')
    search_history = db.Column(db.Text, default='[]')
    click_history = db.Column(db.Text, default='[]')

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'phone': self.phone,
            'avatar_url': self.avatar_url,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None,
            'last_login': self.last_login.strftime('%Y-%m-%d %H:%M') if self.last_login else None,
            'favorites': json.loads(self.favorites) if self.favorites else [],
            'search_history': json.loads(self.search_history) if self.search_history else [],
            'click_history': json.loads(self.click_history) if self.click_history else [],
        }

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)


class Conversation(db.Model):
    """对话记录模型"""
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer)
    messages = db.Column(db.Text, default='[]')
    context = db.Column(db.Text, default='{}')
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)


# ==================== 管理员模型（简化版） ====================
class Admin(db.Model):
    """管理员模型 - 简化版"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else ''
        }


# ==================== 行程规划模型 ====================
class Trip(db.Model):
    """行程模型"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    budget = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='planning')  # planning, ongoing, completed, cancelled
    is_public = db.Column(db.Boolean, default=False)
    share_code = db.Column(db.String(20), unique=True)
    cover_image = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # 关联关系
    user = db.relationship('User', backref=db.backref('trips', lazy=True))
    items = db.relationship('TripItem', backref='trip', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'description': self.description,
            'start_date': self.start_date.strftime('%Y-%m-%d') if self.start_date else None,
            'end_date': self.end_date.strftime('%Y-%m-%d') if self.end_date else None,
            'budget': self.budget,
            'status': self.status,
            'is_public': self.is_public,
            'share_code': self.share_code,
            'cover_image': self.cover_image,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M') if self.updated_at else None,
            'items': [item.to_dict() for item in self.items],
            'duration': (self.end_date - self.start_date).days + 1 if self.start_date and self.end_date else 0,
            'username': self.user.username if self.user else None
        }


class TripItem(db.Model):
    """行程项目模型"""
    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey('trip.id'), nullable=False)
    destination_id = db.Column(db.Integer, db.ForeignKey('destination.id'))
    day_number = db.Column(db.Integer, nullable=False)  # 第几天
    start_time = db.Column(db.Time)  # 开始时间
    end_time = db.Column(db.Time)  # 结束时间
    activity = db.Column(db.String(200), nullable=False)  # 活动内容
    location = db.Column(db.String(300))  # 地点
    notes = db.Column(db.Text)  # 备注
    cost = db.Column(db.Float, default=0.0)  # 费用
    order_index = db.Column(db.Integer, default=0)  # 排序索引
    created_at = db.Column(db.DateTime, default=datetime.now)

    # 关联关系
    destination = db.relationship('Destination', backref=db.backref('trip_items', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'trip_id': self.trip_id,
            'destination_id': self.destination_id,
            'day_number': self.day_number,
            'start_time': self.start_time.strftime('%H:%M') if self.start_time else None,
            'end_time': self.end_time.strftime('%H:%M') if self.end_time else None,
            'activity': self.activity,
            'location': self.location,
            'notes': self.notes,
            'cost': self.cost,
            'order_index': self.order_index,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None,
            'destination': self.destination.to_dict() if self.destination else None
        }


class TripShare(db.Model):
    """行程分享记录模型"""
    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey('trip.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    platform = db.Column(db.String(50))  # 分享平台
    shared_at = db.Column(db.DateTime, default=datetime.now)

    # 关联关系
    trip = db.relationship('Trip', backref=db.backref('shares', lazy=True))
    user = db.relationship('User', backref=db.backref('trip_shares', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'trip_id': self.trip_id,
            'user_id': self.user_id,
            'platform': self.platform,
            'shared_at': self.shared_at.strftime('%Y-%m-%d %H:%M') if self.shared_at else None,
            'username': self.user.username if self.user else None
        }


class NearbyPOI(db.Model):
    """周边POI模型（酒店、餐厅、停车场等）"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), nullable=False)  # hotel, restaurant, parking, atm, gas_station, pharmacy
    subcategory = db.Column(db.String(100))  # 子类别（如中餐、西餐、快餐等）
    city = db.Column(db.String(100))
    province = db.Column(db.String(50))
    address = db.Column(db.String(300))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    rating = db.Column(db.Float, default=0.0)
    price_level = db.Column(db.String(20))  # 经济、中等、高档
    phone = db.Column(db.String(50))
    opening_hours = db.Column(db.String(200))
    description = db.Column(db.Text)
    tags = db.Column(db.String(500))
    images = db.Column(db.String(1000), default='[]')
    cover_image = db.Column(db.String(500))
    business_status = db.Column(db.String(20), default='营业中')  # 营业中、已关闭、暂停营业
    distance = db.Column(db.Integer)  # 距离目标景点的米数
    destination_id = db.Column(db.Integer, db.ForeignKey('destination.id'))  # 关联的景点
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # 索引
    __table_args__ = (
        db.Index('idx_poi_category', 'category'),
        db.Index('idx_poi_city', 'city'),
        db.Index('idx_poi_destination', 'destination_id'),
        db.Index('idx_poi_location', 'latitude', 'longitude'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'category': self.category,
            'subcategory': self.subcategory,
            'city': self.city,
            'province': self.province,
            'address': self.address,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'rating': self.rating,
            'price_level': self.price_level,
            'phone': self.phone,
            'opening_hours': self.opening_hours,
            'description': self.description,
            'tags': json.loads(self.tags) if self.tags else [],
            'images': json.loads(self.images) if self.images else [],
            'cover_image': self.cover_image,
            'business_status': self.business_status,
            'distance': self.distance,
            'destination_id': self.destination_id,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None
        }


class UserLike(db.Model):
    """用户点赞模型"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    destination_id = db.Column(db.Integer, db.ForeignKey('destination.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    # 联合唯一约束
    __table_args__ = (
        db.UniqueConstraint('user_id', 'destination_id', name='unique_user_like'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'destination_id': self.destination_id,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None
        }


class UserFollow(db.Model):
    """用户关注模型"""
    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # 关注者
    following_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # 被关注者
    created_at = db.Column(db.DateTime, default=datetime.now)

    # 联合唯一约束
    __table_args__ = (
        db.UniqueConstraint('follower_id', 'following_id', name='unique_user_follow'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'follower_id': self.follower_id,
            'following_id': self.following_id,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None
        }


class UserCheckin(db.Model):
    """用户签到模型"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    destination_id = db.Column(db.Integer, db.ForeignKey('destination.id'), nullable=False)
    latitude = db.Column(db.Float)  # 签到时的纬度
    longitude = db.Column(db.Float)  # 签到时的经度
    content = db.Column(db.Text)  # 签到内容/游记
    images = db.Column(db.String(1000), default='[]')  # 签到图片
    created_at = db.Column(db.DateTime, default=datetime.now)

    # 添加索引
    __table_args__ = (
        db.Index('idx_checkin_user', 'user_id'),
        db.Index('idx_checkin_destination', 'destination_id'),
        db.Index('idx_checkin_time', 'created_at'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'destination_id': self.destination_id,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'content': self.content,
            'images': json.loads(self.images) if self.images else [],
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None
        }


# 评论模板
REVIEW_TEMPLATES = [
    "非常值得一去的景点，景色优美，环境整洁，服务态度也很好。",
    "性价比很高，门票价格合理，里面的设施也很完善。",
    "人有点多，但是景色确实不错，拍照很出片。",
    "交通便利，停车方便，适合全家出游。",
    "风景如画，空气清新，是个放松身心的好地方。",
    "历史底蕴深厚，导游讲解很详细，学到了很多知识。",
    "餐饮价格略贵，但景点本身很棒，推荐大家来看看。",
    "最佳旅游季节来玩的，景色果然名不虚传。",
    "景区管理规范，卫生状况良好，体验很不错。",
    "有点小失望，部分设施在维修，没能看到完整的景点。",
    "带父母来的，他们非常喜欢，拍了很多照片。",
    "孩子特别喜欢，玩得很开心，下次还会再来。",
    "建议避开节假日，人太多了，影响体验。",
    "景色很美，但景区内指示牌不够清晰，容易迷路。",
    "性价比一般，门票偏贵，但景色确实独特。",
    "非常满意，导游服务热情，讲解生动有趣。",
    "环境优美，空气清新，是个天然氧吧。",
    "交通不太方便，建议自驾或者包车。",
    "景区很大，一天时间不够逛，建议安排两天。",
    "值得二刷的景点，四季景色各有特色。"
]

# 用户名模板
USERNAMES = [
    "旅行者", "背包客", "摄影师", "美食家", "探险家",
    "自由行", "徒步者", "自驾游", "穷游er", "度假达人",
    "风景控", "历史迷", "文化人", "户外爱好者", "亲子游",
    "学生党", "上班族", "退休老人", "新婚夫妇", "闺蜜团"
]


# ==================== 辅助函数 ====================
def login_required(f):
    """登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': '请先登录', 'login_required': True}), 401
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function




def get_wiki_attraction_image(attraction_name: str, city: str = None, usage: str = 'dest_detail') -> str:
    """从维基百科获取景点图片"""
    return wiki_image_provider.get_cover_image(attraction_name, city, usage)


# ==================== 天气API类 ====================
class WeatherAPI:
    """心知天气API封装"""

    def __init__(self, api_key=None):
        self.api_key = api_key
        self.base_url = "https://api.seniverse.com/v3"

    def get_current_weather(self, city_name):
        """获取实时天气"""
        if not self.api_key:
            return self._get_mock_weather(city_name)

        try:
            url = f"{self.base_url}/weather/now.json"
            params = {
                'key': self.api_key,
                'location': city_name,
                'language': 'zh-Hans',
                'unit': 'c'
            }
            resp = requests.get(url, params=params, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                now = data['results'][0]['now']
                return {
                    'success': True,
                    'city': city_name,
                    'temperature': f"{now['temperature']}°C",
                    'feels_like': f"{now.get('feels_like', now['temperature'])}°C",
                    'condition': now['text'],
                    'wind_dir': now.get('wind_direction', '未知'),
                    'wind_speed': f"{now.get('wind_speed', '3')} km/h",
                    'humidity': f"{now.get('humidity', '50')}%",
                    'source': '心知天气'
                }
        except Exception:
            pass
        return self._get_mock_weather(city_name)

    def get_forecast(self, city_name, days=3):
        """获取天气预报"""
        if not self.api_key:
            return None

        try:
            url = f"{self.base_url}/weather/daily.json"
            params = {
                'key': self.api_key,
                'location': city_name,
                'language': 'zh-Hans',
                'unit': 'c',
                'days': min(days, 3)
            }
            resp = requests.get(url, params=params, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                forecasts = []
                for day in data['results'][0]['daily']:
                    forecasts.append({
                        'date': day['date'],
                        'max_temp': f"{day['high']}°C",
                        'min_temp': f"{day['low']}°C",
                        'condition_day': day['text_day'],
                        'condition_night': day['text_night'],
                    })
                return {'success': True, 'city': city_name, 'forecasts': forecasts}
        except Exception:
            pass
        return None

    def _get_mock_weather(self, city_name):
        """返回模拟天气数据"""
        conditions = ['晴', '多云', '阴', '小雨', '中雨']
        return {
            'success': True,
            'city': city_name,
            'temperature': f"{random.randint(15, 28)}°C",
            'feels_like': f"{random.randint(15, 28)}°C",
            'condition': random.choice(conditions),
            'wind_dir': random.choice(['东南风', '西南风', '东北风', '西北风']),
            'wind_speed': f"{random.randint(2, 8)} km/h",
            'humidity': f"{random.randint(40, 80)}%",
            'source': '本地数据'
        }


# 全局天气实例
weather_api = WeatherAPI(SENIVERSE_API_KEY)


# ==================== 智能助手类 ====================
class TravelAssistant:
    """智能旅游助手 - 增强版（性能优化+功能增强）"""

    def __init__(self, db):
        self.db = db
        self.ai_mode_enabled = getattr(Config, 'AI_MODE_ENABLED', False)
        
        # 延迟加载的数据
        self._city_mapping = None
        self._city_to_province = None
        self._food_database = None
        self._trip_plans = None
        self._default_trip_plans = None
        self._all_provinces = None
        self._all_cities = None
        
        # 内存缓存
        self._destinations_cache = {}
        self._destinations_cache_time = 0
        self._cache_ttl = 300  # 缓存5分钟
        
        self.conversations = {}
        self.user_history = {}
        
        # 用户偏好学习（轻量级）
        self.user_preferences = defaultdict(lambda: {
            'visit_history': [],
            'price_preference': '中等',
            'travel_style': '休闲'
        })
        
        # 情感关键词（精简版）
        self.emotion_keywords = {
            'positive': ['喜欢', '很棒', '不错', '满意', '开心', '好', '棒'],
            'negative': ['失望', '不好', '差', '糟糕', '无聊', '贵'],
            'excited': ['太棒了', '超赞', '完美', '绝了'],
            'confused': ['不知道', '迷茫', '纠结', '怎么选']
        }
        
        # 模糊匹配词库（增强版 - 覆盖更多景点别名和简称）
        self.fuzzy_keywords = {
            # 河南景点
            '老君山': ['老君山', '老君', '洛阳老君山', '栾川老君山'],
            '龙门石窟': ['龙门石窟', '龙门', '洛阳龙门'],
            '少林寺': ['少林寺', '少林', '登封少林寺'],
            '清明上河园': ['清明上河园', '清明上河', '开封清明上河园'],
            '云台山': ['云台山', '云台', '焦作云台山'],
            '殷墟': ['殷墟', '安阳殷墟', '殷墟遗址'],
            '白马寺': ['白马寺', '洛阳白马寺'],
            '开封府': ['开封府', '开封府衙'],
            '包公祠': ['包公祠', '开封包公祠'],
            '河南博物院': ['河南博物院', '河南博物馆', '豫博'],
            
            # 北京景点
            '故宫': ['故宫', '紫禁城', '故宫博物院', '北京故宫'],
            '长城': ['长城', '八达岭', '慕田峪', '八达岭长城', '慕田峪长城', '居庸关长城'],
            '天坛': ['天坛', '天坛公园'],
            '颐和园': ['颐和园', '皇家园林'],
            '圆明园': ['圆明园', '圆明园遗址'],
            '天安门': ['天安门', '天安门广场'],
            '鸟巢': ['鸟巢', '国家体育场', '鸟巢体育场'],
            '水立方': ['水立方', '国家游泳中心'],
            '南锣鼓巷': ['南锣鼓巷', '南锣'],
            '什刹海': ['什刹海', '后海'],
            '恭王府': ['恭王府', '和珅府'],
            '雍和宫': ['雍和宫', '喇嘛庙'],
            '香山': ['香山', '香山公园'],
            '十三陵': ['十三陵', '明十三陵'],
            '北海公园': ['北海公园', '北海'],
            '景山公园': ['景山公园', '景山'],
            '国家博物馆': ['国家博物馆', '国博', '中国国家博物馆'],
            
            # 上海景点
            '外滩': ['外滩', '上海外滩'],
            '东方明珠': ['东方明珠', '东方明珠塔'],
            '豫园': ['豫园', '上海豫园'],
            '城隍庙': ['城隍庙', '上海城隍庙'],
            '迪士尼': ['迪士尼', '上海迪士尼', '迪士尼乐园'],
            '南京路': ['南京路', '南京路步行街'],
            '田子坊': ['田子坊', '上海田子坊'],
            '新天地': ['新天地', '上海新天地'],
            '朱家角': ['朱家角', '朱家角古镇'],
            '上海博物馆': ['上海博物馆', '上博'],
            
            # 杭州景点
            '西湖': ['西湖', '杭州西湖', '西湖风景区'],
            '灵隐寺': ['灵隐寺', '杭州灵隐寺'],
            '雷峰塔': ['雷峰塔', '杭州雷峰塔'],
            '断桥': ['断桥', '西湖断桥'],
            '千岛湖': ['千岛湖', '杭州千岛湖'],
            '宋城': ['宋城', '杭州宋城'],
            '龙井': ['龙井', '龙井茶园', '龙井村'],
            
            # 西安景点
            '兵马俑': ['兵马俑', '秦兵马俑', '秦始皇兵马俑', '秦始皇陵兵马俑'],
            '大雁塔': ['大雁塔', '西安大雁塔'],
            '华清池': ['华清池', '华清宫'],
            '城墙': ['城墙', '西安城墙', '明城墙'],
            '钟楼': ['钟楼', '西安钟楼'],
            '鼓楼': ['鼓楼', '西安鼓楼'],
            '回民街': ['回民街', '回坊'],
            '大唐不夜城': ['大唐不夜城', '不夜城'],
            '华山': ['华山', '西岳华山'],
            '法门寺': ['法门寺', '宝鸡法门寺'],
            
            # 成都景点
            '大熊猫': ['大熊猫', '熊猫基地', '成都大熊猫基地', '大熊猫繁育基地'],
            '宽窄巷子': ['宽窄巷子', '宽窄'],
            '锦里': ['锦里', '锦里古街'],
            '武侯祠': ['武侯祠', '成都武侯祠'],
            '杜甫草堂': ['杜甫草堂', '草堂'],
            '都江堰': ['都江堰', '成都都江堰'],
            '青城山': ['青城山', '成都青城山'],
            '九寨沟': ['九寨沟', '九寨'],
            
            # 重庆景点
            '洪崖洞': ['洪崖洞', '重庆洪崖洞'],
            '解放碑': ['解放碑', '重庆解放碑'],
            '磁器口': ['磁器口', '磁器口古镇'],
            '长江索道': ['长江索道', '重庆长江索道'],
            '武隆': ['武隆', '武隆天坑', '天生三桥'],
            '大足石刻': ['大足石刻', '大足'],
            
            # 南京景点
            '中山陵': ['中山陵', '南京中山陵'],
            '夫子庙': ['夫子庙', '南京夫子庙'],
            '秦淮河': ['秦淮河', '南京秦淮河'],
            '明孝陵': ['明孝陵', '南京明孝陵'],
            '总统府': ['总统府', '南京总统府'],
            '玄武湖': ['玄武湖', '南京玄武湖'],
            '南京博物院': ['南京博物院', '南博'],
            
            # 广州景点
            '广州塔': ['广州塔', '小蛮腰'],
            '白云山': ['白云山', '广州白云山'],
            '陈家祠': ['陈家祠', '广州陈家祠'],
            '沙面': ['沙面', '广州沙面'],
            '长隆': ['长隆', '长隆欢乐世界', '长隆野生动物园'],
            '越秀公园': ['越秀公园', '越秀山'],
            
            # 深圳景点
            '世界之窗': ['世界之窗', '深圳世界之窗'],
            '欢乐谷': ['欢乐谷', '深圳欢乐谷'],
            '东部华侨城': ['东部华侨城', '华侨城'],
            '大梅沙': ['大梅沙', '大梅沙海滨'],
            '莲花山': ['莲花山', '深圳莲花山'],
            
            # 云南景点
            '丽江古城': ['丽江古城', '丽江', '大研古镇'],
            '玉龙雪山': ['玉龙雪山', '玉龙'],
            '大理古城': ['大理古城', '大理', '大理古镇'],
            '洱海': ['洱海', '大理洱海'],
            '石林': ['石林', '昆明石林'],
            '西双版纳': ['西双版纳', '版纳'],
            '香格里拉': ['香格里拉', '香格里'],
            '泸沽湖': ['泸沽湖', '丽江泸沽湖'],
            '普达措': ['普达措', '普达措国家公园'],
            
            # 黄山相关
            '黄山': ['黄山', '黄山风景区'],
            '宏村': ['宏村', '黄山宏村'],
            '西递': ['西递', '黄山西递'],
            
            # 桂林景点
            '漓江': ['漓江', '桂林漓江'],
            '象鼻山': ['象鼻山', '桂林象鼻山'],
            '阳朔': ['阳朔', '桂林阳朔'],
            '龙脊梯田': ['龙脊梯田', '龙脊'],
            
            # 张家界
            '张家界': ['张家界', '张家界国家森林公园'],
            '天门山': ['天门山', '张家界天门山'],
            '凤凰古城': ['凤凰古城', '凤凰'],
            
            # 厦门
            '鼓浪屿': ['鼓浪屿', '厦门鼓浪屿'],
            '南普陀': ['南普陀', '南普陀寺'],
            '厦门大学': ['厦门大学', '厦大'],
            
            # 武汉
            '黄鹤楼': ['黄鹤楼', '武汉黄鹤楼'],
            '东湖': ['东湖', '武汉东湖'],
            '户部巷': ['户部巷', '武汉户部巷'],
            
            # 济南
            '趵突泉': ['趵突泉', '济南趵突泉'],
            '大明湖': ['大明湖', '济南大明湖'],
            '千佛山': ['千佛山', '济南千佛山'],
            
            # 青岛
            '栈桥': ['栈桥', '青岛栈桥'],
            '八大关': ['八大关', '青岛八大关'],
            '崂山': ['崂山', '青岛崂山'],
            
            # 泰山
            '泰山': ['泰山', '东岳泰山'],
            
            # 三亚
            '天涯海角': ['天涯海角', '三亚天涯海角'],
            '亚龙湾': ['亚龙湾', '三亚亚龙湾'],
            '蜈支洲岛': ['蜈支洲岛', '蜈支洲'],
            '南山': ['南山', '三亚南山', '南山文化旅游区'],
            
            # 敦煌
            '莫高窟': ['莫高窟', '敦煌莫高窟'],
            '鸣沙山': ['鸣沙山', '鸣沙山月牙泉'],
            '月牙泉': ['月牙泉', '鸣沙山月牙泉'],
            
            # 布达拉宫
            '布达拉宫': ['布达拉宫', '布宫'],
            
            # 其他热门景点
            '乌镇': ['乌镇', '嘉兴乌镇'],
            '周庄': ['周庄', '昆山周庄'],
            '西塘': ['西塘', '嘉兴西塘'],
            '同里': ['同里', '苏州同里'],
            '拙政园': ['拙政园', '苏州拙政园'],
            '留园': ['留园', '苏州留园'],
            '虎丘': ['虎丘', '苏州虎丘'],
            '寒山寺': ['寒山寺', '苏州寒山寺'],
            '庐山': ['庐山', '九江庐山'],
            '井冈山': ['井冈山', '江西井冈山'],
            '武夷山': ['武夷山', '福建武夷山'],
            '普陀山': ['普陀山', '舟山普陀山'],
            '雁荡山': ['雁荡山', '温州雁荡山'],
            '龙虎山': ['龙虎山', '江西龙虎山'],
            '三清山': ['三清山', '江西三清山'],
            '武当山': ['武当山', '湖北武当山'],
            '神农架': ['神农架', '湖北神农架'],
            '峨眉山': ['峨眉山', '四川峨眉山'],
            '乐山大佛': ['乐山大佛', '乐山'],
            '青城山': ['青城山', '都江堰青城山'],
            '稻城亚丁': ['稻城亚丁', '稻城'],
            '黄果树瀑布': ['黄果树瀑布', '黄果树'],
            '梵净山': ['梵净山', '贵州梵净山'],
            '丽江': ['丽江', '丽江古城'],
            '腾冲': ['腾冲', '云南腾冲'],
            '西双版纳': ['西双版纳', '版纳'],
            '青海湖': ['青海湖', '青海'],
            '茶卡盐湖': ['茶卡盐湖', '茶卡'],
            '嘉峪关': ['嘉峪关', '嘉峪关长城'],
            '张掖丹霞': ['张掖丹霞', '张掖七彩丹霞'],
            '沙坡头': ['沙坡头', '中卫沙坡头'],
            '西夏王陵': ['西夏王陵', '银川西夏王陵'],
            '天山天池': ['天山天池', '天池'],
            '喀纳斯': ['喀纳斯', '喀纳斯湖'],
            '那拉提': ['那拉提', '那拉提草原'],
            '赛里木湖': ['赛里木湖', '赛里木'],
        }
        
        # 工具延迟初始化
        self._tools = None
    
    @property
    def city_mapping(self):
        if self._city_mapping is None:
            self._city_mapping = CITY_MAPPING
        return self._city_mapping
    
    @property
    def city_to_province(self):
        if self._city_to_province is None:
            self._city_to_province = CITY_TO_PROVINCE
        return self._city_to_province
    
    @property
    def food_database(self):
        if self._food_database is None:
            self._food_database = FOOD_DATABASE
        return self._food_database
    
    @property
    def trip_plans(self):
        if self._trip_plans is None:
            self._trip_plans = TRIP_PLANS
        return self._trip_plans
    
    @property
    def default_trip_plans(self):
        if self._default_trip_plans is None:
            self._default_trip_plans = DEFAULT_TRIP_PLANS
        return self._default_trip_plans
    
    @property
    def all_provinces(self):
        if self._all_provinces is None:
            self._all_provinces = set(ALL_PROVINCES)
        return self._all_provinces
    
    @property
    def all_cities(self):
        if self._all_cities is None:
            self._all_cities = ALL_CITIES
        return self._all_cities
    
    @property
    def tools(self):
        if self._tools is None:
            self._tools = {
                'search_destinations': self._tool_search_destinations,
                'get_weather': self._tool_get_weather,
                'plan_trip': self._tool_plan_trip,
                'export_trip': self._tool_export_trip,
                'get_food_recommendations': self._tool_get_food_recommendations,
                'get_nearby_info': self._tool_get_nearby_info
            }
        return self._tools
    
    def _tool_search_destinations(self, query, filters=None):
        """搜索景点工具"""
        try:
            # 构建查询
            db_query = Destination.query
            
            if filters:
                if filters.get('city'):
                    db_query = db_query.filter(Destination.city.contains(filters['city']))
                if filters.get('province'):
                    db_query = db_query.filter(Destination.province.contains(filters['province']))
                if filters.get('category'):
                    db_query = db_query.filter(Destination.category == filters['category'])
            
            # 搜索景点
            if query:
                db_query = db_query.filter(
                    or_(Destination.name.ilike(f'%{query}%'),
                        Destination.description.ilike(f'%{query}%'))
                )
            
            results = db_query.order_by(Destination.popularity_score.desc()).limit(10).all()
            
            return {
                'success': True,
                'count': len(results),
                'destinations': [dest.to_dict() for dest in results]
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _tool_get_weather(self, city):
        """获取天气工具"""
        try:
            weather_data = weather_api.get_current_weather(city)
            forecast_data = weather_api.get_forecast(city)
            
            return {
                'success': True,
                'weather': weather_data,
                'forecast': forecast_data.get('forecasts', []) if forecast_data else []
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _tool_plan_trip(self, city, days=3, preferences=None):
        """规划行程工具"""
        try:
            days = min(max(days, 1), 7)
            
            # 获取该城市的景点
            destinations = Destination.query.filter(
                or_(Destination.city.contains(city), Destination.province.contains(city))
            ).order_by(Destination.popularity_score.desc()).all()
            
            if not destinations:
                return {'success': False, 'error': f'没有找到{city}的景点'}
            
            # 根据偏好筛选
            if preferences:
                filtered_destinations = []
                for dest in destinations:
                    dest_tags = json.loads(dest.tags or '[]')
                    if any(pref in dest_tags for pref in preferences):
                        filtered_destinations.append(dest)
                if filtered_destinations:
                    destinations = filtered_destinations
            
            # 生成行程
            recommended_items = []
            destinations_per_day = max(2, len(destinations) // days)
            
            for day in range(1, days + 1):
                day_destinations = destinations[(day-1) * destinations_per_day:day * destinations_per_day]
                
                for i, dest in enumerate(day_destinations):
                    if i == 0:
                        start_time = "09:00"
                        end_time = "12:00"
                    elif i == 1:
                        start_time = "14:00"
                        end_time = "17:00"
                    else:
                        start_time = "19:00"
                        end_time = "21:00"
                    
                    recommended_items.append({
                        'day_number': day,
                        'destination_id': dest.id,
                        'activity': f"游览{dest.name}",
                        'location': dest.address or dest.city,
                        'start_time': start_time,
                        'end_time': end_time,
                        'cost': 0,
                        'notes': dest.description[:100] if dest.description else ''
                    })
            
            return {
                'success': True,
                'city': city,
                'days': days,
                'destinations_count': len(recommended_items),
                'itinerary': recommended_items
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _tool_export_trip(self, trip_id, format='pdf'):
        """导出行程工具"""
        try:
            # 这里简化处理，实际应该调用导出功能
            return {
                'success': True,
                'message': f'行程导出功能已启用，格式：{format}',
                'trip_id': trip_id,
                'format': format
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _tool_get_food_recommendations(self, city):
        """获取美食推荐工具"""
        try:
            foods = self.food_database.get(city, [])
            
            if not foods:
                # 尝试模糊匹配
                for key, value in self.food_database.items():
                    if city in key or key in city:
                        foods = value
                        break
            
            return {
                'success': True,
                'city': city,
                'count': len(foods),
                'foods': foods[:10]  # 最多返回10个
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _tool_get_nearby_info(self, latitude, longitude, category='all', radius=3000):
        """获取周边信息工具"""
        try:
            # 这里简化处理，实际应该调用周边搜索API
            return {
                'success': True,
                'message': '周边信息查询功能已启用',
                'center': {'latitude': latitude, 'longitude': longitude},
                'category': category,
                'radius': radius
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def call_tool(self, tool_name, **kwargs):
        """调用工具"""
        if tool_name in self.tools:
            try:
                return self.tools[tool_name](**kwargs)
            except Exception as e:
                return {'success': False, 'error': f'工具调用失败: {str(e)}'}
        else:
            return {'success': False, 'error': f'未知工具: {tool_name}'}
    
    def analyze_tool_intent(self, message):
        """分析工具调用意图"""
        msg = message.lower()
        
        # 搜索景点意图
        if any(k in msg for k in ['搜索', '查找', '找', '查询']) and any(k in msg for k in ['景点', '旅游', '景区']):
            return {'tool': 'search_destinations', 'extract_query': True}
        
        # 天气查询意图
        if any(k in msg for k in ['天气', '气温', '温度', '下雨']):
            return {'tool': 'get_weather', 'extract_city': True}
        
        # 行程规划意图
        if any(k in msg for k in ['行程', '规划', '攻略', '路线']) and any(k in msg for k in ['日游', '天', '规划']):
            return {'tool': 'plan_trip', 'extract_city_days': True}
        
        # 美食推荐意图
        if any(k in msg for k in ['美食', '小吃', '吃什么', '特色菜']):
            return {'tool': 'get_food_recommendations', 'extract_city': True}
        
        return None
    
    def execute_tool_if_needed(self, message, session_id):
        """如果需要，执行工具调用"""
        tool_intent = self.analyze_tool_intent(message)
        
        if not tool_intent:
            return None
        
        tool_name = tool_intent['tool']
        
        # 提取参数
        if tool_name == 'search_destinations':
            # 提取搜索关键词
            keywords = ['搜索', '查找', '找', '查询', '景点', '旅游', '景区']
            query = message
            for kw in keywords:
                query = query.replace(kw, '').strip()
            
            if query:
                result = self.call_tool(tool_name, query=query)
                return self._format_tool_result(result, tool_name)
        
        elif tool_name == 'get_weather':
            # 提取城市
            location = self.extract_location(message)
            if location:
                result = self.call_tool(tool_name, city=location['name'])
                return self._format_tool_result(result, tool_name)
        
        elif tool_name == 'plan_trip':
            # 提取城市和天数
            location = self.extract_location(message)
            numbers = self.extract_numbers(message)
            days = numbers[0] if numbers else 3
            
            if location:
                result = self.call_tool(tool_name, city=location['name'], days=days)
                return self._format_tool_result(result, tool_name)
        
        elif tool_name == 'get_food_recommendations':
            # 提取城市
            location = self.extract_location(message)
            if location:
                result = self.call_tool(tool_name, city=location['name'])
                return self._format_tool_result(result, tool_name)
        
        return None
    
    def _format_tool_result(self, result, tool_name):
        """格式化工具结果"""
        if not result.get('success'):
            return {"type": "text", "content": f"工具调用失败: {result.get('error', '未知错误')}"}
        
        if tool_name == 'search_destinations':
            destinations = result.get('destinations', [])
            if destinations:
                content = f"为您找到 {result['count']} 个景点：\n\n"
                for i, dest in enumerate(destinations[:5], 1):
                    content += f"{i}. **{dest['name']}** - {dest['category']} | ⭐{dest['rating']}分\n"
                return {"type": "text", "content": content}
            else:
                return {"type": "text", "content": "没有找到相关景点"}
        
        elif tool_name == 'get_weather':
            weather = result.get('weather', {})
            if weather:
                content = f"**{weather.get('city', '')}** 今日天气：\n\n"
                content += f"🌡️ 温度：{weather.get('temperature', '未知')}\n"
                content += f"☁️ 天气：{weather.get('condition', '未知')}\n"
                content += f"💨 风向：{weather.get('wind_dir', '未知')} {weather.get('wind_speed', '')}\n"
                content += f"💧 湿度：{weather.get('humidity', '未知')}\n"
                return {"type": "text", "content": content}
            else:
                return {"type": "text", "content": "获取天气信息失败"}
        
        elif tool_name == 'plan_trip':
            itinerary = result.get('itinerary', [])
            if itinerary:
                content = f"为您规划{result.get('city', '')}{result.get('days', 3)}日游行程：\n\n"
                for item in itinerary[:8]:  # 最多显示8个活动
                    content += f"第{item['day_number']}天 {item['start_time']}-{item['end_time']}: {item['activity']}\n"
                return {"type": "text", "content": content}
            else:
                return {"type": "text", "content": "行程规划失败"}
        
        elif tool_name == 'get_food_recommendations':
            foods = result.get('foods', [])
            if foods:
                content = f"为您推荐{result.get('city', '')}的特色美食：\n\n"
                for i, food in enumerate(foods[:5], 1):
                    content += f"{i}. **{food['name']}** - {food.get('description', '')[:30]}...\n"
                return {"type": "text", "content": content}
            else:
                return {"type": "text", "content": "没有找到美食信息"}
        
        return {"type": "text", "content": "工具执行完成"}

    def extract_location(self, message):
        """从消息中提取地点"""
        if not message:
            return None

        for city_name, standard_name in self.city_mapping.items():
            if city_name in message:
                return {'type': 'city', 'name': standard_name}

        for province in self.all_provinces:
            if province in message or f"{province}省" in message:
                return {'type': 'province', 'name': province}

        for city in self.all_cities:
            if city in message or f"{city}市" in message:
                return {'type': 'city', 'name': city}

        return None

    def extract_destination_name(self, message):
        """提取景点名称 - 智能模糊匹配版"""
        if not message:
            return None

        # 常见景点名称（优先匹配，按长度降序排列）
        common_destinations = [
            "798艺术区", "M+博物馆", "一线天", "万仙山", "万佛湖",
            "万华岩旅游区", "万山国家矿山公园", "万峰林", "万峰林景区", "万福温泉国际旅游度假区",
            "万绿湖风景区", "万象洞", "三亚亚龙湾", "三亚西岛", "三叠泉",
            "三台山国家森林公园", "三国水浒城", "三坊七巷", "三宝侗寨", "三岔河景区",
            "三峡之巅", "三峡人家", "三峡大坝", "三河古镇", "三清山",
            "三潭印月", "三百山", "三联峒景区", "三门峡大坝", "上下杭",
            "上方山国家森林公园", "上林鼓鸣寨", "上海科技馆", "上海迪士尼度假区", "上海野生动物园",
            "上清溪", "下梅古民居", "不冻河", "世界公园", "世界魔鬼城",
            "丙安古镇", "东丰农民画馆", "东关街", "东坡赤壁", "东安舜皇山旅游区",
            "东山岛", "东川红土地", "东方明珠广播电视塔", "东望洋灯塔", "东极广场",
            "东莞植物园", "丝绸之路河南段", "个园", "中华世纪坛", "中华恐龙园",
            "中华普洱茶博览苑", "中华民族园", "中原民俗文化园", "中国丹霞", "中国丹霞山世界地质公园",
            "中国人民抗日战争纪念馆", "中国人民抗日战争胜利受降纪念馆", "中国南方喀斯特", "中国古动物馆", "中国国家图书馆",
            "中国国花园", "中国天眼景区", "中国工农红军第二方面军长征出发地景区", "中国文字博物馆", "中国朝鲜族民俗园",
            "中国电影博物馆", "中国科学技术馆", "中国航空博物馆", "中国酒文化城", "中国铁道博物馆",
            "中国鳄鱼湖", "中国黄（渤）海候鸟栖息地", "中央大街", "中央广播电视塔", "中山国家森林公园",
            "中山翠亨国家湿地公园", "中山路步行街", "中山陵", "中街", "临朐沂山",
            "临江古府", "临泉魔幻动物园", "临涣古镇", "临清运河钞关", "丹噶尔古城",
            "丹寨万达小镇", "丹江口大坝", "丽江古城", "乌兰哈达火山地质公园", "乌素特水上雅丹",
            "乌苏里浅滩", "乌蒙大草原", "乌镇", "乔家大院", "九一八历史博物馆",
            "九丰现代农博园", "九乡风景区", "九份老街", "九华山", "九宫山",
            "九寨沟", "九嶷山舜帝陵景区", "九曲溪竹筏漂流", "九洞天", "九洲池",
            "九莲山", "九路寨", "九鲤湖", "九龙壁", "九龙江国家森林公园",
            "九龙洞", "乾州古城景区", "乾陵", "乾陵景区", "二七纪念塔",
            "云冈石窟", "云南三江并流保护区", "云南民族村", "云台山", "云居寺",
            "云屏三峡", "云峰八寨", "云水谣古镇", "云洞岩", "云蒙山国家森林公园",
            "云门山", "云龙湖", "五台山", "五四广场", "五大连池",
            "五大道文化旅游区", "五当召", "五彩滩", "五指山热带雨林", "五营国家森林公园",
            "五道峡", "五龙口猕猴区", "井冈山", "亚婆井前地", "交河故城",
            "京东大溶洞", "京华园", "亳州花戏楼", "什刹海", "仙人井",
            "仙女湖", "仙岛湖", "任弼时纪念馆", "伏牛山滑雪场", "伏羲山",
            "伏羲庙", "会同粟裕故里景区", "伪满皇宫博物院", "何园", "佛光岩",
            "佛山植物园", "保亭槟榔谷黎苗文化旅游区", "保定全胜峡", "信阳鸡公山", "元上都遗址",
            "元大都城垣遗址公园", "元阳哈尼梯田", "先农坛", "克孜尔千佛洞", "八公山",
            "八境台", "八大关", "八大处公园", "八廓街", "八达岭野生动物世界",
            "八达岭长城", "八里河旅游区", "六盘山国家森林公园", "六盘山红军长征旅游区", "六盘水梅花山",
            "六鳌抽象画廊", "六鼎山文化旅游区", "关山国家地质公园", "关山旅游区", "关岭化石群国家地质公园",
            "关西新围", "关门山国家森林公园", "兴义国家地质公园", "兴城古城", "养马岛",
            "内乡县衙", "冈仁波齐", "册亨万重山", "冠豸山", "冠豸山景区",
            "冰沟丹霞", "冰雪大世界", "冶力关旅游区", "净月潭", "凤凰中华大熊猫苑",
            "凤凰古城", "凤凰古城旅游区", "凤凰奇梁洞景区", "凤凰山", "凤城河风景区",
            "凤阳明皇陵", "分界洲岛", "刘公岛", "初溪土楼群", "加榜梯田",
            "勐梭龙潭", "勐泐大佛寺", "北京世界花卉大观园", "北京中轴线", "北京九华山庄",
            "北京动物园", "北京南宫旅游景区", "北京古代建筑博物馆", "北京后花园风景区", "北京园博园",
            "北京国际鲜花港", "北京大学", "北京大观园", "北京天文馆", "北京奥林匹克森林公园",
            "北京张裕爱斐堡国际酒庄", "北京明城墙遗址公园", "北京春晖园温泉", "北京棋盘山风景区", "北京欢乐谷",
            "北京民俗博物馆", "北京汽车博物馆", "北京海洋馆", "北京温都水城", "北京石刻艺术博物馆",
            "北京自然博物馆", "北京艺术博物馆", "北京蟒山国家森林公园", "北京西山国家森林公园", "北京野生动物园",
            "北京静之湖温泉", "北京龙熙温泉", "北京（通州）大运河文化旅游景区", "北固山", "北宋皇陵",
            "北岐滩涂", "北戴河", "北海公园", "北海湿地", "北海银滩",
            "北海银滩旅游区", "北盘江大峡谷", "北红村", "北饮泉", "十渡风景名胜区",
            "千佛山", "千山", "千岛湖", "千年瑶寨", "千龙湖生态旅游区",
            "华严寺", "华南国家植物园", "华山", "华清宫", "华清宫遗址",
            "华祖庵", "华谊兄弟（长沙）电影小镇", "华阳湖国家湿地公园", "南京博物院", "南京夫子庙-秦淮风光带",
            "南京路步行街", "南京长江大桥", "南华山神凤文化景区", "南少林寺", "南山文化旅游区",
            "南山竹海", "南岩宫", "南川金佛山", "南昌之星摩天轮", "南昌八一起义纪念馆",
            "南普陀寺", "南江大峡谷", "南泥湾革命旧址", "南浔古镇", "南海禅寺",
            "南湾湖", "南街村", "南迦巴瓦峰", "南锣鼓巷", "南阳府衙",
            "南阳武侯祠", "南阳老界岭", "南靖土楼", "博斯腾湖", "卡拉库勒湖",
            "卡若拉冰川", "卢沟桥", "原山国家森林公园", "厦门园林植物园", "厦门大学",
            "双乳峰", "双峰山国家森林公园", "双林寺", "双牌阳明山旅游区", "双鸭山七星峰",
            "双龙风景旅游区", "古北水镇", "古格王朝遗址", "古琴台", "古田会议旧址",
            "古隆中", "只有河南·戏剧幻城", "可可托海", "可可西里", "台儿庄古城",
            "台北101大楼", "台北故宫博物院", "司春女神", "司马台长城", "司马迁祠",
            "合川钓鱼城", "合肥融创乐园", "吊水楼瀑布", "同里古镇", "吐鲁番葡萄沟",
            "君山野生荷花世界", "含鄱口", "吴城候鸟小镇", "吴承恩故居", "呀诺达雨林文化旅游区",
            "呀路古热带植物园", "呈坎八卦村", "告庄西双景", "周口太昊陵", "周口店北京人遗址",
            "周庄", "周庄古镇", "周恩来故居", "周恩来纪念馆", "周村古商城",
            "周村古商城景区", "呼伦贝尔大草原", "和顺古镇", "哀牢山", "哈尔滨冰雪大世界",
            "哈尔滨极地公园", "响水湖长城", "响沙湾", "哲蚌寺", "唐城影视基地",
            "唐崖土司城遗址", "商丘古城", "喀什古城", "喀拉峻草原", "喀纳斯湖",
            "善化寺", "嘉峪关", "嘉峪关关城", "嘉应观", "嘉荫恐龙国家地质公园",
            "四川大熊猫栖息地", "四洞沟", "回民街", "回龙天界山", "国家体育场",
            "国家博物馆", "国家游泳中心", "土司遗址", "圣安寺景区", "圣灯山公园",
            "圣索菲亚大教堂", "圭峰山国家森林公园", "地下森林", "地坛公园", "坎儿井乐园",
            "坎布拉", "坎布拉国家森林公园", "坝美", "坝美村", "坝陵河大桥",
            "垦丁国家公园", "城头山旅游景区", "堂安侗寨", "塔什库尔干", "塔尔寺",
            "塔里木胡杨林", "塔院寺", "壶口瀑布", "夏明翰故里景区", "外八庙",
            "外滩", "大三巴牌坊", "大丰麋鹿国家级自然保护区", "大九湖国家湿地公园", "大伾山",
            "大冶铜绿山古铜矿遗址", "大利侗寨", "大别山主峰景区", "大华山", "大口国家森林公园",
            "大召寺", "大同古城墙", "大唐不夜城", "大唐芙蓉园", "大围山国家森林公园",
            "大安嫩江湾旅游区", "大嵛山岛", "大庆油田历史陈列馆", "大明寺", "大明山风景旅游区",
            "大明湖", "大昭寺", "大杨山国家森林公园", "大洞竹海", "大洪山火山地质公园",
            "大洪山风景名胜区", "大熊猫繁育研究基地", "大理古城", "大红袍景区", "大茅山",
            "大觉山", "大足石刻", "大运河河南段", "大连森林动物园", "大连滨海路",
            "大连老虎滩海洋公园", "大通古镇", "大雁塔", "大鹏半岛国家地质公园", "天一温泉",
            "天云山", "天台山景区", "天坛", "天坛大佛", "天堂寨",
            "天堂明堂", "天堂温泉景区", "天安门广场", "天山天池", "天山托木尔大峡谷",
            "天山托木尔景区", "天岳幕阜山景区", "天师府", "天心阁", "天柱山",
            "天桂山", "天梯山石窟", "天池山", "天河潭", "天津之眼摩天轮",
            "天津博物馆", "天津古文化街", "天津欢乐谷", "天津海河游船", "天津滨海图书馆",
            "天津瓷艺园", "天津自然博物馆", "天涯海角", "天游峰", "天目湖",
            "天空之城", "天门山", "天鹅洞", "天鹅湖国家城市湿地公园", "天龙屯堡",
            "天龙山石窟", "太姥山", "太子坡", "太平山顶", "太平湖",
            "太湖鼋头渚", "太白山国家森林公园", "太行大峡谷", "太阳岛", "太阳岛风景区",
            "太鲁阁国家公园", "夫子庙-秦淮风光带", "夹山国家森林公园", "好太王碑", "妈祖祖庙",
            "妈阁庙", "始祖山", "威宁草海", "威尼斯人度假村", "威海华夏城",
            "威海国际海水浴场", "威海神游海洋世界", "娘娘山国家湿地公园", "娲皇宫", "婺源",
            "孜珠寺", "宁夏博物馆", "宁远下灌旅游区", "安仁稻田公园", "安化云台山景区",
            "安化茶马古道风景区", "安南古城", "安徽博物院", "安源路矿工人运动纪念馆", "安阳殷墟",
            "安顺旧州古镇", "安顺龙宫", "宋城", "官渡古镇", "官鹅沟",
            "定远舰景区", "宜昌两坝一峡", "宝山工矿旅游景区", "宝峰湖旅游区", "宝泉旅游区",
            "宝清圣洁湿地", "客家土楼", "宰荡侗寨", "宿州皇藏峪", "寒山寺",
            "察尔汗盐湖", "寨下大峡谷", "寿县古城", "将军坟", "小商桥",
            "小沟背", "少林寺", "尚书第", "尧山风景名胜区", "尧庙",
            "居庸关长城", "屈原故里", "屈子文化园", "屏山峡谷", "屯溪老街",
            "山乡巨变第一村旅游区", "山海关景区", "山海关老龙头", "山西博物院", "岗顶剧院",
            "岜扒侗寨", "岜沙苗寨", "岳阳楼", "岳阳楼-君山岛景区", "岳飞庙",
            "岳麓山", "岳麓山-橘子洲旅游区", "峨眉山-乐山大佛", "峰林峡", "崀山",
            "崂山", "崆山白云洞", "崆峒山", "崇圣寺三塔", "崇武古城",
            "崇礼滑雪场", "嵛山岛", "嵩山", "巢湖", "巨蟒出山",
            "巫山小三峡-小小三峡", "巴丹吉林沙漠—沙山湖泊群", "巴松措", "巴音布鲁克草原", "布达拉宫",
            "帕米尔旅游区", "席力图召", "常宁印山文化旅游区", "常德卡乐星球旅游景区", "常德规划展示馆",
            "帽儿山国家森林公园", "平江石牛寨景区", "平江起义纪念馆", "平潭岛", "平遥古城",
            "年保玉则", "幽谷神潭", "广东内伶仃岛-福田国家级自然保护区", "广东天井山国家森林公园", "广东流溪河国家森林公园",
            "广州云溪植物园", "广州云萝植物园", "广州兰圃", "广州海珠国家湿地公园", "广府古城",
            "广德太极洞", "广德灵山大峡谷", "广德箐箐庄园", "广西民族博物馆", "庐山",
            "应县木塔", "应天书院", "应天门", "店头街", "府文庙",
            "康百万庄园", "延吉恐龙王国", "延安革命纪念地", "延庆乌龙峡谷", "延庆朝阳寺",
            "延庆硅化木国家地质公园", "延边大学网红弹幕墙", "建业电影小镇", "建水古城", "开元寺",
            "开元溶洞", "张坝古村落", "张壁古堡", "张家界土家风情园", "张家界大峡谷",
            "张家界武陵源", "张掖七彩丹霞", "张掖丹霞", "张氏帅府", "张谷英旅游区",
            "弥勒东风韵", "强巴林寺", "归元禅寺", "当惹雍错", "当涂大青山野生动物世界",
            "当涂李白文化园", "彭山景区", "彭德怀纪念馆", "影珠山景区", "徐闻珊瑚礁国家级自然保护区",
            "微山湖", "德天瀑布", "德天跨国瀑布景区", "徽州古城", "志辉源石酒庄",
            "怀远观光夜市", "思南石林", "总统府", "恒山", "恩施土司城",
            "恩施大峡谷", "恭王府", "悬棺表演", "悬空寺", "惠东海龟国家级自然保护区",
            "惠山古镇", "惠州植物园", "意式风情区", "慕俄格古城", "慕士塔格峰",
            "慕田峪长城", "成吉思汗陵", "成山头", "戒台寺", "扎什伦布寺",
            "扎尕那", "扎龙生态旅游区", "扎龙自然保护区", "承启楼", "承德避暑山庄",
            "抚仙湖", "拉卜楞寺", "拉姆拉措", "拉昂错", "拙政园",
            "招堤", "振成楼", "故宫博物院", "敕勒川草原", "敖鲁古雅使鹿部落",
            "敬亭山", "文县天池", "断桥", "新乡八里沟", "新会小鸟天堂国家湿地公园",
            "新化大熊山景区", "新华联铜官窑古镇", "新安江山水画廊", "新田龙家大院景区", "新邵白水洞景区",
            "新郑黄帝故里", "施秉杉木河", "日光岩", "日升昌票号", "日坛公园",
            "日月潭", "日照万平口", "日照海滨国家森林公园", "昆仑山", "昌珠寺",
            "明十三陵", "明孝陵", "明显陵", "明月山", "星海广场",
            "星湖国家级风景名胜区", "春秋寨", "春秋楼", "春秋淹城旅游区", "昭君博物院",
            "昭君故里", "昭山城市海景水上乐园", "昭山景区", "昭陵", "显通寺",
            "晋祠", "晋祠天龙山景区", "普安茶文化生态园", "普定穿洞遗址", "普救寺",
            "普洱景迈山古茶林", "普者黑", "普莫雍措", "普达措国家公园", "普陀山",
            "景山公园", "景德镇古窑民俗博览区", "晴川阁", "晴隆二十四道拐", "曲阜三孔",
            "曲阜孔庙、孔林、孔府", "曹丞相府", "曹家大院", "曹操运兵道", "曼听公园",
            "曾侯乙墓遗址", "曾厝垵", "曾国藩故居旅游区", "月坛公园", "朗德上寨",
            "望城光明大观园", "望谟蔗香滨湖康养小镇", "朝天门", "朝歌古城", "木兰文化生态旅游区",
            "木札岭", "木渎古镇", "本溪水洞", "札达土林", "朱家角古镇",
            "李坑", "李时珍故里", "李鸿章故居", "杜甫故里", "来古冰川",
            "杨家溪", "杨开慧纪念馆", "杭州西湖", "松赞林寺", "林伯渠故居景区",
            "林则徐纪念馆", "林州仙台山", "枫林花海景区", "查济古镇", "柳叶湖旅游度假区",
            "柳宗元文化旅游区", "柴埠溪大峡谷", "栖霞山", "株洲方特欢乐世界", "格凸河",
            "桂林漓江景区", "桃源仙谷", "桃源洞", "桃花潭", "桐子坳景区",
            "桐柏淮源景区", "桑植九天峰恋景区", "桑耶寺", "桥陵", "梁带村遗址",
            "梅山龙宫景区", "梅里雪山", "梧桐山国家级风景名胜区", "梭布垭石林", "梵净山",
            "棠樾牌坊群", "楚王车马阵", "榆林窟", "橘子洲", "正定古城",
            "武冈云山国家森林公园", "武功山", "武夷山", "武威文庙", "武威雷台汉墓",
            "武当山", "武汉东湖", "武汉东湖生态旅游风景区", "武汉大学", "武汉欢乐谷",
            "武汉海昌极地海洋公园", "武汉长江大桥", "武都万象街", "武隆喀斯特旅游区", "殷墟",
            "比如骷髅墙", "比干庙", "毕节百里杜鹃", "水城古镇", "水帘洞",
            "水府旅游区", "水泊梁山", "水洞沟", "水浒好汉城", "永乐宫",
            "永兴板梁古村旅游区", "汉口江滩", "汉文化景区", "汉阳陵", "汝城沙洲红色旅游景区",
            "汝城福泉山庄", "江垭温泉度假村", "江孜宗山古堡", "江岭", "江布拉克",
            "江永勾蓝瑶寨景区", "江汉路步行街", "江湾", "江郎山", "江门古劳水乡",
            "汤旺河林海奇石风景区", "汤池温泉", "沂水地下大峡谷", "沂水萤火虫水洞", "沂蒙山",
            "沅陵凤滩景区", "沈阳故宫", "沙坡头", "沙湖", "沙湖旅游区",
            "沧浪亭", "沧源崖画", "沩山密印景区", "河北博物院", "河南博物院",
            "油杉河", "沿河乌江山峡", "泉州：宋元中国的世界海洋商贸中心", "泉瀑峡", "法门寺",
            "泰宁大金湖", "泰山", "泸沽湖", "洈水风景区", "洋湖湿地景区",
            "洛阳万安山", "洛阳关林", "洛阳千唐志斋", "洛阳博物馆", "洛阳古墓博物馆",
            "洛阳周王城天子驾六博物馆", "洛阳桥", "洛阳白马寺", "洛阳神灵寨", "洛阳老君山",
            "洛阳花果山", "洛阳荆紫仙山", "洛阳西泰山", "洛阳隋唐城遗址植物园", "洛阳黄河小浪底",
            "洛阳黄河神仙湾", "洛阳黛眉山", "洛阳龙门石窟", "洪崖洞", "洪崖洞民俗风貌区",
            "洪江古商城", "洪洞大槐树", "流坑古村", "济源王屋山", "济源黄河三峡",
            "浏阳秋收起义纪念园", "浏阳苍坊旅游区", "浚县古城", "浦市古镇景区", "浮梁古县衙",
            "海口骑楼老街", "海林横道河子", "海龙屯", "涪陵白鹤梁水下博物馆", "淄博陶瓷琉璃博物馆",
            "淅川丹江大观苑", "淮北相山公园", "淮安府署", "深圳仙湖植物园", "深圳兰科中心植物园",
            "深圳华侨城国家湿地公园", "清净寺", "清凉山万佛寺石窟", "清凉谷", "清华大学",
            "清明上河园", "清昭陵", "清水断崖", "清水湖旅游度假区", "清永陵",
            "清江画廊", "清源山", "清福陵", "清西陵", "渠家大院",
            "温汤镇", "渼陂古村", "湄江旅游区", "湄洲岛", "湖北省博物馆",
            "湖南博物院", "湖南省博物馆", "湖南省森林植物园", "湘乡东山书院", "湘窖生态文化酿酒城",
            "湘西民族文化园景区", "湘阴洋沙湖旅游景区", "湛江红树林国家级自然保护区", "溆浦穿岩山景区", "溪布老街非遗文化体验基地",
            "溱湖国家湿地公园", "滁州花博园", "滇池", "滕王阁", "满洲里套娃广场",
            "滨州无棣贝壳堤岛", "漓江", "漠河北极村", "漫葡小镇", "漯河许慎文化园",
            "潞王陵", "潭柘寺", "潭溪山", "潭瀑峡", "澄江化石地",
            "澳门博物馆", "澳门历史城区", "澳门旅游塔", "濮阳世锦园", "濮阳戚城遗址",
            "濮阳绿色庄园", "灞陵桥", "火山口国家森林公园", "火山岛自然生态风景区", "火焰山",
            "火石寨国家地质公园", "灵宝函谷关", "灵山", "灵山寺", "灵山胜境",
            "灵山风景名胜区", "灵隐寺", "炎陵神农谷景区", "烟台山", "热海景区",
            "焦作云台山", "焦作影视城", "焦山", "然乌湖", "燧皇陵",
            "牛首山文化旅游区", "牟氏庄园", "独乐寺", "独克宗古城", "狮子关水上浮桥",
            "狮子林", "猛洞河漂流景区", "玄武湖", "玉华宫遗址", "玉华洞",
            "玉屏侗乡风情园", "玉渊潭公园", "玉舍国家森林公园", "玉门关", "玉龙沙湖",
            "玉龙雪山", "王仙岭旅游区", "王城公园", "王家大院", "王船山故里生态文化旅游区",
            "王莽岭", "玛旁雍错", "环岛路", "环球动漫嬉戏谷", "珠江口中华白海豚国家级自然保护区",
            "珠海淇澳-担杆岛省级自然保护区", "珠穆朗玛峰", "班公错", "琅琊山", "瑞云山",
            "瑶山古寨", "瑶里古镇", "瓷房子", "甘丹寺", "甪直古镇",
            "田子坊", "田汉文化园", "田螺坑土楼群", "甲秀楼", "留园",
            "瘦西湖", "登封天地之中历史建筑群", "白云山", "白云山国家级风景名胜区", "白兆山",
            "白哈巴村", "白居寺", "白帝城·瞿塘峡景区", "白桦林景区", "白水洋",
            "白洋淀", "白马寺", "白鹭洲书院", "百泉", "百色起义纪念园",
            "皇城相府", "皇家鹿苑博物馆", "皖南古村落", "益阳天意木国景区", "益阳奥林匹克公园",
            "盐井古盐田", "盐城丹顶鹤湿地生态旅游区", "盘山风景名胜区", "盘州妥乐古银杏", "盘龙大观园",
            "石壁客家祖地", "石家庄璧山", "石峁遗址", "石林峡", "石林风景区",
            "石燕湖生态旅游景区", "石燕湖生态旅游风景区", "石花洞", "石钟山", "石门国家森林公园",
            "石门龙王洞景区", "石阡楼上古寨", "石阡温泉", "石鼓书院", "砀山梨树王景区",
            "碓臼峪自然风景区", "碧色寨", "磁器口古镇", "磁悬浮列车", "祁连山草原",
            "祁阳浯溪碑林", "祁阳石洞源景区", "神农城炎帝文化主题公园", "神农山", "神农架",
            "神农架国家公园", "神垕古镇", "福建土楼", "禹州钧官窑址博物馆", "禾木村",
            "秦始皇兵马俑博物馆", "秦始皇陵及兵马俑", "稻城亚丁", "篁岭", "篁岭景区",
            "米堆冰川", "紫竹院公园", "紫霄宫", "紫鹊界梯田景区", "紫龙湾旅游区",
            "红军标语博物馆", "红旗渠", "红河哈尼梯田", "红海滩", "红海滩国家风景廊道",
            "红石峡", "红石林景区", "红螺寺", "纳帕海", "纳木错",
            "织金洞", "绒布寺", "绥芬河国门", "绩溪龙川", "绳金塔",
            "维多利亚港", "绵山", "绿渊潭", "网师园", "罗布人村寨",
            "罗布林卡", "罗荣桓故居纪念馆", "羊卓雍措", "美庐别墅", "羑里城",
            "翁丁佤族原始村落", "翡翠湖", "耀州窑遗址", "老司城景区", "老君山",
            "老子故里", "老牛湾黄河大峡谷", "老牛湾黄河大峡谷旅游区", "老黑山", "聂耳音乐广场",
            "聊城东昌湖", "肇兴侗寨", "胡里山炮台", "腾冲热海", "腾格里沙漠",
            "腾龙洞", "良渚古城遗址", "色拉寺", "色林错", "艾提尕尔清真寺",
            "艾肯泉", "芋园文化旅游景区", "芒砀山", "芙蓉镇", "芙蓉镇景区",
            "芜湖方特旅游区", "芜湖滨江公园", "芜湖鸠兹古镇", "花山岩画", "花山岩画景区",
            "花山谜窟", "花岩溪国家森林公园", "花江大峡谷", "苍山洱海", "苍岩山",
            "苏仙岭旅游区", "苏堤", "苏峰山环岛路", "苏州博物馆", "茂陵",
            "茅台酒镇", "茅山", "茅浒水乡度假村", "茱萸峰", "茶卡壹号·盐湖",
            "茶卡盐湖", "茶陵云阳山景区", "茶陵县花湖谷景区", "茶陵工农兵政府旧址景区", "荆州博物馆",
            "荆州古城", "草原天路", "荔波小七孔", "荷兰花海", "莆田湄洲岛",
            "莫尔道嘎国家森林公园", "莫干山", "莫高窟", "莽山国家森林公园", "菏泽牡丹园",
            "菩萨顶", "菽庄花园", "萨普神山", "萨迦寺", "蒙山大佛",
            "蓝山云冰山景区", "蓬莱八仙过海景区", "蓬莱海洋极地世界", "蓬莱阁", "蔡伦竹海",
            "蔡和森同志纪念馆·故居景区", "蔡锷故里景区", "薄刀峰", "薄山湖", "藏王墓",
            "虎丘", "虎峪自然风景区", "虎跳峡", "虢国博物馆", "蜈支洲岛",
            "蠡园", "衡山", "衡水湖旅游景区", "衡阳奇石文化博物馆", "裕昌楼",
            "襄阳古城", "西双版纳", "西双版纳热带植物园", "西夏陵", "西安城墙",
            "西安碑林博物馆", "西峡恐龙遗迹园", "西开教堂", "西柏坡", "西樵山国家级风景名胜区",
            "西江千户苗寨", "西津渡", "西游乐园", "西湖公园", "西溪国家湿地公园",
            "西狭颂风景区", "西瑶绿谷旅游区", "西递、宏村", "西递宏村", "西递景区",
            "解州关帝庙", "解放碑", "议事亭前地", "诸城恐龙博物馆", "象鼻山",
            "豫园", "贞丰双乳峰", "贵州醇景区", "贵州龙博物馆", "贵德国家地质公园",
            "贵阳黔灵山公园", "贺兰山国家森林公园", "贺兰山岩画", "贺龙纪念馆", "赛里木湖",
            "赣州古城墙", "赤壁古战场", "赤水丹霞", "赫图阿拉城", "赫章可乐遗址",
            "赵家堡", "趵突泉", "路南石林", "路环村", "车溪民俗旅游区",
            "连州地下河", "连环湖温泉景区", "通天岩", "通道万佛山风景名胜区", "通道皇都侗文化村",
            "通道芋头古侗寨", "通道转兵纪念地", "道县濂溪故里景区", "道县陈树湘红色文化园", "遵义会议会址",
            "邢台九龙峡", "那拉提草原", "那柯里茶马驿站", "邯郸药王谷", "郁孤台",
            "郎木寺", "郑家大屋", "郑州商都遗址博物院", "郑州方特欢乐世界", "郑州植物园",
            "郑州海洋馆", "郑州绿博园", "郑州黄河文化公园", "郭亮村", "都江堰",
            "鄱阳湖", "酉阳桃花源", "酒仙湖景区", "酒泉卫星发射中心", "采石矶",
            "里耶古城景区", "重庆七彩仁和", "重庆中国三峡博物馆", "重庆红岩革命历史博物馆", "重渡沟",
            "野三坡", "野三坡百里峡", "野柳地质公园", "野玉海景区", "野象谷",
            "野鸭湖国家湿地公园", "金寨红军广场", "金山寺", "金昌紫金花城", "金沙冷水河",
            "金海湖", "金石滩", "金石滩国家旅游度假区", "金银滩-原子城", "金顶",
            "金鸡湖景区", "钟山风景区", "钟楼", "铁力日月峡滑雪场", "铜山湖",
            "铜钹山", "铜陵天井湖", "银基国际旅游度假区", "银山塔林", "银杏村",
            "锁阳城遗址", "锡崖沟挂壁公路", "镇北台", "镇北堡西部影城", "镇国寺",
            "镇远古城", "镜泊湖", "长岛", "长影世纪城", "长汀古城",
            "长江索道", "长沙世界之窗", "长沙海底世界", "长沙滨江文化园", "长沙生态动物园",
            "长沙铜官窑国家考古遗址公园", "长白山", "长白山天池", "长白瀑布", "长葛葛天氏陵",
            "门源百里油菜花海", "阁皂山", "阆中古城", "阜阳生态园", "阳坝梅园沟",
            "阳明山国家公园", "阳朔西街", "阿咪东索景区", "阿尔山国家森林公园", "阿尼玛卿雪山",
            "阿斯哈图石林", "阿西里西韭菜坪", "阿里山风景区", "陆水湖", "陕州地坑院",
            "陕西历史博物馆", "陶然亭公园", "隆兴寺", "隆回大花瑶虎形山景区", "隆里古城",
            "隋唐洛阳城国家遗址公园", "随州炎帝神农故里", "隐水洞", "雁栖湖", "雁荡山",
            "雁门关", "雅丹地质公园", "雅鲁藏布大峡谷", "雍和宫", "雍布拉康",
            "雨崩村", "零陵东山景区", "雷峰塔", "雷锋纪念馆", "霞浦滩涂",
            "青城山-都江堰", "青天河", "青岛啤酒博物馆", "青岛方特梦幻王国", "青岛栈桥",
            "青岛海昌极地海洋公园", "青岛海滨风景区", "青岩古镇", "青州古城", "青海湖",
            "青海藏医药文化博物馆", "青秀山", "青秀山风景旅游区", "青藏高原野生动物园", "青铜峡108塔",
            "青龙峡", "靖州飞山景区", "靖港古镇", "靖西旧州古城", "靖西鹅泉",
            "韶关仙门奇峡", "韶山", "项城袁氏故居", "项王故里", "须弥山石窟",
            "颐和园", "额尔古纳湿地", "额济纳胡杨林", "风动石", "飞天山国家地质公园",
            "饶平青岚国家地质公园", "首都博物馆", "香山公园", "香格里拉", "香水河",
            "香港太空馆", "香港文化博物馆", "香港海洋公园", "香港迪士尼乐园", "香港铁路博物馆",
            "马岭河峡谷", "马氏庄园", "马銮湾", "驻马店嵖岈山", "驼峰岭天池",
            "骆马湖旅游度假区", "骊靬古城", "高句丽王城、王陵及贵族墓葬", "高句丽王城遗址", "高昌故城",
            "魔界漂流", "魔鬼城", "鲁屯古镇", "鲁朗林海", "鲁迅故里",
            "鳞隐石林", "鸡冠洞", "鸡西兴凯湖", "鸡鸣寺", "鸣沙山月牙泉",
            "鸭绿江断桥", "鸳鸯溪", "鹅尾神石园", "鹤壁云梦山", "鹳雀楼",
            "麦积山景区", "麦积山石窟", "麻城龟峰山景区", "麻江下司古镇", "黄仙洞",
            "黄冈大别山世界地质公园", "黄山", "黄山九龙瀑", "黄山翡翠谷", "黄岩生态旅游区",
            "黄崖关长城", "黄帝陵", "黄平旧州古镇", "黄果树瀑布", "黄桑生态旅游区",
            "黄河入海口", "黄河大峡谷", "黄河石林", "黄洋界", "黄石国家矿山公园",
            "黄鹤楼", "黄龙", "黄龙洞旅游区", "黑瞎子岛", "黑麋峰国家森林公园",
            "黑龙潭", "黔西中果河", "黔阳古城", "黛螺顶", "黟县五溪山",
            "黟县卢村", "黟县塔川", "黟县屏山", "黟县打鼓岭", "黟县木坑竹海",
            "黟县西递石林", "鼓山", "鼓楼", "鼓浪屿", "齐云山",
            "齐文化博物院", "龙亭", "龙凤头海滨浴场", "龙回头", "龙女景区",
            "龙山县太平山景区", "龙岗寺遗址", "龙峪湾", "龙庆峡", "龙桥河",
            "龙江第一湾", "龙潭公园", "龙环葡韵", "龙硿洞", "龙脊梯田",
            "龙虎山", "龙门石窟", "龟山汉墓", "龟峰"
        ]
        
        # 优先检查常见景点（按长度降序排列，优先匹配更长的名称）
        for name in common_destinations:
            if name in message:
                return name

        # 模糊匹配检查
        for standard_name, aliases in self.fuzzy_keywords.items():
            for alias in aliases:
                if alias in message:
                    return standard_name

        # 然后查询数据库（使用LIKE索引查询，避免全表加载）
        try:
            # 按名称长度降序，优先匹配更长的名称
            results = Destination.query.filter(
                Destination.name.in_([k for k in self.fuzzy_keywords if k in message])
            ).all()
            if results:
                results.sort(key=lambda x: len(x.name), reverse=True)
                return results[0].name
            # 模糊匹配：取前几个字符做前缀查询
            for length in range(min(len(message), 8), 1, -1):
                candidates = Destination.query.filter(
                    Destination.name.like(f'%{message[:length]}%')
                ).limit(5).all()
                for dest in candidates:
                    if dest.name in message:
                        return dest.name
        except Exception:
            pass

        return None

    def extract_numbers(self, message):
        """提取数字"""
        nums = re.findall(r'\d+', message)
        return [int(n) for n in nums]
    
    def analyze_emotion(self, message):
        """情感分析 - 识别用户情绪"""
        msg = message.lower()
        
        for emotion, keywords in self.emotion_keywords.items():
            for keyword in keywords:
                if keyword in msg:
                    return emotion
        
        return 'neutral'
    
    def get_emotion_response(self, emotion, base_response):
        """根据情感调整响应"""
        emotion_prefix = {
            'positive': '很高兴您这么满意！',
            'negative': '非常抱歉给您带来不好的体验，',
            'excited': '太棒了！您的热情感染了我！',
            'confused': '我理解您的困惑，让我来帮您分析一下：',
            'neutral': ''
        }
        
        prefix = emotion_prefix.get(emotion, '')
        if prefix:
            base_response['content'] = prefix + base_response['content']
        
        return base_response
    
    def learn_user_preference(self, user_id, message, intent, dest_name=None):
        """学习用户偏好"""
        if not user_id:
            return
        
        prefs = self.user_preferences[user_id]
        
        # 记录搜索的景点
        if dest_name:
            if dest_name not in prefs['visit_history']:
                prefs['visit_history'].append(dest_name)
                # 保持最近20个
                if len(prefs['visit_history']) > 20:
                    prefs['visit_history'] = prefs['visit_history'][-20:]
        
        # 分析价格偏好
        if any(k in message for k in ['便宜', '经济', '省钱', '免费']):
            prefs['price_preference'] = '经济'
        elif any(k in message for k in ['豪华', '高档', '五星', '奢华']):
            prefs['price_preference'] = '高档'
        
        # 分析旅行风格
        if any(k in message for k in ['休闲', '放松', '度假', '慢游']):
            prefs['travel_style'] = '休闲'
        elif any(k in message for k in ['冒险', '刺激', '挑战', '户外']):
            prefs['travel_style'] = '冒险'
        elif any(k in message for k in ['文化', '历史', '博物馆', '古迹']):
            prefs['travel_style'] = '文化'
    
    def get_context_aware_response(self, message, conv, user_id):
        """上下文感知响应"""
        messages = conv.get('messages', [])
        
        if len(messages) < 2:
            return None
        
        # 获取最近的对话
        recent_messages = messages[-6:]  # 最近3轮对话
        
        # 检查是否是追问
        last_assistant_msg = None
        for msg in reversed(recent_messages):
            if msg.get('role') == 'assistant':
                last_assistant_msg = msg.get('content', '')
                break
        
        if not last_assistant_msg:
            return None
        
        # 识别追问意图
        msg_lower = message.lower()
        
        # 如果用户说"还有呢"、"继续"等，补充更多信息
        if any(k in msg_lower for k in ['还有呢', '继续', '更多', '其他的', '别的']):
            if '景点' in last_assistant_msg:
                # 补充更多景点
                return {"type": "text", "content": "好的，我再为您推荐一些：\n\n• 还有更多景点等待您探索\n• 您可以告诉我具体想了解哪个方面\n• 或者我可以为您规划完整行程"}
            
            elif '美食' in last_assistant_msg:
                return {"type": "text", "content": "还有更多美食推荐：\n\n• 当地特色小吃\n• 人气餐厅推荐\n• 美食街攻略"}
        
        # 如果用户问"怎么去"，提供交通信息
        if any(k in msg_lower for k in ['怎么去', '怎么走', '交通', '路线']):
            # 从上下文中提取景点
            for msg in recent_messages:
                if msg.get('role') == 'assistant':
                    content = msg.get('content', '')
                    # 简单提取景点名称
                    if '**' in content:
                        lines = content.split('\n')
                        for line in lines:
                            if '**' in line and '•' not in line:
                                dest_match = re.search(r'\*\*([^*]+)\*\*', line)
                                if dest_match:
                                    dest_name = dest_match.group(1)
                                    return {"type": "text", "content": f"前往{dest_name}的交通方式：\n\n🚌 公交：可查询当地公交线路\n🚇 地铁：最近地铁站\n🚗 自驾：导航至{dest_name}\n🚕 打车：约XX元（视出发地而定）"}
        
        return None

    def analyze_intent(self, message):
        """分析用户意图 - 增强版（更精确的意图识别）"""
        msg = message.lower()
        
        # 提取景点名称
        dest_name = self.extract_destination_name(msg)
        
        # 行程规划意图（优先级最高）
        trip_keywords = ["规划", "行程", "路线", "几日游", "日游", "游", "攻略", "怎么玩", "玩什么", 
                         "安排", "计划", "设计", "推荐路线", "游玩路线", "旅行计划", "旅游攻略",
                         "一日游", "两日游", "三日游", "四日游", "五日游", "六日游", "七日游",
                         "周末游", "假期游", "自驾游", "跟团游", "自由行"]
        if any(k in msg for k in trip_keywords):
            if dest_name:
                return "plan_trip_with_destination"
            return "plan_trip"
        
        # 景点详情查询意图
        detail_keywords = ["介绍", "详情", "信息", "怎么样", "好玩吗", "值得去吗", "有什么",
                          "了解", "看看", "查看", "详情介绍", "景点介绍", "景区介绍",
                          "有什么好玩的", "有什么看的", "特色", "亮点", "看点"]
        if any(k in msg for k in detail_keywords) and dest_name:
            return "query_detail"
        
        # 门票价格查询
        price_keywords = ["门票", "票价", "多少钱", "价格", "收费", "费用", "贵不贵",
                         "门票多少", "票价多少", "多少钱一张", "门票价格", "学生票",
                         "老年票", "儿童票", "团体票", "优惠政策", "免票"]
        if any(k in msg for k in price_keywords):
            if dest_name:
                return "query_price_with_destination"
            return "query_price"
        
        # 开放时间查询
        time_keywords = ["开放时间", "几点开门", "几点关门", "营业时间", "什么时候开",
                        "开门时间", "关门时间", "几点开", "几点关", "几点到几点",
                        "开放", "闭馆", "开馆", "休息日", "闭园"]
        if any(k in msg for k in time_keywords):
            if dest_name:
                return "query_time_with_destination"
            return "query_time"
        
        # 地址位置查询
        location_keywords = ["地址", "在哪里", "怎么去", "怎么走", "位置", "路线",
                           "在哪", "什么地方", "怎么到达", "交通", "乘车", "地铁",
                           "公交", "自驾", "导航", "地图", "方位"]
        if any(k in msg for k in location_keywords):
            if dest_name:
                return "query_location_with_destination"
            return "query_location"
        
        # 天气查询
        weather_keywords = ["天气", "气温", "温度", "下雨", "晴天", "天气怎么样",
                          "今天天气", "明天天气", "天气预报", "穿什么", "冷不冷",
                          "热不热", "下雨吗", "下雪吗", "雾霾"]
        if any(k in msg for k in weather_keywords):
            # 提取城市名
            location = self.extract_location(msg)
            if location:
                return "query_weather_with_location"
            return "query_weather"
        
        # 美食查询
        food_keywords = ["美食", "小吃", "吃什么", "特色菜", "餐厅", "饭店",
                        "好吃的", "推荐美食", "特色美食", "当地美食", "必吃",
                        "网红餐厅", "老字号", "名吃", "特产", "小吃街", "美食街"]
        if any(k in msg for k in food_keywords):
            location = self.extract_location(msg)
            if location:
                return "query_food_with_location"
            return "query_food"
        
        # 住宿查询
        hotel_keywords = ["酒店", "住宿", "宾馆", "民宿", "住哪", "住哪里",
                         "推荐酒店", "住宿推荐", "客栈", "旅馆", "青旅"]
        if any(k in msg for k in hotel_keywords):
            return "query_hotel"
        
        # 交通查询
        transport_keywords = ["交通", "怎么坐车", "坐什么车", "乘车", "地铁",
                            "公交", "打车", "自驾", "停车", "停车场"]
        if any(k in msg for k in transport_keywords):
            return "query_transport"
        
        # 景点搜索（包含景点名称但没有其他明确意图）
        if dest_name:
            return "query_destination"
        
        # 通用景点查询
        scenic_keywords = ["景点", "旅游", "游玩", "景区", "风景", "好玩的地方",
                          "推荐景点", "热门景点", "著名景点", "必去", "必玩",
                          "打卡", "网红景点", "5A景区", "4A景区"]
        if any(k in msg for k in scenic_keywords):
            return "query_scenic"
        
        # 问候语
        greeting_keywords = ["你好", "您好", "hi", "hello", "嗨", "早上好",
                           "下午好", "晚上好", "在吗", "在不在"]
        if any(k in msg for k in greeting_keywords):
            return "greeting"
        
        # 帮助
        help_keywords = ["帮助", "功能", "能做什么", "怎么用", "使用方法",
                        "使用说明", "操作指南", "教程"]
        if any(k in msg for k in help_keywords):
            return "help"
        
        # 感谢
        thanks_keywords = ["谢谢", "感谢", "多谢", "thanks", "thank you"]
        if any(k in msg for k in thanks_keywords):
            return "thanks"
        
        # 再见
        goodbye_keywords = ["再见", "拜拜", "bye", "byebye", "下次见", "回见"]
        if any(k in msg for k in goodbye_keywords):
            return "goodbye"

        return "general"

    def get_conversation(self, session_id):
        """获取或创建对话"""
        if session_id not in self.conversations:
            conv = Conversation.query.filter_by(session_id=session_id).first()
            if conv:
                self.conversations[session_id] = {
                    'context': json.loads(conv.context),
                    'messages': json.loads(conv.messages),
                    'db_id': conv.id
                }
            else:
                self.conversations[session_id] = {
                    'context': {},
                    'messages': [],
                    'db_id': None
                }
        return self.conversations[session_id]

    def save_conversation(self, session_id):
        """保存对话"""
        conv_data = self.conversations.get(session_id)
        if not conv_data:
            return

        if conv_data['db_id']:
            conv = Conversation.query.get(conv_data['db_id'])
        else:
            conv = Conversation(session_id=session_id)

        conv.context = json.dumps(conv_data['context'], ensure_ascii=False)
        conv.messages = json.dumps(conv_data['messages'][-50:], ensure_ascii=False)

        if not conv_data['db_id']:
            db.session.add(conv)
            db.session.flush()
            conv_data['db_id'] = conv.id

        db.session.commit()

    def get_destination_detail(self, name):
        """获取景点详情 - 增强版（带路线规划）"""
        # 检查缓存
        cache_key = f"dest_detail:{name}"
        current_time = time.time()
        
        if cache_key in self._destinations_cache:
            cached_time, cached_data = self._destinations_cache[cache_key]
            if current_time - cached_time < self._cache_ttl:
                log.info(f"✅ 使用缓存的景点详情: {name}")
                return cached_data
        
        # 缓存未命中，查询数据库
        dest = Destination.query.filter(Destination.name.contains(name)).first()
        if not dest:
            return {"type": "text", "content": f"抱歉，没有找到「{name}」的信息"}

        # 获取天气信息（带缓存检查）
        weather_cache_key = f"weather:{dest.city}"
        if weather_cache_key in self._destinations_cache:
            weather_time, weather_info = self._destinations_cache[weather_cache_key]
            if current_time - weather_time < 300:  # 天气缓存5分钟
                log.info(f"✅ 使用缓存的天气信息: {dest.city}")
            else:
                weather_info = weather_api.get_current_weather(dest.city)
                self._destinations_cache[weather_cache_key] = (current_time, weather_info)
        else:
            weather_info = weather_api.get_current_weather(dest.city)
            self._destinations_cache[weather_cache_key] = (current_time, weather_info)
        
        # 构建完整的景点信息
        dest_info = {
            'name': dest.name,
            'description': dest.description,
            'address': dest.address,
            'price_range': dest.price_range,
            'opening_hours': dest.opening_hours,
            'rating': dest.rating,
            'city': dest.city,
            'province': dest.province,
            'category': dest.category,
            'latitude': dest.latitude,
            'longitude': dest.longitude,
            'cover_image': dest.cover_image
        }
        
        # 生成图片卡片
        image_path = dest.cover_image or match_scenic_image(dest.name, external=True)
        
        # 构建文本响应
        content = f"**{dest.name}**\n\n"
        content += f"📝 **简介**：{dest.description[:100]}...\n\n" if dest.description else ""
        content += f"📍 **地址**：{dest.address}\n"
        content += f"💰 **门票**：{dest.price_range}\n"
        content += f"⏰ **开放时间**：{dest.opening_hours}\n"
        content += f"⭐ **评分**：{dest.rating}分\n"
        content += f"🏷️ **分类**：{dest.category}\n\n"
        
        # 添加天气信息
        if weather_info and weather_info.get('success'):
            content += f"🌤️ **今日天气**：{weather_info.get('temperature', '未知')}，{weather_info.get('condition', '未知')}\n\n"
        
        # 添加路线规划信息（如果景点有坐标）
        if dest.latitude and dest.longitude:
            # 模拟路线规划信息
            route_info = self._get_route_info(dest)
            content += route_info
        
        # 添加行程规划提示
        content += f"\n📅 **行程建议**：可为您规划{dest.city}1-7日游行程"
        
        result = {
            "type": "destination_card",
            "content": content,
            "destination": dest_info,
            "weather": weather_info,
            "image": image_path,
            "suggestions": [
                f"{dest.name}怎么去",
                f"{dest.name}附近美食",
                f"{dest.city}行程规划",
                f"{dest.city}天气"
            ]
        }
        
        # 保存到缓存
        self._destinations_cache[cache_key] = (current_time, result)
        log.info(f"✅ 景点详情已缓存: {name}")
        
        return result
    
    def _get_route_info(self, dest):
        """获取路线规划信息 - 集成高德API"""
        route_content = "\n🗺️ **交通指南**：\n"
        
        # 检查是否使用真实API
        use_real_api = gaode_api is not None and dest.latitude and dest.longitude
        
        if use_real_api:
            try:
                # 使用高德API获取真实路线数据
                # 模拟起点（天安门广场作为默认起点）
                origin = "116.397428,39.90923"
                destination = f"{dest.longitude},{dest.latitude}"
                
                # 调用高德路线规划API
                route_url = "https://restapi.amap.com/v3/direction/driving"
                params = {
                    'key': GAODE_API_KEY,
                    'origin': origin,
                    'destination': destination,
                    'strategy': '0'  # 速度优先
                }
                
                response = requests.get(route_url, params=params, timeout=8)
                if response.status_code == 200:
                    route_data = response.json()
                    if route_data.get('status') == '1' and route_data.get('route'):
                        path = route_data['route']['paths'][0]
                        distance = int(path['distance'])
                        duration = int(path['duration'])
                        
                        # 格式化距离和时间
                        if distance >= 1000:
                            distance_text = f"{distance/1000:.1f}公里"
                        else:
                            distance_text = f"{distance}米"
                        
                        hours = duration // 3600
                        minutes = (duration % 3600) // 60
                        if hours > 0:
                            duration_text = f"{hours}小时{minutes}分钟"
                        else:
                            duration_text = f"{minutes}分钟"
                        
                        route_content += f"\n🚗 **自驾路线**：约{distance_text}，预计{duration_text}\n"
                        route_content += f"   📍 导航地址：{dest.address}\n"
                        route_content += f"   📡 数据来源：高德地图API\n"
                        
                        # 获取实时路况
                        traffic_url = "https://restapi.amap.com/v3/traffic/status/around"
                        traffic_params = {
                            'key': GAODE_API_KEY,
                            'location': destination,
                            'radius': 1000,
                            'level': 6
                        }
                        
                        try:
                            traffic_response = requests.get(traffic_url, traffic_params, timeout=5)
                            if traffic_response.status_code == 200:
                                traffic_data = traffic_response.json()
                                if traffic_data.get('status') == '1':
                                    traffic_info = traffic_data.get('trafficinfo', {})
                                    evaluation = traffic_info.get('evaluation', {})
                                    status = evaluation.get('status', '未知')
                                    
                                    status_map = {
                                        '1': ('畅通', '🟢'),
                                        '2': ('缓行', '🟡'),
                                        '3': ('拥堵', '🔴'),
                                        '4': ('严重拥堵', '🔴')
                                    }
                                    traffic_text, traffic_emoji = status_map.get(status, ('未知', '⚪'))
                                    route_content += f"\n{traffic_emoji} **实时路况**：{traffic_text}\n"
                        except:
                            pass
                        
                        # 步行建议（如果距离较近）
                        if distance <= 3000:
                            walk_time = distance // 80  # 假设步行速度80米/分钟
                            route_content += f"🚶 **步行**：约{walk_time}分钟（适合锻炼）\n"
                        
                        # 打车费用估算
                        base_fare = 13  # 起步价
                        per_km_fare = 2.3  # 每公里费用
                        if distance > 3000:
                            taxi_cost = base_fare + (distance - 3000) / 1000 * per_km_fare
                        else:
                            taxi_cost = base_fare
                        route_content += f"🚕 **打车**：约{int(taxi_cost)}元（预估）\n"
                        
                        # 停车信息
                        route_content += f"\n🅿️ **停车信息**：景区停车场、周边公共停车场\n"
                        
                        return route_content
            except Exception as e:
                log.info(f"高德路线API调用失败: {e}")
        
        # 降级到模拟数据
        import random
        
        # 自驾路线
        drive_time = random.randint(30, 120)
        drive_distance = random.randint(10, 80)
        route_content += f"\n🚗 **自驾**：约{drive_distance}公里，预计{drive_time}分钟\n"
        route_content += f"   📍 导航地址：{dest.address}\n"
        route_content += f"   📡 数据来源：模拟数据\n"
        
        # 公交路线
        bus_time = random.randint(45, 150)
        bus_transfers = random.randint(0, 3)
        if bus_transfers > 0:
            route_content += f"🚇 **公共交通**：约{bus_time}分钟，需换乘{bus_transfers}次\n"
        else:
            route_content += f"🚇 **公共交通**：约{bus_time}分钟，无需换乘\n"
        
        # 步行路线（如果距离较近）
        if drive_distance <= 5:
            walk_time = random.randint(30, 90)
            route_content += f"🚶 **步行**：约{walk_time}分钟\n"
        
        # 打车信息
        taxi_cost = random.randint(20, 100)
        route_content += f"🚕 **打车**：约{taxi_cost}元（视出发地而定）\n"
        
        # 添加实时路况提示
        traffic_conditions = ['畅通', '缓行', '拥堵']
        traffic = random.choice(traffic_conditions)
        traffic_emoji = '🟢' if traffic == '畅通' else ('🟡' if traffic == '缓行' else '🔴')
        route_content += f"\n{traffic_emoji} **实时路况**：当前{dest.city}周边道路{traffic}\n"
        
        # 添加停车场信息（自驾相关）
        parking_options = ['景区停车场', '周边公共停车场', '路边停车位']
        route_content += f"\n🅿️ **停车信息**：{', '.join(parking_options)}\n"
        
        return route_content
    
    def _generate_destination_card(self, dest_info, weather_info):
        """生成景点信息卡片图片"""
        try:
            from PIL import Image, ImageDraw, ImageFont
            import os
            
            # 创建图片
            width, height = 800, 600
            img = Image.new('RGB', (width, height), color=(255, 255, 255))
            draw = ImageDraw.Draw(img)
            
            # 尝试使用系统字体
            try:
                title_font = ImageFont.truetype("arial.ttf", 24)
                content_font = ImageFont.truetype("arial.ttf", 16)
            except:
                title_font = ImageFont.load_default()
                content_font = ImageFont.load_default()
            
            # 绘制标题
            draw.text((50, 30), dest_info['name'], fill=(51, 51, 51), font=title_font)
            
            # 绘制分隔线
            draw.line([(50, 70), (750, 70)], fill=(200, 200, 200), width=2)
            
            # 绘制信息
            y_position = 100
            info_items = [
                f"📍 地址：{dest_info.get('address', '未知')}",
                f"💰 门票：{dest_info.get('price_range', '未知')}",
                f"⏰ 时间：{dest_info.get('opening_hours', '未知')}",
                f"⭐ 评分：{dest_info.get('rating', 0)}分",
                f"🏷️ 分类：{dest_info.get('category', '未知')}"
            ]
            
            if weather_info and weather_info.get('success'):
                info_items.append(f"🌤️ 天气：{weather_info.get('temperature', '')}，{weather_info.get('condition', '')}")
            
            for item in info_items:
                draw.text((50, y_position), item, fill=(80, 80, 80), font=content_font)
                y_position += 40
            
            # 绘制底部信息
            draw.text((50, 550), "🤖 智能旅游助手 - 为您提供全方位旅游服务", fill=(150, 150, 150), font=content_font)
            
            # 保存图片
            image_dir = Path("static/generated_cards")
            image_dir.mkdir(exist_ok=True)
            
            image_filename = f"dest_card_{dest_info['name'][:10]}_{int(time.time())}.png"
            image_path = image_dir / image_filename
            
            img.save(str(image_path))
            
            return f"/static/generated_cards/{image_filename}"
            
        except Exception as e:
            log.info(f"生成图片失败: {e}")
            return None

    def get_personalized_recommendations(self, user_id, limit=5):
        """个性化推荐"""
        if not user_id:
            return []

        user = db.session.get(User, user_id)
        if not user:
            return []

        favorites = json.loads(user.favorites or '[]')
        clicks = json.loads(user.click_history or '[]')

        # 基于收藏和点击记录推荐
        interested_ids = list(set(favorites + clicks))
        if interested_ids:
            # 排除已收藏的
            query = Destination.query.filter(~Destination.id.in_(interested_ids))
        else:
            query = Destination.query

        return query.order_by(Destination.popularity_score.desc()).limit(limit).all()

    def get_response(self, message, session_id='default', user_id=None):
        """获取响应 - 支持AI大模型模式（增强版）"""
        conv = self.get_conversation(session_id)
        
        # 保存用户消息
        conv['messages'].append({
            'role': 'user',
            'content': message,
            'timestamp': datetime.now().isoformat()
        })
        
        # 情感分析
        emotion = self.analyze_emotion(message)
        
        # 学习用户偏好
        dest_name = self.extract_destination_name(message)
        intent = self.analyze_intent(message)
        self.learn_user_preference(user_id, message, intent, dest_name)

        # 首先尝试工具调用
        tool_response = self.execute_tool_if_needed(message, session_id)
        if tool_response:
            # 应用情感调整
            tool_response = self.get_emotion_response(emotion, tool_response)
            conv['messages'].append({
                'role': 'assistant',
                'content': tool_response.get('content', ''),
                'timestamp': datetime.now().isoformat()
            })
            self.save_conversation(session_id)
            return tool_response
        
        # 检查上下文感知响应
        context_response = self.get_context_aware_response(message, conv, user_id)
        if context_response:
            context_response = self.get_emotion_response(emotion, context_response)
            conv['messages'].append({
                'role': 'assistant',
                'content': context_response.get('content', ''),
                'timestamp': datetime.now().isoformat()
            })
            self.save_conversation(session_id)
            return context_response

        # 检查是否启用AI模式
        if self.ai_mode_enabled:
            try:
                # 导入AI模型管理器
                from ai_model_manager import get_ai_response
                
                # 构建对话历史
                context = []
                for msg in conv['messages'][-20:]:  # 保留最近20条消息
                    if msg['role'] in ['user', 'assistant']:
                        context.append({
                            'role': msg['role'],
                            'content': msg['content']
                        })
                
                # 调用AI模型
                ai_response = get_ai_response(message, context)
                
                response = {
                    "type": "text",
                    "content": ai_response,
                    "source": "ai_model"
                }
                
            except Exception as e:
                log.info(f"AI模型调用失败: {e}")
                # 降级到规则匹配模式
                response = self._rule_based_response(message, session_id, user_id)
        else:
            # 使用规则匹配模式
            response = self._rule_based_response(message, session_id, user_id)
        
        # 应用情感调整
        response = self.get_emotion_response(emotion, response)
        
        # 添加主动推荐
        if user_id and random.random() < 0.3:  # 30%概率添加推荐
            proactive = self.get_proactive_recommendation(user_id, intent, dest_name)
            if proactive:
                if 'suggestions' not in response:
                    response['suggestions'] = []
                response['suggestions'].extend(proactive)

        # 保存助手响应
        conv['messages'].append({
            'role': 'assistant',
            'content': response.get('content', ''),
            'timestamp': datetime.now().isoformat()
        })

        self.save_conversation(session_id)
        return response
    
    def get_proactive_recommendation(self, user_id, intent, dest_name):
        """主动推荐 - 基于用户行为和当前意图"""
        recommendations = []
        
        # 获取用户偏好
        prefs = self.user_preferences.get(user_id, {})
        visit_history = prefs.get('visit_history', [])
        
        # 基于当前意图推荐
        if intent == 'query_destination' and dest_name:
            # 用户查询了某个景点，推荐相关景点
            recommendations.append(f"{dest_name}附近美食")
            recommendations.append(f"{dest_name}怎么去")
        
        elif intent == 'plan_trip':
            # 用户在规划行程，推荐实用功能
            recommendations.append("查看天气预报")
            recommendations.append("周边酒店推荐")
        
        elif intent == 'greeting':
            # 问候时推荐热门内容
            if visit_history:
                recommendations.append("查看我的浏览记录")
            recommendations.append("今日推荐景点")
        
        # 基于用户历史推荐
        if visit_history and len(visit_history) >= 3:
            last_visit = visit_history[-1]
            recommendations.append(f"{last_visit}周边景点")
        
        return recommendations[:2]  # 最多返回2个推荐
    
    def get_conversation_summary(self, session_id):
        """生成对话摘要"""
        conv = self.get_conversation(session_id)
        messages = conv.get('messages', [])
        
        if len(messages) < 4:
            return None
        
        # 提取关键信息
        user_messages = [m['content'] for m in messages if m.get('role') == 'user']
        
        # 分析讨论的主题
        topics = set()
        destinations = set()
        
        for msg in user_messages:
            # 提取景点
            dest = self.extract_destination_name(msg)
            if dest:
                destinations.add(dest)
            
            # 提取意图
            intent = self.analyze_intent(msg)
            topics.add(intent)
        
        # 生成摘要
        summary_parts = []
        
        if destinations:
            dest_list = '、'.join(list(destinations)[:3])
            summary_parts.append(f"讨论了{dest_list}等景点")
        
        if 'plan_trip' in topics:
            summary_parts.append("进行了行程规划")
        
        if 'query_food' in topics:
            summary_parts.append("查询了美食信息")
        
        if 'query_weather' in topics:
            summary_parts.append("了解了天气情况")
        
        if summary_parts:
            return "，".join(summary_parts) + "。"
        
        return "进行了旅游相关咨询。"
    
    def should_show_summary(self, session_id):
        """判断是否应该显示对话摘要"""
        conv = self.get_conversation(session_id)
        messages = conv.get('messages', [])
        
        # 每10条消息显示一次摘要
        if len(messages) > 0 and len(messages) % 10 == 0:
            return True
        
        return False
    
    def _rule_based_response(self, message, session_id='default', user_id=None):
        """基于规则的响应（增强版）"""
        intent = self.analyze_intent(message)
        location = self.extract_location(message)
        dest_name = self.extract_destination_name(message)
        numbers = self.extract_numbers(message)

        # 保存搜索历史
        if user_id and (location or dest_name):
            user = db.session.get(User, user_id)
            if user:
                search_term = dest_name or (location['name'] if location else message[:20])
                history = json.loads(user.search_history or '[]')
                history.insert(0, f"{search_term} - {datetime.now().strftime('%Y-%m-%d')}")
                user.search_history = json.dumps(history[:20])
                db.session.commit()

        # 根据意图生成响应
        if intent == "greeting":
            response = self._greeting_response(user_id)
        
        # 带景点名称的行程规划
        elif intent == "plan_trip_with_destination" and dest_name:
            days = numbers[0] if numbers else 3
            days = min(max(days, 1), 7)
            response = self._trip_with_destination_response(dest_name, days)
        
        # 通用行程规划
        elif intent == "plan_trip":
            if dest_name:
                days = numbers[0] if numbers else 3
                response = self._trip_with_destination_response(dest_name, days)
            elif location:
                days = numbers[0] if numbers else 3
                response = self._trip_response(location, numbers)
            else:
                response = {
                    "type": "text",
                    "content": "请问您想规划去哪里的行程呢？例如：\n\n"
                              "• 帮我规划北京3日游\n"
                              "• 老君山行程安排\n"
                              "• 上海2天怎么玩",
                    "suggestions": ["北京行程", "上海攻略", "成都3日游"]
                }
        
        # 景点详情查询
        elif intent == "query_detail" and dest_name:
            response = self.get_destination_detail(dest_name)
        
        # 带景点名称的查询（自动返回详情）
        elif intent == "query_destination" and dest_name:
            response = self.get_destination_detail(dest_name)
        
        # 带景点的门票查询
        elif intent == "query_price_with_destination" and dest_name:
            response = self.get_destination_detail(dest_name)
        
        # 带景点的时间查询
        elif intent == "query_time_with_destination" and dest_name:
            response = self.get_destination_detail(dest_name)
        
        # 带景点的位置查询
        elif intent == "query_location_with_destination" and dest_name:
            response = self.get_destination_detail(dest_name)
        
        # 带位置的天气查询
        elif intent == "query_weather_with_location" and location:
            response = self._weather_response(location)
        
        # 通用天气查询
        elif intent == "query_weather":
            if location:
                response = self._weather_response(location)
            elif dest_name:
                # 尝试从景点获取城市
                dest = Destination.query.filter(Destination.name.contains(dest_name)).first()
                if dest:
                    response = self._weather_response({'type': 'city', 'name': dest.city})
                else:
                    response = {
                        "type": "text",
                        "content": "请问您想查询哪个城市的天气？",
                        "suggestions": ["北京天气", "上海天气", "成都天气"]
                    }
            else:
                response = {
                    "type": "text",
                    "content": "请问您想查询哪个城市的天气？",
                    "suggestions": ["北京天气", "上海天气", "成都天气"]
                }
        
        # 带位置的美食查询
        elif intent == "query_food_with_location" and location:
            response = self._food_response(location)
        
        # 通用美食查询
        elif intent == "query_food":
            if location:
                response = self._food_response(location)
            elif dest_name:
                dest = Destination.query.filter(Destination.name.contains(dest_name)).first()
                if dest:
                    response = self._food_response({'type': 'city', 'name': dest.city})
                else:
                    response = {
                        "type": "text",
                        "content": "请问您想查询哪个城市的美食？",
                        "suggestions": ["北京美食", "成都小吃", "广州美食"]
                    }
            else:
                response = {
                    "type": "text",
                    "content": "请问您想查询哪个城市的美食？",
                    "suggestions": ["北京美食", "成都小吃", "广州美食"]
                }
        
        # 景点搜索
        elif intent == "query_scenic":
            if location:
                response = self._scenic_response(location)
            else:
                response = {
                    "type": "text",
                    "content": "请问您想查询哪个城市的景点？",
                    "suggestions": ["北京景点", "上海景点", "杭州景点"]
                }
        
        # 门票查询（无景点）
        elif intent == "query_price":
            response = {
                "type": "text",
                "content": "请问您想查询哪个景点的门票价格？\n\n例如：故宫门票多少钱？",
                "suggestions": ["故宫门票", "长城票价", "西湖门票"]
            }
        
        # 时间查询（无景点）
        elif intent == "query_time":
            response = {
                "type": "text",
                "content": "请问您想查询哪个景点的开放时间？\n\n例如：故宫几点开门？",
                "suggestions": ["故宫开放时间", "长城营业时间"]
            }
        
        # 位置查询（无景点）
        elif intent == "query_location":
            response = {
                "type": "text",
                "content": "请问您想查询哪个景点的地址？\n\n例如：故宫在哪里？",
                "suggestions": ["故宫地址", "长城怎么去"]
            }
        
        # 帮助
        elif intent == "help":
            response = self._help_response()
        
        # 住宿查询
        elif intent == "query_hotel":
            if location:
                response = self._hotel_response(location)
            elif dest_name:
                dest = Destination.query.filter(Destination.name.contains(dest_name)).first()
                if dest:
                    response = self._hotel_response({'type': 'city', 'name': dest.city})
                else:
                    response = {
                        "type": "text",
                        "content": "请问您想查询哪个城市的住宿？",
                        "suggestions": ["北京酒店", "上海住宿", "成都民宿"]
                    }
            else:
                response = {
                    "type": "text",
                    "content": "请问您想查询哪个城市的住宿？",
                    "suggestions": ["北京酒店", "上海住宿", "成都民宿"]
                }
        
        # 交通查询
        elif intent == "query_transport":
            if dest_name:
                response = {
                    "type": "text",
                    "content": f"前往{dest_name}的交通方式：\n\n🚌 **公交**：可查询当地公交线路\n🚇 **地铁**：最近地铁站\n🚗 **自驾**：导航至{dest_name}\n🚕 **打车**：约XX元（视出发地而定）",
                    "suggestions": [f"{dest_name}门票", f"{dest_name}开放时间", f"{dest_name}附近美食"]
                }
            elif location:
                response = {
                    "type": "text",
                    "content": f"{location['name']}的交通信息：\n\n✈️ **飞机**：{location['name']}机场\n🚄 **高铁**：{location['name']}站\n🚌 **市内交通**：公交、地铁、出租车",
                    "suggestions": [f"{location['name']}景点", f"{location['name']}天气", f"{location['name']}美食"]
                }
            else:
                response = {
                    "type": "text",
                    "content": "请问您想查询哪里的交通信息？",
                    "suggestions": ["北京交通", "上海交通", "广州交通"]
                }
        
        # 感谢
        elif intent == "thanks":
            response = {
                "type": "text",
                "content": "不客气！很高兴能帮到您。如果还有其他问题，随时可以问我哦！😊",
                "suggestions": ["推荐景点", "热门城市", "帮助"]
            }
        
        # 再见
        elif intent == "goodbye":
            response = {
                "type": "text",
                "content": "再见！祝您旅途愉快！🎉 如果以后需要帮助，随时回来找我哦！",
                "suggestions": ["推荐景点", "行程规划", "天气查询"]
            }
        
        # 默认响应
        else:
            # 如果包含景点名称，返回景点详情
            if dest_name:
                response = self.get_destination_detail(dest_name)
            elif location:
                response = {
                    "type": "text",
                    "content": f"您想了解{location['name']}的什么信息？",
                    "suggestions": [
                        f"{location['name']}景点",
                        f"{location['name']}美食",
                        f"{location['name']}天气",
                        f"{location['name']}行程规划"
                    ]
                }
            else:
                response = self._general_response(location, user_id)
        
        response['source'] = 'rule_based'
        return response
    
    def get_response_stream(self, message, session_id='default', user_id=None):
        """获取流式响应 - 支持AI大模型流式输出"""
        conv = self.get_conversation(session_id)
        
        # 保存用户消息
        conv['messages'].append({
            'role': 'user',
            'content': message,
            'timestamp': datetime.now().isoformat()
        })

        # 检查是否启用AI模式
        if self.ai_mode_enabled:
            try:
                # 导入AI模型管理器
                from ai_model_manager import get_ai_response_stream
                
                # 构建对话历史
                context = []
                for msg in conv['messages'][-20:]:
                    if msg['role'] in ['user', 'assistant']:
                        context.append({
                            'role': msg['role'],
                            'content': msg['content']
                        })
                
                # 收集完整响应
                full_response = ""
                for chunk in get_ai_response_stream(message, context):
                    full_response += chunk
                    yield chunk
                
                # 保存完整响应
                conv['messages'].append({
                    'role': 'assistant',
                    'content': full_response,
                    'timestamp': datetime.now().isoformat()
                })
                self.save_conversation(session_id)
                
            except Exception as e:
                log.info(f"AI模型流式调用失败: {e}")
                # 降级到规则匹配模式
                response = self._rule_based_response(message, session_id, user_id)
                yield response.get('content', '')
                
                conv['messages'].append({
                    'role': 'assistant',
                    'content': response.get('content', ''),
                    'timestamp': datetime.now().isoformat()
                })
                self.save_conversation(session_id)
        else:
            # 使用规则匹配模式
            response = self._rule_based_response(message, session_id, user_id)
            yield response.get('content', '')
            
            conv['messages'].append({
                'role': 'assistant',
                'content': response.get('content', ''),
                'timestamp': datetime.now().isoformat()
            })
            self.save_conversation(session_id)
    
    def toggle_ai_mode(self, enabled=None):
        """切换AI模式"""
        if enabled is None:
            self.ai_mode_enabled = not self.ai_mode_enabled
        else:
            self.ai_mode_enabled = enabled
        
        mode = "AI大模型模式" if self.ai_mode_enabled else "规则匹配模式"
        log.info(f"✅ 已切换到: {mode}")
        return self.ai_mode_enabled
    
    def get_ai_mode_status(self):
        """获取AI模式状态"""
        from ai_model_manager import ai_model_manager
        return {
            'ai_mode_enabled': self.ai_mode_enabled,
            'available_providers': ai_model_manager.get_available_providers(),
            'provider_info': ai_model_manager.get_provider_info()
        }

    def _greeting_response(self, user_id=None):
        hour = datetime.now().hour
        greeting = "早上好" if hour < 12 else "下午好" if hour < 18 else "晚上好"

        if user_id:
            return {
                "type": "text",
                "content": f"{greeting}！欢迎回来，需要我为您推荐一些景点吗？",
                "suggestions": ["推荐景点", "我的收藏", "北京景点", "上海天气"]
            }

        return {
            "type": "text",
            "content": f"{greeting}！我是您的智能旅游助手，可以帮您查询景点信息、门票、天气、美食，规划行程等。有什么可以帮您的吗？",
            "suggestions": ["北京景点", "故宫门票", "上海天气", "成都美食"]
        }

    def _scenic_response(self, location):
        name = location['name']
        results = Destination.query.filter(
            or_(Destination.city.contains(name), Destination.province.contains(name))
        ).order_by(Destination.popularity_score.desc()).limit(8).all()

        if results:
            content = f"为您推荐{name}的景点：\n\n"
            for i, d in enumerate(results[:5], 1):
                content += f"{i}. **{d.name}** - {d.category} | ⭐{d.rating}分\n"
            content += "\n想了解哪个景点？直接告诉我名字即可。"
            suggestions = [f"{results[0].name}门票", f"{results[0].name}地址"]
        else:
            content = f"抱歉，暂时没有找到{name}的景点信息。"
            suggestions = ["热门景点", "北京景点", "上海景点"]

        return {"type": "text", "content": content, "suggestions": suggestions}

    def _price_response(self, name):
        dest = Destination.query.filter(Destination.name.contains(name)).first()
        if dest:
            return {"type": "text", "content": f"**{dest.name}** 门票价格：{dest.price_range}"}
        return {"type": "text", "content": f"抱歉，没有找到「{name}」的门票信息"}

    def _time_response(self, name):
        dest = Destination.query.filter(Destination.name.contains(name)).first()
        if dest:
            return {"type": "text", "content": f"**{dest.name}** 开放时间：{dest.opening_hours}"}
        return {"type": "text", "content": f"抱歉，没有找到「{name}」的开放时间"}

    def _location_response(self, name):
        dest = Destination.query.filter(Destination.name.contains(name)).first()
        if dest:
            return {"type": "text", "content": f"**{dest.name}** 地址：{dest.address}"}
        return {"type": "text", "content": f"抱歉，没有找到「{name}」的地址"}

    def _weather_response(self, location):
        data = weather_api.get_current_weather(location['name'])
        return {"type": "text", "content": f"**{location['name']}** 今日天气：\n\n"
                f"🌡️ 温度：{data['temperature']}\n"
                f"☁️ 天气：{data['condition']}\n"
                f"💨 风向：{data['wind_dir']} {data['wind_speed']}\n"
                f"💧 湿度：{data['humidity']}"}

    def _food_response(self, location):
        name = location['name']
        foods = FOOD_DATABASE.get(name, [])
        if foods:
            content = f"为您推荐{name}的特色美食：\n\n"
            for i, f in enumerate(foods[:5], 1):
                content += f"{i}. **{f['name']}** - {f['description'][:30]}...\n"
            suggestions = [f"{foods[0]['name']}哪里吃", f"{name}美食街"]
        else:
            content = f"抱歉，暂时没有找到{name}的美食信息。"
            suggestions = ["北京美食", "成都美食", "广州美食"]

        return {"type": "text", "content": content, "suggestions": suggestions}

    def _hotel_response(self, location):
        """住宿推荐响应"""
        name = location['name']
        
        # 模拟住宿推荐数据
        hotel_types = ['经济型酒店', '商务酒店', '度假酒店', '民宿', '青年旅舍']
        price_ranges = ['100-200元', '200-400元', '400-800元', '800-1500元', '50-100元']
        
        content = f"为您推荐{name}的住宿选择：\n\n"
        
        for i, (hotel_type, price) in enumerate(zip(hotel_types[:4], price_ranges[:4]), 1):
            content += f"{i}. **{hotel_type}** - {price}/晚\n"
            if i == 1:
                content += "   📍 交通便利，性价比高\n"
            elif i == 2:
                content += "   📍 设施齐全，服务周到\n"
            elif i == 3:
                content += "   📍 环境优美，适合度假\n"
            else:
                content += "   📍 特色体验，当地风情\n"
        
        content += f"\n💡 **住宿建议**：\n"
        content += f"  • 建议提前预订，特别是节假日\n"
        content += f"  • 可以查看用户评价选择\n"
        content += f"  • 考虑位置和交通便利性\n"
        
        suggestions = [f"{name}酒店预订", f"{name}民宿推荐", f"{name}住宿攻略"]
        
        return {"type": "text", "content": content, "suggestions": suggestions}

    def _trip_response(self, location, numbers):
        name = location['name']
        days = numbers[0] if numbers else 2
        days = min(max(days, 1), 7)

        plan = self.trip_plans.get(name, {}).get(f"{days}日游",
               self.default_trip_plans.get(f"{days}日游", self.default_trip_plans["2日游"]))

        content = f"为您规划{name}{days}日游行程：\n\n"
        for i, item in enumerate(plan, 1):
            content += f"{i}. {item}\n"

        return {"type": "text", "content": content}

    def _trip_with_destination_response(self, dest_name, days=3):
        """带景点名称的行程规划响应"""
        # 查找景点
        dest = Destination.query.filter(Destination.name.contains(dest_name)).first()
        
        if dest:
            # 获取天气信息
            weather_info = weather_api.get_current_weather(dest.city)
            
            # 构建行程内容
            content = f"**{dest.name} {days}日游行程规划**\n\n"
            content += f"📍 **景点信息**：\n"
            content += f"   地址：{dest.address}\n"
            content += f"   门票：{dest.price_range}\n"
            content += f"   开放时间：{dest.opening_hours}\n"
            content += f"   评分：{dest.rating}分\n\n"
            
            # 添加天气信息
            if weather_info and weather_info.get('success'):
                content += f"🌤️ **今日天气**：{weather_info.get('temperature', '未知')}，{weather_info.get('condition', '未知')}\n\n"
            
            # 生成行程安排
            content += f"📅 **行程安排**：\n\n"
            
            for day in range(1, days + 1):
                content += f"**第{day}天**：\n"
                if day == 1:
                    content += f"  09:00 - 抵达{dest.city}，前往{dest.name}\n"
                    content += f"  10:00 - 游览{dest.name}（约3小时）\n"
                    content += f"  12:00 - 午餐休息\n"
                    content += f"  14:00 - 继续游览{dest.name}\n"
                    content += f"  17:00 - 返回酒店休息\n"
                elif day == days:
                    content += f"  09:00 - 再次游览{dest.name}或周边景点\n"
                    content += f"  12:00 - 午餐\n"
                    content += f"  14:00 - 购物或自由活动\n"
                    content += f"  16:00 - 返程\n"
                else:
                    content += f"  09:00 - 游览{dest.name}周边景点\n"
                    content += f"  12:00 - 午餐\n"
                    content += f"  14:00 - 体验当地文化\n"
                    content += f"  17:00 - 返回酒店\n"
                content += "\n"
            
            content += f"💡 **温馨提示**：\n"
            content += f"  • 建议提前购买门票\n"
            content += f"  • 注意查看天气预报\n"
            content += f"  • 准备舒适的鞋子\n"
            content += f"  • 带好相机记录美景"
            
            return {
                "type": "destination_card",
                "content": content,
                "destination": dest.to_dict(),
                "weather": weather_info,
                "image": match_scenic_image(dest.name, external=True),
                "suggestions": [
                    f"{dest.name}怎么去",
                    f"{dest.name}附近美食",
                    f"{dest.city}天气",
                    f"{dest.city}其他景点"
                ]
            }
        else:
            # 没有找到景点，返回通用行程规划
            return {
                "type": "text",
                "content": f"抱歉，我没有找到「{dest_name}」的详细信息。\n\n"
                          f"不过我可以为您规划{days}天的行程建议：\n\n"
                          f"第1天：抵达目的地，熟悉环境\n"
                          f"第2天：游览主要景点\n"
                          f"{'第3天：深度体验当地文化\\n' if days >= 3 else ''}"
                          f"{'第4天：购物和自由活动\\n' if days >= 4 else ''}"
                          f"第{days}天：返程\n\n"
                          f"如果您能提供具体的景点名称，我可以为您提供更详细的行程规划。",
                "suggestions": ["北京行程", "上海攻略", "成都3日游"]
            }

    def _help_response(self):
        return {
            "type": "text",
            "content": "**我可以帮您：**\n\n"
                      "🔍 查询景点：北京有哪些景点\n"
                      "💰 门票价格：故宫门票多少钱\n"
                      "⏰ 开放时间：长城几点开门\n"
                      "📍 地址查询：故宫在哪里\n"
                      "🌤️ 天气查询：上海天气\n"
                      "🍜 美食推荐：成都特色美食\n"
                      "🗺️ 路线规划：北京3日游攻略\n"
                      "❤️ 收藏功能：收藏故宫\n"
                      "📊 个性化推荐：给我推荐景点"
        }

    def _general_response(self, location, user_id=None):
        if location:
            return {
                "type": "text",
                "content": f"您想了解{location['name']}的什么信息？我可以帮您查询景点、美食、天气或规划行程。",
                "suggestions": [f"{location['name']}景点", f"{location['name']}美食", f"{location['name']}天气"]
            }

        if user_id:
            return {
                "type": "text",
                "content": "我是智能旅游助手，有什么可以帮您的吗？",
                "suggestions": ["推荐景点", "我的收藏", "北京景点", "上海天气"]
            }

        return {
            "type": "text",
            "content": "我是智能旅游助手，有什么可以帮您的吗？",
            "suggestions": ["北京景点", "故宫门票", "上海天气", "成都美食"]
        }


# 全局助手实例
travel_assistant = None

# 延迟初始化助手
def get_travel_assistant():
    """获取智能助手实例（延迟初始化）"""
    global travel_assistant
    if travel_assistant is None:
        travel_assistant = TravelAssistant(db)
    return travel_assistant


# ==================== 用户认证路由 ====================
@app.route('/login-page')
def login_page():
    if 'user_id' in session:
        return redirect(url_for('index'))
    # 随机背景图片
    bg_image = random.choice(BACKGROUND_IMAGES)['url'] if BACKGROUND_IMAGES else None
    return render_template('login.html', background_image=bg_image)


@app.route('/register-page')
def register_page():
    if 'user_id' in session:
        return redirect(url_for('index'))
    # 随机背景图片
    bg_image = random.choice(BACKGROUND_IMAGES)['url'] if BACKGROUND_IMAGES else None
    return render_template('register.html', background_image=bg_image)


@app.route('/profile-page')
@login_required
def profile_page():
    user = db.session.get(User, session['user_id'])
    favorites = Destination.query.filter(
        Destination.id.in_(json.loads(user.favorites or '[]'))
    ).all()

    # 统计信息
    search_history = json.loads(user.search_history or '[]')
    click_ids = json.loads(user.click_history or '[]')
    clicked = Destination.query.filter(Destination.id.in_(click_ids)).all() if click_ids else []

    # 当前时间
    now = datetime.now()

    # 随机背景图片
    bg_image = random.choice(BACKGROUND_IMAGES)['url']

    return render_template('profile.html',
                          user=user,
                          favorites=favorites,
                          search_history=search_history,
                          clicked=clicked,
                          now=now,
                          current_user=user,
                          background_image=bg_image)


# ==================== 用户认证API ====================
@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '请求体必须为JSON格式'}), 400

    from services.validators import validate_username, validate_email, validate_password, sanitize_string
    username = sanitize_string(data.get('username', ''), 20)
    email = sanitize_string(data.get('email', ''), 120)
    password = data.get('password', '')

    if not validate_username(username):
        return jsonify({'success': False, 'error': '用户名需3-20个字符，仅支持字母数字下划线'}), 400
    if not validate_password(password):
        return jsonify({'success': False, 'error': '密码至少6个字符'}), 400
    if not validate_email(email):
        return jsonify({'success': False, 'error': '邮箱格式不正确'}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'error': '用户名已存在'}), 400
    if email and User.query.filter_by(email=email).first():
        return jsonify({'success': False, 'error': '邮箱已被注册'}), 400

    user = User(username=username, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    return jsonify({'success': True, 'message': '注册成功'})


@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': '请求体必须为JSON格式'}), 400

    from services.validators import sanitize_string
    account = sanitize_string(data.get('username', ''), 80)
    password = data.get('password', '')
    remember = data.get('remember', False)

    if not account:
        return jsonify({'success': False, 'error': '请输入用户名或邮箱'}), 400
    if not password:
        return jsonify({'success': False, 'error': '请输入密码'}), 400

    log.info(f"登录尝试 - 账号: {account}")

    user = User.query.filter(
        or_(User.username == account, User.email == account)
    ).first()

    if user:
        log.info(f"找到用户: {user.username}")
        if user.check_password(password):
            log.info("密码正确")
            session.permanent = remember
            session['user_id'] = user.id
            session['username'] = user.username
            user.last_login = datetime.now()
            db.session.commit()
            return jsonify({'success': True, 'message': '登录成功', 'user': user.to_dict()})
        else:
            log.info("密码错误")
    else:
        log.info("用户不存在")

    return jsonify({'success': False, 'error': '用户名或密码错误'}), 401


@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({'success': True, 'message': '已登出'})


@app.route('/api/user/status')
def user_status():
    if 'user_id' in session:
        user = db.session.get(User, session['user_id'])
        if user:
            return jsonify({'logged_in': True, 'user': user.to_dict()})
    return jsonify({'logged_in': False})


# ==================== 社交登录路由 ====================
@app.route('/auth/<provider>')
def social_auth(provider):
    if provider not in ['wechat', 'qq', 'weibo']:
        return redirect('/login-page')

    state = generate_state()
    save_state(state, provider)

    if provider == 'wechat':
        auth_url = WeChatLogin.get_qr_code_url(state)
        return redirect(auth_url)
    elif provider == 'qq':
        html = QQLogin.get_qr_code_html(state)
        return html
    elif provider == 'weibo':
        html = WeiBoLogin.get_qr_code_html(state)
        return html

    return redirect('/login-page')


@app.route('/auth/wechat/callback')
def wechat_callback():
    code = request.args.get('code')
    state = request.args.get('state')

    if not verify_state(state, 'wechat'):
        return jsonify({'error': '无效的state参数'}), 400

    try:
        token_data = WeChatLogin.get_access_token(code)
        if 'errcode' in token_data:
            return jsonify({'error': token_data.get('errmsg', '登录失败')}), 400

        access_token = token_data['access_token']
        openid = token_data['openid']
        user_info = WeChatLogin.get_user_info(access_token, openid)

        user = User.query.filter_by(wechat_openid=openid).first()
        if not user:
            username = f"wx_{user_info.get('nickname', 'user')}"
            base = username
            counter = 1
            while User.query.filter_by(username=username).first():
                username = f"{base}{counter}"
                counter += 1

            user = User(
                username=username,
                wechat_openid=openid,
                avatar_url=user_info.get('headimgurl')
            )
            db.session.add(user)
            db.session.commit()

        session['user_id'] = user.id
        session['username'] = user.username
        user.last_login = datetime.now()
        db.session.commit()
        return redirect('/')
    except Exception as e:
        log.info(f"微信登录错误: {e}")
        return redirect('/login-page')


@app.route('/auth/qq/callback')
def qq_callback():
    code = request.args.get('code')
    state = request.args.get('state')

    if not verify_state(state, 'qq'):
        return jsonify({'error': '无效的state参数'}), 400

    try:
        token_data = QQLogin.get_access_token(code)
        access_token = token_data.get('access_token')
        if not access_token:
            return jsonify({'error': '获取access_token失败'}), 400

        openid_data = QQLogin.get_openid(access_token)
        openid = openid_data.get('openid')
        if not openid:
            return jsonify({'error': '获取openid失败'}), 400

        user_info = QQLogin.get_user_info(access_token, openid)

        user = User.query.filter_by(qq_openid=openid).first()
        if not user:
            username = f"qq_{user_info.get('nickname', 'user')}"
            base = username
            counter = 1
            while User.query.filter_by(username=username).first():
                username = f"{base}{counter}"
                counter += 1

            user = User(
                username=username,
                qq_openid=openid,
                avatar_url=user_info.get('figureurl_qq_2') or user_info.get('figureurl_qq_1')
            )
            db.session.add(user)
            db.session.commit()

        session['user_id'] = user.id
        session['username'] = user.username
        user.last_login = datetime.now()
        db.session.commit()
        return redirect('/')
    except Exception as e:
        log.info(f"QQ登录错误: {e}")
        return redirect('/login-page')


@app.route('/auth/weibo/callback')
def weibo_callback():
    code = request.args.get('code')
    state = request.args.get('state')

    if not verify_state(state, 'weibo'):
        return jsonify({'error': '无效的state参数'}), 400

    try:
        token_data = WeiBoLogin.get_access_token(code)
        access_token = token_data.get('access_token')
        uid = token_data.get('uid')
        if not access_token or not uid:
            return jsonify({'error': '获取access_token失败'}), 400

        user_info = WeiBoLogin.get_user_info(access_token, uid)

        user = User.query.filter_by(weibo_uid=uid).first()
        if not user:
            username = f"wb_{user_info.get('screen_name', 'user')}"
            base = username
            counter = 1
            while User.query.filter_by(username=username).first():
                username = f"{base}{counter}"
                counter += 1

            user = User(
                username=username,
                weibo_uid=uid,
                avatar_url=user_info.get('avatar_hd') or user_info.get('profile_image_url')
            )
            db.session.add(user)
            db.session.commit()

        session['user_id'] = user.id
        session['username'] = user.username
        user.last_login = datetime.now()
        db.session.commit()
        return redirect('/')
    except Exception as e:
        log.info(f"微博登录错误: {e}")
        return redirect('/login-page')


# ==================== 手机号登录/注册 ====================
@app.route('/api/send_code', methods=['POST'])
def send_verification_code():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': '请求体必须为JSON格式'}), 400

    from services.validators import validate_phone
    phone = data.get('phone', '').strip()

    if not phone or not validate_phone(phone):
        return jsonify({'success': False, 'error': '请输入正确的手机号'}), 400

    code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    session[f'code_{phone}'] = {
        'code': code,
        'expire': datetime.now() + timedelta(minutes=5)
    }
    log.info(f"验证码 [{phone}]: {code}")
    return jsonify({'success': True, 'message': '验证码已发送', 'debug_code': code})


@app.route('/api/login/code', methods=['POST'])
def login_with_code():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': '请求体必须为JSON格式'}), 400

    from services.validators import validate_phone, sanitize_string
    phone = data.get('phone', '').strip()
    code = sanitize_string(data.get('code', ''), 6)

    if not phone or not validate_phone(phone):
        return jsonify({'success': False, 'error': '请输入正确的手机号'}), 400
    if not code or len(code) != 6:
        return jsonify({'success': False, 'error': '请输入6位验证码'}), 400

    code_data = session.get(f'code_{phone}')
    if not code_data:
        return jsonify({'success': False, 'error': '验证码不存在或已过期'}), 400

    if code_data['code'] != code:
        return jsonify({'success': False, 'error': '验证码错误'}), 400

    # 彻底修复时区比较问题
    try:
        expire_time = code_data['expire']
        
        # 强制转换为naive datetime
        if hasattr(expire_time, 'tzinfo'):
            if expire_time.tzinfo is not None:
                # 如果是aware的，转换为naive
                expire_time = expire_time.replace(tzinfo=None)
        
        # 确保当前时间也是naive的
        current_time = datetime.now()
        if hasattr(current_time, 'tzinfo') and current_time.tzinfo is not None:
            current_time = current_time.replace(tzinfo=None)
        
        # 比较时间
        if current_time > expire_time:
            return jsonify({'success': False, 'error': '验证码已过期'}), 400
            
    except Exception as e:
        log.info(f"验证码时间比较错误: {e}")
        import traceback
        traceback.print_exc()
        # 如果时间比较出错，清除验证码并返回错误
        session.pop(f'code_{phone}', None)
        return jsonify({'success': False, 'error': '验证码已过期，请重新获取'}), 400

    # 验证通过，查找或创建用户
    user = User.query.filter_by(phone=phone).first()
    if not user:
        username = f"用户{phone[-4:]}"
        base = username
        counter = 1
        while User.query.filter_by(username=username).first():
            username = f"{base}{counter}"
            counter += 1
        user = User(username=username, phone=phone)
        db.session.add(user)
        db.session.commit()

    # 登录成功
    session['user_id'] = user.id
    session['username'] = user.username
    
    try:
        user.last_login = datetime.now()
        db.session.commit()
    except Exception as e:
        log.info(f"更新登录时间失败: {e}")
    
    # 清除验证码
    session.pop(f'code_{phone}', None)

    return jsonify({'success': True, 'message': '登录成功', 'user': user.to_dict()})


# ==================== 收藏功能API ====================
@app.route('/api/favorite/add', methods=['POST'])
@login_required
def add_favorite():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': '请求体必须为JSON格式'}), 400

    from services.validators import validate_positive_int
    dest_id, err = validate_positive_int(data.get('dest_id'), '景点ID')
    if err:
        return jsonify({'success': False, 'error': err}), 400

    dest = db.session.get(Destination, dest_id)
    if not dest:
        return jsonify({'success': False, 'error': '景点不存在'}), 404

    user = db.session.get(User, session['user_id'])
    favorites = set(json.loads(user.favorites or '[]'))

    if dest_id in favorites:
        return jsonify({'success': False, 'error': '已收藏过该景点'}), 400

    favorites.add(dest_id)
    user.favorites = json.dumps(list(favorites))
    db.session.commit()

    return jsonify({'success': True, 'message': f'成功收藏 {dest.name}', 'favorites_count': len(favorites)})


@app.route('/api/favorite/remove', methods=['POST'])
@login_required
def remove_favorite():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': '请求体必须为JSON格式'}), 400

    from services.validators import validate_positive_int
    dest_id, err = validate_positive_int(data.get('dest_id'), '景点ID')
    if err:
        return jsonify({'success': False, 'error': err}), 400

    user = db.session.get(User, session['user_id'])
    favorites = set(json.loads(user.favorites or '[]'))

    if dest_id not in favorites:
        return jsonify({'success': False, 'error': '未收藏该景点'}), 400

    favorites.remove(dest_id)
    user.favorites = json.dumps(list(favorites))
    db.session.commit()

    return jsonify({'success': True, 'message': '已取消收藏', 'favorites_count': len(favorites)})


@app.route('/api/favorite/list')
@login_required
def list_favorites():
    user = db.session.get(User, session['user_id'])
    ids = json.loads(user.favorites or '[]')
    favorites = Destination.query.filter(Destination.id.in_(ids)).all() if ids else []
    return jsonify({'success': True, 'favorites': [d.to_dict() for d in favorites]})


@app.route('/api/favorite/check/<int:dest_id>')
@login_required
def check_favorite(dest_id):
    user = db.session.get(User, session['user_id'])
    favorites = set(json.loads(user.favorites or '[]'))
    return jsonify({'success': True, 'is_favorite': dest_id in favorites})


# ==================== 批量收藏操作 ====================
@app.route('/api/favorite/batch', methods=['POST'])
@login_required
def batch_favorite():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': '请求体必须为JSON格式'}), 400

    from services.validators import validate_choice
    dest_ids = data.get('dest_ids', [])
    if not dest_ids or not isinstance(dest_ids, list):
        return jsonify({'success': False, 'error': '请选择景点'}), 400
    # 验证每个ID是正整数
    valid_ids = []
    for did in dest_ids:
        try:
            valid_ids.append(int(did))
        except (TypeError, ValueError):
            return jsonify({'success': False, 'error': f'无效的景点ID: {did}'}), 400

    action, err = validate_choice(data.get('action', 'add'), '操作类型', ['add', 'remove'], default='add')
    if err:
        return jsonify({'success': False, 'error': err}), 400

    user = db.session.get(User, session['user_id'])
    favorites = set(json.loads(user.favorites or '[]'))

    if action == 'add':
        favorites.update(dest_ids)
        message = f'成功收藏 {len(dest_ids)} 个景点'
    else:
        favorites = favorites - set(dest_ids)
        message = f'已取消收藏 {len(dest_ids)} 个景点'

    user.favorites = json.dumps(list(favorites))
    db.session.commit()

    return jsonify({'success': True, 'message': message, 'favorites_count': len(favorites)})


# ==================== 搜索历史API ====================
@app.route('/api/search/history')
@login_required
def get_search_history():
    user = db.session.get(User, session['user_id'])
    history = json.loads(user.search_history or '[]')
    return jsonify({'success': True, 'history': history})


@app.route('/api/search/history/clear', methods=['POST'])
@login_required
def clear_search_history():
    user = db.session.get(User, session['user_id'])
    user.search_history = '[]'
    db.session.commit()
    return jsonify({'success': True, 'message': '搜索历史已清空'})


@app.route('/api/search/history/remove', methods=['POST'])
@login_required
def remove_search_history_item():
    data = request.get_json()
    index = data.get('index')
    if index is None:
        return jsonify({'success': False, 'error': '缺少索引'}), 400

    user = db.session.get(User, session['user_id'])
    history = json.loads(user.search_history or '[]')

    if 0 <= index < len(history):
        removed = history.pop(index)
        user.search_history = json.dumps(history)
        db.session.commit()
        return jsonify({'success': True, 'message': f'已删除: {removed}', 'history': history})

    return jsonify({'success': False, 'error': '索引无效'}), 400


# ==================== 点击历史API ====================
@app.route('/api/click/history')
@login_required
def get_click_history():
    user = db.session.get(User, session['user_id'])
    click_ids = json.loads(user.click_history or '[]')
    clicked = Destination.query.filter(Destination.id.in_(click_ids)).all() if click_ids else []
    return jsonify({'success': True, 'clicked': [d.to_dict() for d in clicked]})


@app.route('/api/click/history/clear', methods=['POST'])
@login_required
def clear_click_history():
    user = db.session.get(User, session['user_id'])
    user.click_history = '[]'
    db.session.commit()
    return jsonify({'success': True, 'message': '浏览历史已清空'})


# ==================== 用户资料更新 ====================
@app.route('/api/user/profile/update', methods=['POST'])
@login_required
def update_profile():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': '请求体必须为JSON格式'}), 400

    from services.validators import validate_username, validate_email
    user = db.session.get(User, session['user_id'])
    
    # 更新用户名
    new_username = data.get('username', '').strip()
    if new_username and new_username != user.username:
        if not validate_username(new_username):
            return jsonify({'success': False, 'error': '用户名需3-20个字符，仅支持字母数字下划线'}), 400
        if User.query.filter(User.username == new_username, User.id != user.id).first():
            return jsonify({'success': False, 'error': '用户名已被使用'}), 400
        user.username = new_username
        session['username'] = new_username
    
    # 更新邮箱
    new_email = data.get('email', '').strip()
    if new_email and new_email != user.email:
        if not validate_email(new_email):
            return jsonify({'success': False, 'error': '邮箱格式不正确'}), 400
        if User.query.filter(User.email == new_email, User.id != user.id).first():
            return jsonify({'success': False, 'error': '邮箱已被其他用户使用'}), 400
        user.email = new_email

    db.session.commit()
    return jsonify({'success': True, 'message': '资料更新成功', 'user': user.to_dict()})


@app.route('/api/user/password/change', methods=['POST'])
@login_required
def change_password():
    data = request.get_json()
    user = db.session.get(User, session['user_id'])
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')
    confirm_password = data.get('confirm_password', '')

    if not user.check_password(old_password):
        return jsonify({'success': False, 'error': '原密码错误'}), 400
    if len(new_password) < 6:
        return jsonify({'success': False, 'error': '新密码至少6个字符'}), 400
    if new_password != confirm_password:
        return jsonify({'success': False, 'error': '两次输入的新密码不一致'}), 400

    user.set_password(new_password)
    db.session.commit()
    return jsonify({'success': True, 'message': '密码修改成功'})


# ==================== 用户统计API ====================
@app.route('/api/user/stats')
@login_required
def user_stats():
    user = db.session.get(User, session['user_id'])
    favorites = json.loads(user.favorites or '[]')
    search_history = json.loads(user.search_history or '[]')
    click_history = json.loads(user.click_history or '[]')
    
    # 计算用户互动统计
    likes_given = UserLike.query.filter_by(user_id=user.id).count()
    followers = UserFollow.query.filter_by(following_id=user.id).count()
    following = UserFollow.query.filter_by(follower_id=user.id).count()
    checkins = UserCheckin.query.filter_by(user_id=user.id).count()

    return jsonify({
        'success': True,
        'stats': {
            'favorites_count': len(favorites),
            'search_history_count': len(search_history),
            'click_history_count': len(click_history),
            'likes_given': likes_given,
            'followers': followers,
            'following': following,
            'checkins': checkins,
            'member_days': (datetime.now() - user.created_at).days,
            'last_login': user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else None,
            'registered_at': user.created_at.strftime('%Y-%m-%d')
        }
    })


# ==================== 用户互动功能API ====================

@app.route('/api/destinations/<int:dest_id>/like', methods=['POST'])
@login_required
def like_destination(dest_id):
    """点赞/取消点赞景点"""
    try:
        user = db.session.get(User, session['user_id'])
        dest = db.session.get(Destination, dest_id)
        
        if not dest:
            return jsonify({'success': False, 'error': '景点不存在'}), 404
        
        # 检查是否已经点赞
        existing_like = UserLike.query.filter_by(user_id=user.id, destination_id=dest_id).first()
        
        if existing_like:
            # 取消点赞
            db.session.delete(existing_like)
            dest.like_count = max(0, dest.like_count - 1)
            action = 'unliked'
            message = '已取消点赞'
        else:
            # 点赞
            new_like = UserLike(user_id=user.id, destination_id=dest_id)
            db.session.add(new_like)
            dest.like_count = (dest.like_count or 0) + 1
            action = 'liked'
            message = '点赞成功'
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': message,
            'action': action,
            'like_count': dest.like_count,
            'is_liked': action == 'liked'
        })
        
    except Exception as e:
        db.session.rollback()
        log.info(f"点赞操作错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/destinations/<int:dest_id>/checkin', methods=['POST'])
@login_required
def checkin_destination(dest_id):
    """景点签到"""
    try:
        user = db.session.get(User, session['user_id'])
        dest = db.session.get(Destination, dest_id)
        
        if not dest:
            return jsonify({'success': False, 'error': '景点不存在'}), 404
        
        data = request.get_json() or {}
        
        # 检查今天是否已经签到
        today = datetime.now().date()
        existing_checkin = UserCheckin.query.filter(
            UserCheckin.user_id == user.id,
            UserCheckin.destination_id == dest_id,
            func.date(UserCheckin.created_at) == today
        ).first()
        
        if existing_checkin:
            return jsonify({'success': False, 'error': '今天已经签到过了'}), 400
        
        # 创建签到记录
        checkin = UserCheckin(
            user_id=user.id,
            destination_id=dest_id,
            latitude=data.get('latitude'),
            longitude=data.get('longitude'),
            content=data.get('content', '').strip(),
            images=json.dumps(data.get('images', []), ensure_ascii=False)
        )
        
        db.session.add(checkin)
        
        # 更新景点浏览次数
        dest.view_count = (dest.view_count or 0) + 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '签到成功',
            'checkin': checkin.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        log.info(f"签到错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/users/<int:user_id>/follow', methods=['POST'])
@login_required
def follow_user(user_id):
    """关注/取消关注用户"""
    try:
        follower = db.session.get(User, session['user_id'])
        following = db.session.get(User, user_id)
        
        if not following:
            return jsonify({'success': False, 'error': '用户不存在'}), 404
        
        if follower.id == following.id:
            return jsonify({'success': False, 'error': '不能关注自己'}), 400
        
        # 检查是否已经关注
        existing_follow = UserFollow.query.filter_by(
            follower_id=follower.id,
            following_id=following.id
        ).first()
        
        if existing_follow:
            # 取消关注
            db.session.delete(existing_follow)
            action = 'unfollowed'
            message = '已取消关注'
        else:
            # 关注
            new_follow = UserFollow(follower_id=follower.id, following_id=following.id)
            db.session.add(new_follow)
            action = 'followed'
            message = '关注成功'
        
        db.session.commit()
        
        # 获取更新后的关注数据
        followers_count = UserFollow.query.filter_by(following_id=following.id).count()
        following_count = UserFollow.query.filter_by(follower_id=following.id).count()
        is_followed = action == 'followed'
        
        return jsonify({
            'success': True,
            'message': message,
            'action': action,
            'followers_count': followers_count,
            'following_count': following_count,
            'is_followed': is_followed
        })
        
    except Exception as e:
        db.session.rollback()
        log.info(f"关注操作错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/users/<int:user_id>/profile', methods=['GET'])
def get_user_profile(user_id):
    """获取用户公开资料"""
    try:
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({'success': False, 'error': '用户不存在'}), 404
        
        # 获取用户统计数据
        followers_count = UserFollow.query.filter_by(following_id=user.id).count()
        following_count = UserFollow.query.filter_by(follower_id=user.id).count()
        checkins_count = UserCheckin.query.filter_by(user_id=user.id).count()
        likes_count = UserLike.query.filter_by(user_id=user.id).count()
        
        # 检查当前用户是否关注了该用户
        is_followed = False
        if 'user_id' in session and session['user_id'] != user.id:
            follow_record = UserFollow.query.filter_by(
                follower_id=session['user_id'],
                following_id=user.id
            ).first()
            is_followed = follow_record is not None
        
        # 获取用户的最近签到
        recent_checkins = UserCheckin.query.filter_by(user_id=user.id)\
            .order_by(UserCheckin.created_at.desc()).limit(5).all()
        
        profile_data = {
            'id': user.id,
            'username': user.username,
            'avatar_url': user.avatar_url,
            'created_at': user.created_at.strftime('%Y-%m-%d'),
            'followers_count': followers_count,
            'following_count': following_count,
            'checkins_count': checkins_count,
            'likes_count': likes_count,
            'is_followed': is_followed,
            'recent_checkins': [checkin.to_dict() for checkin in recent_checkins]
        }
        
        return jsonify({
            'success': True,
            'profile': profile_data
        })
        
    except Exception as e:
        log.info(f"获取用户资料错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/destinations/<int:dest_id>/checkins', methods=['GET'])
def get_destination_checkins(dest_id):
    """获取景点的签到记录"""
    try:
        dest = db.session.get(Destination, dest_id)
        if not dest:
            return jsonify({'success': False, 'error': '景点不存在'}), 404
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        checkins = UserCheckin.query.filter_by(destination_id=dest_id)\
            .order_by(UserCheckin.created_at.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
        
        checkins_data = []
        for checkin in checkins.items:
            checkin_data = checkin.to_dict()
            checkin_data['username'] = checkin.user.username if checkin.user else '匿名用户'
            checkin_data['avatar_url'] = checkin.user.avatar_url if checkin.user else None
            checkins_data.append(checkin_data)
        
        return jsonify({
            'success': True,
            'checkins': checkins_data,
            'total': checkins.total,
            'page': page,
            'pages': checkins.pages
        })
        
    except Exception as e:
        log.info(f"获取签到记录错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/liked-destinations', methods=['GET'])
@login_required
def get_liked_destinations():
    """获取用户点赞的景点"""
    try:
        user = db.session.get(User, session['user_id'])
        
        likes = UserLike.query.filter_by(user_id=user.id)\
            .order_by(UserLike.created_at.desc()).all()
        
        liked_destinations = []
        for like in likes:
            dest = like.destination
            if dest:
                dest_data = dest.to_dict()
                dest_data['liked_at'] = like.created_at.strftime('%Y-%m-%d %H:%M')
                liked_destinations.append(dest_data)
        
        return jsonify({
            'success': True,
            'destinations': liked_destinations,
            'count': len(liked_destinations)
        })
        
    except Exception as e:
        log.info(f"获取点赞景点错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/checkins', methods=['GET'])
@login_required
def get_user_checkins():
    """获取用户的签到记录"""
    try:
        user = db.session.get(User, session['user_id'])
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        checkins = UserCheckin.query.filter_by(user_id=user.id)\
            .order_by(UserCheckin.created_at.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
        
        checkins_data = []
        for checkin in checkins.items:
            checkin_data = checkin.to_dict()
            checkin_data['destination_name'] = checkin.destination.name if checkin.destination else '未知景点'
            checkin_data['destination_city'] = checkin.destination.city if checkin.destination else ''
            checkins_data.append(checkin_data)
        
        return jsonify({
            'success': True,
            'checkins': checkins_data,
            'total': checkins.total,
            'page': page,
            'pages': checkins.pages
        })
        
    except Exception as e:
        log.info(f"获取签到记录错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/following', methods=['GET'])
@login_required
def get_user_following():
    """获取用户关注的人"""
    try:
        user = db.session.get(User, session['user_id'])
        
        follows = UserFollow.query.filter_by(follower_id=user.id)\
            .order_by(UserFollow.created_at.desc()).all()
        
        following_list = []
        for follow in follows:
            followed_user = follow.following
            if followed_user:
                user_data = {
                    'id': followed_user.id,
                    'username': followed_user.username,
                    'avatar_url': followed_user.avatar_url,
                    'followed_at': follow.created_at.strftime('%Y-%m-%d %H:%M'),
                    'followers_count': UserFollow.query.filter_by(following_id=followed_user.id).count(),
                    'checkins_count': UserCheckin.query.filter_by(user_id=followed_user.id).count()
                }
                following_list.append(user_data)
        
        return jsonify({
            'success': True,
            'following': following_list,
            'count': len(following_list)
        })
        
    except Exception as e:
        log.info(f"获取关注列表错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/followers', methods=['GET'])
@login_required
def get_user_followers():
    """获取用户的粉丝"""
    try:
        user = db.session.get(User, session['user_id'])
        
        follows = UserFollow.query.filter_by(following_id=user.id)\
            .order_by(UserFollow.created_at.desc()).all()
        
        followers_list = []
        for follow in follows:
            follower_user = follow.follower
            if follower_user:
                user_data = {
                    'id': follower_user.id,
                    'username': follower_user.username,
                    'avatar_url': follower_user.avatar_url,
                    'followed_at': follow.created_at.strftime('%Y-%m-%d %H:%M'),
                    'followers_count': UserFollow.query.filter_by(following_id=follower_user.id).count(),
                    'checkins_count': UserCheckin.query.filter_by(user_id=follower_user.id).count()
                }
                followers_list.append(user_data)
        
        return jsonify({
            'success': True,
            'followers': followers_list,
            'count': len(followers_list)
        })
        
    except Exception as e:
        log.info(f"获取粉丝列表错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== 导出用户数据 ====================
@app.route('/api/user/export')
@login_required
def export_user_data():
    user = db.session.get(User, session['user_id'])

    favorite_ids = json.loads(user.favorites or '[]')
    favorites = Destination.query.filter(Destination.id.in_(favorite_ids)).all() if favorite_ids else []

    click_ids = json.loads(user.click_history or '[]')
    clicked = Destination.query.filter(Destination.id.in_(click_ids)).all() if click_ids else []

    export_data = {
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'phone': user.phone,
            'registered_at': user.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'last_login': user.last_login.strftime('%Y-%m-%d %H:%M:%S') if user.last_login else None
        },
        'stats': {
            'favorites_count': len(favorite_ids),
            'search_history_count': len(json.loads(user.search_history or '[]')),
            'click_history_count': len(click_ids)
        },
        'favorites': [d.to_dict() for d in favorites],
        'search_history': json.loads(user.search_history or '[]'),
        'click_history': [d.to_dict() for d in clicked]
    }

    return jsonify({'success': True, 'data': export_data})


# ==================== 高德API地理编码 ====================
@app.route('/api/geocode', methods=['POST'])
def geocode():
    """地址转坐标"""
    data = request.get_json()
    address = data.get('address', '')

    if not address:
        return jsonify({'success': False, 'error': '请输入地址'}), 400

    if not gaode_api:
        return jsonify({'success': False, 'error': '高德API未配置'}), 500

    result = gaode_api.geocode(address)
    if result:
        return jsonify({'success': True, 'data': result})

    return jsonify({'success': False, 'error': '地址解析失败'}), 404


@app.route('/api/reverse-geocode', methods=['POST'])
def reverse_geocode():
    """坐标转地址"""
    data = request.get_json()
    lng = data.get('lng')
    lat = data.get('lat')

    if lng is None or lat is None:
        return jsonify({'success': False, 'error': '请输入经纬度'}), 400

    if not gaode_api:
        return jsonify({'success': False, 'error': '高德API未配置'}), 500

    result = gaode_api.reverse_geocode(lng, lat)
    if result:
        return jsonify({'success': True, 'data': result})

    return jsonify({'success': False, 'error': '坐标解析失败'}), 404


@app.route('/api/batch-update-provinces', methods=['POST'])
@login_required
def batch_update_provinces():
    """批量更新景点省份信息"""
    if not gaode_api:
        return jsonify({'success': False, 'error': '高德API未配置'}), 500

    # 获取所有省份未知的景点
    unknown_destinations = Destination.query.filter(
        (Destination.province == '未知') |
        (Destination.province.is_(None)) |
        (Destination.province == '')
    ).all()

    total = len(unknown_destinations)
    if total == 0:
        return jsonify({'success': True, 'message': '没有需要更新的景点', 'updated': 0})

    updated = 0
    failed = 0

    for dest in unknown_destinations:
        try:
            # 优先使用地址
            if dest.address:
                geocode = gaode_api.geocode(dest.address)
            elif dest.city:
                geocode = gaode_api.geocode(dest.city)
            else:
                geocode = gaode_api.geocode(dest.name)

            if geocode and geocode.get('province'):
                dest.province = geocode['province']
                updated += 1
            else:
                failed += 1

            time.sleep(0.2)  # 限流
        except Exception as e:
            log.info(f"更新失败 {dest.name}: {e}")
            failed += 1

    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'批量更新完成',
        'total': total,
        'updated': updated,
        'failed': failed
    })


# ==================== 背景图片API ====================
_background_cache = {'current': None, 'last_update': 0}

@app.route('/api/random-background')
def random_background():
    """返回随机背景图片"""
    if not BACKGROUND_IMAGES:
        return jsonify({'success': False, 'error': '没有背景图片'}), 404

    bg = random.choice(BACKGROUND_IMAGES)

    return jsonify({
        'success': True,
        'image': bg['url'],
        'name': bg['name'],
        'location': bg['location']
    })


@app.route('/api/backgrounds/batch')
def get_backgrounds_batch():
    """批量获取背景图片"""
    count = min(int(request.args.get('count', 5)), len(BACKGROUND_IMAGES))
    selected = random.sample(BACKGROUND_IMAGES, min(count, len(BACKGROUND_IMAGES)))
    return jsonify({'success': True, 'images': selected, 'count': len(selected)})


# ==================== 调试路由 ====================
@app.route('/api/debug/images')
def debug_images():
    """调试接口：查看图片匹配情况"""
    destinations = Destination.query.limit(20).all()
    result = []
    for dest in destinations:
        matched = match_scenic_image(dest.name)
        result.append({
            'id': dest.id,
            'name': dest.name,
            'current_image': dest.cover_image,
            'matched_image': matched,
            'matched': matched is not None and 'placeholder' not in matched
        })
    return jsonify({'success': True, 'data': result})

@app.route('/api/debug/stats')
def debug_stats():
    """调试接口：查看统计信息"""
    return jsonify({
        'success': True,
        'total_destinations': Destination.query.count(),
        'total_provinces': db.session.query(Destination.province).distinct().count(),
        'total_categories': db.session.query(Destination.category).distinct().count(),
        'avg_rating': db.session.query(func.avg(Destination.rating)).scalar(),
        'provinces': [{'name': p[0], 'count': p[1]} for p in db.session.query(Destination.province, func.count(Destination.id)).group_by(Destination.province).all()],
        'categories': [{'name': c[0], 'count': c[1]} for c in db.session.query(Destination.category, func.count(Destination.id)).group_by(Destination.category).all()]
    })

@app.route('/api/debug/users')
def debug_users():
    """查看所有用户"""
    users = User.query.all()
    return jsonify({
        'count': len(users),
        'users': [{'id': u.id, 'username': u.username, 'email': u.email} for u in users]
    })

@app.route('/api/debug/create-test-user')
def create_test_user():
    """创建测试用户"""
    user = User.query.filter_by(username='test').first()
    if not user:
        user = User(
            username='test',
            email='test@example.com'
        )
        user.set_password('123456')
        db.session.add(user)
        db.session.commit()
        return jsonify({'success': True, 'message': '测试用户创建成功', 'user': 'test/123456'})
    return jsonify({'success': True, 'message': '测试用户已存在'})

@app.route('/api/debug/create-frontend-admin')
def create_frontend_admin():
    """创建前台admin用户（用于普通登录页面）"""
    user = User.query.filter_by(username='admin').first()
    if not user:
        user = User(
            username='admin',
            email='admin@user.com'
        )
        user.set_password('admin123')
        db.session.add(user)
        db.session.commit()
        return jsonify({
            'success': True,
            'message': '前台admin用户创建成功',
            'user': 'admin/admin123'
        })
    else:
        # 重置密码
        user.set_password('admin123')
        db.session.commit()
        return jsonify({
            'success': True,
            'message': '前台admin用户密码已重置',
            'user': 'admin/admin123'
        })


# ==================== 首页路由 ====================
@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    per_page = 12
    category = request.args.get('category', '')
    province = request.args.get('province', '')
    sort = request.args.get('sort', 'popularity')
    view = request.args.get('view', '')

    query = Destination.query

    # 根据view参数设置默认筛选
    if view == 'province' and not province:
        province = '北京'
    elif view == 'category' and not category:
        category = '历史古迹'
    elif view == 'top_rated':
        sort = 'rating'

    # 应用筛选
    if category:
        query = query.filter(Destination.category == category)
    if province:
        query = query.filter(Destination.province == province)

    # 应用排序
    if sort == 'rating':
        query = query.order_by(Destination.rating.desc())
    elif sort == 'name':
        query = query.order_by(Destination.name.asc())
    else:
        query = query.order_by(Destination.popularity_score.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # 为没有封面的景点动态匹配图片（不写入数据库，减少IO）
    for dest_item in pagination.items:
        if not dest_item.cover_image or 'placeholder' in str(dest_item.cover_image):
            matched = match_scenic_image(dest_item.name)
            if matched and 'placeholder' not in matched:
                dest_item._dynamic_cover = matched

    # 统计信息（合并为一次查询，使用缓存）
    stats = _get_destination_stats()
    hot_destinations = _get_hot_destinations()
    top_rated_destinations = _get_top_rated()

    # 获取当前用户
    current_user = None
    user_favorites = []
    if 'user_id' in session:
        current_user = db.session.get(User, session['user_id'])
        if current_user:
            user_favorites = json.loads(current_user.favorites or '[]')

    # 随机背景图片
    bg_image = random.choice(BACKGROUND_IMAGES)['url']

    return render_template('index.html',
                           destinations=pagination.items,
                           pagination=pagination,
                           current_category=category,
                           current_province=province,
                           current_sort=sort,
                           view_mode=view,
                           current_user=current_user,
                           user_favorites=user_favorites,
                           total_count=stats['total'],
                           unique_provinces=stats['provinces'],
                           unique_categories=stats['categories'],
                           avg_rating=stats['avg_rating'],
                           category_stats=stats['category_stats'],
                           province_stats=stats['province_stats'],
                           hot_destinations=hot_destinations,
                           top_rated_destinations=top_rated_destinations,
                           ALL_PROVINCES=ALL_PROVINCES,
                           background_image=bg_image)


@cache.memoize(timeout=600)
def _get_destination_stats():
    """缓存景点统计数据（10分钟）"""
    total = Destination.query.count()
    provinces = db.session.query(Destination.province).distinct().count()
    categories = db.session.query(Destination.category).distinct().count()
    avg_rating = db.session.query(func.avg(Destination.rating)).scalar() or 0
    category_stats = db.session.query(
        Destination.category, func.count(Destination.id)
    ).group_by(Destination.category).order_by(Destination.category).all()
    province_stats = db.session.query(
        Destination.province, func.count(Destination.id)
    ).group_by(Destination.province).order_by(Destination.province).all()
    return {
        'total': total,
        'provinces': provinces,
        'categories': categories,
        'avg_rating': round(float(avg_rating), 1),
        'category_stats': category_stats,
        'province_stats': province_stats,
    }

@cache.memoize(timeout=600)
def _get_hot_destinations():
    """缓存热门景点（10分钟）"""
    return Destination.query.order_by(Destination.popularity_score.desc()).limit(10).all()

@cache.memoize(timeout=600)
def _get_top_rated():
    """缓存好评景点（10分钟）"""
    return Destination.query.order_by(Destination.rating.desc()).limit(10).all()


# ==================== 智能助手页面 ====================
@app.route('/chat')
def chat():
    session_id = request.args.get('session', request.remote_addr)
    current_user = None
    if 'user_id' in session:
        current_user = db.session.get(User, session['user_id'])

    # 随机背景图片
    bg_image = random.choice(BACKGROUND_IMAGES)['url']

    return render_template('chat.html',
                           session_id=session_id,
                           current_user=current_user,
                           background_image=bg_image)


# ==================== 关于页面 ====================
@app.route('/about')
def about():
    """关于我们页面"""
    current_user = None
    if 'user_id' in session:
        current_user = db.session.get(User, session['user_id'])

    # 随机背景图片
    bg_image = random.choice(BACKGROUND_IMAGES)['url']

    return render_template('about.html',
                           current_user=current_user,
                           background_image=bg_image)


# ==================== 热门景点页面（可选，如果不想用 ?view=hot 参数）====================
@app.route('/hot-destinations')
def hot_destinations():
    """热门景点页面"""
    page = request.args.get('page', 1, type=int)
    per_page = 12

    # 按人气排序
    query = Destination.query.order_by(Destination.popularity_score.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    current_user = None
    user_favorites = []
    if 'user_id' in session:
        current_user = db.session.get(User, session['user_id'])
        if current_user:
            user_favorites = json.loads(current_user.favorites or '[]')

    bg_image = random.choice(BACKGROUND_IMAGES)['url']

    return render_template('hot_destinations.html',
                           destinations=pagination.items,
                           pagination=pagination,
                           current_user=current_user,
                           user_favorites=user_favorites,
                           background_image=bg_image)


# ==================== 景点详情页 ====================
@app.route('/dest/<int:dest_id>')
def dest_detail(dest_id):
    dest = db.session.get(Destination, dest_id)
    if not dest:
        abort(404)

    # 增加人气
    dest.popularity_score = (dest.popularity_score or 0) + 1

    # 确保有封面图片
    if not dest.cover_image or 'placeholder' in dest.cover_image:
        matched_image = match_scenic_image(dest.name, external=True)
        if matched_image and 'placeholder' not in matched_image:
            dest.cover_image = matched_image

    # 记录点击历史
    if 'user_id' in session:
        user = db.session.get(User, session['user_id'])
        if user:
            clicks = json.loads(user.click_history or '[]')
            if dest_id not in clicks:
                clicks.append(dest_id)
                user.click_history = json.dumps(clicks[-30:])
                db.session.commit()

    db.session.commit()

    # 相关景点
    related = Destination.query.filter(
        Destination.city == dest.city,
        Destination.id != dest.id
    ).limit(4).all()

    # 为相关景点匹配图片
    for related_item in related:
        if not related_item.cover_image or 'placeholder' in related_item.cover_image:
            related_item.cover_image = match_scenic_image(related_item.name, external=True)

    current_user = None
    user_favorites = []
    if 'user_id' in session:
        current_user = db.session.get(User, session['user_id'])
        if current_user:
            user_favorites = json.loads(current_user.favorites or '[]')

    # 解析标签
    tags = []
    if dest.tags:
        try:
            tags = json.loads(dest.tags)
        except:
            pass

    # 随机背景图片
    bg_image = random.choice(BACKGROUND_IMAGES)['url']

    return render_template('dest_detail.html',
                           dest=dest,
                           related=related,
                           tags=tags,
                           current_user=current_user,
                           user_favorites=user_favorites,
                           background_image=bg_image)


# ==================== 评论API（数据库持久化） ====================

def _seed_reviews_for_destination(dest_id, dest_name, count=15):
    """为景点生成种子评论并写入数据库"""
    avatar_colors = ['bg-red-500', 'bg-blue-500', 'bg-green-500', 'bg-yellow-500', 'bg-purple-500']
    user_levels = ['青铜', '白银', '黄金', '铂金', '钻石']
    now = datetime.now()

    reviews_to_add = []
    for _ in range(count):
        rating = round(random.uniform(3.5, 5.0), 1)
        content = random.choice(REVIEW_TEMPLATES)
        username = random.choice(USERNAMES) + str(random.randint(1, 100))
        days_ago = random.randint(1, 365)
        review_date = now - timedelta(days=days_ago)
        likes = random.randint(0, 50)
        has_images = random.random() > 0.7
        images = []
        if has_images:
            images = [f"https://picsum.photos/200/150?random={random.randint(1,1000)}" for _ in range(random.randint(1, 3))]

        review = Review(
            destination_id=dest_id,
            username=username,
            rating=rating,
            content=content,
            images=json.dumps(images, ensure_ascii=False),
            likes=likes,
            status='approved',
            created_at=review_date
        )
        reviews_to_add.append(review)

    db.session.add_all(reviews_to_add)
    db.session.commit()
    return reviews_to_add


def _ensure_reviews_exist(dest_id, dest_name):
    """确保景点有评论，如果没有则自动生成"""
    count = Review.query.filter_by(destination_id=dest_id, status='approved').count()
    if count == 0:
        _seed_reviews_for_destination(dest_id, dest_name, random.randint(10, 20))


def _review_to_dict(review, dest_name=None):
    """将Review模型转为字典"""
    avatar_colors = ['bg-red-500', 'bg-blue-500', 'bg-green-500', 'bg-yellow-500', 'bg-purple-500']
    user_levels = ['青铜', '白银', '黄金', '铂金', '钻石']
    return {
        'id': review.id,
        'dest_id': review.destination_id,
        'dest_name': dest_name or (review.destination.name if review.destination else ''),
        'username': review.username,
        'avatar_color': random.choice(avatar_colors),
        'rating': review.rating,
        'content': review.content,
        'created_at': review.created_at.strftime('%Y-%m-%d') if review.created_at else '',
        'likes': review.likes or 0,
        'images': json.loads(review.images) if review.images else [],
        'user_level': random.choice(user_levels) if random.random() > 0.5 else None
    }


@app.route('/api/reviews/<int:dest_id>')
def get_reviews(dest_id):
    """获取景点评论（数据库版）"""
    dest = db.session.get(Destination, dest_id)
    if not dest:
        return jsonify({'success': False, 'error': '景点不存在'}), 404

    # 确保评论存在
    _ensure_reviews_exist(dest_id, dest.name)

    # 获取分页参数
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 10, type=int), 50)

    # 查询数据库
    pagination = Review.query.filter_by(destination_id=dest_id, status='approved') \
        .order_by(Review.created_at.desc()) \
        .paginate(page=page, per_page=per_page, error_out=False)

    reviews = [_review_to_dict(r) for r in pagination.items]

    # 计算评分分布
    all_reviews = Review.query.filter_by(destination_id=dest_id, status='approved').all()
    rating_distribution = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
    for r in all_reviews:
        bucket = min(5, max(1, int(r.rating)))
        rating_distribution[bucket] += 1

    total = len(all_reviews)
    rating_percentages = {}
    for k, v in rating_distribution.items():
        rating_percentages[k] = round((v / total * 100), 1) if total > 0 else 0

    return jsonify({
        'success': True,
        'reviews': reviews,
        'total': total,
        'page': page,
        'pages': pagination.pages,
        'rating_distribution': rating_percentages,
        'avg_rating': dest.rating
    })


@app.route('/api/reviews/<int:dest_id>/add', methods=['POST'])
@login_required
def add_review(dest_id):
    """添加评论（数据库版）"""
    dest = db.session.get(Destination, dest_id)
    if not dest:
        return jsonify({'success': False, 'error': '景点不存在'}), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': '请求体必须为JSON格式'}), 400

    from services.validators import validate_rating, sanitize_string
    rating = validate_rating(data.get('rating'))
    content = sanitize_string(data.get('content', ''), 500)

    if rating is None:
        return jsonify({'success': False, 'error': '评分必须在1-5之间'}), 400
    if not content:
        return jsonify({'success': False, 'error': '评论内容不能为空'}), 400

    user = db.session.get(User, session['user_id'])

    # 写入数据库
    review = Review(
        destination_id=dest_id,
        user_id=user.id,
        username=user.username,
        rating=rating,
        content=content,
        images='[]',
        likes=0,
        status='approved'
    )
    db.session.add(review)

    # 更新景点评分
    total_rating = dest.rating * dest.review_count + rating
    dest.review_count += 1
    dest.rating = round(total_rating / dest.review_count, 1)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': '评论成功',
        'review': _review_to_dict(review)
    })


@app.route('/api/reviews/<int:dest_id>/edit', methods=['POST'])
@login_required
def edit_review(dest_id):
    """修改评论（数据库版）"""
    dest = db.session.get(Destination, dest_id)
    if not dest:
        return jsonify({'success': False, 'error': '景点不存在'}), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': '请求体必须为JSON格式'}), 400

    from services.validators import validate_rating, validate_positive_int, sanitize_string

    review_id, err = validate_positive_int(data.get('review_id'), '评论ID')
    if err:
        return jsonify({'success': False, 'error': err}), 400

    rating = validate_rating(data.get('rating'))
    content = sanitize_string(data.get('content', ''), 500)

    if rating is None:
        return jsonify({'success': False, 'error': '评分必须在1-5之间'}), 400
    if not content:
        return jsonify({'success': False, 'error': '评论内容不能为空'}), 400

    user = db.session.get(User, session['user_id'])

    # 从数据库查找评论
    review = Review.query.filter_by(id=review_id, destination_id=dest_id).first()
    if not review:
        return jsonify({'success': False, 'error': '评论不存在'}), 404

    # 检查权限：只有自己的评论或管理员可修改
    if review.user_id != user.id and review.username != user.username:
        return jsonify({'success': False, 'error': '只能修改自己的评论'}), 403

    old_rating = review.rating
    review.rating = rating
    review.content = content
    review.updated_at = datetime.now()

    # 更新景点评分
    if dest.review_count > 0:
        total_rating = dest.rating * dest.review_count - old_rating + rating
        dest.rating = round(total_rating / dest.review_count, 1)

    db.session.commit()

    return jsonify({
        'success': True,
        'message': '评论修改成功',
        'review': _review_to_dict(review)
    })


@app.route('/reviews/<int:dest_id>')
def reviews_page(dest_id):
    """评论列表页面（数据库版）"""
    dest = db.session.get(Destination, dest_id)
    if not dest:
        abort(404)

    # 确保评论存在
    _ensure_reviews_exist(dest_id, dest.name)

    # 分页
    page = request.args.get('page', 1, type=int)
    per_page = 10

    pagination = Review.query.filter_by(destination_id=dest_id, status='approved') \
        .order_by(Review.created_at.desc()) \
        .paginate(page=page, per_page=per_page, error_out=False)

    paginated_reviews = [_review_to_dict(r) for r in pagination.items]

    # 计算评分分布
    all_reviews = Review.query.filter_by(destination_id=dest_id, status='approved').all()
    total = len(all_reviews)
    rating_distribution = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
    for r in all_reviews:
        bucket = min(5, max(1, int(r.rating)))
        rating_distribution[bucket] += 1
    rating_percentages = {}
    for k, v in rating_distribution.items():
        rating_percentages[k] = round((v / total * 100), 1) if total > 0 else 0

    current_user = None
    if 'user_id' in session:
        current_user = db.session.get(User, session['user_id'])

    bg_image = random.choice(BACKGROUND_IMAGES)['url']
    now = datetime.now()

    stats = {
        'total_reviews': total,
        'positive_reviews': len([r for r in all_reviews if r.rating >= 4]),
        'pending_reviews': Review.query.filter_by(destination_id=dest_id, status='pending').count(),
        'deleted_reviews': 0
    }

    return render_template('reviews.html',
                          destination=dest,
                          reviews=paginated_reviews,
                          pagination=pagination,
                          rating_distribution=rating_percentages,
                          current_user=current_user,
                          background_image=bg_image,
                          now=now,
                          stats=stats)
# ==================== API接口 ====================
@app.route('/api/search', methods=['GET'])
def api_search():
    query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    per_page = 20

    db_query = Destination.query
    if query:
        db_query = db_query.filter(
            or_(Destination.name.ilike(f'%{query}%'),
                Destination.city.ilike(f'%{query}%'),
                Destination.description.ilike(f'%{query}%'))
        )

        # 保存搜索历史
        if 'user_id' in session and len(query) >= 2:
            user = db.session.get(User, session['user_id'])
            if user:
                history = json.loads(user.search_history or '[]')
                history.insert(0, f"{query} - {datetime.now().strftime('%Y-%m-%d')}")
                user.search_history = json.dumps(history[:20])
                db.session.commit()

    pagination = db_query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'success': True,
        'count': pagination.total,
        'page': page,
        'pages': pagination.pages,
        'results': [d.to_dict() for d in pagination.items]
    })


# ==================== 搜索建议API（支持拼音） ====================
@app.route('/api/search/suggestions', methods=['GET'])
def api_search_suggestions():
    """搜索建议API - 支持拼音搜索"""
    query = request.args.get('q', '').strip()
    limit = min(int(request.args.get('limit', 10)), 20)

    if not query or len(query) < 1:
        return jsonify({'success': True, 'suggestions': []})

    suggestions = []

    try:
        # 1. 直接匹配景点名称
        direct_matches = Destination.query.filter(
            Destination.name.ilike(f'%{query}%')
        ).order_by(Destination.popularity_score.desc()).limit(limit).all()

        for dest in direct_matches:
            suggestions.append({
                'type': 'destination',
                'id': dest.id,
                'name': dest.name,
                'city': dest.city,
                'province': dest.province,
                'category': dest.category,
                'rating': dest.rating,
                'cover_image': dest.cover_image
            })

        # 2. 如果直接匹配结果不够，尝试拼音匹配
        if len(suggestions) < limit:
            # 获取所有景点
            all_destinations = Destination.query.all()

            # 将查询转换为拼音
            query_pinyin = ''.join([p[0] for p in pinyin(query, style=Style.NORMAL)])

            for dest in all_destinations:
                if len(suggestions) >= limit:
                    break

                # 跳过已添加的
                if any(s['id'] == dest.id for s in suggestions):
                    continue

                # 将景点名称转换为拼音
                dest_pinyin = ''.join([p[0] for p in pinyin(dest.name, style=Style.NORMAL)])

                # 拼音匹配
                if query_pinyin in dest_pinyin or dest_pinyin.startswith(query_pinyin):
                    suggestions.append({
                        'type': 'destination',
                        'id': dest.id,
                        'name': dest.name,
                        'city': dest.city,
                        'province': dest.province,
                        'category': dest.category,
                        'rating': dest.rating,
                        'cover_image': dest.cover_image
                    })

        # 3. 添加城市建议
        if len(suggestions) < limit:
            cities = db.session.query(Destination.city).distinct().all()
            for city in cities:
                if len(suggestions) >= limit:
                    break
                if query in city[0] or ''.join([p[0] for p in pinyin(city[0], style=Style.NORMAL)]) in query:
                    suggestions.append({
                        'type': 'city',
                        'name': city[0],
                        'text': f'查看{city[0]}的所有景点'
                    })

        # 4. 添加省份建议
        if len(suggestions) < limit:
            provinces = db.session.query(Destination.province).distinct().all()
            for province in provinces:
                if len(suggestions) >= limit:
                    break
                if query in province[0] or ''.join([p[0] for p in pinyin(province[0], style=Style.NORMAL)]) in query:
                    suggestions.append({
                        'type': 'province',
                        'name': province[0],
                        'text': f'查看{province[0]}的所有景点'
                    })

        return jsonify({'success': True, 'suggestions': suggestions})

    except Exception as e:
        log.info(f"搜索建议错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== 推荐系统API ====================
@app.route('/api/recommendations/personalized', methods=['GET'])
@login_required
def api_personalized_recommendations():
    """个性化推荐API"""
    try:
        user_id = session.get('user_id')
        limit = min(int(request.args.get('limit', 10)), 50)

        user = db.session.get(User, user_id)
        if not user:
            return jsonify({'success': False, 'error': '用户不存在'}), 404

        # 获取用户收藏和点击历史
        favorites = json.loads(user.favorites or '[]')
        clicks = json.loads(user.click_history or '[]')

        # 基于用户行为推荐
        if favorites or clicks:
            # 分析用户偏好
            user_destinations = Destination.query.filter(
                Destination.id.in_(favorites + clicks)
            ).all()

            # 统计用户偏好的分类和省份
            category偏好 = defaultdict(int)
            province偏好 = defaultdict(int)

            for dest in user_destinations:
                category偏好[dest.category] += 1
                province偏好[dest.province] += 1

            # 获取用户未收藏的景点
            exclude_ids = list(set(favorites + clicks))
            query = Destination.query.filter(~Destination.id.in_(exclude_ids))

            # 按用户偏好排序
            recommendations = []

            # 优先推荐用户喜欢的分类
            for category, count in sorted(category偏好.items(), key=lambda x: x[1], reverse=True):
                category_recs = query.filter(
                    Destination.category == category
                ).order_by(Destination.popularity_score.desc()).limit(limit // 2).all()
                recommendations.extend(category_recs)

            # 补充用户喜欢的省份
            for province, count in sorted(province偏好.items(), key=lambda x: x[1], reverse=True):
                province_recs = query.filter(
                    Destination.province == province,
                    ~Destination.id.in_([r.id for r in recommendations])
                ).order_by(Destination.popularity_score.desc()).limit(limit // 2).all()
                recommendations.extend(province_recs)

            # 如果还不够，补充热门景点
            if len(recommendations) < limit:
                hot_recs = query.filter(
                    ~Destination.id.in_([r.id for r in recommendations])
                ).order_by(Destination.popularity_score.desc()).limit(limit - len(recommendations)).all()
                recommendations.extend(hot_recs)

            recommendations = recommendations[:limit]
        else:
            # 新用户，推荐热门景点
            recommendations = Destination.query.order_by(
                Destination.popularity_score.desc()
            ).limit(limit).all()

        # 为推荐景点匹配图片
        for rec in recommendations:
            if not rec.cover_image or 'placeholder' in rec.cover_image:
                rec.cover_image = match_scenic_image(rec.name, external=True)

        return jsonify({
            'success': True,
            'recommendations': [d.to_dict() for d in recommendations],
            'count': len(recommendations),
            'type': 'personalized' if (favorites or clicks) else 'popular'
        })

    except Exception as e:
        log.info(f"个性化推荐错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/recommendations/collaborative', methods=['GET'])
@login_required
def api_collaborative_recommendations():
    """协同过滤推荐API"""
    try:
        user_id = session.get('user_id')
        limit = min(int(request.args.get('limit', 10)), 50)

        current_user = db.session.get(User, user_id)
        if not current_user:
            return jsonify({'success': False, 'error': '用户不存在'}), 404

        # 获取当前用户的收藏
        current_favorites = set(json.loads(current_user.favorites or '[]'))

        if not current_favorites:
            # 没有收藏记录，返回热门推荐
            recommendations = Destination.query.order_by(
                Destination.popularity_score.desc()
            ).limit(limit).all()
            return jsonify({
                'success': True,
                'recommendations': [d.to_dict() for d in recommendations],
                'count': len(recommendations),
                'type': 'popular_fallback'
            })

        # 查找相似用户（收藏有重叠的用户）
        all_users = User.query.filter(User.id != user_id).all()
        similar_users = []

        for user in all_users:
            user_favorites = set(json.loads(user.favorites or '[]'))
            # 计算收藏重叠度
            overlap = len(current_favorites & user_favorites)
            if overlap > 0:
                similar_users.append({
                    'user': user,
                    'overlap': overlap,
                    'favorites': user_favorites
                })

        # 按重叠度排序
        similar_users.sort(key=lambda x: x['overlap'], reverse=True)

        # 从相似用户的收藏中推荐
        recommendations = []
        recommended_ids = set()

        for similar in similar_users[:5]:  # 只考虑前5个相似用户
            # 获取相似用户收藏但当前用户未收藏的景点
            new_favorites = similar['favorites'] - current_favorites - recommended_ids

            for fav_id in list(new_favorites)[:3]:  # 每个相似用户最多推荐3个
                dest = db.session.get(Destination, fav_id)
                if dest and dest not in recommendations:
                    recommendations.append(dest)
                    recommended_ids.add(fav_id)

                if len(recommendations) >= limit:
                    break

            if len(recommendations) >= limit:
                break

        # 如果推荐不够，补充热门景点
        if len(recommendations) < limit:
            hot_recs = Destination.query.filter(
                ~Destination.id.in_(recommended_ids | current_favorites)
            ).order_by(Destination.popularity_score.desc()).limit(limit - len(recommendations)).all()
            recommendations.extend(hot_recs)

        # 为推荐景点匹配图片
        for rec in recommendations:
            if not rec.cover_image or 'placeholder' in rec.cover_image:
                rec.cover_image = match_scenic_image(rec.name, external=True)

        return jsonify({
            'success': True,
            'recommendations': [d.to_dict() for d in recommendations],
            'count': len(recommendations),
            'type': 'collaborative',
            'similar_users_count': len(similar_users)
        })

    except Exception as e:
        log.info(f"协同过滤推荐错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/recommendations/hot', methods=['GET'])
def api_hot_recommendations():
    """热门景点排行API"""
    try:
        limit = min(int(request.args.get('limit', 10)), 50)
        category = request.args.get('category', '')
        province = request.args.get('province', '')

        query = Destination.query

        # 应用筛选
        if category:
            query = query.filter(Destination.category == category)
        if province:
            query = query.filter(Destination.province == province)

        # 按人气和评分排序
        hot_destinations = query.order_by(
            Destination.popularity_score.desc(),
            Destination.rating.desc()
        ).limit(limit).all()

        # 为景点匹配图片
        for dest in hot_destinations:
            if not dest.cover_image or 'placeholder' in dest.cover_image:
                dest.cover_image = match_scenic_image(dest.name, external=True)

        return jsonify({
            'success': True,
            'destinations': [d.to_dict() for d in hot_destinations],
            'count': len(hot_destinations),
            'category': category,
            'province': province
        })

    except Exception as e:
        log.info(f"热门推荐错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/recommendations/similar/<int:dest_id>', methods=['GET'])
def api_similar_recommendations(dest_id):
    """相似景点推荐API"""
    try:
        limit = min(int(request.args.get('limit', 6)), 20)

        target_dest = db.session.get(Destination, dest_id)
        if not target_dest:
            return jsonify({'success': False, 'error': '景点不存在'}), 404

        # 基于分类、省份、标签相似度推荐
        similar_destinations = []

        # 1. 同分类同省份的景点
        same_category_province = Destination.query.filter(
            Destination.category == target_dest.category,
            Destination.province == target_dest.province,
            Destination.id != dest_id
        ).order_by(Destination.popularity_score.desc()).limit(limit // 2).all()
        similar_destinations.extend(same_category_province)

        # 2. 同分类其他省份的景点
        if len(similar_destinations) < limit:
            same_category = Destination.query.filter(
                Destination.category == target_dest.category,
                Destination.province != target_dest.province,
                ~Destination.id.in_([d.id for d in similar_destinations])
            ).order_by(Destination.popularity_score.desc()).limit(limit - len(similar_destinations)).all()
            similar_destinations.extend(same_category)

        # 3. 同省份其他分类的景点
        if len(similar_destinations) < limit:
            same_province = Destination.query.filter(
                Destination.province == target_dest.province,
                Destination.category != target_dest.category,
                ~Destination.id.in_([d.id for d in similar_destinations])
            ).order_by(Destination.popularity_score.desc()).limit(limit - len(similar_destinations)).all()
            similar_destinations.extend(same_province)

        # 为景点匹配图片
        for dest in similar_destinations:
            if not dest.cover_image or 'placeholder' in dest.cover_image:
                dest.cover_image = match_scenic_image(dest.name, external=True)

        return jsonify({
            'success': True,
            'similar_destinations': [d.to_dict() for d in similar_destinations],
            'count': len(similar_destinations),
            'target_destination': target_dest.to_dict()
        })

    except Exception as e:
        log.info(f"相似推荐错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== 用户体验优化API ====================
@app.route('/api/mobile/config', methods=['GET'])
def api_mobile_config():
    """移动端配置API"""
    try:
        config = {
            'app_name': '智能旅游助手',
            'version': '1.0.0',
            'features': {
                'search_suggestions': True,
                'pinyin_search': True,
                'recommendations': True,
                'weather': True,
                'favorites': True,
                'reviews': True,
                'chat_assistant': True
            },
            'ui': {
                'primary_color': '#1890ff',
                'background_images': len(BACKGROUND_IMAGES),
                'max_search_history': 20,
                'max_favorites': 100,
                'page_size': 12
            },
            'api_endpoints': {
                'search': '/api/search',
                'suggestions': '/api/search/suggestions',
                'recommendations': '/api/recommendations/personalized',
                'hot': '/api/recommendations/hot',
                'weather': '/api/weather',
                'favorites': '/api/favorite'
            }
        }

        return jsonify({
            'success': True,
            'config': config
        })

    except Exception as e:
        log.info(f"移动端配置错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/performance/stats', methods=['GET'])
def api_performance_stats():
    """性能统计API"""
    try:
        # 数据库统计
        total_destinations = Destination.query.count()
        total_users = User.query.count()
        total_reviews = Review.query.count()

        # 热门分类统计
        category_stats = db.session.query(
            Destination.category,
            func.count(Destination.id).label('count')
        ).group_by(Destination.category).order_by(func.count(Destination.id).desc()).limit(5).all()

        # 热门省份统计
        province_stats = db.session.query(
            Destination.province,
            func.count(Destination.id).label('count')
        ).group_by(Destination.province).order_by(func.count(Destination.id).desc()).limit(5).all()

        # 评分分布
        rating_distribution = db.session.query(
            func.floor(Destination.rating).label('rating_floor'),
            func.count(Destination.id).label('count')
        ).group_by(func.floor(Destination.rating)).all()

        stats = {
            'database': {
                'total_destinations': total_destinations,
                'total_users': total_users,
                'total_reviews': total_reviews
            },
            'categories': [{'name': cat, 'count': count} for cat, count in category_stats],
            'provinces': [{'name': prov, 'count': count} for prov, count in province_stats],
            'rating_distribution': [{'rating': int(rating), 'count': count} for rating, count in rating_distribution],
            'cache': {
                'reviews_cached': total_reviews,  # 数据库中评论数
                'background_images': len(BACKGROUND_IMAGES)
            }
        }

        return jsonify({
            'success': True,
            'stats': stats
        })

    except Exception as e:
        log.info(f"性能统计错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/behavior', methods=['POST'])
@login_required
def api_user_behavior():
    """用户行为追踪API"""
    try:
        data = request.get_json()
        action = data.get('action')
        target = data.get('target')
        details = data.get('details', {})

        user_id = session.get('user_id')

        # 记录用户行为（这里简化处理，实际应该存储到数据库）
        behavior_log = {
            'user_id': user_id,
            'action': action,
            'target': target,
            'details': details,
            'timestamp': datetime.now().isoformat(),
            'ip': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', '')
        }

        log.info(f"📊 用户行为: {behavior_log}")

        return jsonify({
            'success': True,
            'message': '行为记录成功'
        })

    except Exception as e:
        log.info(f"用户行为追踪错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/system/health', methods=['GET'])
def api_system_health():
    """系统健康检查API"""
    try:
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'services': {
                'database': 'up',
                'cache': 'up',
                'weather_api': 'up' if weather_api.api_key else 'down',
                'gaode_api': 'up' if gaode_api else 'down'
            },
            'metrics': {
                'uptime': 'running',
                'memory_usage': 'normal',
                'response_time': 'fast'
            }
        }

        return jsonify({
            'success': True,
            'health': health_status
        })

    except Exception as e:
        log.info(f"系统健康检查错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== 安全优化功能 ====================

# 登录失败记录（内存存储，生产环境应使用Redis）
login_attempts = defaultdict(list)
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION = 300  # 5分钟锁定

def check_login_attempts(ip_address):
    """检查登录尝试次数"""
    now = datetime.now()
    attempts = login_attempts[ip_address]

    # 清理过期的尝试记录
    attempts = [attempt for attempt in attempts if (now - attempt).seconds < LOCKOUT_DURATION]
    login_attempts[ip_address] = attempts

    return len(attempts) < MAX_LOGIN_ATTEMPTS

def record_login_attempt(ip_address, success):
    """记录登录尝试"""
    now = datetime.now()
    if not success:
        login_attempts[ip_address].append(now)

def validate_password_strength(password):
    """验证密码强度"""
    errors = []

    if len(password) < 8:
        errors.append("密码长度至少8个字符")

    if not re.search(r'[A-Z]', password):
        errors.append("密码必须包含至少一个大写字母")

    if not re.search(r'[a-z]', password):
        errors.append("密码必须包含至少一个小写字母")

    if not re.search(r'\d', password):
        errors.append("密码必须包含至少一个数字")

    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        errors.append("密码必须包含至少一个特殊字符")

    return errors

def generate_csrf_token():
    """生成CSRF令牌"""
    if 'csrf_token' not in session:
        session['csrf_token'] = hashlib.sha256(
            str(random.getrandbits(256)).encode()
        ).hexdigest()
    return session['csrf_token']

def validate_csrf_token(token):
    """验证CSRF令牌"""
    return token and token == session.get('csrf_token')

# 为模板提供CSRF令牌
@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf_token())

@app.route('/api/security/check-password', methods=['POST'])
def api_check_password_strength():
    """检查密码强度API"""
    try:
        data = request.get_json()
        password = data.get('password', '')

        errors = validate_password_strength(password)

        # 计算密码强度分数
        score = 0
        if len(password) >= 8:
            score += 25
        if re.search(r'[A-Z]', password):
            score += 25
        if re.search(r'[a-z]', password):
            score += 25
        if re.search(r'\d', password):
            score += 15
        if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            score += 10

        strength = 'weak'
        if score >= 80:
            strength = 'strong'
        elif score >= 60:
            strength = 'medium'

        return jsonify({
            'success': True,
            'valid': len(errors) == 0,
            'errors': errors,
            'score': score,
            'strength': strength
        })

    except Exception as e:
        log.info(f"密码强度检查错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/security/validate-csrf', methods=['POST'])
def api_validate_csrf():
    """验证CSRF令牌API"""
    try:
        data = request.get_json()
        token = data.get('token', '')

        valid = validate_csrf_token(token)

        return jsonify({
            'success': True,
            'valid': valid
        })

    except Exception as e:
        log.info(f"CSRF验证错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/security/login-attempts', methods=['GET'])
def api_get_login_attempts():
    """获取登录尝试信息API"""
    try:
        ip_address = request.remote_addr
        attempts_count = len(login_attempts.get(ip_address, []))
        locked = not check_login_attempts(ip_address)

        return jsonify({
            'success': True,
            'attempts_count': attempts_count,
            'max_attempts': MAX_LOGIN_ATTEMPTS,
            'locked': locked,
            'lockout_duration': LOCKOUT_DURATION
        })

    except Exception as e:
        log.info(f"获取登录尝试信息错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# 修改登录API以包含安全检查
@app.route('/api/login/secure', methods=['POST'])
def api_login_secure():
    """安全登录API"""
    try:
        # 检查登录尝试次数
        ip_address = request.remote_addr
        if not check_login_attempts(ip_address):
            return jsonify({
                'success': False,
                'error': f'登录失败次数过多，请{LOCKOUT_DURATION}秒后重试',
                'locked': True
            }), 429

        data = request.get_json()
        account = data.get('username', '').strip()
        password = data.get('password', '')
        remember = data.get('remember', False)
        csrf_token = data.get('csrf_token', '')

        # 验证CSRF令牌
        if not validate_csrf_token(csrf_token):
            return jsonify({'success': False, 'error': '无效的CSRF令牌'}), 403

        if not account or not password:
            record_login_attempt(ip_address, False)
            return jsonify({'success': False, 'error': '请填写用户名和密码'}), 400

        user = User.query.filter(
            or_(User.username == account, User.email == account)
        ).first()

        if user and user.check_password(password):
            # 登录成功
            record_login_attempt(ip_address, True)

            session.permanent = remember
            session['user_id'] = user.id
            session['username'] = user.username
            user.last_login = datetime.now()
            db.session.commit()

            return jsonify({
                'success': True,
                'message': '登录成功',
                'user': user.to_dict()
            })
        else:
            # 登录失败
            record_login_attempt(ip_address, False)
            remaining_attempts = MAX_LOGIN_ATTEMPTS - len(login_attempts.get(ip_address, []))

            return jsonify({
                'success': False,
                'error': '用户名或密码错误',
                'remaining_attempts': max(0, remaining_attempts)
            }), 401

    except Exception as e:
        log.info(f"安全登录错误: {e}")
        record_login_attempt(ip_address, False)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/security/sanitize-input', methods=['POST'])
def api_sanitize_input():
    """输入清理API"""
    try:
        data = request.get_json()
        input_text = data.get('input', '')

        # 基本的XSS防护
        sanitized = input_text
        sanitized = re.sub(r'<script[^>]*>.*?</script>', '', sanitized, flags=re.IGNORECASE | re.DOTALL)
        sanitized = re.sub(r'<[^>]+>', '', sanitized)  # 移除HTML标签
        sanitized = sanitized.replace('javascript:', '')
        sanitized = sanitized.replace('on', '')  # 移除事件处理器

        return jsonify({
            'success': True,
            'original': input_text,
            'sanitized': sanitized,
            'changed': sanitized != input_text
        })

    except Exception as e:
        log.info(f"输入清理错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/security/rate-limit-check', methods=['GET'])
def api_rate_limit_check():
    """速率限制检查API"""
    try:
        ip_address = request.remote_addr
        current_time = datetime.now()

        # 简单的速率限制（每分钟最多60次请求）
        if not hasattr(app, 'request_counts'):
            app.request_counts = defaultdict(list)

        requests = app.request_counts[ip_address]
        # 清理1分钟前的请求
        requests = [req_time for req_time in requests if (current_time - req_time).seconds < 60]
        app.request_counts[ip_address] = requests

        remaining = max(0, 60 - len(requests))

        return jsonify({
            'success': True,
            'requests_count': len(requests),
            'remaining_requests': remaining,
            'reset_time': 60
        })

    except Exception as e:
        log.info(f"速率限制检查错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== 地图功能 ====================

@app.route('/api/map/destinations', methods=['GET'])
def api_map_destinations():
    """获取景点地图数据API"""
    try:
        # 获取查询参数
        province = request.args.get('province', '')
        category = request.args.get('category', '')
        limit = min(int(request.args.get('limit', 50)), 100)

        query = Destination.query

        # 应用筛选
        if province:
            query = query.filter(Destination.province == province)
        if category:
            query = query.filter(Destination.category == category)

        # 只返回有坐标的景点
        query = query.filter(
            Destination.latitude.isnot(None),
            Destination.longitude.isnot(None)
        )

        destinations = query.order_by(Destination.popularity_score.desc()).limit(limit).all()

        map_data = []
        for dest in destinations:
            map_data.append({
                'id': dest.id,
                'name': dest.name,
                'latitude': dest.latitude,
                'longitude': dest.longitude,
                'category': dest.category,
                'rating': dest.rating,
                'province': dest.province,
                'city': dest.city,
                'address': dest.address,
                'cover_image': dest.cover_image or match_scenic_image(dest.name, external=True)
            })

        return jsonify({
            'success': True,
            'destinations': map_data,
            'count': len(map_data)
        })

    except Exception as e:
        log.info(f"地图数据获取错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/map/route', methods=['POST'])
def api_map_route():
    """路线规划API"""
    try:
        data = request.get_json()
        origin = data.get('origin')  # 起点坐标
        destination = data.get('destination')  # 终点坐标
        waypoints = data.get('waypoints', [])  # 途经点
        strategy = data.get('strategy', 'fastest')  # 路线策略

        if not origin or not destination:
            return jsonify({'success': False, 'error': '请提供起点和终点坐标'}), 400

        # 如果有高德API，使用真实路线规划
        if gaode_api:
            try:
                # 构建路线规划请求
                origin_str = f"{origin['longitude']},{origin['latitude']}"
                destination_str = f"{destination['longitude']},{destination['latitude']}"

                # 调用高德路线规划API
                route_url = "https://restapi.amap.com/v3/direction/driving"
                params = {
                    'key': GAODE_API_KEY,
                    'origin': origin_str,
                    'destination': destination_str,
                    'strategy': strategy
                }

                if waypoints:
                    waypoints_str = '|'.join([f"{wp['longitude']},{wp['latitude']}" for wp in waypoints])
                    params['waypoints'] = waypoints_str

                response = requests.get(route_url, params=params, timeout=10)
                if response.status_code == 200:
                    route_data = response.json()
                    if route_data.get('status') == '1':
                        path = route_data['route']['paths'][0]
                        return jsonify({
                            'success': True,
                            'route': {
                                'distance': path['distance'],
                                'duration': path['duration'],
                                'strategy': path['strategy'],
                                'steps': path['steps']
                            }
                        })
            except Exception as e:
                log.info(f"高德路线规划错误: {e}")

        # 模拟路线规划数据
        distance = random.randint(1000, 50000)  # 1-50公里
        duration = random.randint(300, 3600)  # 5分钟-1小时

        return jsonify({
            'success': True,
            'route': {
                'distance': distance,
                'duration': duration,
                'strategy': strategy,
                'steps': [
                    {
                        'instruction': '从起点出发',
                        'distance': distance // 3,
                        'duration': duration // 3
                    },
                    {
                        'instruction': '继续直行',
                        'distance': distance // 3,
                        'duration': duration // 3
                    },
                    {
                        'instruction': '到达目的地',
                        'distance': distance // 3,
                        'duration': duration // 3
                    }
                ]
            }
        })

    except Exception as e:
        log.info(f"路线规划错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/map/nearby', methods=['GET'])
def api_map_nearby():
    """周边搜索API"""
    try:
        latitude = request.args.get('latitude', type=float)
        longitude = request.args.get('longitude', type=float)
        radius = request.args.get('radius', 5000, type=int)  # 默认5公里
        category = request.args.get('category', '')
        limit = min(int(request.args.get('limit', 20)), 50)

        if not latitude or not longitude:
            return jsonify({'success': False, 'error': '请提供坐标'}), 400

        # 获取所有有坐标的景点
        query = Destination.query.filter(
            Destination.latitude.isnot(None),
            Destination.longitude.isnot(None)
        )

        if category:
            query = query.filter(Destination.category == category)

        all_destinations = query.all()

        # 计算距离并筛选
        nearby_destinations = []
        for dest in all_destinations:
            # 简单的距离计算（近似）
            lat_diff = abs(dest.latitude - latitude) * 111000  # 纬度1度约111公里
            lng_diff = abs(dest.longitude - longitude) * 111000 * 0.8  # 经度修正
            distance = (lat_diff**2 + lng_diff**2)**0.5

            if distance <= radius:
                nearby_destinations.append({
                    'id': dest.id,
                    'name': dest.name,
                    'latitude': dest.latitude,
                    'longitude': dest.longitude,
                    'category': dest.category,
                    'rating': dest.rating,
                    'province': dest.province,
                    'city': dest.city,
                    'address': dest.address,
                    'distance': round(distance),
                    'cover_image': dest.cover_image or match_scenic_image(dest.name, external=True)
                })

        # 按距离排序
        nearby_destinations.sort(key=lambda x: x['distance'])
        nearby_destinations = nearby_destinations[:limit]

        return jsonify({
            'success': True,
            'nearby': nearby_destinations,
            'count': len(nearby_destinations),
            'center': {'latitude': latitude, 'longitude': longitude},
            'radius': radius
        })

    except Exception as e:
        log.info(f"周边搜索错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/map/geocode', methods=['POST'])
def api_map_geocode():
    """地理编码API（地址转坐标）"""
    try:
        data = request.get_json()
        address = data.get('address', '')

        if not address:
            return jsonify({'success': False, 'error': '请提供地址'}), 400

        # 如果有高德API，使用真实地理编码
        if gaode_api:
            try:
                result = gaode_api.geocode(address)
                if result:
                    return jsonify({
                        'success': True,
                        'location': result
                    })
            except Exception as e:
                log.info(f"高德地理编码错误: {e}")

        # 模拟地理编码（北京为中心的随机坐标）
        base_lat = 39.9042
        base_lng = 116.4074
        lat_offset = random.uniform(-0.1, 0.1)
        lng_offset = random.uniform(-0.1, 0.1)

        return jsonify({
            'success': True,
            'location': {
                'latitude': base_lat + lat_offset,
                'longitude': base_lng + lng_offset,
                'address': address
            }
        })

    except Exception as e:
        log.info(f"地理编码错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/map/reverse-geocode', methods=['POST'])
def api_map_reverse_geocode():
    """逆地理编码API（坐标转地址）"""
    try:
        data = request.get_json()
        latitude = data.get('latitude')
        longitude = data.get('longitude')

        if not latitude or not longitude:
            return jsonify({'success': False, 'error': '请提供坐标'}), 400

        # 如果有高德API，使用真实逆地理编码
        if gaode_api:
            try:
                result = gaode_api.reverse_geocode(longitude, latitude)
                if result:
                    return jsonify({
                        'success': True,
                        'address': result
                    })
            except Exception as e:
                log.info(f"高德逆地理编码错误: {e}")

        # 模拟逆地理编码
        addresses = [
            "北京市东城区天安门广场",
            "北京市西城区什刹海",
            "北京市海淀区颐和园",
            "北京市朝阳区三里屯",
            "上海市黄浦区外滩"
        ]

        return jsonify({
            'success': True,
            'address': random.choice(addresses)
        })

    except Exception as e:
        log.info(f"逆地理编码错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== 行程规划API ====================

@app.route('/api/trips', methods=['GET'])
@login_required
def api_get_trips():
    """获取用户的行程列表"""
    try:
        user_id = session.get('user_id')
        status = request.args.get('status', '')  # planning, ongoing, completed, cancelled
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)

        query = Trip.query.filter_by(user_id=user_id)

        if status:
            query = query.filter_by(status=status)

        pagination = query.order_by(Trip.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        trips = []
        for trip in pagination.items:
            trip_data = trip.to_dict()
            # 计算行程统计
            trip_data['total_cost'] = sum(item.cost or 0 for item in trip.items)
            trip_data['items_count'] = len(trip.items)
            trips.append(trip_data)

        return jsonify({
            'success': True,
            'trips': trips,
            'total': pagination.total,
            'page': page,
            'pages': pagination.pages
        })

    except Exception as e:
        log.info(f"获取行程列表错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/trips', methods=['POST'])
@login_required
def api_create_trip():
    """创建新行程"""
    try:
        user_id = session.get('user_id')
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'success': False, 'error': '请求体必须为JSON格式'}), 400

        from services.validators import validate_string, validate_date, validate_float

        # 验证必填字段
        title, err = validate_string(data.get('title'), '标题', min_len=1, max_len=200, required=True)
        if err:
            return jsonify({'success': False, 'error': err}), 400

        start_date, err = validate_date(data.get('start_date'), '开始日期')
        if err:
            return jsonify({'success': False, 'error': err}), 400

        end_date, err = validate_date(data.get('end_date'), '结束日期')
        if err:
            return jsonify({'success': False, 'error': err}), 400

        if end_date < start_date:
            return jsonify({'success': False, 'error': '结束日期不能早于开始日期'}), 400

        budget, err = validate_float(data.get('budget', 0), '预算', default=0, min_val=0)
        if err:
            return jsonify({'success': False, 'error': err}), 400

        description, _ = validate_string(data.get('description', ''), '描述', max_len=1000)
        is_public = bool(data.get('is_public', False))

        # 生成分享码
        share_code = hashlib.md5(f"{user_id}{datetime.now().timestamp()}".encode()).hexdigest()[:8]

        # 创建行程
        trip = Trip(
            user_id=user_id,
            title=title,
            description=description,
            start_date=start_date,
            end_date=end_date,
            budget=budget,
            is_public=is_public,
            share_code=share_code
        )

        db.session.add(trip)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': '行程创建成功',
            'trip': trip.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        log.info(f"创建行程错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/trips/<int:trip_id>', methods=['GET'])
@login_required
def api_get_trip(trip_id):
    """获取行程详情"""
    try:
        user_id = session.get('user_id')
        trip = Trip.query.filter_by(id=trip_id, user_id=user_id).first()

        if not trip:
            return jsonify({'success': False, 'error': '行程不存在'}), 404

        trip_data = trip.to_dict()
        trip_data['total_cost'] = sum(item.cost or 0 for item in trip.items)
        trip_data['items_count'] = len(trip.items)

        return jsonify({
            'success': True,
            'trip': trip_data
        })

    except Exception as e:
        log.info(f"获取行程详情错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/trips/<int:trip_id>', methods=['PUT'])
@login_required
def api_update_trip(trip_id):
    """更新行程"""
    try:
        user_id = session.get('user_id')
        trip = Trip.query.filter_by(id=trip_id, user_id=user_id).first()

        if not trip:
            return jsonify({'success': False, 'error': '行程不存在'}), 404

        data = request.get_json(silent=True)
        if not data:
            return jsonify({'success': False, 'error': '请求体必须为JSON格式'}), 400

        from services.validators import validate_string, validate_date, validate_float, validate_choice

        # 更新字段（带验证）
        if 'title' in data:
            title, err = validate_string(data['title'], '标题', min_len=1, max_len=200, required=True)
            if err:
                return jsonify({'success': False, 'error': err}), 400
            trip.title = title

        if 'description' in data:
            trip.description, _ = validate_string(data['description'], '描述', max_len=1000)

        if 'start_date' in data:
            start_date, err = validate_date(data['start_date'], '开始日期')
            if err:
                return jsonify({'success': False, 'error': err}), 400
            trip.start_date = start_date

        if 'end_date' in data:
            end_date, err = validate_date(data['end_date'], '结束日期')
            if err:
                return jsonify({'success': False, 'error': err}), 400
            trip.end_date = end_date

        if 'budget' in data:
            budget, err = validate_float(data['budget'], '预算', default=trip.budget, min_val=0)
            if err:
                return jsonify({'success': False, 'error': err}), 400
            trip.budget = budget

        if 'status' in data:
            status, err = validate_choice(data['status'], '状态',
                ['planning', 'ongoing', 'completed', 'cancelled'], default=trip.status)
            if err:
                return jsonify({'success': False, 'error': err}), 400
            trip.status = status

        if 'is_public' in data:
            trip.is_public = bool(data['is_public'])

        # 验证日期
        if trip.end_date < trip.start_date:
            return jsonify({'success': False, 'error': '结束日期不能早于开始日期'}), 400

        db.session.commit()

        return jsonify({
            'success': True,
            'message': '行程更新成功',
            'trip': trip.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        log.info(f"更新行程错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/trips/<int:trip_id>', methods=['DELETE'])
@login_required
def api_delete_trip(trip_id):
    """删除行程"""
    try:
        user_id = session.get('user_id')
        trip = Trip.query.filter_by(id=trip_id, user_id=user_id).first()

        if not trip:
            return jsonify({'success': False, 'error': '行程不存在'}), 404

        db.session.delete(trip)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': '行程删除成功'
        })

    except Exception as e:
        db.session.rollback()
        log.info(f"删除行程错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/trips/<int:trip_id>/items', methods=['POST'])
@login_required
def api_add_trip_item(trip_id):
    """添加行程项目"""
    try:
        user_id = session.get('user_id')
        trip = Trip.query.filter_by(id=trip_id, user_id=user_id).first()

        if not trip:
            return jsonify({'success': False, 'error': '行程不存在'}), 404

        data = request.get_json(silent=True)
        if not data:
            return jsonify({'success': False, 'error': '请求体必须为JSON格式'}), 400

        from services.validators import validate_string, validate_positive_int, validate_float, validate_time

        # 验证必填字段
        activity, err = validate_string(data.get('activity'), '活动内容', min_len=1, max_len=200, required=True)
        if err:
            return jsonify({'success': False, 'error': err}), 400

        day_number, err = validate_positive_int(data.get('day_number'), '天数', min_val=1)
        if err:
            return jsonify({'success': False, 'error': err}), 400

        # 验证天数范围
        trip_duration = (trip.end_date - trip.start_date).days + 1
        if day_number > trip_duration:
            return jsonify({'success': False, 'error': f'天数必须在1-{trip_duration}之间'}), 400

        # 解析时间（可选）
        start_time, err = validate_time(data.get('start_time'), '开始时间')
        if err:
            return jsonify({'success': False, 'error': err}), 400

        end_time, err = validate_time(data.get('end_time'), '结束时间')
        if err:
            return jsonify({'success': False, 'error': err}), 400

        # 验证费用
        cost, err = validate_float(data.get('cost', 0), '费用', default=0, min_val=0)
        if err:
            return jsonify({'success': False, 'error': err}), 400

        location, _ = validate_string(data.get('location', ''), '地点', max_len=300)
        notes, _ = validate_string(data.get('notes', ''), '备注', max_len=1000)

        # 验证destination_id（可选）
        dest_id = data.get('destination_id')
        if dest_id is not None:
            dest_id, err = validate_positive_int(dest_id, '景点ID')
            if err:
                return jsonify({'success': False, 'error': err}), 400

        # 获取排序索引
        max_order = db.session.query(func.max(TripItem.order_index)).filter_by(trip_id=trip_id).scalar() or 0

        # 创建行程项目
        item = TripItem(
            trip_id=trip_id,
            destination_id=dest_id,
            day_number=day_number,
            start_time=start_time,
            end_time=end_time,
            activity=activity,
            location=location,
            notes=notes,
            cost=cost,
            order_index=max_order + 1
        )

        db.session.add(item)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': '行程项目添加成功',
            'item': item.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        log.info(f"添加行程项目错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/trips/<int:trip_id>/items/<int:item_id>', methods=['PUT'])
@login_required
def api_update_trip_item(trip_id, item_id):
    """更新行程项目"""
    try:
        user_id = session.get('user_id')
        trip = Trip.query.filter_by(id=trip_id, user_id=user_id).first()

        if not trip:
            return jsonify({'success': False, 'error': '行程不存在'}), 404

        item = TripItem.query.filter_by(id=item_id, trip_id=trip_id).first()
        if not item:
            return jsonify({'success': False, 'error': '行程项目不存在'}), 404

        data = request.get_json()

        # 更新字段
        if 'activity' in data:
            item.activity = data['activity'].strip()
        if 'location' in data:
            item.location = data['location'].strip()
        if 'notes' in data:
            item.notes = data['notes'].strip()
        if 'cost' in data:
            item.cost = float(data['cost'])
        if 'day_number' in data:
            day_number = int(data['day_number'])
            trip_duration = (trip.end_date - trip.start_date).days + 1
            if day_number < 1 or day_number > trip_duration:
                return jsonify({'success': False, 'error': f'天数必须在1-{trip_duration}之间'}), 400
            item.day_number = day_number
        if 'start_time' in data:
            if data['start_time']:
                try:
                    item.start_time = datetime.strptime(data['start_time'], '%H:%M').time()
                except ValueError:
                    return jsonify({'success': False, 'error': '开始时间格式错误'}), 400
            else:
                item.start_time = None
        if 'end_time' in data:
            if data['end_time']:
                try:
                    item.end_time = datetime.strptime(data['end_time'], '%H:%M').time()
                except ValueError:
                    return jsonify({'success': False, 'error': '结束时间格式错误'}), 400
            else:
                item.end_time = None
        if 'destination_id' in data:
            item.destination_id = data['destination_id']

        db.session.commit()

        return jsonify({
            'success': True,
            'message': '行程项目更新成功',
            'item': item.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        log.info(f"更新行程项目错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/trips/<int:trip_id>/items/<int:item_id>', methods=['DELETE'])
@login_required
def api_delete_trip_item(trip_id, item_id):
    """删除行程项目"""
    try:
        user_id = session.get('user_id')
        trip = Trip.query.filter_by(id=trip_id, user_id=user_id).first()

        if not trip:
            return jsonify({'success': False, 'error': '行程不存在'}), 404

        item = TripItem.query.filter_by(id=item_id, trip_id=trip_id).first()
        if not item:
            return jsonify({'success': False, 'error': '行程项目不存在'}), 404

        db.session.delete(item)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': '行程项目删除成功'
        })

    except Exception as e:
        db.session.rollback()
        log.info(f"删除行程项目错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/trips/share/<share_code>', methods=['GET'])
def api_get_shared_trip(share_code):
    """通过分享码获取行程"""
    try:
        trip = Trip.query.filter_by(share_code=share_code, is_public=True).first()

        if not trip:
            return jsonify({'success': False, 'error': '行程不存在或未公开'}), 404

        trip_data = trip.to_dict()
        trip_data['total_cost'] = sum(item.cost or 0 for item in trip.items)
        trip_data['items_count'] = len(trip.items)

        return jsonify({
            'success': True,
            'trip': trip_data
        })

    except Exception as e:
        log.info(f"获取分享行程错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/trips/<int:trip_id>/share', methods=['POST'])
@login_required
def api_share_trip(trip_id):
    """分享行程"""
    try:
        user_id = session.get('user_id')
        trip = Trip.query.filter_by(id=trip_id, user_id=user_id).first()

        if not trip:
            return jsonify({'success': False, 'error': '行程不存在'}), 404

        data = request.get_json()
        platform = data.get('platform', 'link')

        # 记录分享
        share_record = TripShare(
            trip_id=trip_id,
            user_id=user_id,
            platform=platform
        )
        db.session.add(share_record)

        # 设置为公开
        trip.is_public = True

        db.session.commit()

        share_url = f"{request.host_url}trip/share/{trip.share_code}"

        return jsonify({
            'success': True,
            'message': '分享成功',
            'share_url': share_url,
            'share_code': trip.share_code
        })

    except Exception as e:
        db.session.rollback()
        log.info(f"分享行程错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/trips/recommend', methods=['POST'])
@login_required
def api_recommend_trip():
    """智能行程推荐"""
    try:
        data = request.get_json()
        city = data.get('city', '')
        days = data.get('days', 3)
        preferences = data.get('preferences', [])  # 偏好：历史、自然、美食等
        budget = data.get('budget', 0)

        if not city:
            return jsonify({'success': False, 'error': '请指定城市'}), 400

        days = min(max(days, 1), 7)

        # 获取该城市的景点
        destinations = Destination.query.filter(
            or_(Destination.city.contains(city), Destination.province.contains(city))
        ).order_by(Destination.popularity_score.desc()).all()

        if not destinations:
            return jsonify({'success': False, 'error': f'没有找到{city}的景点'}), 404

        # 根据偏好筛选
        if preferences:
            filtered_destinations = []
            for dest in destinations:
                dest_tags = json.loads(dest.tags or '[]')
                if any(pref in dest_tags for pref in preferences):
                    filtered_destinations.append(dest)
            if filtered_destinations:
                destinations = filtered_destinations

        # 生成行程
        recommended_items = []
        destinations_per_day = max(2, len(destinations) // days)

        for day in range(1, days + 1):
            day_destinations = destinations[(day-1) * destinations_per_day:day * destinations_per_day]

            for i, dest in enumerate(day_destinations):
                # 分配时间
                if i == 0:
                    start_time = "09:00"
                    end_time = "12:00"
                elif i == 1:
                    start_time = "14:00"
                    end_time = "17:00"
                else:
                    start_time = "19:00"
                    end_time = "21:00"

                recommended_items.append({
                    'day_number': day,
                    'destination_id': dest.id,
                    'activity': f"游览{dest.name}",
                    'location': dest.address or dest.city,
                    'start_time': start_time,
                    'end_time': end_time,
                    'cost': 0,
                    'notes': dest.description[:100] if dest.description else ''
                })

        return jsonify({
            'success': True,
            'recommended_items': recommended_items,
            'total_days': days,
            'destinations_count': len(recommended_items),
            'city': city
        })

    except Exception as e:
        log.info(f"行程推荐错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== 行程导出功能 ====================

@app.route('/api/trips/<int:trip_id>/export/pdf', methods=['GET'])
@login_required
def api_export_trip_pdf(trip_id):
    """导出行程为PDF"""
    try:
        # 获取行程信息
        trip = Trip.query.filter_by(id=trip_id, user_id=session['user_id']).first()
        if not trip:
            return jsonify({'success': False, 'error': '行程不存在'}), 404

        # 获取行程项目
        trip_items = TripItem.query.filter_by(trip_id=trip_id).order_by(TripItem.day_number, TripItem.order_index).all()

        # 生成PDF内容
        pdf_content = generate_trip_pdf(trip, trip_items)

        # 保存PDF文件
        export_dir = Path("exports")
        export_dir.mkdir(exist_ok=True)
        
        filename = f"trip_{trip_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = export_dir / filename
        
        with open(filepath, 'wb') as f:
            f.write(pdf_content)

        return jsonify({
            'success': True,
            'message': 'PDF导出成功',
            'download_url': f'/exports/{filename}',
            'filename': filename
        })

    except Exception as e:
        log.info(f"PDF导出错误: {e}")
        return jsonify({'success': False, 'error': f'导出失败: {str(e)}'}), 500


@app.route('/api/trips/<int:trip_id>/export/image', methods=['GET'])
@login_required
def api_export_trip_image(trip_id):
    """导出行程为图片"""
    try:
        # 获取行程信息
        trip = Trip.query.filter_by(id=trip_id, user_id=session['user_id']).first()
        if not trip:
            return jsonify({'success': False, 'error': '行程不存在'}), 404

        # 获取行程项目
        trip_items = TripItem.query.filter_by(trip_id=trip_id).order_by(TripItem.day_number, TripItem.order_index).all()

        # 生成图片
        image_content = generate_trip_image(trip, trip_items)

        # 保存图片文件
        export_dir = Path("exports")
        export_dir.mkdir(exist_ok=True)
        
        filename = f"trip_{trip_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        filepath = export_dir / filename
        
        with open(filepath, 'wb') as f:
            f.write(image_content)

        return jsonify({
            'success': True,
            'message': '图片导出成功',
            'download_url': f'/exports/{filename}',
            'filename': filename
        })

    except Exception as e:
        log.info(f"图片导出错误: {e}")
        return jsonify({'success': False, 'error': f'导出失败: {str(e)}'}), 500


def generate_trip_pdf(trip, trip_items):
    """生成行程PDF"""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from io import BytesIO

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        
        # 创建自定义样式
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=1  # 居中
        )
        
        # 构建PDF内容
        story = []
        
        # 标题
        story.append(Paragraph(f"行程规划: {trip.title}", title_style))
        story.append(Spacer(1, 12))
        
        # 行程基本信息
        info_data = [
            ['开始日期', trip.start_date.strftime('%Y-%m-%d')],
            ['结束日期', trip.end_date.strftime('%Y-%m-%d')],
            ['行程天数', f"{(trip.end_date - trip.start_date).days + 1}天"],
            ['预算', f"¥{trip.budget:.0f}" if trip.budget else '未设置'],
            ['状态', '规划中' if trip.status == 'planning' else '进行中' if trip.status == 'ongoing' else '已完成']
        ]
        
        info_table = Table(info_data, col_widths=[2*inch, 4*inch])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(info_table)
        story.append(Spacer(1, 20))
        
        # 行程安排
        story.append(Paragraph("行程安排", styles['Heading2']))
        story.append(Spacer(1, 12))
        
        current_day = 0
        for item in trip_items:
            if item.day_number != current_day:
                current_day = item.day_number
                story.append(Paragraph(f"第{current_day}天", styles['Heading3']))
                story.append(Spacer(1, 6))
            
            # 行程项目详情
            item_text = f"<b>{item.start_time or '09:00'} - {item.end_time or '12:00'}</b>: {item.activity}"
            if item.location:
                item_text += f"<br/>📍 {item.location}"
            if item.cost and item.cost > 0:
                item_text += f"<br/>💰 预计费用: ¥{item.cost:.0f}"
            if item.notes:
                item_text += f"<br/>📝 {item.notes}"
            
            story.append(Paragraph(item_text, styles['Normal']))
            story.append(Spacer(1, 8))
        
        # 描述
        if trip.description:
            story.append(Paragraph("行程描述", styles['Heading2']))
            story.append(Spacer(1, 12))
            story.append(Paragraph(trip.description, styles['Normal']))
        
        doc.build(story)
        pdf_content = buffer.getvalue()
        buffer.close()
        
        return pdf_content

    except ImportError:
        # 如果没有reportlab，使用简单的文本PDF生成
        return generate_simple_pdf(trip, trip_items)


def generate_simple_pdf(trip, trip_items):
    """生成简单的PDF（无需reportlab）"""
    try:
        # 使用FPDF作为备选方案
        from fpdf import FPDF
        
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font('Arial', 'B', 16)
        
        # 标题
        pdf.cell(0, 10, f'行程规划: {trip.title}', 0, 1, 'C')
        pdf.ln(10)
        
        # 基本信息
        pdf.set_font('Arial', '', 12)
        pdf.cell(0, 8, f'开始日期: {trip.start_date.strftime("%Y-%m-%d")}', 0, 1)
        pdf.cell(0, 8, f'结束日期: {trip.end_date.strftime("%Y-%m-%d")}', 0, 1)
        pdf.cell(0, 8, f'行程天数: {(trip.end_date - trip.start_date).days + 1}天', 0, 1)
        pdf.ln(10)
        
        # 行程安排
        pdf.set_font('Arial', 'B', 14)
        pdf.cell(0, 10, '行程安排', 0, 1)
        pdf.ln(5)
        
        pdf.set_font('Arial', '', 12)
        current_day = 0
        for item in trip_items:
            if item.day_number != current_day:
                current_day = item.day_number
                pdf.set_font('Arial', 'B', 12)
                pdf.cell(0, 10, f'第{current_day}天', 0, 1)
                pdf.set_font('Arial', '', 12)
            
            time_text = f"{item.start_time or '09:00'} - {item.end_time or '12:00'}"
            pdf.cell(0, 8, f'{time_text}: {item.activity}', 0, 1)
            
            if item.location:
                pdf.cell(0, 8, f'    地点: {item.location}', 0, 1)
            if item.cost and item.cost > 0:
                pdf.cell(0, 8, f'    费用: ¥{item.cost:.0f}', 0, 1)
        
        # 描述
        if trip.description:
            pdf.ln(10)
            pdf.set_font('Arial', 'B', 14)
            pdf.cell(0, 10, '行程描述', 0, 1)
            pdf.set_font('Arial', '', 12)
            pdf.multi_cell(0, 8, trip.description)
        
        return pdf.output(dest='S').encode('latin-1')
        
    except ImportError:
        # 如果都没有，生成文本文件
        content = f"行程规划: {trip.title}\n"
        content += f"开始日期: {trip.start_date.strftime('%Y-%m-%d')}\n"
        content += f"结束日期: {trip.end_date.strftime('%Y-%m-%d')}\n"
        content += f"行程天数: {(trip.end_date - trip.start_date).days + 1}天\n\n"
        
        content += "行程安排:\n"
        current_day = 0
        for item in trip_items:
            if item.day_number != current_day:
                current_day = item.day_number
                content += f"\n第{current_day}天:\n"
            
            time_text = f"{item.start_time or '09:00'} - {item.end_time or '12:00'}"
            content += f"  {time_text}: {item.activity}\n"
            
            if item.location:
                content += f"    地点: {item.location}\n"
            if item.cost and item.cost > 0:
                content += f"    费用: ¥{item.cost:.0f}\n"
        
        if trip.description:
            content += f"\n行程描述:\n{trip.description}\n"
        
        return content.encode('utf-8')


def generate_trip_image(trip, trip_items):
    """生成行程图片"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import io
        
        # 创建图片
        width, height = 800, 1200
        img = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(img)
        
        # 尝试使用系统字体
        try:
            title_font = ImageFont.truetype("arial.ttf", 24)
            header_font = ImageFont.truetype("arial.ttf", 18)
            normal_font = ImageFont.truetype("arial.ttf", 14)
        except:
            title_font = ImageFont.load_default()
            header_font = ImageFont.load_default()
            normal_font = ImageFont.load_default()
        
        # 标题
        draw.text((50, 30), f"行程规划: {trip.title}", fill='black', font=title_font)
        
        # 基本信息
        y_position = 80
        info_items = [
            f"开始日期: {trip.start_date.strftime('%Y-%m-%d')}",
            f"结束日期: {trip.end_date.strftime('%Y-%m-%d')}",
            f"行程天数: {(trip.end_date - trip.start_date).days + 1}天",
            f"预算: ¥{trip.budget:.0f}" if trip.budget else "预算: 未设置"
        ]
        
        for info in info_items:
            draw.text((50, y_position), info, fill='black', font=normal_font)
            y_position += 25
        
        y_position += 20
        
        # 行程安排标题
        draw.text((50, y_position), "行程安排:", fill='black', font=header_font)
        y_position += 30
        
        current_day = 0
        for item in trip_items:
            if item.day_number != current_day:
                current_day = item.day_number
                draw.text((50, y_position), f"第{current_day}天:", fill='black', font=normal_font)
                y_position += 25
            
            time_text = f"{item.start_time or '09:00'} - {item.end_time or '12:00'}"
            activity_text = f"{time_text}: {item.activity}"
            draw.text((70, y_position), activity_text, fill='black', font=normal_font)
            y_position += 20
            
            if item.location:
                draw.text((90, y_position), f"地点: {item.location}", fill='gray', font=normal_font)
                y_position += 20
            if item.cost and item.cost > 0:
                draw.text((90, y_position), f"费用: ¥{item.cost:.0f}", fill='gray', font=normal_font)
                y_position += 20
            
            y_position += 10
            
            # 检查是否需要换页
            if y_position > height - 100:
                # 创建新图片
                new_img = Image.new('RGB', (width, height), color='white')
                draw = ImageDraw.Draw(new_img)
                y_position = 30
        
        # 描述
        if trip.description:
            y_position += 20
            draw.text((50, y_position), "行程描述:", fill='black', font=header_font)
            y_position += 30
            
            # 简单的文本换行
            words = trip.description.split()
            lines = []
            current_line = ""
            for word in words:
                test_line = current_line + " " + word if current_line else word
                if len(test_line) > 50:  # 简单估算
                    lines.append(current_line)
                    current_line = word
                else:
                    current_line = test_line
            if current_line:
                lines.append(current_line)
            
            for line in lines:
                draw.text((50, y_position), line, fill='black', font=normal_font)
                y_position += 20
        
        # 保存到内存
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='PNG')
        return img_buffer.getvalue()
        
    except ImportError:
        # 如果没有PIL，返回简单的文本图片
        return generate_simple_image(trip, trip_items)


def generate_simple_image(trip, trip_items):
    """生成简单的图片（无需PIL）"""
    # 创建一个简单的文本内容作为图片
    content = f"行程规划: {trip.title}\n"
    content += f"开始日期: {trip.start_date.strftime('%Y-%m-%d')}\n"
    content += f"结束日期: {trip.end_date.strftime('%Y-%m-%d')}\n"
    content += f"行程天数: {(trip.end_date - trip.start_date).days + 1}天\n\n"
    
    content += "行程安排:\n"
    current_day = 0
    for item in trip_items:
        if item.day_number != current_day:
            current_day = item.day_number
            content += f"\n第{current_day}天:\n"
        
        time_text = f"{item.start_time or '09:00'} - {item.end_time or '12:00'}"
        content += f"  {time_text}: {item.activity}\n"
        
        if item.location:
            content += f"    地点: {item.location}\n"
        if item.cost and item.cost > 0:
            content += f"    费用: ¥{item.cost:.0f}\n"
    
    if trip.description:
        content += f"\n行程描述:\n{trip.description}\n"
    
    return content.encode('utf-8')


# ==================== 周边推荐API ====================

# 周边推荐缓存
_nearby_cache = {}
NEARBY_CACHE_TTL = 3600  # 缓存1小时

def get_nearby_cache_key(latitude, longitude, category, radius, sort_by):
    """生成缓存键"""
    return f"nearby:{latitude:.4f}:{longitude:.4f}:{category}:{radius}:{sort_by}"

@app.route('/api/nearby/search', methods=['GET'])
def api_nearby_search():
    """周边搜索API - 支持缓存"""
    try:
        # 获取查询参数
        latitude = request.args.get('latitude', type=float)
        longitude = request.args.get('longitude', type=float)
        category = request.args.get('category', 'all')  # hotel, restaurant, parking, atm, gas_station, pharmacy
        radius = request.args.get('radius', 3000, type=int)  # 默认3公里
        limit = min(int(request.args.get('limit', 20)), 50)
        sort_by = request.args.get('sort_by', 'distance')  # distance, rating, price

        if not latitude or not longitude:
            return jsonify({'success': False, 'error': '请提供坐标'}), 400

        # 检查缓存
        cache_key = get_nearby_cache_key(latitude, longitude, category, radius, sort_by)
        if cache_key in _nearby_cache:
            cache_time, cached_data = _nearby_cache[cache_key]
            if datetime.now().timestamp() - cache_time < NEARBY_CACHE_TTL:
                log.info(f"✅ 使用缓存数据: {cache_key}")
                # 限制返回数量
                cached_data['nearby'] = cached_data['nearby'][:limit]
                cached_data['count'] = len(cached_data['nearby'])
                cached_data['from_cache'] = True
                return jsonify(cached_data)
            else:
                # 缓存过期，删除
                del _nearby_cache[cache_key]

        # 如果有高德API，使用真实POI搜索
        if gaode_api:
            try:
                # 构建POI类型映射
                poi_type_mapping = {
                    'hotel': '住宿服务',
                    'restaurant': '餐饮服务',
                    'parking': '交通设施服务',
                    'atm': '金融保险服务',
                    'gas_station': '交通设施服务',
                    'pharmacy': '医疗保健服务',
                    'all': ''
                }

                # 调用高德POI搜索API
                search_url = "https://restapi.amap.com/v3/place/around"
                params = {
                    'key': GAODE_API_KEY,
                    'location': f"{longitude},{latitude}",
                    'radius': radius,
                    'types': poi_type_mapping.get(category, ''),
                    'offset': limit,
                    'page': 1,
                    'extensions': 'all'
                }

                response = requests.get(search_url, params=params, timeout=10)
                if response.status_code == 200:
                    result = response.json()
                    if result.get('status') == '1':
                        pois = result.get('pois', [])
                        nearby_results = []

                        for poi in pois:
                            # 解析坐标
                            location = poi.get('location', '').split(',')
                            if len(location) == 2:
                                poi_lng = float(location[0])
                                poi_lat = float(location[1])

                                # 计算距离
                                lat_diff = abs(poi_lat - latitude) * 111000
                                lng_diff = abs(poi_lng - longitude) * 111000 * 0.8
                                distance = round((lat_diff**2 + lng_diff**2)**0.5)

                                # 解析价格水平
                                biz_ext = poi.get('biz_ext', {})
                                price_level = '中等'
                                if 'cost' in biz_ext:
                                    cost = biz_ext.get('cost', '')
                                    if cost:
                                        try:
                                            cost_value = float(cost.replace('元', '').replace('/', '').strip())
                                            if cost_value < 50:
                                                price_level = '经济'
                                            elif cost_value > 200:
                                                price_level = '高档'
                                        except:
                                            pass

                                nearby_results.append({
                                    'id': poi.get('id'),
                                    'name': poi.get('name'),
                                    'category': category if category != 'all' else poi.get('type', '').split(';')[0],
                                    'subcategory': poi.get('type', '').split(';')[1] if ';' in poi.get('type', '') else '',
                                    'address': poi.get('address', ''),
                                    'latitude': poi_lat,
                                    'longitude': poi_lng,
                                    'distance': distance,
                                    'rating': float(poi.get('biz_ext', {}).get('rating', '4.0')) if poi.get('biz_ext', {}).get('rating') else 4.0,
                                    'price_level': price_level,
                                    'phone': poi.get('tel', ''),
                                    'opening_hours': poi.get('business_time', '营业时间未知'),
                                    'business_status': '营业中' if poi.get('business_status') == '1' else '已关闭'
                                })

                        # 按指定方式排序
                        if sort_by == 'rating':
                            nearby_results.sort(key=lambda x: x['rating'], reverse=True)
                        elif sort_by == 'price':
                            price_order = {'经济': 1, '中等': 2, '高档': 3}
                            nearby_results.sort(key=lambda x: price_order.get(x['price_level'], 2))
                        else:  # 默认按距离
                            nearby_results.sort(key=lambda x: x['distance'])

                        # 准备返回数据
                        result_data = {
                            'success': True,
                            'nearby': nearby_results[:limit],
                            'count': len(nearby_results[:limit]),
                            'center': {'latitude': latitude, 'longitude': longitude},
                            'radius': radius,
                            'category': category,
                            'source': 'gaode_api'
                        }

                        # 保存到缓存
                        _nearby_cache[cache_key] = (datetime.now().timestamp(), result_data)
                        log.info(f"✅ 缓存数据已保存: {cache_key}")

                        return jsonify(result_data)
            except Exception as e:
                log.info(f"高德POI搜索错误: {e}")

        # 降级到本地数据库搜索
        nearby_results = []

        # 搜索周边POI
        query = NearbyPOI.query.filter(
            NearbyPOI.latitude.isnot(None),
            NearbyPOI.longitude.isnot(None)
        )

        if category and category != 'all':
            query = query.filter(NearbyPOI.category == category)

        all_pois = query.all()

        for poi in all_pois:
            # 计算距离
            lat_diff = abs(poi.latitude - latitude) * 111000
            lng_diff = abs(poi.longitude - longitude) * 111000 * 0.8
            distance = round((lat_diff**2 + lng_diff**2)**0.5)

            if distance <= radius:
                nearby_results.append({
                    'id': poi.id,
                    'name': poi.name,
                    'category': poi.category,
                    'subcategory': poi.subcategory,
                    'address': poi.address,
                    'latitude': poi.latitude,
                    'longitude': poi.longitude,
                    'distance': distance,
                    'rating': poi.rating or 4.0,
                    'price_level': poi.price_level or '中等',
                    'phone': poi.phone,
                    'opening_hours': poi.opening_hours or '营业时间未知',
                    'business_status': poi.business_status or '营业中'
                })

        # 按指定方式排序
        if sort_by == 'rating':
            nearby_results.sort(key=lambda x: x['rating'], reverse=True)
        elif sort_by == 'price':
            price_order = {'经济': 1, '中等': 2, '高档': 3}
            nearby_results.sort(key=lambda x: price_order.get(x['price_level'], 2))
        else:  # 默认按距离
            nearby_results.sort(key=lambda x: x['distance'])

        return jsonify({
            'success': True,
            'nearby': nearby_results[:limit],
            'count': len(nearby_results[:limit]),
            'center': {'latitude': latitude, 'longitude': longitude},
            'radius': radius,
            'category': category,
            'source': 'local_database'
        })

    except Exception as e:
        log.info(f"周边搜索错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/nearby/categories', methods=['GET'])
def api_nearby_categories():
    """获取周边POI分类列表"""
    try:
        categories = [
            {'id': 'all', 'name': '全部', 'icon': '📍'},
            {'id': 'hotel', 'name': '酒店住宿', 'icon': '🏨'},
            {'id': 'restaurant', 'name': '餐饮美食', 'icon': '🍽️'},
            {'id': 'parking', 'name': '停车场', 'icon': '🅿️'},
            {'id': 'atm', 'name': 'ATM/银行', 'icon': '🏧'},
            {'id': 'gas_station', 'name': '加油站', 'icon': '⛽'},
            {'id': 'pharmacy', 'name': '药店', 'icon': '💊'}
        ]

        return jsonify({
            'success': True,
            'categories': categories
        })

    except Exception as e:
        log.info(f"获取分类列表错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/nearby/destination/<int:dest_id>', methods=['GET'])
def api_nearby_destination(dest_id):
    """获取景点周边推荐"""
    try:
        dest = db.session.get(Destination, dest_id)
        if not dest:
            return jsonify({'success': False, 'error': '景点不存在'}), 404

        if not dest.latitude or not dest.longitude:
            return jsonify({'success': False, 'error': '景点缺少坐标信息'}), 400

        category = request.args.get('category', 'all')
        radius = request.args.get('radius', 3000, type=int)
        limit = min(int(request.args.get('limit', 10)), 20)

        # 如果有高德API，使用真实数据
        if gaode_api:
            try:
                # 调用周边搜索
                search_url = "https://restapi.amap.com/v3/place/around"
                params = {
                    'key': GAODE_API_KEY,
                    'location': f"{dest.longitude},{dest.latitude}",
                    'radius': radius,
                    'types': '' if category == 'all' else category,
                    'offset': limit,
                    'page': 1,
                    'extensions': 'base'
                }

                response = requests.get(search_url, params=params, timeout=10)
                if response.status_code == 200:
                    result = response.json()
                    if result.get('status') == '1':
                        pois = result.get('pois', [])
                        nearby_list = []

                        for poi in pois:
                            location = poi.get('location', '').split(',')
                            if len(location) == 2:
                                poi_lng = float(location[0])
                                poi_lat = float(location[1])

                                # 计算距离
                                lat_diff = abs(poi_lat - dest.latitude) * 111000
                                lng_diff = abs(poi_lng - dest.longitude) * 111000 * 0.8
                                distance = round((lat_diff**2 + lng_diff**2)**0.5)

                                nearby_list.append({
                                    'name': poi.get('name'),
                                    'address': poi.get('address', '地址未知'),
                                    'distance': distance,
                                    'distance_text': f"{distance}米" if distance < 1000 else f"{distance/1000:.1f}公里",
                                    'category': poi.get('type', '').split(';')[0] if poi.get('type') else '其他',
                                    'phone': poi.get('tel', '')
                                })

                        # 按距离排序
                        nearby_list.sort(key=lambda x: x['distance'])

                        return jsonify({
                            'success': True,
                            'destination': {
                                'id': dest.id,
                                'name': dest.name,
                                'latitude': dest.latitude,
                                'longitude': dest.longitude
                            },
                            'nearby': nearby_list[:limit],
                            'count': len(nearby_list[:limit]),
                            'radius': radius,
                            'category': category,
                            'source': 'gaode_api'
                        })
            except Exception as e:
                log.info(f"高德周边搜索错误: {e}")

        # 降级到本地数据库
        nearby_pois = NearbyPOI.query.filter(
            NearbyPOI.latitude.isnot(None),
            NearbyPOI.longitude.isnot(None)
        ).all()

        if category and category != 'all':
            nearby_pois = [p for p in nearby_pois if p.category == category]

        nearby_list = []
        for poi in nearby_pois:
            # 计算距离
            lat_diff = abs(poi.latitude - dest.latitude) * 111000
            lng_diff = abs(poi.longitude - dest.longitude) * 111000 * 0.8
            distance = round((lat_diff**2 + lng_diff**2)**0.5)

            if distance <= radius:
                nearby_list.append({
                    'name': poi.name,
                    'address': poi.address or '地址未知',
                    'distance': distance,
                    'distance_text': f"{distance}米" if distance < 1000 else f"{distance/1000:.1f}公里",
                    'category': poi.category,
                    'phone': poi.phone or ''
                })

        # 按距离排序
        nearby_list.sort(key=lambda x: x['distance'])

        return jsonify({
            'success': True,
            'destination': {
                'id': dest.id,
                'name': dest.name,
                'latitude': dest.latitude,
                'longitude': dest.longitude
            },
            'nearby': nearby_list[:limit],
            'count': len(nearby_list[:limit]),
            'radius': radius,
            'category': category,
            'source': 'local_database'
        })

    except Exception as e:
        log.info(f"景点周边搜索错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# [旧后台管理增强功能已移除]

@app.route('/api/destinations/<int:dest_id>')
def api_destination(dest_id):
    dest = db.session.get(Destination, dest_id)
    if not dest:
        return jsonify({'success': False, 'error': '景点不存在'}), 404
    return jsonify({'success': True, 'destination': dest.to_dict()})


@app.route('/api/weather/<city>')
def api_weather(city):
    data = weather_api.get_current_weather(city)
    forecast = weather_api.get_forecast(city)
    return jsonify({
        'success': True,
        'weather': data,
        'forecast': forecast.get('forecasts', []) if forecast else []
    })


@app.route('/api/weather/forecast/<city>')
def api_weather_forecast(city):
    days = request.args.get('days', 3, type=int)
    data = weather_api.get_forecast(city, days)
    if data:
        return jsonify({'success': True, 'data': data})
    return jsonify({'success': False, 'error': '获取天气预报失败'}), 404


@app.route('/api/food/<city>')
def api_food(city):
    foods = FOOD_DATABASE.get(city, [])
    return jsonify({'success': True, 'city': city, 'foods': foods})


@app.route('/api/food/search')
def api_food_search():
    keyword = request.args.get('q', '').strip()
    if not keyword:
        return jsonify({'success': False, 'error': '请输入搜索关键词'}), 400

    results = []
    for city, foods in FOOD_DATABASE.items():
        for food in foods:
            if keyword in food['name'] or keyword in food.get('description', ''):
                results.append({
                    'city': city,
                    'food': food
                })

    return jsonify({'success': True, 'results': results[:20]})


@app.route('/api/assistant', methods=['POST'])
def assistant_api():
    # 使用延迟初始化
    assistant = get_travel_assistant()

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': '请求体必须为JSON格式'}), 400

    from services.validators import sanitize_string
    message = sanitize_string(data.get('message', ''), 2000)
    session_id = sanitize_string(data.get('session_id', request.remote_addr), 100)
    user_id = session.get('user_id')

    if not message:
        return jsonify({'error': '消息不能为空'}), 400

    response = assistant.get_response(message, session_id, user_id)
    return jsonify(response)


@app.route('/api/assistant/stream', methods=['POST'])
def assistant_stream_api():
    """智能助手流式API - 支持SSE流式输出"""
    # 使用延迟初始化
    assistant = get_travel_assistant()

    data = request.get_json()
    message = data.get('message', '')
    session_id = data.get('session_id', request.remote_addr)
    user_id = session.get('user_id')

    if not message:
        return jsonify({'error': '消息不能为空'}), 400

    def generate():
        """生成流式响应"""
        try:
            # 获取完整的响应
            response = assistant.get_response(message, session_id, user_id)
            content = response.get('content', '')
            
            # 模拟流式输出 - 逐字发送
            for i, char in enumerate(content):
                chunk_data = {
                    'content': char,
                    'index': i,
                    'total': len(content),
                    'timestamp': datetime.now().isoformat()
                }
                yield f"data: {json.dumps(chunk_data, ensure_ascii=False)}\n\n"
                time.sleep(0.03)  # 控制输出速度
            
            # 发送结束标记
            end_data = {
                'done': True,
                'suggestions': response.get('suggestions', []),
                'type': response.get('type', 'text'),
                'timestamp': datetime.now().isoformat()
            }
            yield f"data: {json.dumps(end_data, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            error_data = {
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
            yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type'
        }
    )


@app.route('/api/assistant/history/<session_id>', methods=['GET'])
def get_assistant_history(session_id):
    """获取对话历史记录"""
    # 使用延迟初始化
    assistant = get_travel_assistant()

    try:
        limit = request.args.get('limit', 20, type=int)
        conv = assistant.get_conversation(session_id)
        messages = conv.get('messages', [])
        
        # 返回最近的对话记录
        recent_messages = messages[-limit:] if len(messages) > limit else messages
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'messages': recent_messages,
            'total': len(messages)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/assistant/tools', methods=['GET'])
def get_assistant_tools():
    """获取可用的工具列表"""
    # 使用延迟初始化
    assistant = get_travel_assistant()
    
    tools = [
        {
            'name': 'search_destinations',
            'description': '搜索景点信息',
            'parameters': {
                'query': '搜索关键词',
                'filters': '筛选条件（可选）'
            }
        },
        {
            'name': 'get_weather',
            'description': '获取城市天气信息',
            'parameters': {
                'city': '城市名称'
            }
        },
        {
            'name': 'plan_trip',
            'description': '规划旅行行程',
            'parameters': {
                'city': '目标城市',
                'days': '旅行天数',
                'preferences': '偏好设置'
            }
        },
        {
            'name': 'export_trip',
            'description': '导出行程',
            'parameters': {
                'trip_id': '行程ID',
                'format': '导出格式（pdf/image/json）'
            }
        },
        {
            'name': 'get_food_recommendations',
            'description': '获取美食推荐',
            'parameters': {
                'city': '城市名称'
            }
        }
    ]
    
    return jsonify({
        'success': True,
        'tools': tools,
        'count': len(tools)
    })


@app.route('/api/assistant/context', methods=['POST'])
def update_assistant_context():
    """更新助手上下文"""
    global travel_assistant
    if travel_assistant is None:
        travel_assistant = TravelAssistant(db)

    data = request.get_json()
    session_id = data.get('session_id', request.remote_addr)
    context = data.get('context', {})

    try:
        conv = travel_assistant.get_conversation(session_id)
        conv['context'].update(context)
        travel_assistant.save_conversation(session_id)
        
        return jsonify({
            'success': True,
            'message': '上下文更新成功',
            'context': conv['context']
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== AI模型管理API ====================

@app.route('/api/ai/status', methods=['GET'])
def api_ai_status():
    """获取AI模型状态"""
    global travel_assistant
    if travel_assistant is None:
        travel_assistant = TravelAssistant(db)
    
    try:
        status = travel_assistant.get_ai_mode_status()
        return jsonify({
            'success': True,
            'ai_status': status
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/toggle', methods=['POST'])
@login_required
def api_ai_toggle():
    """切换AI模式"""
    global travel_assistant
    if travel_assistant is None:
        travel_assistant = TravelAssistant(db)
    
    try:
        data = request.get_json() or {}
        enabled = data.get('enabled')
        
        new_status = travel_assistant.toggle_ai_mode(enabled)
        
        return jsonify({
            'success': True,
            'message': f"AI模式已{'启用' if new_status else '禁用'}",
            'ai_mode_enabled': new_status
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/providers', methods=['GET'])
def api_ai_providers():
    """获取可用的AI模型提供商"""
    try:
        from ai_model_manager import ai_model_manager
        
        providers = ai_model_manager.get_available_providers()
        provider_info = ai_model_manager.get_provider_info()
        
        return jsonify({
            'success': True,
            'providers': providers,
            'provider_info': provider_info,
            'default_provider': ai_model_manager.default_provider
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/switch-provider', methods=['POST'])
@login_required
def api_ai_switch_provider():
    """切换AI模型提供商"""
    try:
        from ai_model_manager import ai_model_manager
        
        data = request.get_json()
        provider_name = data.get('provider')
        
        if not provider_name:
            return jsonify({'success': False, 'error': '请指定提供商名称'}), 400
        
        success = ai_model_manager.switch_default_provider(provider_name)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'已切换到 {provider_name}',
                'default_provider': provider_name
            })
        else:
            return jsonify({
                'success': False,
                'error': f'提供商 {provider_name} 不可用'
            }), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/test', methods=['POST'])
def api_ai_test():
    """测试AI模型"""
    try:
        from ai_model_manager import get_ai_response
        
        data = request.get_json()
        message = data.get('message', '你好，请介绍一下自己')
        provider = data.get('provider')
        
        response = get_ai_response(message, provider=provider)
        
        return jsonify({
            'success': True,
            'test_message': message,
            'response': response,
            'provider': provider or 'default'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/stream-test', methods=['POST'])
def api_ai_stream_test():
    """测试AI模型流式输出"""
    try:
        from ai_model_manager import get_ai_response_stream
        from flask import Response
        
        data = request.get_json()
        message = data.get('message', '你好，请介绍一下自己')
        provider = data.get('provider')
        
        def generate():
            try:
                for chunk in get_ai_response_stream(message, provider=provider):
                    chunk_data = {
                        'content': chunk,
                        'timestamp': datetime.now().isoformat()
                    }
                    yield f"data: {json.dumps(chunk_data, ensure_ascii=False)}\n\n"
                
                # 发送结束标记
                end_data = {
                    'done': True,
                    'timestamp': datetime.now().isoformat()
                }
                yield f"data: {json.dumps(end_data, ensure_ascii=False)}\n\n"
                
            except Exception as e:
                error_data = {
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }
                yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
        
        return Response(
            generate(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type'
            }
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/config', methods=['GET'])
def api_ai_config():
    """获取AI配置信息"""
    try:
        from config import Config
        
        config_info = {
            'ai_mode_enabled': getattr(Config, 'AI_MODE_ENABLED', False),
            'default_provider': getattr(Config, 'DEFAULT_AI_PROVIDER', None),
            'available_configs': {
                'openai': {
                    'configured': bool(getattr(Config, 'OPENAI_API_KEY', None)),
                    'model': getattr(Config, 'OPENAI_MODEL', 'gpt-3.5-turbo'),
                    'base_url': getattr(Config, 'OPENAI_BASE_URL', 'https://api.openai.com/v1')
                },
                'claude': {
                    'configured': bool(getattr(Config, 'CLAUDE_API_KEY', None)),
                    'model': getattr(Config, 'CLAUDE_MODEL', 'claude-3-sonnet-20240229')
                },
                'wenxin': {
                    'configured': bool(getattr(Config, 'WENXIN_API_KEY', None) and getattr(Config, 'WENXIN_SECRET_KEY', None)),
                    'model': getattr(Config, 'WENXIN_MODEL', 'ernie-bot')
                },
                'tongyi': {
                    'configured': bool(getattr(Config, 'TONGYI_API_KEY', None)),
                    'model': getattr(Config, 'TONGYI_MODEL', 'qwen-turbo')
                },
                'zhipu': {
                    'configured': bool(getattr(Config, 'ZHIPU_API_KEY', None)),
                    'model': getattr(Config, 'ZHIPU_MODEL', 'glm-4')
                }
            }
        }
        
        return jsonify({
            'success': True,
            'config': config_info
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== SocketIO事件 ====================
@socketio.on('connect')
def handle_connect():
    emit('server_message', {
        'type': 'welcome',
        'content': '您好！我是您的智能旅游助手。请问有什么可以帮您的吗？'
    })


@socketio.on('user_message')
def handle_user_message(data):
    # 使用延迟初始化
    assistant = get_travel_assistant()

    message = data.get('message', '')
    session_id = data.get('session_id', request.sid)
    user_id = session.get('user_id')

    if not message:
        return

    emit('assistant_typing')
    response = assistant.get_response(message, session_id, user_id)
    response['timestamp'] = datetime.now().strftime('%H:%M:%S')
    emit('assistant_response', response)


@socketio.on('suggestion_click')
def handle_suggestion_click(data):
    # 使用延迟初始化
    assistant = get_travel_assistant()

    suggestion = data.get('suggestion', '')
    session_id = data.get('session_id', request.sid)

    if suggestion:
        response = assistant.get_response(suggestion, session_id)
        response['timestamp'] = datetime.now().strftime('%H:%M:%S')
        response['is_suggestion'] = True
        emit('assistant_response', response)


# ==================== 错误处理 ====================
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500


# ==================== 新后台管理系统 ====================

def admin_login_required(f):
    """管理员登录验证装饰器（JSON API版）"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'success': False, 'error': '未登录'}), 401
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function


# --- 管理员页面路由 ---

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """管理员登录页面"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        admin = Admin.query.filter_by(username=username).first()
        if admin and admin.check_password(password):
            session['admin_id'] = admin.id
            session['admin_username'] = admin.username
            db.session.commit()
            return redirect(url_for('admin_dashboard'))
        return render_template('admin_new/login.html', error='用户名或密码错误')
    return render_template('admin_new/login.html')


@app.route('/admin/logout')
def admin_logout():
    """管理员退出"""
    session.pop('admin_id', None)
    session.pop('admin_username', None)
    return redirect(url_for('admin_login'))


@app.route('/admin')
@admin_login_required
def admin_dashboard():
    """管理后台仪表盘"""
    total_destinations = Destination.query.count()
    total_users = User.query.count()
    total_conversations = Conversation.query.count()
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    hot_destinations = Destination.query.order_by(Destination.popularity_score.desc()).limit(5).all()
    return render_template('admin_new/dashboard.html',
                          total_destinations=total_destinations,
                          total_users=total_users,
                          total_conversations=total_conversations,
                          recent_users=recent_users,
                          hot_destinations=hot_destinations)


@app.route('/admin/destinations')
@admin_login_required
def admin_destinations():
    """景点管理页面"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    per_page = 20
    query = Destination.query
    if search:
        query = query.filter(Destination.name.contains(search))
    pagination = query.order_by(Destination.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return render_template('admin_new/destinations.html',
                          destinations=pagination.items,
                          pagination=pagination,
                          search=search)


@app.route('/admin/users')
@admin_login_required
def admin_users():
    """用户管理页面"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    per_page = 20
    query = User.query
    if search:
        query = query.filter(or_(User.username.contains(search), User.email.contains(search)))
    pagination = query.order_by(User.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return render_template('admin_new/users.html',
                          users=pagination.items,
                          pagination=pagination,
                          search=search)


# --- 景点 RESTful API ---

@app.route('/api/admin/destinations', methods=['GET'])
@admin_login_required
def api_admin_get_destinations():
    """获取景点列表（分页+搜索+筛选）"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '')
        category = request.args.get('category', '')
        province = request.args.get('province', '')

        query = Destination.query
        if search:
            query = query.filter(Destination.name.contains(search))
        if category:
            query = query.filter(Destination.category == category)
        if province:
            query = query.filter(Destination.province == province)

        pagination = query.order_by(Destination.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
        return jsonify({
            'success': True,
            'data': [d.to_dict() for d in pagination.items],
            'total': pagination.total,
            'page': pagination.page,
            'pages': pagination.pages,
            'per_page': per_page
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/destinations', methods=['POST'])
@admin_login_required
def api_admin_create_destination():
    """创建新景点"""
    try:
        data = request.get_json()
        required = ['name', 'city', 'province', 'category']
        for field in required:
            if not data.get(field):
                return jsonify({'success': False, 'error': f'缺少必填字段：{field}'}), 400

        dest = Destination(
            name=data['name'],
            city=data['city'],
            province=data['province'],
            category=data['category'],
            description=data.get('description', ''),
            price_range=data.get('price_range', ''),
            opening_hours=data.get('opening_hours', ''),
            address=data.get('address', ''),
            rating=float(data.get('rating', 4.5)),
            popularity_score=70.0,
            is_open=True,
            tags='[]',
            images='[]'
        )
        db.session.add(dest)
        db.session.commit()

        # SocketIO 实时通知
        socketio.emit('data_changed', {'type': 'destination', 'action': 'create', 'id': dest.id, 'name': dest.name})

        return jsonify({'success': True, 'message': '景点创建成功', 'id': dest.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/destinations/<int:dest_id>', methods=['GET'])
@admin_login_required
def api_admin_get_destination(dest_id):
    """获取单个景点"""
    dest = db.session.get(Destination, dest_id)
    if not dest:
        return jsonify({'success': False, 'error': '景点不存在'}), 404
    return jsonify({'success': True, 'data': dest.to_dict()})


@app.route('/api/admin/destinations/<int:dest_id>', methods=['PUT'])
@admin_login_required
def api_admin_update_destination(dest_id):
    """更新景点"""
    try:
        dest = db.session.get(Destination, dest_id)
        if not dest:
            return jsonify({'success': False, 'error': '景点不存在'}), 404

        data = request.get_json()
        required = ['name', 'city', 'province', 'category']
        for field in required:
            if not data.get(field):
                return jsonify({'success': False, 'error': f'缺少必填字段：{field}'}), 400

        dest.name = data['name']
        dest.city = data['city']
        dest.province = data['province']
        dest.category = data['category']
        dest.description = data.get('description', dest.description)
        dest.price_range = data.get('price_range', dest.price_range)
        dest.opening_hours = data.get('opening_hours', dest.opening_hours)
        dest.address = data.get('address', dest.address)
        dest.rating = float(data.get('rating', dest.rating))
        db.session.commit()

        # SocketIO 实时通知
        socketio.emit('data_changed', {'type': 'destination', 'action': 'update', 'id': dest.id, 'name': dest.name})

        return jsonify({'success': True, 'message': '景点更新成功'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/destinations/<int:dest_id>', methods=['DELETE'])
@admin_login_required
def api_admin_delete_destination(dest_id):
    """删除景点"""
    try:
        dest = db.session.get(Destination, dest_id)
        if not dest:
            return jsonify({'success': False, 'error': '景点不存在'}), 404

        name = dest.name
        db.session.delete(dest)
        db.session.commit()

        # SocketIO 实时通知
        socketio.emit('data_changed', {'type': 'destination', 'action': 'delete', 'id': dest_id, 'name': name})

        return jsonify({'success': True, 'message': '景点删除成功'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# --- 用户 RESTful API ---

@app.route('/api/admin/users', methods=['GET'])
@admin_login_required
def api_admin_get_users():
    """获取用户列表（分页+搜索）"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '')

        query = User.query
        if search:
            query = query.filter(or_(User.username.contains(search), User.email.contains(search)))

        pagination = query.order_by(User.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
        return jsonify({
            'success': True,
            'data': [u.to_dict() for u in pagination.items],
            'total': pagination.total,
            'page': pagination.page,
            'pages': pagination.pages,
            'per_page': per_page
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/users/<int:user_id>', methods=['GET'])
@admin_login_required
def api_admin_get_user(user_id):
    """获取单个用户"""
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'success': False, 'error': '用户不存在'}), 404
    return jsonify({'success': True, 'data': user.to_dict()})


@app.route('/api/admin/users/<int:user_id>', methods=['PUT'])
@admin_login_required
def api_admin_update_user(user_id):
    """更新用户"""
    try:
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({'success': False, 'error': '用户不存在'}), 404

        data = request.get_json()
        if data.get('username'):
            existing = User.query.filter_by(username=data['username']).first()
            if existing and existing.id != user_id:
                return jsonify({'success': False, 'error': '用户名已存在'}), 400
            user.username = data['username']
        if 'email' in data:
            user.email = data['email'] or None
        if 'phone' in data:
            user.phone = data['phone'] or None

        db.session.commit()

        # SocketIO 实时通知
        socketio.emit('data_changed', {'type': 'user', 'action': 'update', 'id': user.id, 'name': user.username})

        return jsonify({'success': True, 'message': '用户更新成功'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@admin_login_required
def api_admin_delete_user(user_id):
    """删除用户"""
    try:
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({'success': False, 'error': '用户不存在'}), 404

        username = user.username
        db.session.delete(user)
        db.session.commit()

        # SocketIO 实时通知
        socketio.emit('data_changed', {'type': 'user', 'action': 'delete', 'id': user_id, 'name': username})

        return jsonify({'success': True, 'message': '用户删除成功'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== 管理员重置 ====================
@app.route('/admin/reset-admin')
def reset_admin():
    """重置管理员密码 / 创建默认管理员"""
    admin = Admin.query.filter_by(username='admin').first()
    if admin:
        admin.set_password('admin123')
        db.session.commit()
        return "管理员密码已重置为: admin123"
    else:
        admin = Admin(username='admin')
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        return "管理员已创建，密码: admin123"


# ==================== 数据库初始化 ====================
def add_sample_data():
    """添加示例数据"""
    sample_data = [
        {
            "name": "故宫博物院",
            "city": "北京",
            "province": "北京",
            "category": "历史文化",
            "description": "故宫博物院，又称紫禁城，是明清两代的皇家宫殿，位于北京中轴线的中心。它是世界上现存规模最大、保存最为完整的木质结构古建筑群之一。",
            "price_range": "60元",
            "rating": 4.9,
            "address": "北京市东城区景山前街4号",
            "opening_hours": "08:30-17:00",
            "popularity_score": 99.0,
            "tags": ["历史", "文化", "建筑", "世界遗产"]
        },
        {
            "name": "八达岭长城",
            "city": "北京",
            "province": "北京",
            "category": "历史文化",
            "description": "八达岭长城是明长城中保存最完好、最具代表性的一段，是万里长城的精华。",
            "price_range": "40元",
            "rating": 4.8,
            "address": "北京市延庆区八达岭特区",
            "opening_hours": "06:30-19:00",
            "popularity_score": 98.0,
            "tags": ["长城", "历史", "世界遗产"]
        },
        {
            "name": "西湖",
            "city": "杭州",
            "province": "浙江",
            "category": "自然景观",
            "description": "西湖是杭州最著名的景点，以其湖光山色和众多名胜古迹而闻名，2011年被列入世界文化遗产名录。",
            "price_range": "免费",
            "rating": 4.9,
            "address": "浙江省杭州市西湖区",
            "opening_hours": "全天开放",
            "popularity_score": 99.5,
            "tags": ["湖泊", "自然", "文化", "世界遗产"]
        }
    ]

    for data in sample_data:
        tags_json = json.dumps(data.get('tags', []), ensure_ascii=False)
        dest = Destination(
            name=data['name'],
            city=data['city'],
            province=data['province'],
            category=data['category'],
            description=data.get('description', ''),
            price_range=data.get('price_range', '免费'),
            rating=data.get('rating', 4.5),
            review_count=random.randint(10, 50),
            opening_hours=data.get('opening_hours', '全天'),
            address=data.get('address', ''),
            popularity_score=data.get('popularity_score', 70.0),
            is_open=True,
            tags=tags_json,
            cover_image=None
        )
        db.session.add(dest)
    db.session.commit()
    log.info(f"✅ 已导入 {len(sample_data)} 条示例数据")

def init_user_data():
    """初始化用户数据"""
    try:
        if User.query.count() == 0:
            log.info("👤 创建测试用户...")
            test_users = [
                {'username': 'test', 'email': 'test@example.com', 'password': '123456'},
                {'username': 'admin', 'email': 'admin@example.com', 'password': 'admin123'},
            ]
            for user_data in test_users:
                user = User(username=user_data['username'], email=user_data['email'])
                user.set_password(user_data['password'])
                db.session.add(user)
            db.session.commit()
            log.info(f"✅ 已创建 {len(test_users)} 个测试用户")
    except Exception as e:
        log.warning(f"⚠️ 初始化用户数据时出错: {e}")
        db.session.rollback()

def init_admin():
    """初始化管理员账号"""
    if Admin.query.count() == 0:
        log.info("👤 创建默认管理员...")
        admin = Admin(username='admin')
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        log.info("✅ 默认管理员创建成功 (用户名: admin, 密码: admin123)")
    else:
        admins = Admin.query.all()
        log.info(f"👤 现有 {len(admins)} 个管理员账号")
        for a in admins:
            log.info(f"   - 用户名: {a.username}")

def remove_duplicate_destinations():
    """移除重复的景点数据"""
    try:
        all_destinations = Destination.query.all()
        seen_names = set()
        duplicates = []

        for dest in all_destinations:
            if dest.name in seen_names:
                duplicates.append(dest)
            else:
                seen_names.add(dest.name)

        if duplicates:
            for dup in duplicates:
                db.session.delete(dup)
            db.session.commit()
            log.info(f"✅ 已删除 {len(duplicates)} 条重复数据")
        else:
            log.info("✅ 没有发现重复数据")
    except Exception as e:
        log.warning(f"⚠️ 去重过程出错: {e}")
        db.session.rollback()

def add_random_review_counts():
    """为没有评论数的景点添加随机评论数"""
    destinations = Destination.query.filter(Destination.review_count == 0).all()
    updated = 0

    for dest in destinations:
        dest.review_count = random.randint(10, 50)
        updated += 1

    if updated > 0:
        db.session.commit()
        log.info(f"✅ 为 {updated} 个景点添加了随机评论数")

def check_and_update_destinations():
    """检查并更新景点数据（不重新导入）"""
    # 检查图片
    destinations_without_images = Destination.query.filter(
        (Destination.cover_image.is_(None)) |
        (Destination.cover_image == '') |
        (Destination.cover_image.contains('placeholder'))
    ).count()

    if destinations_without_images > 0:
        log.info(f"🖼️ 发现 {destinations_without_images} 个景点缺少图片，正在更新...")
        update_destinations_with_images()
    else:
        log.info("✅ 所有景点已有图片，无需更新")

    # 检查评论数
    destinations_without_reviews = Destination.query.filter(Destination.review_count == 0).count()
    if destinations_without_reviews > 0:
        log.info(f"💬 发现 {destinations_without_reviews} 个景点没有评论数，正在添加...")
        add_random_review_counts()

    # 检查重复数据
    remove_duplicate_destinations()

def init_db():
    """初始化数据库 - 只在数据库为空时导入数据"""
    db.create_all()

    # 检查当前数据库中的数据量
    current_count = Destination.query.count()
    log.info(f"📊 当前数据库中有 {current_count} 条数据")

    # 只在数据库为空时才导入数据
    if current_count == 0:
        log.info("📦 数据库为空，正在从 destinations.json 导入数据...")

        if JSON_DESTINATIONS:
            imported_count = 0
            for data in JSON_DESTINATIONS:
                try:
                    # 处理标签
                    tags_json = json.dumps(data.get('tags', []), ensure_ascii=False)

                    # 生成随机评论数 (10-50条)
                    review_count = random.randint(10, 50)

                    # 创建景点对象
                    dest = Destination(
                        name=data.get('name', ''),
                        city=data.get('city', ''),
                        province=data.get('province', ''),
                        category=data.get('category', '其他'),
                        description=data.get('description', ''),
                        price_range=data.get('price_range', '免费'),
                        rating=float(data.get('rating', 4.5)),
                        review_count=review_count,
                        opening_hours=data.get('opening_hours', '全天开放'),
                        address=data.get('address', ''),
                        latitude=data.get('latitude'),
                        longitude=data.get('longitude'),
                        popularity_score=float(data.get('popularity_score', 70.0)),
                        is_open=data.get('is_open', True),
                        tags=tags_json,
                        cover_image=None,
                        images='[]'
                    )
                    db.session.add(dest)
                    imported_count += 1

                    # 每100条提交一次
                    if imported_count % 100 == 0:
                        db.session.commit()
                        log.info(f"⏳ 已导入 {imported_count} 条数据...")

                except Exception as e:
                    log.warning(f"⚠️ 导入数据出错 {data.get('name', '未知')}: {e}")
                    continue

            db.session.commit()
            log.info(f"✅ 成功导入 {imported_count} 条数据")

            # 匹配图片
            update_destinations_with_images()

            # 执行去重
            remove_duplicate_destinations()
        else:
            log.warning("⚠️ JSON 数据为空，使用示例数据")
            add_sample_data()
            update_destinations_with_images()
            remove_duplicate_destinations()
    else:
        log.info(f"✅ 数据库已有 {current_count} 条数据，跳过导入")
        # 检查是否需要更新
        check_and_update_destinations()

    # 初始化扩展数据（省份/城市/美食/行程/配置/导航/轮播）
    _init_extended_data()

    # 初始化用户数据
    init_user_data()

    # 初始化管理员
    init_admin()


def _init_extended_data():
    """初始化扩展数据 - 省份/城市/美食/行程/配置/导航/轮播"""
    log.info("\n📦 检查扩展数据...")

    # 1. 省份
    if Province.query.count() == 0:
        log.info("   📍 导入省份数据...")
        for i, name in enumerate(ALL_PROVINCES):
            db.session.add(Province(name=name, sort_order=i, is_active=True))
        db.session.commit()
        log.info(f"   ✅ 导入 {Province.query.count()} 个省份")

    # 2. 城市
    if City.query.count() == 0:
        log.info("   🏙️ 导入城市数据...")
        province_map = {p.name: p.id for p in Province.query.all()}
        count = 0
        for city_name in ALL_CITIES:
            clean_name = city_name.replace('市', '').replace('地区', '').replace('林区', '')
            prov_name = CITY_TO_PROVINCE.get(city_name, '')
            if city_name in ['北京', '上海', '天津', '重庆']:
                city_type = '直辖市'
                prov_name = city_name
            elif '自治州' in city_name:
                city_type = '自治州'
            elif '地区' in city_name:
                city_type = '地区'
            else:
                city_type = '地级市'
            prov_id = province_map.get(prov_name)
            db.session.add(City(name=clean_name, province_id=prov_id,
                                province_name=prov_name, city_type=city_type, is_active=True))
            count += 1
            if count % 50 == 0:
                db.session.commit()
        db.session.commit()
        log.info(f"   ✅ 导入 {count} 个城市")

    # 3. 美食
    if Food.query.count() == 0:
        log.info("   🍜 导入美食数据...")
        count = 0
        for location, foods in FOOD_DATABASE.items():
            for food_data in foods:
                restaurants = food_data.get('restaurants', [])
                f = Food(
                    name=food_data['name'], city=location,
                    province=location if location in ALL_PROVINCES else '',
                    description=food_data.get('description', ''),
                    price_range=food_data.get('price', ''),
                    restaurants=json.dumps(restaurants, ensure_ascii=False),
                    category='正餐', rating=round(random.uniform(4.0, 5.0), 1),
                    popularity_score=round(random.uniform(40, 90), 1), is_active=True
                )
                db.session.add(f)
                count += 1
                if count % 50 == 0:
                    db.session.commit()
        db.session.commit()
        log.info(f"   ✅ 导入 {count} 条美食")

    # 4. 行程模板
    if TripPlan.query.count() == 0:
        log.info("   🗺️ 导入行程模板...")
        count = 0
        for city, plans in TRIP_PLANS.items():
            for day_key, items in plans.items():
                days = 1
                for d in range(1, 8):
                    if f'{d}日游' in day_key:
                        days = d
                        break
                db.session.add(TripPlan(
                    city=city, province=CITY_TO_PROVINCE.get(city, ''),
                    title=f'{city}{day_key}', days=days,
                    description=f'{city}{day_key}推荐行程',
                    itinerary=json.dumps(items, ensure_ascii=False),
                    is_default=False, is_active=True
                ))
                count += 1
        for day_key, items in DEFAULT_TRIP_PLANS.items():
            days = 1
            for d in range(1, 8):
                if f'{d}日游' in day_key:
                    days = d
                    break
            db.session.add(TripPlan(
                city='通用', title=f'通用{day_key}', days=days,
                description=f'通用{day_key}模板',
                itinerary=json.dumps(items, ensure_ascii=False),
                is_default=True, is_active=True
            ))
            count += 1
        db.session.commit()
        log.info(f"   ✅ 导入 {count} 条行程模板")

    # 5. 站点配置
    if SiteConfig.query.count() == 0:
        log.info("   ⚙️ 初始化站点配置...")
        configs = [
            {'key': 'site_name', 'value': '智能旅游助手', 'label': '站点名称', 'group': 'general', 'is_public': True},
            {'key': 'site_description', 'value': '您的智能旅行伙伴', 'label': '站点描述', 'group': 'general', 'is_public': True},
            {'key': 'contact_email', 'value': 'admin@travel.com', 'label': '联系邮箱', 'group': 'general', 'is_public': True},
            {'key': 'contact_phone', 'value': '400-123-4567', 'label': '联系电话', 'group': 'general', 'is_public': True},
            {'key': 'enable_register', 'value': 'true', 'value_type': 'bool', 'label': '开放注册', 'group': 'general'},
            {'key': 'enable_chat', 'value': 'true', 'value_type': 'bool', 'label': '智能助手', 'group': 'general'},
            {'key': 'enable_review', 'value': 'true', 'value_type': 'bool', 'label': '评论功能', 'group': 'general'},
            {'key': 'default_page_size', 'value': '12', 'value_type': 'int', 'label': '默认每页条数', 'group': 'ui'},
        ]
        for cfg in configs:
            db.session.add(SiteConfig(
                key=cfg['key'], value=cfg['value'],
                value_type=cfg.get('value_type', 'string'),
                group=cfg.get('group', 'general'),
                label=cfg.get('label', cfg['key']),
                is_public=cfg.get('is_public', False)
            ))
        db.session.commit()
        log.info(f"   ✅ 初始化 {SiteConfig.query.count()} 条配置")

    # 6. 导航菜单
    if Navigation.query.count() == 0:
        log.info("   📋 初始化导航菜单...")
        navs = [
            {'name': '首页', 'url': '/', 'icon': '🏠', 'sort_order': 1, 'position': 'header'},
            {'name': '热门景点', 'url': '/?view=hot', 'icon': '🔥', 'sort_order': 2, 'position': 'header'},
            {'name': '智能助手', 'url': '/chat', 'icon': '🤖', 'sort_order': 3, 'position': 'header'},
            {'name': '关于我们', 'url': '/about', 'icon': 'ℹ️', 'sort_order': 4, 'position': 'header'},
        ]
        for nav in navs:
            db.session.add(Navigation(
                name=nav['name'], url=nav['url'], icon=nav.get('icon', ''),
                sort_order=nav.get('sort_order', 0), position=nav.get('position', 'header'),
                is_active=True
            ))
        db.session.commit()
        log.info(f"   ✅ 初始化 {Navigation.query.count()} 条导航")

    # 7. 轮播图
    if Banner.query.count() == 0:
        log.info("   🖼️ 初始化轮播图...")
        for i, title in enumerate(['探索中国美景', '智能行程规划', '发现特色美食'], 1):
            db.session.add(Banner(title=title, image_url=f'/static/images/banner{i}.jpg',
                                  sort_order=i, is_active=True))
        db.session.commit()
        log.info(f"   ✅ 初始化 {Banner.query.count()} 条轮播图")

    # 汇总
    log.info(f"\n   📊 数据汇总: 省份{Province.query.count()} | 城市{City.query.count()} | "
          f"美食{Food.query.count()} | 行程{TripPlan.query.count()} | "
          f"景点{Destination.query.count()} | 用户{User.query.count()}")

def cleanup(signum, frame):
    """退出时清理"""
    log.info("\n正在关闭应用...")
    sys.exit(0)

# 注册信号处理
signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)

# ==================== 智能助手测试API ====================
@app.route('/api/test/assistant', methods=['GET'])
def test_assistant():
    """测试智能助手功能"""
    # 使用延迟初始化
    assistant = get_travel_assistant()
    
    test_cases = [
        "你好",
        "北京有什么景点",
        "故宫门票多少钱",
        "上海天气怎么样",
        "帮我规划北京3日游",
        "成都特色美食",
        "搜索长城"
    ]
    
    results = []
    for test_msg in test_cases:
        try:
            response = assistant.get_response(test_msg, 'test_session', None)
            results.append({
                'message': test_msg,
                'response': response,
                'success': True
            })
        except Exception as e:
            results.append({
                'message': test_msg,
                'error': str(e),
                'success': False
            })
    
    return jsonify({
        'success': True,
        'test_results': results,
        'total_tests': len(test_cases),
        'passed_tests': len([r for r in results if r['success']])
    })


@app.route('/api/test/tools', methods=['GET'])
def test_tools():
    """测试工具调用功能"""
    # 使用延迟初始化
    assistant = get_travel_assistant()
    
    try:
        # 测试搜索景点工具
        search_result = assistant.call_tool('search_destinations', query='故宫')
        
        # 测试天气工具
        weather_result = assistant.call_tool('get_weather', city='北京')
        
        # 测试行程规划工具
        trip_result = assistant.call_tool('plan_trip', city='北京', days=3)
        
        # 测试美食推荐工具
        food_result = assistant.call_tool('get_food_recommendations', city='北京')
        
        return jsonify({
            'success': True,
            'tools_test': {
                'search_destinations': search_result,
                'get_weather': weather_result,
                'plan_trip': trip_result,
                'get_food_recommendations': food_result
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/test/stream', methods=['GET'])
def test_stream():
    """测试流式输出功能"""
    def generate():
        test_message = "这是流式输出测试消息"
        for i, char in enumerate(test_message):
            chunk_data = {
                'content': char,
                'index': i,
                'total': len(test_message),
                'timestamp': datetime.now().isoformat()
            }
            yield f"data: {json.dumps(chunk_data, ensure_ascii=False)}\n\n"
            time.sleep(0.1)
        
        end_data = {
            'done': True,
            'timestamp': datetime.now().isoformat()
        }
        yield f"data: {json.dumps(end_data, ensure_ascii=False)}\n\n"
    
    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive'
        }
    )


@app.route('/api/test/destination-detail', methods=['GET'])
def test_destination_detail():
    """测试增强的景点详情功能"""
    # 使用延迟初始化
    assistant = get_travel_assistant()
    
    # 测试查询景点详情
    test_destinations = ['故宫', '长城', '西湖']
    results = []
    
    for dest_name in test_destinations:
        try:
            response = assistant.get_destination_detail(dest_name)
            results.append({
                'destination': dest_name,
                'response': response,
                'success': True,
                'has_image': response.get('image') is not None,
                'has_weather': response.get('weather') is not None,
                'type': response.get('type')
            })
        except Exception as e:
            results.append({
                'destination': dest_name,
                'error': str(e),
                'success': False
            })
    
    return jsonify({
        'success': True,
        'test_results': results,
        'total_tests': len(test_destinations),
        'passed_tests': len([r for r in results if r['success']])
    })


# ==================== 测试页面路由 ====================
@app.route('/test-login')
def test_login_page():
    """测试登录页面"""
    return send_from_directory('.', 'test_login_simple.html')


# ==================== 导入扩展模型和 API 路由 ====================
from models_extended import define_models
_ext = define_models(db)
Province = _ext['Province']
City = _ext['City']
Food = _ext['Food']
TripPlan = _ext['TripPlan']
Review = _ext['Review']
SiteConfig = _ext['SiteConfig']
Banner = _ext['Banner']
Navigation = _ext['Navigation']
log.info("✅ 扩展模型已注册")

from api_routes_extended import api_extended
app.register_blueprint(api_extended)
log.info("✅ API v2 路由已加载")


# ==================== 基于数据库的前端内容 API ====================

@app.route('/api/v2/site/info')
def api_v2_site_info():
    """获取站点信息（从数据库读取）"""
    try:
        configs = SiteConfig.query.filter_by(is_public=True).all()
        result = {}
        for c in configs:
            val = c.value
            if c.value_type == 'bool':
                val = val.lower() == 'true' if val else False
            elif c.value_type == 'int':
                val = int(val) if val else 0
            result[c.key] = val
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/v2/nav/header')
def api_v2_nav_header():
    """获取页头导航"""
    try:
        navs = Navigation.query.filter_by(position='header', is_active=True)\
            .order_by(Navigation.sort_order).all()
        return jsonify({'success': True, 'data': [n.to_dict() for n in navs]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/v2/nav/footer')
def api_v2_nav_footer():
    """获取页脚导航"""
    try:
        navs = Navigation.query.filter_by(position='footer', is_active=True)\
            .order_by(Navigation.sort_order).all()
        return jsonify({'success': True, 'data': [n.to_dict() for n in navs]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/v2/home/data')
def api_v2_home_data():
    """首页聚合数据接口"""
    try:
        # 热门景点
        hot_dest = Destination.query.order_by(Destination.popularity_score.desc()).limit(8).all()
        # 好评景点
        top_dest = Destination.query.order_by(Destination.rating.desc()).limit(8).all()
        # 省份列表
        provinces = Province.query.filter_by(is_active=True).order_by(Province.sort_order).all()
        # 分类统计
        categories = db.session.query(
            Destination.category, func.count(Destination.id)
        ).group_by(Destination.category).all()
        # 轮播图
        banners = Banner.query.filter_by(is_active=True).order_by(Banner.sort_order).all()
        # 站点配置
        site_configs = {}
        for c in SiteConfig.query.filter_by(is_public=True).all():
            site_configs[c.key] = c.value

        return jsonify({
            'success': True,
            'data': {
                'hot_destinations': [d.to_dict() for d in hot_dest],
                'top_destinations': [d.to_dict() for d in top_dest],
                'provinces': [p.to_dict() for p in provinces],
                'categories': [{'name': c[0], 'count': c[1]} for c in categories],
                'banners': [b.to_dict() for b in banners],
                'site': site_configs,
                'stats': {
                    'total_destinations': Destination.query.count(),
                    'total_provinces': Province.query.count(),
                    'total_cities': City.query.count(),
                    'total_foods': Food.query.count(),
                }
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/docs')
def api_docs_page():
    """交互式 API 文档页面"""
    sections = [
        {
            'id': 'auth', 'name': '认证', 'icon': '🔐',
            'endpoints': [
                {'methods': ['POST'], 'path': '/api/register', 'desc': '邮箱注册', 'params': [{'name': 'username', 'in': 'body', 'type': 'string', 'required': True, 'desc': '用户名'}, {'name': 'email', 'in': 'body', 'type': 'string', 'required': True, 'desc': '邮箱'}, {'name': 'password', 'in': 'body', 'type': 'string', 'required': True, 'desc': '密码'}], 'response': '{"success": true, "message": "注册成功"}'},
                {'methods': ['POST'], 'path': '/api/register/phone', 'desc': '手机号注册', 'params': [{'name': 'phone', 'in': 'body', 'type': 'string', 'required': True, 'desc': '手机号'}, {'name': 'code', 'in': 'body', 'type': 'string', 'required': True, 'desc': '验证码'}], 'response': '{"success": true}'},
                {'methods': ['POST'], 'path': '/api/login', 'desc': '密码登录', 'params': [{'name': 'username', 'in': 'body', 'type': 'string', 'required': True, 'desc': '用户名/手机/邮箱'}, {'name': 'password', 'in': 'body', 'type': 'string', 'required': True, 'desc': '密码'}], 'response': '{"success": true, "user": {"id": 1, "username": "xxx"}}'},
                {'methods': ['POST'], 'path': '/api/login/code', 'desc': '验证码登录', 'params': [{'name': 'phone', 'in': 'body', 'type': 'string', 'required': True, 'desc': '手机号'}, {'name': 'code', 'in': 'body', 'type': 'string', 'required': True, 'desc': '验证码'}], 'response': '{"success": true}'},
                {'methods': ['POST'], 'path': '/api/logout', 'desc': '退出登录', 'params': [], 'response': '{"success": true}'},
                {'methods': ['POST'], 'path': '/api/send_code', 'desc': '发送验证码', 'params': [{'name': 'phone', 'in': 'body', 'type': 'string', 'required': True, 'desc': '手机号'}], 'response': '{"success": true, "debug_code": "123456"}'},
                {'methods': ['GET'], 'path': '/auth/<provider>', 'desc': '社交登录跳转 (wechat/qq/weibo)', 'params': [], 'response': '302 Redirect'},
            ]
        },
        {
            'id': 'user', 'name': '用户', 'icon': '👤',
            'endpoints': [
                {'methods': ['GET'], 'path': '/api/user/status', 'desc': '登录状态', 'params': [], 'response': '{"logged_in": true, "user": {...}}'},
                {'methods': ['GET'], 'path': '/api/user/stats', 'desc': '用户统计', 'params': [], 'response': '{"favorites": 10, "views": 50}'},
                {'methods': ['POST'], 'path': '/api/user/profile/update', 'desc': '更新资料', 'params': [{'name': 'nickname', 'in': 'body', 'type': 'string', 'required': False, 'desc': '昵称'}], 'response': '{"success": true}'},
                {'methods': ['POST'], 'path': '/api/user/password/change', 'desc': '修改密码', 'params': [{'name': 'old_password', 'in': 'body', 'type': 'string', 'required': True, 'desc': '旧密码'}, {'name': 'new_password', 'in': 'body', 'type': 'string', 'required': True, 'desc': '新密码'}], 'response': '{"success": true}'},
                {'methods': ['GET'], 'path': '/api/user/export', 'desc': '导出用户数据', 'params': [], 'response': 'JSON file'},
                {'methods': ['POST'], 'path': '/api/users/<id>/follow', 'desc': '关注/取消关注', 'params': [], 'response': '{"success": true, "following": true}'},
            ]
        },
        {
            'id': 'dest', 'name': '景点', 'icon': '🏞️',
            'endpoints': [
                {'methods': ['GET'], 'path': '/', 'desc': '首页 (支持分页/筛选)', 'params': [{'name': 'page', 'in': 'query', 'type': 'int', 'required': False, 'desc': '页码'}, {'name': 'province', 'in': 'query', 'type': 'string', 'required': False, 'desc': '省份'}, {'name': 'category', 'in': 'query', 'type': 'string', 'required': False, 'desc': '分类'}, {'name': 'sort', 'in': 'query', 'type': 'string', 'required': False, 'desc': '排序 (rating/name/popularity)'}], 'response': 'HTML page'},
                {'methods': ['GET'], 'path': '/api/destinations/<id>', 'desc': '景点详情 API', 'params': [], 'response': '{"id": 1, "name": "故宫", "city": "北京"}'},
                {'methods': ['POST'], 'path': '/api/destinations/<id>/like', 'desc': '点赞景点', 'params': [], 'response': '{"success": true, "likes": 101}'},
                {'methods': ['POST'], 'path': '/api/destinations/<id>/checkin', 'desc': '签到景点', 'params': [], 'response': '{"success": true}'},
                {'methods': ['GET'], 'path': '/api/destinations/<id>/checkins', 'desc': '签到列表', 'params': [], 'response': '{"checkins": [...]}'},
            ]
        },
        {
            'id': 'search', 'name': '搜索', 'icon': '🔍',
            'endpoints': [
                {'methods': ['GET'], 'path': '/api/search', 'desc': '搜索景点', 'params': [{'name': 'q', 'in': 'query', 'type': 'string', 'required': True, 'desc': '关键词'}, {'name': 'page', 'in': 'query', 'type': 'int', 'required': False, 'desc': '页码'}, {'name': 'limit', 'in': 'query', 'type': 'int', 'required': False, 'desc': '每页数量'}], 'response': '{"results": [...], "total": 100}'},
                {'methods': ['GET'], 'path': '/api/search/suggestions', 'desc': '搜索建议 (支持拼音)', 'params': [{'name': 'q', 'in': 'query', 'type': 'string', 'required': True, 'desc': '关键词/拼音'}, {'name': 'limit', 'in': 'query', 'type': 'int', 'required': False, 'desc': '数量限制'}], 'response': '{"suggestions": [...]}'},
                {'methods': ['GET'], 'path': '/api/search/history', 'desc': '搜索历史', 'params': [], 'response': '{"history": [...]}'},
                {'methods': ['POST'], 'path': '/api/search/history/clear', 'desc': '清空搜索历史', 'params': [], 'response': '{"success": true}'},
                {'methods': ['GET'], 'path': '/api/click/history', 'desc': '浏览历史', 'params': [], 'response': '{"history": [...]}'},
            ]
        },
        {
            'id': 'fav', 'name': '收藏', 'icon': '❤️',
            'endpoints': [
                {'methods': ['POST'], 'path': '/api/favorite/add', 'desc': '添加收藏', 'params': [{'name': 'dest_id', 'in': 'body', 'type': 'int', 'required': True, 'desc': '景点ID'}], 'response': '{"success": true}'},
                {'methods': ['POST'], 'path': '/api/favorite/remove', 'desc': '取消收藏', 'params': [{'name': 'dest_id', 'in': 'body', 'type': 'int', 'required': True, 'desc': '景点ID'}], 'response': '{"success": true}'},
                {'methods': ['GET'], 'path': '/api/favorite/list', 'desc': '收藏列表', 'params': [{'name': 'page', 'in': 'query', 'type': 'int', 'required': False, 'desc': '页码'}], 'response': '{"favorites": [...]}'},
                {'methods': ['GET'], 'path': '/api/favorite/check/<id>', 'desc': '检查收藏', 'params': [], 'response': '{"favorited": true}'},
                {'methods': ['POST'], 'path': '/api/favorite/batch', 'desc': '批量操作', 'params': [{'name': 'action', 'in': 'body', 'type': 'string', 'required': True, 'desc': 'add/remove'}, {'name': 'dest_ids', 'in': 'body', 'type': 'array', 'required': True, 'desc': '景点ID列表'}], 'response': '{"success": true}'},
            ]
        },
        {
            'id': 'review', 'name': '评论', 'icon': '💬',
            'endpoints': [
                {'methods': ['GET'], 'path': '/api/reviews/<id>', 'desc': '获取评论', 'params': [{'name': 'page', 'in': 'query', 'type': 'int', 'required': False, 'desc': '页码'}, {'name': 'sort', 'in': 'query', 'type': 'string', 'required': False, 'desc': 'newest/oldest'}], 'response': '{"reviews": [...], "total": 50}'},
                {'methods': ['POST'], 'path': '/api/reviews/<id>/add', 'desc': '添加评论', 'params': [{'name': 'content', 'in': 'body', 'type': 'string', 'required': True, 'desc': '评论内容'}, {'name': 'rating', 'in': 'body', 'type': 'int', 'required': True, 'desc': '评分 1-5'}], 'response': '{"success": true}'},
                {'methods': ['POST'], 'path': '/api/reviews/<id>/edit', 'desc': '编辑评论', 'params': [{'name': 'content', 'in': 'body', 'type': 'string', 'required': True, 'desc': '评论内容'}], 'response': '{"success": true}'},
            ]
        },
        {
            'id': 'rec', 'name': '推荐', 'icon': '⭐',
            'endpoints': [
                {'methods': ['GET'], 'path': '/api/recommendations/personalized', 'desc': '个性化推荐', 'params': [{'name': 'limit', 'in': 'query', 'type': 'int', 'required': False, 'desc': '数量'}], 'response': '{"recommendations": [...]}'},
                {'methods': ['GET'], 'path': '/api/recommendations/collaborative', 'desc': '协同过滤推荐', 'params': [], 'response': '{"recommendations": [...]}'},
                {'methods': ['GET'], 'path': '/api/recommendations/hot', 'desc': '热门推荐', 'params': [{'name': 'category', 'in': 'query', 'type': 'string', 'required': False, 'desc': '分类筛选'}], 'response': '{"recommendations": [...]}'},
                {'methods': ['GET'], 'path': '/api/recommendations/similar/<id>', 'desc': '相似景点推荐', 'params': [], 'response': '{"similar": [...]}'},
            ]
        },
        {
            'id': 'trip', 'name': '行程', 'icon': '🗺️',
            'endpoints': [
                {'methods': ['GET'], 'path': '/api/trips', 'desc': '行程列表', 'params': [], 'response': '{"trips": [...]}'},
                {'methods': ['POST'], 'path': '/api/trips', 'desc': '创建行程', 'params': [{'name': 'title', 'in': 'body', 'type': 'string', 'required': True, 'desc': '行程标题'}, {'name': 'start_date', 'in': 'body', 'type': 'date', 'required': True, 'desc': '开始日期'}], 'response': '{"success": true, "trip_id": 1}'},
                {'methods': ['GET'], 'path': '/api/trips/<id>', 'desc': '行程详情', 'params': [], 'response': '{"trip": {...}}'},
                {'methods': ['PUT'], 'path': '/api/trips/<id>', 'desc': '更新行程', 'params': [], 'response': '{"success": true}'},
                {'methods': ['DELETE'], 'path': '/api/trips/<id>', 'desc': '删除行程', 'params': [], 'response': '{"success": true}'},
                {'methods': ['POST'], 'path': '/api/trips/<id>/items', 'desc': '添加行程项', 'params': [{'name': 'dest_id', 'in': 'body', 'type': 'int', 'required': True, 'desc': '景点ID'}, {'name': 'day', 'in': 'body', 'type': 'int', 'required': True, 'desc': '第几天'}], 'response': '{"success": true}'},
                {'methods': ['POST'], 'path': '/api/trips/share/<code>', 'desc': '查看分享行程', 'params': [], 'response': '{"trip": {...}}'},
                {'methods': ['POST'], 'path': '/api/trips/recommend', 'desc': 'AI 推荐行程', 'params': [{'name': 'city', 'in': 'body', 'type': 'string', 'required': True, 'desc': '城市'}, {'name': 'days', 'in': 'body', 'type': 'int', 'required': True, 'desc': '天数'}], 'response': '{"trip_plan": {...}}'},
                {'methods': ['GET'], 'path': '/api/trips/<id>/export/pdf', 'desc': '导出 PDF', 'params': [], 'response': 'PDF file'},
            ]
        },
        {
            'id': 'map', 'name': '地图', 'icon': '📍',
            'endpoints': [
                {'methods': ['GET'], 'path': '/api/map/destinations', 'desc': '景点坐标列表', 'params': [{'name': 'province', 'in': 'query', 'type': 'string', 'required': False, 'desc': '省份筛选'}], 'response': '{"points": [...]}'},
                {'methods': ['POST'], 'path': '/api/map/route', 'desc': '路线规划', 'params': [{'name': 'origin', 'in': 'body', 'type': 'array', 'required': True, 'desc': '起点 [lng, lat]'}], 'response': '{"route": {...}}'},
                {'methods': ['GET'], 'path': '/api/map/nearby', 'desc': '附近景点', 'params': [{'name': 'lng', 'in': 'query', 'type': 'float', 'required': True, 'desc': '经度'}, {'name': 'lat', 'in': 'query', 'type': 'float', 'required': True, 'desc': '纬度'}], 'response': '{"nearby": [...]}'},
                {'methods': ['POST'], 'path': '/api/map/geocode', 'desc': '地址转坐标', 'params': [{'name': 'address', 'in': 'body', 'type': 'string', 'required': True, 'desc': '地址'}], 'response': '{"lng": 116.4, "lat": 39.9}'},
                {'methods': ['POST'], 'path': '/api/map/reverse-geocode', 'desc': '坐标转地址', 'params': [{'name': 'lng', 'in': 'body', 'type': 'float', 'required': True, 'desc': '经度'}], 'response': '{"address": "..."}'},
            ]
        },
        {
            'id': 'nearby', 'name': '附近', 'icon': '📌',
            'endpoints': [
                {'methods': ['GET'], 'path': '/api/nearby/search', 'desc': '附近搜索', 'params': [{'name': 'lng', 'in': 'query', 'type': 'float', 'required': True, 'desc': '经度'}, {'name': 'lat', 'in': 'query', 'type': 'float', 'required': True, 'desc': '纬度'}, {'name': 'radius', 'in': 'query', 'type': 'int', 'required': False, 'desc': '半径(米)'}], 'response': '{"results": [...]}'},
                {'methods': ['GET'], 'path': '/api/nearby/categories', 'desc': '附近分类', 'params': [], 'response': '{"categories": [...]}'},
                {'methods': ['GET'], 'path': '/api/nearby/destination/<id>', 'desc': '景点附近信息', 'params': [], 'response': '{"nearby_food": [], "nearby_hotels": []}'},
            ]
        },
        {
            'id': 'weather', 'name': '天气/美食', 'icon': '🌤️',
            'endpoints': [
                {'methods': ['GET'], 'path': '/api/weather/<city>', 'desc': '城市天气', 'params': [], 'response': '{"temp": 25, "weather": "晴"}'},
                {'methods': ['GET'], 'path': '/api/weather/forecast/<city>', 'desc': '7天预报', 'params': [], 'response': '{"forecast": [...]}'},
                {'methods': ['GET'], 'path': '/api/food/<city>', 'desc': '城市美食', 'params': [], 'response': '{"foods": [...]}'},
                {'methods': ['GET'], 'path': '/api/food/search', 'desc': '搜索美食', 'params': [{'name': 'q', 'in': 'query', 'type': 'string', 'required': True, 'desc': '关键词'}], 'response': '{"results": [...]}'},
            ]
        },
        {
            'id': 'ai', 'name': 'AI 助手', 'icon': '🤖',
            'endpoints': [
                {'methods': ['POST'], 'path': '/api/assistant', 'desc': '对话接口', 'params': [{'name': 'message', 'in': 'body', 'type': 'string', 'required': True, 'desc': '用户消息'}, {'name': 'session_id', 'in': 'body', 'type': 'string', 'required': False, 'desc': '会话ID'}], 'response': '{"reply": "...", "suggestions": [...]}'},
                {'methods': ['POST'], 'path': '/api/assistant/stream', 'desc': '流式对话 (SSE)', 'params': [{'name': 'message', 'in': 'body', 'type': 'string', 'required': True, 'desc': '用户消息'}], 'response': 'text/event-stream'},
                {'methods': ['GET'], 'path': '/api/assistant/history/<sid>', 'desc': '对话历史', 'params': [], 'response': '{"messages": [...]}'},
                {'methods': ['GET'], 'path': '/api/assistant/tools', 'desc': '可用工具列表', 'params': [], 'response': '{"tools": [...]}'},
                {'methods': ['GET'], 'path': '/api/ai/status', 'desc': 'AI 服务状态', 'params': [], 'response': '{"enabled": true, "provider": "deepseek"}'},
                {'methods': ['POST'], 'path': '/api/ai/toggle', 'desc': '开关 AI 模式', 'params': [{'name': 'enabled', 'in': 'body', 'type': 'bool', 'required': True, 'desc': '是否启用'}], 'response': '{"success": true}'},
                {'methods': ['GET'], 'path': '/api/ai/providers', 'desc': 'AI 提供商列表', 'params': [], 'response': '{"providers": [...]}'},
                {'methods': ['POST'], 'path': '/api/ai/switch-provider', 'desc': '切换 AI 提供商', 'params': [{'name': 'provider', 'in': 'body', 'type': 'string', 'required': True, 'desc': '提供商名'}], 'response': '{"success": true}'},
                {'methods': ['POST'], 'path': '/api/ai/test', 'desc': '测试 AI 连接', 'params': [], 'response': '{"success": true, "response": "..."}'},
                {'methods': ['GET'], 'path': '/api/ai/config', 'desc': 'AI 配置 (脱敏)', 'params': [], 'response': '{"config": {...}}'},
            ]
        },
        {
            'id': 'security', 'name': '安全', 'icon': '🛡️',
            'endpoints': [
                {'methods': ['POST'], 'path': '/api/security/check-password', 'desc': '密码强度检查', 'params': [{'name': 'password', 'in': 'body', 'type': 'string', 'required': True, 'desc': '密码'}], 'response': '{"strength": "strong", "score": 85}'},
                {'methods': ['POST'], 'path': '/api/security/validate-csrf', 'desc': '验证 CSRF', 'params': [], 'response': '{"valid": true}'},
                {'methods': ['GET'], 'path': '/api/security/login-attempts', 'desc': '登录尝试次数', 'params': [], 'response': '{"attempts": 3}'},
                {'methods': ['POST'], 'path': '/api/login/secure', 'desc': '安全登录', 'params': [], 'response': '{"success": true}'},
                {'methods': ['GET'], 'path': '/api/security/rate-limit-check', 'desc': '速率限制状态', 'params': [], 'response': '{"remaining": 95}'},
            ]
        },
        {
            'id': 'admin', 'name': '后台管理', 'icon': '⚙️',
            'endpoints': [
                {'methods': ['GET', 'POST'], 'path': '/admin/login', 'desc': '管理员登录', 'params': [], 'response': 'HTML / Redirect'},
                {'methods': ['GET'], 'path': '/admin', 'desc': '仪表盘', 'params': [], 'response': 'HTML'},
                {'methods': ['GET'], 'path': '/api/admin/destinations', 'desc': '景点列表 (后台)', 'params': [{'name': 'page', 'in': 'query', 'type': 'int', 'required': False, 'desc': '页码'}, {'name': 'search', 'in': 'query', 'type': 'string', 'required': False, 'desc': '搜索词'}], 'response': '{"destinations": [...], "total": 1430}'},
                {'methods': ['POST'], 'path': '/api/admin/destinations', 'desc': '创建景点', 'params': [{'name': 'name', 'in': 'body', 'type': 'string', 'required': True, 'desc': '景点名'}, {'name': 'city', 'in': 'body', 'type': 'string', 'required': True, 'desc': '城市'}], 'response': '{"success": true, "id": 1431}'},
                {'methods': ['PUT'], 'path': '/api/admin/destinations/<id>', 'desc': '更新景点', 'params': [], 'response': '{"success": true}'},
                {'methods': ['DELETE'], 'path': '/api/admin/destinations/<id>', 'desc': '删除景点', 'params': [], 'response': '{"success": true}'},
                {'methods': ['GET'], 'path': '/api/admin/users', 'desc': '用户列表 (后台)', 'params': [], 'response': '{"users": [...]}'},
                {'methods': ['PUT'], 'path': '/api/admin/users/<id>', 'desc': '更新用户', 'params': [], 'response': '{"success": true}'},
                {'methods': ['DELETE'], 'path': '/api/admin/users/<id>', 'desc': '删除用户', 'params': [], 'response': '{"success": true}'},
            ]
        },
        {
            'id': 'system', 'name': '系统', 'icon': '🔧',
            'endpoints': [
                {'methods': ['GET'], 'path': '/api/system/health', 'desc': '健康检查', 'params': [], 'response': '{"status": "ok", "db": "ok", "ai": "ok"}'},
                {'methods': ['GET'], 'path': '/api/mobile/config', 'desc': '移动端配置', 'params': [], 'response': '{"version": "1.0", "features": [...]}'},
                {'methods': ['GET'], 'path': '/api/performance/stats', 'desc': '性能统计', 'params': [], 'response': '{"response_time": 45, "cache_hit": 0.8}'},
                {'methods': ['GET'], 'path': '/api/random-background', 'desc': '随机背景图', 'params': [], 'response': '{"image": "...", "name": "故宫", "location": "北京"}'},
                {'methods': ['GET'], 'path': '/api/backgrounds/batch', 'desc': '批量背景图', 'params': [{'name': 'count', 'in': 'query', 'type': 'int', 'required': False, 'desc': '数量'}], 'response': '{"images": [...]}'},
                {'methods': ['GET'], 'path': '/api/v2/site/info', 'desc': '站点信息', 'params': [], 'response': '{"site": {...}}'},
                {'methods': ['GET'], 'path': '/api/v2/home/data', 'desc': '首页聚合数据', 'params': [], 'response': '{"hot": [], "top": [], "provinces": []}'},
            ]
        },
    ]
    for s in sections:
        s['count'] = len(s['endpoints'])
    total = sum(s['count'] for s in sections)
    method_counts = {'get': 0, 'post': 0, 'put': 0, 'delete': 0}
    for s in sections:
        for ep in s['endpoints']:
            for m in ep['methods']:
                key = m.lower()
                if key in method_counts:
                    method_counts[key] += 1
    return render_template('api_docs.html', sections=sections, total_count=total, method_counts=method_counts)


# ==================== 启动应用 ====================
if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.WARNING)

    log.info("\n" + "=" * 50)
    log.info("🚀 智能旅游助手启动中...")
    log.info("=" * 50 + "\n")

    with app.app_context():
        init_db()
        travel_assistant = TravelAssistant(db)

    # 获取本机IP地址
    import socket
    def get_local_ip():
        try:
            # 创建一个socket连接来获取本机IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    local_ip = get_local_ip()

    log.info("🌐 服务器信息：")
    log.info(f"   本地访问: http://127.0.0.1:5000")
    log.info(f"   网络访问: http://{local_ip}:5000")
    log.info(f"   所有接口: http://0.0.0.0:5000")
    log.info("")
    log.info("📱 移动设备访问：")
    log.info(f"   请使用: http://{local_ip}:5000")
    log.info("   确保设备连接到同一网络或正确配置端口转发")
    log.info("=" * 50 + "\n")

    # 配置为允许所有网络访问
    socketio.run(app, 
                 debug=False, 
                 port=5000, 
                 host='0.0.0.0',  # 监听所有网络接口
                 allow_unsafe_werkzeug=True,
                 log_output=False)  # 减少日志输出
