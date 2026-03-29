"""
models/core.py — 核心数据库模型
从 app.py 中提取的 11 个核心模型
"""
import json
from datetime import datetime
from functools import wraps

from werkzeug.security import generate_password_hash, check_password_hash
from flask import url_for

from extensions import db


# ==================== 景点模型 ====================
class Destination(db.Model):
    """景点模型"""
    __tablename__ = 'destination'
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
    view_count = db.Column(db.Integer, default=0)
    like_count = db.Column(db.Integer, default=0)

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


# ==================== 用户模型 ====================
class User(db.Model):
    """用户模型"""
    __tablename__ = 'user'
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


# ==================== 对话记录模型 ====================
class Conversation(db.Model):
    """对话记录模型"""
    __tablename__ = 'conversation'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer)
    messages = db.Column(db.Text, default='[]')
    context = db.Column(db.Text, default='{}')
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)


# ==================== 管理员模型 ====================
class Admin(db.Model):
    """管理员模型"""
    __tablename__ = 'admin'
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


# ==================== 行程模型 ====================
class Trip(db.Model):
    """行程模型"""
    __tablename__ = 'trip'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    budget = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='planning')
    is_public = db.Column(db.Boolean, default=False)
    share_code = db.Column(db.String(20), unique=True)
    cover_image = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

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


# ==================== 行程项目模型 ====================
class TripItem(db.Model):
    """行程项目模型"""
    __tablename__ = 'trip_item'
    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey('trip.id'), nullable=False)
    destination_id = db.Column(db.Integer, db.ForeignKey('destination.id'))
    day_number = db.Column(db.Integer, nullable=False)
    start_time = db.Column(db.Time)
    end_time = db.Column(db.Time)
    activity = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(300))
    notes = db.Column(db.Text)
    cost = db.Column(db.Float, default=0.0)
    order_index = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now)

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


# ==================== 行程分享模型 ====================
class TripShare(db.Model):
    """行程分享记录模型"""
    __tablename__ = 'trip_share'
    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey('trip.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    platform = db.Column(db.String(50))
    shared_at = db.Column(db.DateTime, default=datetime.now)

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


# ==================== 周边POI模型 ====================
class NearbyPOI(db.Model):
    """周边POI模型"""
    __tablename__ = 'nearby_poi'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    subcategory = db.Column(db.String(100))
    city = db.Column(db.String(100))
    province = db.Column(db.String(50))
    address = db.Column(db.String(300))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    rating = db.Column(db.Float, default=0.0)
    price_level = db.Column(db.String(20))
    phone = db.Column(db.String(50))
    opening_hours = db.Column(db.String(200))
    description = db.Column(db.Text)
    tags = db.Column(db.String(500))
    images = db.Column(db.String(1000), default='[]')
    cover_image = db.Column(db.String(500))
    business_status = db.Column(db.String(20), default='营业中')
    distance = db.Column(db.Integer)
    destination_id = db.Column(db.Integer, db.ForeignKey('destination.id'))
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

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


# ==================== 用户点赞模型 ====================
class UserLike(db.Model):
    """用户点赞模型"""
    __tablename__ = 'user_like'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    destination_id = db.Column(db.Integer, db.ForeignKey('destination.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

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


# ==================== 用户关注模型 ====================
class UserFollow(db.Model):
    """用户关注模型"""
    __tablename__ = 'user_follow'
    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    following_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

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


# ==================== 用户签到模型 ====================
class UserCheckin(db.Model):
    """用户签到模型"""
    __tablename__ = 'user_checkin'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    destination_id = db.Column(db.Integer, db.ForeignKey('destination.id'), nullable=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    content = db.Column(db.Text)
    images = db.Column(db.String(1000), default='[]')
    created_at = db.Column(db.DateTime, default=datetime.now)

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
