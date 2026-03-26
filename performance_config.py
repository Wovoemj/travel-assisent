"""
性能优化配置模块
包含缓存、压缩、资源优化等配置
"""

import os
import hashlib
from datetime import datetime

class PerformanceConfig:
    """性能优化配置"""
    
    # 缓存配置
    CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 300  # 5分钟
    CACHE_KEY_PREFIX = 'travel_assistant_'
    
    # 静态资源配置
    STATIC_FOLDER = 'static'
    STATIC_URL_PATH = '/static'
    
    # 压缩配置
    COMPRESS_MIMETYPES = [
        'text/html',
        'text/css',
        'text/xml',
        'application/json',
        'application/javascript',
        'text/javascript',
        'image/svg+xml'
    ]
    COMPRESS_LEVEL = 6
    COMPRESS_MIN_SIZE = 500
    
    # 资源版本控制
    VERSION = datetime.now().strftime('%Y%m%d%H%M%S')
    
    # CDN配置
    CDN_ENABLED = True
    CDN_BASE_URL = 'https://cdn.jsdelivr.net'
    
    # 懒加载配置
    LAZY_LOAD_ENABLED = True
    LAZY_LOAD_THRESHOLD = 200  # 提前200px加载
    
    # 图片优化配置
    IMAGE_QUALITY = 85
    IMAGE_MAX_WIDTH = 1920
    IMAGE_MAX_HEIGHT = 1080
    
    # 数据库优化配置
    DB_POOL_SIZE = 10
    DB_POOL_RECYCLE = 3600
    DB_POOL_TIMEOUT = 30
    
    # 会话优化
    SESSION_COOKIE_SECURE = False  # 开发环境设为False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    @staticmethod
    def get_version_hash(file_path):
        """获取文件版本哈希"""
        try:
            if os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    content = f.read()
                    return hashlib.md5(content).hexdigest()[:8]
        except:
            pass
        return PerformanceConfig.VERSION
    
    @staticmethod
    def get_static_url(filename, versioned=True):
        """获取静态资源URL，支持版本控制"""
        base_url = f'/static/{filename}'
        if versioned:
            file_path = os.path.join('static', filename)
            version = PerformanceConfig.get_version_hash(file_path)
            return f'{base_url}?v={version}'
        return base_url

class DevelopmentConfig(PerformanceConfig):
    """开发环境配置"""
    DEBUG = True
    CACHE_TYPE = 'simple'
    COMPRESS_DEBUG = True

class ProductionConfig(PerformanceConfig):
    """生产环境配置"""
    DEBUG = False
    CACHE_TYPE = 'redis'  # 生产环境使用Redis
    COMPRESS_DEBUG = False
    SESSION_COOKIE_SECURE = True

# 根据环境选择配置
def get_config():
    env = os.environ.get('FLASK_ENV', 'development')
    if env == 'production':
        return ProductionConfig()
    return DevelopmentConfig()