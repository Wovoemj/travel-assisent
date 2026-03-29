"""输入验证工具 - 统一校验API参数"""
import re
from functools import wraps
from flask import request, jsonify


def validate_json(*required_fields):
    """验证JSON请求体包含必填字段"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            data = request.get_json(silent=True)
            if not data:
                return jsonify({'success': False, 'error': '请求体必须为JSON格式'}), 400
            missing = [f for f in required_fields if not data.get(f)]
            if missing:
                return jsonify({'success': False, 'error': f'缺少必填字段: {", ".join(missing)}'}), 400
            return f(*args, **kwargs)
        return wrapper
    return decorator


def validate_rating(value):
    """验证评分范围 1-5"""
    try:
        r = float(value)
        if 1 <= r <= 5:
            return r
    except (TypeError, ValueError):
        pass
    return None


def validate_username(username):
    """验证用户名：3-20字符，仅字母数字下划线"""
    if not username or len(username) < 3 or len(username) > 20:
        return False
    return bool(re.match(r'^[\w\u4e00-\u9fff]+$', username))


def validate_email(email):
    """验证邮箱格式"""
    if not email:
        return True  # 邮箱可选
    return bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email))


def validate_password(password):
    """验证密码：至少6字符"""
    return password and len(password) >= 6


def validate_phone(phone):
    """验证手机号"""
    if not phone:
        return True  # 手机号可选
    return bool(re.match(r'^1[3-9]\d{9}$', phone))


def validate_pagination():
    """从请求参数中提取并验证分页参数"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    return max(1, page), min(max(1, per_page), 100)


def sanitize_string(value, max_length=500):
    """清理字符串：去除首尾空白，限制长度"""
    if not value:
        return ''
    cleaned = str(value).strip()
    # 移除潜在的XSS字符
    cleaned = re.sub(r'<[^>]+>', '', cleaned)
    return cleaned[:max_length]
