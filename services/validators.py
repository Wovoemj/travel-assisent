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


def validate_json_optional(*optional_fields):
    """验证JSON请求体（可选字段模式，允许空请求体）"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            data = request.get_json(silent=True)
            if data is None:
                data = {}
            request._validated_data = data
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


def validate_positive_int(value, field_name, default=None, min_val=1, max_val=None):
    """验证正整数参数"""
    if value is None:
        if default is not None:
            return default
        return None, f'缺少参数: {field_name}'
    try:
        n = int(value)
        if n < min_val:
            return None, f'{field_name}不能小于{min_val}'
        if max_val is not None and n > max_val:
            return None, f'{field_name}不能大于{max_val}'
        return n, None
    except (TypeError, ValueError):
        return None, f'{field_name}必须是整数'


def validate_float(value, field_name, default=None, min_val=None, max_val=None):
    """验证浮点数参数"""
    if value is None:
        if default is not None:
            return default
        return None, f'缺少参数: {field_name}'
    try:
        n = float(value)
        if min_val is not None and n < min_val:
            return None, f'{field_name}不能小于{min_val}'
        if max_val is not None and n > max_val:
            return None, f'{field_name}不能大于{max_val}'
        return n, None
    except (TypeError, ValueError):
        return None, f'{field_name}必须是数字'


def validate_date(value, field_name, fmt='%Y-%m-%d'):
    """验证日期格式"""
    if not value:
        return None, f'缺少参数: {field_name}'
    try:
        from datetime import datetime
        return datetime.strptime(value, fmt).date(), None
    except ValueError:
        return None, f'{field_name}格式不正确，应为{fmt}'


def validate_time(value, field_name, fmt='%H:%M'):
    """验证时间格式"""
    if not value:
        return None, None  # 时间字段可选
    try:
        from datetime import datetime
        return datetime.strptime(value, fmt).time(), None
    except ValueError:
        return None, f'{field_name}格式不正确，应为{fmt}'


def validate_choice(value, field_name, choices, default=None):
    """验证枚举选择"""
    if value is None:
        return default, None
    if value not in choices:
        return None, f'{field_name}必须是以下之一: {", ".join(choices)}'
    return value, None


def validate_string(value, field_name, min_len=0, max_len=500, required=False):
    """验证字符串参数"""
    if not value or not str(value).strip():
        if required:
            return None, f'{field_name}不能为空'
        return '', None
    cleaned = sanitize_string(str(value), max_len)
    if len(cleaned) < min_len:
        return None, f'{field_name}长度不能少于{min_len}个字符'
    return cleaned, None


def sanitize_string(value, max_length=500):
    """清理字符串：去除首尾空白，限制长度"""
    if not value:
        return ''
    cleaned = str(value).strip()
    # 移除潜在的XSS字符
    cleaned = re.sub(r'<[^>]+>', '', cleaned)
    return cleaned[:max_length]


def validate_request_json():
    """装饰器：确保请求体是JSON格式"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            data = request.get_json(silent=True)
            if data is None:
                return jsonify({'success': False, 'error': '请求体必须为JSON格式'}), 400
            request._json_data = data
            return f(*args, **kwargs)
        return wrapper
    return decorator


def get_json_data():
    """获取已验证的JSON数据"""
    return getattr(request, '_json_data', request.get_json(silent=True) or {})


def error_response(message, code=400):
    """统一错误响应"""
    return jsonify({'success': False, 'error': message}), code


def success_response(data=None, message=None):
    """统一成功响应"""
    resp = {'success': True}
    if message:
        resp['message'] = message
    if data is not None:
        if isinstance(data, dict):
            resp.update(data)
        else:
            resp['data'] = data
    return jsonify(resp)
