"""
扩展 API 路由 - 完整 CRUD 操作
包含：省份、城市、美食、行程模板、评论、站点配置、导航、轮播图
"""
import json
from datetime import datetime
from flask import Blueprint, request, jsonify, session
from sqlalchemy import or_, func

# 创建蓝图
api_extended = Blueprint('api_extended', __name__)


def get_db():
    """延迟导入 db，避免循环引用"""
    from app import db
    return db


def get_models():
    """从 app.py 导入模型"""
    from app import (
        Province, City, Food, TripPlan, Review, SiteConfig, Banner, Navigation,
        User, Destination, db
    )
    return {
        'Province': Province, 'City': City, 'Food': Food,
        'TripPlan': TripPlan, 'Review': Review, 'SiteConfig': SiteConfig,
        'Banner': Banner, 'Navigation': Navigation,
        'User': User, 'Destination': Destination, 'db': db
    }


def login_required_api(f):
    """API 登录验证装饰器"""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session and 'admin_id' not in session:
            return jsonify({'success': False, 'error': '请先登录', 'code': 401}), 401
        return f(*args, **kwargs)
    return decorated


def admin_required_api(f):
    """API 管理员验证装饰器"""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'admin_id' not in session:
            return jsonify({'success': False, 'error': '需要管理员权限', 'code': 403}), 403
        return f(*args, **kwargs)
    return decorated


# ==================== 省份 CRUD ====================

@api_extended.route('/api/v2/provinces', methods=['GET'])
def list_provinces():
    """获取省份列表"""
    m = get_models()
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        keyword = request.args.get('keyword', '').strip()
        is_active = request.args.get('is_active', type=int)

        query = m['Province'].query
        if keyword:
            query = query.filter(m['Province'].name.contains(keyword))
        if is_active is not None:
            query = query.filter(m['Province'].is_active == bool(is_active))

        pagination = query.order_by(m['Province'].sort_order).paginate(
            page=page, per_page=per_page, error_out=False)

        return jsonify({
            'success': True,
            'data': [p.to_dict() for p in pagination.items],
            'total': pagination.total,
            'page': page,
            'pages': pagination.pages
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_extended.route('/api/v2/provinces', methods=['POST'])
@admin_required_api
def create_province():
    """创建省份"""
    m = get_models()
    try:
        data = request.get_json()
        if not data.get('name'):
            return jsonify({'success': False, 'error': '省份名称不能为空'}), 400

        if m['Province'].query.filter_by(name=data['name']).first():
            return jsonify({'success': False, 'error': '省份已存在'}), 400

        p = m['Province'](
            name=data['name'],
            code=data.get('code', ''),
            description=data.get('description', ''),
            cover_image=data.get('cover_image', ''),
            sort_order=data.get('sort_order', 0),
            is_active=data.get('is_active', True)
        )
        m['db'].session.add(p)
        m['db'].session.commit()
        return jsonify({'success': True, 'message': '创建成功', 'data': p.to_dict()})
    except Exception as e:
        m['db'].session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@api_extended.route('/api/v2/provinces/<int:pid>', methods=['GET'])
def get_province(pid):
    """获取省份详情"""
    m = get_models()
    p = m['Province'].query.get(pid)
    if not p:
        return jsonify({'success': False, 'error': '省份不存在'}), 404
    return jsonify({'success': True, 'data': p.to_dict()})


@api_extended.route('/api/v2/provinces/<int:pid>', methods=['PUT'])
@admin_required_api
def update_province(pid):
    """更新省份"""
    m = get_models()
    try:
        p = m['Province'].query.get(pid)
        if not p:
            return jsonify({'success': False, 'error': '省份不存在'}), 404

        data = request.get_json()
        for field in ['name', 'code', 'description', 'cover_image', 'sort_order', 'is_active']:
            if field in data:
                setattr(p, field, data[field])

        m['db'].session.commit()
        return jsonify({'success': True, 'message': '更新成功', 'data': p.to_dict()})
    except Exception as e:
        m['db'].session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@api_extended.route('/api/v2/provinces/<int:pid>', methods=['DELETE'])
@admin_required_api
def delete_province(pid):
    """删除省份"""
    m = get_models()
    try:
        p = m['Province'].query.get(pid)
        if not p:
            return jsonify({'success': False, 'error': '省份不存在'}), 404
        m['db'].session.delete(p)
        m['db'].session.commit()
        return jsonify({'success': True, 'message': '删除成功'})
    except Exception as e:
        m['db'].session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== 城市 CRUD ====================

@api_extended.route('/api/v2/cities', methods=['GET'])
def list_cities():
    """获取城市列表"""
    m = get_models()
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        keyword = request.args.get('keyword', '').strip()
        province_name = request.args.get('province', '').strip()
        city_type = request.args.get('type', '').strip()

        query = m['City'].query
        if keyword:
            query = query.filter(m['City'].name.contains(keyword))
        if province_name:
            query = query.filter(m['City'].province_name == province_name)
        if city_type:
            query = query.filter(m['City'].city_type == city_type)

        pagination = query.order_by(m['City'].sort_order, m['City'].name).paginate(
            page=page, per_page=per_page, error_out=False)

        return jsonify({
            'success': True,
            'data': [c.to_dict() for c in pagination.items],
            'total': pagination.total,
            'page': page,
            'pages': pagination.pages
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_extended.route('/api/v2/cities', methods=['POST'])
@admin_required_api
def create_city():
    """创建城市"""
    m = get_models()
    try:
        data = request.get_json()
        if not data.get('name'):
            return jsonify({'success': False, 'error': '城市名称不能为空'}), 400

        c = m['City'](
            name=data['name'],
            province_id=data.get('province_id'),
            province_name=data.get('province_name', ''),
            city_type=data.get('city_type', '地级市'),
            description=data.get('description', ''),
            cover_image=data.get('cover_image', ''),
            latitude=data.get('latitude'),
            longitude=data.get('longitude'),
            sort_order=data.get('sort_order', 0),
            is_active=data.get('is_active', True)
        )
        m['db'].session.add(c)
        m['db'].session.commit()
        return jsonify({'success': True, 'message': '创建成功', 'data': c.to_dict()})
    except Exception as e:
        m['db'].session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@api_extended.route('/api/v2/cities/<int:cid>', methods=['GET'])
def get_city(cid):
    """获取城市详情"""
    m = get_models()
    c = m['City'].query.get(cid)
    if not c:
        return jsonify({'success': False, 'error': '城市不存在'}), 404
    return jsonify({'success': True, 'data': c.to_dict()})


@api_extended.route('/api/v2/cities/<int:cid>', methods=['PUT'])
@admin_required_api
def update_city(cid):
    """更新城市"""
    m = get_models()
    try:
        c = m['City'].query.get(cid)
        if not c:
            return jsonify({'success': False, 'error': '城市不存在'}), 404

        data = request.get_json()
        for field in ['name', 'province_id', 'province_name', 'city_type',
                      'description', 'cover_image', 'latitude', 'longitude',
                      'sort_order', 'is_active']:
            if field in data:
                setattr(c, field, data[field])

        m['db'].session.commit()
        return jsonify({'success': True, 'message': '更新成功', 'data': c.to_dict()})
    except Exception as e:
        m['db'].session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@api_extended.route('/api/v2/cities/<int:cid>', methods=['DELETE'])
@admin_required_api
def delete_city(cid):
    """删除城市"""
    m = get_models()
    try:
        c = m['City'].query.get(cid)
        if not c:
            return jsonify({'success': False, 'error': '城市不存在'}), 404
        m['db'].session.delete(c)
        m['db'].session.commit()
        return jsonify({'success': True, 'message': '删除成功'})
    except Exception as e:
        m['db'].session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== 美食 CRUD ====================

@api_extended.route('/api/v2/foods', methods=['GET'])
def list_foods():
    """获取美食列表"""
    m = get_models()
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        keyword = request.args.get('keyword', '').strip()
        city = request.args.get('city', '').strip()
        province = request.args.get('province', '').strip()
        category = request.args.get('category', '').strip()

        query = m['Food'].query
        if keyword:
            query = query.filter(
                or_(m['Food'].name.contains(keyword),
                    m['Food'].description.contains(keyword)))
        if city:
            query = query.filter(m['Food'].city.contains(city))
        if province:
            query = query.filter(m['Food'].province.contains(province))
        if category:
            query = query.filter(m['Food'].category == category)

        pagination = query.order_by(m['Food'].popularity_score.desc()).paginate(
            page=page, per_page=per_page, error_out=False)

        return jsonify({
            'success': True,
            'data': [f.to_dict() for f in pagination.items],
            'total': pagination.total,
            'page': page,
            'pages': pagination.pages
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_extended.route('/api/v2/foods', methods=['POST'])
@admin_required_api
def create_food():
    """创建美食"""
    m = get_models()
    try:
        data = request.get_json()
        if not data.get('name'):
            return jsonify({'success': False, 'error': '美食名称不能为空'}), 400

        f = m['Food'](
            name=data['name'],
            city=data.get('city', ''),
            province=data.get('province', ''),
            description=data.get('description', ''),
            price_range=data.get('price_range', ''),
            restaurants=json.dumps(data.get('restaurants', []), ensure_ascii=False),
            cover_image=data.get('cover_image', ''),
            category=data.get('category', '正餐'),
            rating=float(data.get('rating', 4.5)),
            popularity_score=float(data.get('popularity_score', 50)),
            is_active=data.get('is_active', True)
        )
        m['db'].session.add(f)
        m['db'].session.commit()
        return jsonify({'success': True, 'message': '创建成功', 'data': f.to_dict()})
    except Exception as e:
        m['db'].session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@api_extended.route('/api/v2/foods/<int:fid>', methods=['GET'])
def get_food(fid):
    """获取美食详情"""
    m = get_models()
    f = m['Food'].query.get(fid)
    if not f:
        return jsonify({'success': False, 'error': '美食不存在'}), 404
    return jsonify({'success': True, 'data': f.to_dict()})


@api_extended.route('/api/v2/foods/<int:fid>', methods=['PUT'])
@admin_required_api
def update_food(fid):
    """更新美食"""
    m = get_models()
    try:
        f = m['Food'].query.get(fid)
        if not f:
            return jsonify({'success': False, 'error': '美食不存在'}), 404

        data = request.get_json()
        for field in ['name', 'city', 'province', 'description', 'price_range',
                      'cover_image', 'category', 'rating', 'popularity_score', 'is_active']:
            if field in data:
                setattr(f, field, data[field])
        if 'restaurants' in data:
            f.restaurants = json.dumps(data['restaurants'], ensure_ascii=False)

        m['db'].session.commit()
        return jsonify({'success': True, 'message': '更新成功', 'data': f.to_dict()})
    except Exception as e:
        m['db'].session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@api_extended.route('/api/v2/foods/<int:fid>', methods=['DELETE'])
@admin_required_api
def delete_food(fid):
    """删除美食"""
    m = get_models()
    try:
        f = m['Food'].query.get(fid)
        if not f:
            return jsonify({'success': False, 'error': '美食不存在'}), 404
        m['db'].session.delete(f)
        m['db'].session.commit()
        return jsonify({'success': True, 'message': '删除成功'})
    except Exception as e:
        m['db'].session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== 行程模板 CRUD ====================

@api_extended.route('/api/v2/trip-plans', methods=['GET'])
def list_trip_plans():
    """获取行程模板列表"""
    m = get_models()
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        city = request.args.get('city', '').strip()
        days = request.args.get('days', type=int)
        is_default = request.args.get('is_default', type=int)

        query = m['TripPlan'].query
        if city:
            query = query.filter(m['TripPlan'].city.contains(city))
        if days:
            query = query.filter(m['TripPlan'].days == days)
        if is_default is not None:
            query = query.filter(m['TripPlan'].is_default == bool(is_default))

        pagination = query.order_by(m['TripPlan'].city, m['TripPlan'].days).paginate(
            page=page, per_page=per_page, error_out=False)

        return jsonify({
            'success': True,
            'data': [tp.to_dict() for tp in pagination.items],
            'total': pagination.total,
            'page': page,
            'pages': pagination.pages
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_extended.route('/api/v2/trip-plans', methods=['POST'])
@admin_required_api
def create_trip_plan():
    """创建行程模板"""
    m = get_models()
    try:
        data = request.get_json()
        if not data.get('city') or not data.get('title'):
            return jsonify({'success': False, 'error': '城市和标题不能为空'}), 400

        tp = m['TripPlan'](
            city=data['city'],
            province=data.get('province', ''),
            title=data['title'],
            days=int(data.get('days', 1)),
            description=data.get('description', ''),
            itinerary=json.dumps(data.get('itinerary', []), ensure_ascii=False),
            budget_estimate=data.get('budget_estimate', ''),
            best_season=data.get('best_season', ''),
            cover_image=data.get('cover_image', ''),
            is_default=data.get('is_default', False),
            sort_order=data.get('sort_order', 0),
            is_active=data.get('is_active', True)
        )
        m['db'].session.add(tp)
        m['db'].session.commit()
        return jsonify({'success': True, 'message': '创建成功', 'data': tp.to_dict()})
    except Exception as e:
        m['db'].session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@api_extended.route('/api/v2/trip-plans/<int:tpid>', methods=['GET'])
def get_trip_plan(tpid):
    """获取行程模板详情"""
    m = get_models()
    tp = m['TripPlan'].query.get(tpid)
    if not tp:
        return jsonify({'success': False, 'error': '行程模板不存在'}), 404
    return jsonify({'success': True, 'data': tp.to_dict()})


@api_extended.route('/api/v2/trip-plans/<int:tpid>', methods=['PUT'])
@admin_required_api
def update_trip_plan(tpid):
    """更新行程模板"""
    m = get_models()
    try:
        tp = m['TripPlan'].query.get(tpid)
        if not tp:
            return jsonify({'success': False, 'error': '行程模板不存在'}), 404

        data = request.get_json()
        for field in ['city', 'province', 'title', 'days', 'description',
                      'budget_estimate', 'best_season', 'cover_image',
                      'is_default', 'sort_order', 'is_active']:
            if field in data:
                setattr(tp, field, data[field])
        if 'itinerary' in data:
            tp.itinerary = json.dumps(data['itinerary'], ensure_ascii=False)

        m['db'].session.commit()
        return jsonify({'success': True, 'message': '更新成功', 'data': tp.to_dict()})
    except Exception as e:
        m['db'].session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@api_extended.route('/api/v2/trip-plans/<int:tpid>', methods=['DELETE'])
@admin_required_api
def delete_trip_plan(tpid):
    """删除行程模板"""
    m = get_models()
    try:
        tp = m['TripPlan'].query.get(tpid)
        if not tp:
            return jsonify({'success': False, 'error': '行程模板不存在'}), 404
        m['db'].session.delete(tp)
        m['db'].session.commit()
        return jsonify({'success': True, 'message': '删除成功'})
    except Exception as e:
        m['db'].session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== 评论 CRUD ====================

@api_extended.route('/api/v2/reviews', methods=['GET'])
def list_reviews():
    """获取评论列表"""
    m = get_models()
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        dest_id = request.args.get('destination_id', type=int)
        status = request.args.get('status', '').strip()
        keyword = request.args.get('keyword', '').strip()

        query = m['Review'].query
        if dest_id:
            query = query.filter(m['Review'].destination_id == dest_id)
        if status:
            query = query.filter(m['Review'].status == status)
        if keyword:
            query = query.filter(
                or_(m['Review'].content.contains(keyword),
                    m['Review'].username.contains(keyword)))

        pagination = query.order_by(m['Review'].created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False)

        return jsonify({
            'success': True,
            'data': [r.to_dict() for r in pagination.items],
            'total': pagination.total,
            'page': page,
            'pages': pagination.pages
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_extended.route('/api/v2/reviews', methods=['POST'])
@login_required_api
def create_review():
    """创建评论"""
    m = get_models()
    try:
        data = request.get_json()
        if not data.get('destination_id') or not data.get('content'):
            return jsonify({'success': False, 'error': '景点ID和评论内容不能为空'}), 400

        rating = float(data.get('rating', 5))
        if rating < 1 or rating > 5:
            return jsonify({'success': False, 'error': '评分必须在1-5之间'}), 400

        user_id = session.get('user_id')
        username = session.get('username', data.get('username', '匿名用户'))

        r = m['Review'](
            destination_id=data['destination_id'],
            user_id=user_id,
            username=username,
            rating=rating,
            content=data['content'],
            images=json.dumps(data.get('images', []), ensure_ascii=False),
            status='approved'
        )
        m['db'].session.add(r)
        m['db'].session.commit()
        return jsonify({'success': True, 'message': '评论成功', 'data': r.to_dict()})
    except Exception as e:
        m['db'].session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@api_extended.route('/api/v2/reviews/<int:rid>', methods=['PUT'])
@login_required_api
def update_review(rid):
    """更新评论"""
    m = get_models()
    try:
        r = m['Review'].query.get(rid)
        if not r:
            return jsonify({'success': False, 'error': '评论不存在'}), 404

        # 只能修改自己的评论（管理员除外）
        if 'admin_id' not in session and r.user_id != session.get('user_id'):
            return jsonify({'success': False, 'error': '无权修改'}), 403

        data = request.get_json()
        if 'content' in data:
            r.content = data['content']
        if 'rating' in data:
            rating = float(data['rating'])
            if 1 <= rating <= 5:
                r.rating = rating
        if 'status' in data and 'admin_id' in session:
            r.status = data['status']

        m['db'].session.commit()
        return jsonify({'success': True, 'message': '更新成功', 'data': r.to_dict()})
    except Exception as e:
        m['db'].session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@api_extended.route('/api/v2/reviews/<int:rid>', methods=['DELETE'])
@login_required_api
def delete_review(rid):
    """删除评论"""
    m = get_models()
    try:
        r = m['Review'].query.get(rid)
        if not r:
            return jsonify({'success': False, 'error': '评论不存在'}), 404

        if 'admin_id' not in session and r.user_id != session.get('user_id'):
            return jsonify({'success': False, 'error': '无权删除'}), 403

        m['db'].session.delete(r)
        m['db'].session.commit()
        return jsonify({'success': True, 'message': '删除成功'})
    except Exception as e:
        m['db'].session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@api_extended.route('/api/v2/reviews/<int:rid>/approve', methods=['POST'])
@admin_required_api
def approve_review(rid):
    """审核评论"""
    m = get_models()
    try:
        r = m['Review'].query.get(rid)
        if not r:
            return jsonify({'success': False, 'error': '评论不存在'}), 404

        data = request.get_json() or {}
        r.status = data.get('status', 'approved')
        m['db'].session.commit()
        return jsonify({'success': True, 'message': '审核完成', 'data': r.to_dict()})
    except Exception as e:
        m['db'].session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== 站点配置 CRUD ====================

@api_extended.route('/api/v2/configs', methods=['GET'])
def list_configs():
    """获取配置列表"""
    m = get_models()
    try:
        group = request.args.get('group', '').strip()
        is_public = request.args.get('is_public', type=int)

        query = m['SiteConfig'].query
        if group:
            query = query.filter(m['SiteConfig'].group == group)
        if is_public is not None:
            query = query.filter(m['SiteConfig'].is_public == bool(is_public))

        configs = query.order_by(m['SiteConfig'].group, m['SiteConfig'].key).all()

        return jsonify({
            'success': True,
            'data': [c.to_dict() for c in configs],
            'total': len(configs)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_extended.route('/api/v2/configs/public', methods=['GET'])
def get_public_configs():
    """获取公开配置（前端可直接调用）"""
    m = get_models()
    try:
        configs = m['SiteConfig'].query.filter_by(is_public=True).all()
        result = {}
        for c in configs:
            val = c.value
            if c.value_type == 'bool':
                val = val.lower() == 'true' if val else False
            elif c.value_type == 'int':
                val = int(val) if val else 0
            elif c.value_type == 'float':
                val = float(val) if val else 0.0
            elif c.value_type == 'json':
                val = json.loads(val) if val else {}
            result[c.key] = val

        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_extended.route('/api/v2/configs', methods=['POST'])
@admin_required_api
def create_config():
    """创建配置"""
    m = get_models()
    try:
        data = request.get_json()
        if not data.get('key'):
            return jsonify({'success': False, 'error': '配置key不能为空'}), 400

        if m['SiteConfig'].query.filter_by(key=data['key']).first():
            return jsonify({'success': False, 'error': '配置key已存在'}), 400

        c = m['SiteConfig'](
            key=data['key'],
            value=str(data.get('value', '')),
            value_type=data.get('value_type', 'string'),
            group=data.get('group', 'general'),
            label=data.get('label', data['key']),
            description=data.get('description', ''),
            is_public=data.get('is_public', False)
        )
        m['db'].session.add(c)
        m['db'].session.commit()
        return jsonify({'success': True, 'message': '创建成功', 'data': c.to_dict()})
    except Exception as e:
        m['db'].session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@api_extended.route('/api/v2/configs/<key>', methods=['GET'])
def get_config(key):
    """获取配置详情"""
    m = get_models()
    c = m['SiteConfig'].query.filter_by(key=key).first()
    if not c:
        return jsonify({'success': False, 'error': '配置不存在'}), 404
    return jsonify({'success': True, 'data': c.to_dict()})


@api_extended.route('/api/v2/configs/<key>', methods=['PUT'])
@admin_required_api
def update_config(key):
    """更新配置"""
    m = get_models()
    try:
        c = m['SiteConfig'].query.filter_by(key=key).first()
        if not c:
            return jsonify({'success': False, 'error': '配置不存在'}), 404

        data = request.get_json()
        for field in ['value', 'value_type', 'group', 'label', 'description', 'is_public']:
            if field in data:
                setattr(c, field, str(data[field]) if field == 'value' else data[field])

        m['db'].session.commit()
        return jsonify({'success': True, 'message': '更新成功', 'data': c.to_dict()})
    except Exception as e:
        m['db'].session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@api_extended.route('/api/v2/configs/<key>', methods=['DELETE'])
@admin_required_api
def delete_config(key):
    """删除配置"""
    m = get_models()
    try:
        c = m['SiteConfig'].query.filter_by(key=key).first()
        if not c:
            return jsonify({'success': False, 'error': '配置不存在'}), 404
        m['db'].session.delete(c)
        m['db'].session.commit()
        return jsonify({'success': True, 'message': '删除成功'})
    except Exception as e:
        m['db'].session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== 导航 CRUD ====================

@api_extended.route('/api/v2/navigations', methods=['GET'])
def list_navigations():
    """获取导航列表"""
    m = get_models()
    try:
        position = request.args.get('position', '').strip()
        query = m['Navigation'].query
        if position:
            query = query.filter(m['Navigation'].position == position)

        navs = query.order_by(m['Navigation'].position, m['Navigation'].sort_order).all()

        return jsonify({
            'success': True,
            'data': [n.to_dict() for n in navs],
            'total': len(navs)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_extended.route('/api/v2/navigations', methods=['POST'])
@admin_required_api
def create_navigation():
    """创建导航"""
    m = get_models()
    try:
        data = request.get_json()
        if not data.get('name'):
            return jsonify({'success': False, 'error': '导航名称不能为空'}), 400

        n = m['Navigation'](
            name=data['name'],
            url=data.get('url', ''),
            icon=data.get('icon', ''),
            parent_id=data.get('parent_id'),
            sort_order=data.get('sort_order', 0),
            is_active=data.get('is_active', True),
            position=data.get('position', 'header')
        )
        m['db'].session.add(n)
        m['db'].session.commit()
        return jsonify({'success': True, 'message': '创建成功', 'data': n.to_dict()})
    except Exception as e:
        m['db'].session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@api_extended.route('/api/v2/navigations/<int:nid>', methods=['PUT'])
@admin_required_api
def update_navigation(nid):
    """更新导航"""
    m = get_models()
    try:
        n = m['Navigation'].query.get(nid)
        if not n:
            return jsonify({'success': False, 'error': '导航不存在'}), 404

        data = request.get_json()
        for field in ['name', 'url', 'icon', 'parent_id', 'sort_order', 'is_active', 'position']:
            if field in data:
                setattr(n, field, data[field])

        m['db'].session.commit()
        return jsonify({'success': True, 'message': '更新成功', 'data': n.to_dict()})
    except Exception as e:
        m['db'].session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@api_extended.route('/api/v2/navigations/<int:nid>', methods=['DELETE'])
@admin_required_api
def delete_navigation(nid):
    """删除导航"""
    m = get_models()
    try:
        n = m['Navigation'].query.get(nid)
        if not n:
            return jsonify({'success': False, 'error': '导航不存在'}), 404
        m['db'].session.delete(n)
        m['db'].session.commit()
        return jsonify({'success': True, 'message': '删除成功'})
    except Exception as e:
        m['db'].session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== 轮播图 CRUD ====================

@api_extended.route('/api/v2/banners', methods=['GET'])
def list_banners():
    """获取轮播图列表"""
    m = get_models()
    try:
        banners = m['Banner'].query.filter_by(is_active=True).order_by(m['Banner'].sort_order).all()
        return jsonify({
            'success': True,
            'data': [b.to_dict() for b in banners],
            'total': len(banners)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_extended.route('/api/v2/banners', methods=['POST'])
@admin_required_api
def create_banner():
    """创建轮播图"""
    m = get_models()
    try:
        data = request.get_json()
        if not data.get('image_url'):
            return jsonify({'success': False, 'error': '图片URL不能为空'}), 400

        b = m['Banner'](
            title=data.get('title', ''),
            image_url=data['image_url'],
            link_url=data.get('link_url', ''),
            link_type=data.get('link_type', 'url'),
            link_id=data.get('link_id'),
            sort_order=data.get('sort_order', 0),
            is_active=data.get('is_active', True)
        )
        m['db'].session.add(b)
        m['db'].session.commit()
        return jsonify({'success': True, 'message': '创建成功', 'data': b.to_dict()})
    except Exception as e:
        m['db'].session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@api_extended.route('/api/v2/banners/<int:bid>', methods=['PUT'])
@admin_required_api
def update_banner(bid):
    """更新轮播图"""
    m = get_models()
    try:
        b = m['Banner'].query.get(bid)
        if not b:
            return jsonify({'success': False, 'error': '轮播图不存在'}), 404

        data = request.get_json()
        for field in ['title', 'image_url', 'link_url', 'link_type', 'link_id',
                      'sort_order', 'is_active']:
            if field in data:
                setattr(b, field, data[field])

        m['db'].session.commit()
        return jsonify({'success': True, 'message': '更新成功', 'data': b.to_dict()})
    except Exception as e:
        m['db'].session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@api_extended.route('/api/v2/banners/<int:bid>', methods=['DELETE'])
@admin_required_api
def delete_banner(bid):
    """删除轮播图"""
    m = get_models()
    try:
        b = m['Banner'].query.get(bid)
        if not b:
            return jsonify({'success': False, 'error': '轮播图不存在'}), 404
        m['db'].session.delete(b)
        m['db'].session.commit()
        return jsonify({'success': True, 'message': '删除成功'})
    except Exception as e:
        m['db'].session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== 数据统计 API ====================

@api_extended.route('/api/v2/stats/database', methods=['GET'])
@admin_required_api
def database_stats():
    """数据库统计"""
    m = get_models()
    try:
        from sqlalchemy import text
        stats = {}
        tables = [
            ('province', '省份'), ('city', '城市'), ('food', '美食'),
            ('trip_plan', '行程模板'), ('review', '评论'),
            ('site_config', '站点配置'), ('navigation', '导航'),
            ('banner', '轮播图'), ('destination', '景点'),
            ('user', '用户'), ('admin', '管理员'),
            ('trip', '用户行程'), ('nearby_poi', '周边POI'),
            ('user_like', '用户点赞'), ('user_checkin', '用户签到'),
        ]
        for table, label in tables:
            try:
                result = m['db'].session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.scalar()
                stats[table] = {'label': label, 'count': count}
            except:
                stats[table] = {'label': label, 'count': -1}

        return jsonify({'success': True, 'data': stats})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== 批量操作 API ====================

@api_extended.route('/api/v2/batch/update-status', methods=['POST'])
@admin_required_api
def batch_update_status():
    """批量更新状态"""
    m = get_models()
    try:
        data = request.get_json()
        model_name = data.get('model')
        ids = data.get('ids', [])
        action = data.get('action')  # activate/deactivate/delete

        model_map = {
            'province': m['Province'], 'city': m['City'], 'food': m['Food'],
            'trip_plan': m['TripPlan'], 'review': m['Review'],
            'banner': m['Banner'], 'navigation': m['Navigation']
        }

        model = model_map.get(model_name)
        if not model:
            return jsonify({'success': False, 'error': f'未知模型: {model_name}'}), 400

        count = 0
        for item_id in ids:
            item = model.query.get(item_id)
            if item:
                if action == 'delete':
                    m['db'].session.delete(item)
                elif action == 'activate':
                    item.is_active = True
                elif action == 'deactivate':
                    item.is_active = False
                count += 1

        m['db'].session.commit()
        return jsonify({'success': True, 'message': f'已处理 {count} 条记录'})
    except Exception as e:
        m['db'].session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
