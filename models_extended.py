"""
models_extended.py — 扩展数据库模型
包含：省份、城市、美食、行程模板、评论、站点配置、轮播图、导航
直接使用 extensions.db，无需工厂函数
"""
from datetime import datetime
import json

from extensions import db


class Province(db.Model):
    """省份模型"""
    __tablename__ = 'province_ext'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    code = db.Column(db.String(10))
    description = db.Column(db.Text)
    cover_image = db.Column(db.String(500))
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    cities = db.relationship('City', backref='province_ref', lazy=True)

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name, 'code': self.code,
            'description': self.description, 'cover_image': self.cover_image,
            'sort_order': self.sort_order, 'is_active': self.is_active,
            'cities_count': len(self.cities) if self.cities else 0,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M') if self.updated_at else None
        }


class City(db.Model):
    """城市模型"""
    __tablename__ = 'city_ext'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    province_id = db.Column(db.Integer, db.ForeignKey('province_ext.id'))
    province_name = db.Column(db.String(50))
    city_type = db.Column(db.String(20), default='地级市')
    description = db.Column(db.Text)
    cover_image = db.Column(db.String(500))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        db.Index('idx_city_ext_province', 'province_name'),
        db.Index('idx_city_ext_name', 'name'),
    )

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name, 'province_id': self.province_id,
            'province_name': self.province_name, 'city_type': self.city_type,
            'description': self.description, 'cover_image': self.cover_image,
            'latitude': self.latitude, 'longitude': self.longitude,
            'sort_order': self.sort_order, 'is_active': self.is_active,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M') if self.updated_at else None
        }


class Food(db.Model):
    """美食模型"""
    __tablename__ = 'food_ext'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    city = db.Column(db.String(100))
    province = db.Column(db.String(50))
    description = db.Column(db.Text)
    price_range = db.Column(db.String(100))
    restaurants = db.Column(db.Text)  # JSON
    cover_image = db.Column(db.String(500))
    category = db.Column(db.String(50))
    rating = db.Column(db.Float, default=4.5)
    popularity_score = db.Column(db.Float, default=50.0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        db.Index('idx_food_ext_city', 'city'),
        db.Index('idx_food_ext_province', 'province'),
        db.Index('idx_food_ext_category', 'category'),
    )

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name, 'city': self.city,
            'province': self.province, 'description': self.description,
            'price_range': self.price_range,
            'restaurants': json.loads(self.restaurants) if self.restaurants else [],
            'cover_image': self.cover_image, 'category': self.category,
            'rating': self.rating, 'popularity_score': self.popularity_score,
            'is_active': self.is_active,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M') if self.updated_at else None
        }


class TripPlan(db.Model):
    """行程模板模型"""
    __tablename__ = 'trip_plan_ext'
    id = db.Column(db.Integer, primary_key=True)
    city = db.Column(db.String(100), nullable=False)
    province = db.Column(db.String(50))
    title = db.Column(db.String(200), nullable=False)
    days = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text)
    itinerary = db.Column(db.Text)  # JSON
    budget_estimate = db.Column(db.String(100))
    best_season = db.Column(db.String(100))
    cover_image = db.Column(db.String(500))
    is_default = db.Column(db.Boolean, default=False)
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        db.Index('idx_trip_ext_city', 'city'),
        db.Index('idx_trip_ext_days', 'days'),
    )

    def to_dict(self):
        return {
            'id': self.id, 'city': self.city, 'province': self.province,
            'title': self.title, 'days': self.days, 'description': self.description,
            'itinerary': json.loads(self.itinerary) if self.itinerary else [],
            'budget_estimate': self.budget_estimate, 'best_season': self.best_season,
            'cover_image': self.cover_image, 'is_default': self.is_default,
            'sort_order': self.sort_order, 'is_active': self.is_active,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M') if self.updated_at else None
        }


class Review(db.Model):
    """评论模型"""
    __tablename__ = 'review_ext'
    id = db.Column(db.Integer, primary_key=True)
    destination_id = db.Column(db.Integer, db.ForeignKey('destination.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    username = db.Column(db.String(80), nullable=False)
    rating = db.Column(db.Float, nullable=False)
    content = db.Column(db.Text, nullable=False)
    images = db.Column(db.Text, default='[]')
    likes = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='approved')
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    destination = db.relationship('Destination', backref=db.backref('db_reviews', lazy=True))

    __table_args__ = (
        db.Index('idx_review_ext_dest', 'destination_id'),
        db.Index('idx_review_ext_user', 'user_id'),
        db.Index('idx_review_ext_status', 'status'),
    )

    def to_dict(self):
        return {
            'id': self.id, 'destination_id': self.destination_id,
            'destination_name': self.destination.name if self.destination else None,
            'user_id': self.user_id, 'username': self.username,
            'rating': self.rating, 'content': self.content,
            'images': json.loads(self.images) if self.images else [],
            'likes': self.likes, 'status': self.status,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M') if self.updated_at else None
        }


class SiteConfig(db.Model):
    """站点配置模型"""
    __tablename__ = 'site_config_ext'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)
    value_type = db.Column(db.String(20), default='string')
    group = db.Column(db.String(50), default='general')
    label = db.Column(db.String(200))
    description = db.Column(db.Text)
    is_public = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            'id': self.id, 'key': self.key, 'value': self.value,
            'value_type': self.value_type, 'group': self.group,
            'label': self.label, 'description': self.description,
            'is_public': self.is_public,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M') if self.updated_at else None
        }


class Banner(db.Model):
    """轮播图模型"""
    __tablename__ = 'banner_ext'
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
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            'id': self.id, 'title': self.title, 'image_url': self.image_url,
            'link_url': self.link_url, 'link_type': self.link_type,
            'link_id': self.link_id, 'sort_order': self.sort_order,
            'is_active': self.is_active,
            'start_time': self.start_time.strftime('%Y-%m-%d %H:%M') if self.start_time else None,
            'end_time': self.end_time.strftime('%Y-%m-%d %H:%M') if self.end_time else None,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None
        }


class Navigation(db.Model):
    """导航菜单模型"""
    __tablename__ = 'navigation_ext'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(500))
    icon = db.Column(db.String(100))
    parent_id = db.Column(db.Integer, db.ForeignKey('navigation_ext.id'))
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    position = db.Column(db.String(20), default='header')
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    children = db.relationship('Navigation', backref=db.backref('parent', remote_side=[id]), lazy=True)

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name, 'url': self.url,
            'icon': self.icon, 'parent_id': self.parent_id,
            'sort_order': self.sort_order, 'is_active': self.is_active,
            'position': self.position,
            'children': [c.to_dict() for c in self.children] if self.children else [],
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None
        }
