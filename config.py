# config.py - 应用配置 (全部走环境变量)
import os
from datetime import timedelta

# 加载 .env 文件 (如果存在)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def env_bool(key, default=False):
    """解析布尔型环境变量"""
    val = os.environ.get(key, str(default)).lower()
    return val in ('true', '1', 'yes')


def env_int(key, default=0):
    """解析整型环境变量"""
    try:
        return int(os.environ.get(key, default))
    except (ValueError, TypeError):
        return default


def env_list(key, default=None):
    """解析逗号分隔的列表环境变量"""
    val = os.environ.get(key)
    if val:
        return [v.strip() for v in val.split(',')]
    return default or []


class Config:
    # ==================== Flask 核心 ====================
    SECRET_KEY = os.environ.get('SECRET_KEY', 'hard-to-guess-string-change-in-production')
    DEBUG = env_bool('FLASK_DEBUG', True)

    # ==================== 数据库 ====================
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URI', 'sqlite:///travel_destinations.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ==================== Session ====================
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    SESSION_COOKIE_NAME = 'travel_assistant_session'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = env_bool('SESSION_COOKIE_SECURE', False)
    SESSION_COOKIE_SAMESITE = os.environ.get('SESSION_COOKIE_SAMESITE', 'Lax')

    # ==================== 开发模式 ====================
    DEBUG_MODE = env_bool('DEBUG_MODE', True)

    # ==================== 微信 ====================
    WECHAT_APP_ID = os.environ.get('WECHAT_APP_ID', '')
    WECHAT_APP_SECRET = os.environ.get('WECHAT_APP_SECRET', '')
    WECHAT_REDIRECT_URI = os.environ.get('WECHAT_REDIRECT_URI', 'http://127.0.0.1:5000/auth/wechat/callback')

    # ==================== QQ ====================
    QQ_APP_ID = os.environ.get('QQ_APP_ID', '')
    QQ_APP_KEY = os.environ.get('QQ_APP_KEY', '')
    QQ_REDIRECT_URI = os.environ.get('QQ_REDIRECT_URI', 'http://127.0.0.1:5000/auth/qq/callback')

    # ==================== 微博 ====================
    WEIBO_APP_KEY = os.environ.get('WEIBO_APP_KEY', '')
    WEIBO_APP_SECRET = os.environ.get('WEIBO_APP_SECRET', '')
    WEIBO_REDIRECT_URI = os.environ.get('WEIBO_REDIRECT_URI', 'http://127.0.0.1:5000/auth/weibo/callback')

    # ==================== Redis ====================
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

    # ==================== AI 模型 ====================
    # DeepSeek
    DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
    DEEPSEEK_MODEL = os.environ.get('DEEPSEEK_MODEL', 'deepseek-chat')
    DEEPSEEK_BASE_URL = os.environ.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com/v1')

    # 火山方舟
    VOLCENGINE_API_KEY = os.environ.get('VOLCENGINE_API_KEY')
    VOLCENGINE_MODEL = os.environ.get('VOLCENGINE_MODEL', 'ep-20240101000000-xxxxx')
    VOLCENGINE_BASE_URL = os.environ.get('VOLCENGINE_BASE_URL', 'https://ark.cn-beijing.volces.com/api/v3')

    # 智谱 AI
    ZHIPU_API_KEY = os.environ.get('ZHIPU_API_KEY')
    ZHIPU_MODEL = os.environ.get('ZHIPU_MODEL', 'glm-4')
    ZHIPU_BASE_URL = os.environ.get('ZHIPU_BASE_URL', 'https://open.bigmodel.cn/api/paas/v4')

    # 阿里云百炼
    TONGYI_API_KEY = os.environ.get('TONGYI_API_KEY')
    TONGYI_MODEL = os.environ.get('TONGYI_MODEL', 'qwen-turbo')
    TONGYI_BASE_URL = os.environ.get('TONGYI_BASE_URL', 'https://dashscope.aliyuncs.com/compatible-mode/v1')

    # OpenAI
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    OPENAI_BASE_URL = os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com/v1')
    OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-3.5-turbo')

    # Claude
    CLAUDE_API_KEY = os.environ.get('CLAUDE_API_KEY')
    CLAUDE_MODEL = os.environ.get('CLAUDE_MODEL', 'claude-3-sonnet-20240229')

    # AI 策略
    DEFAULT_AI_PROVIDER = os.environ.get('DEFAULT_AI_PROVIDER', 'deepseek')
    AI_MODE_ENABLED = env_bool('AI_MODE_ENABLED', False)
    AI_CALL_STRATEGY = os.environ.get('AI_CALL_STRATEGY', 'sequential')
    AI_PROVIDER_ORDER = [
        'deepseek', 'volcengine', 'zhipu', 'tongyi', 'openai', 'claude'
    ]
