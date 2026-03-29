# config.py
import os
from dotenv import load_dotenv
from datetime import timedelta

# 加载 .env 文件
load_dotenv()


class Config:
    # Flask配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-string-change-in-production'

    # 数据库配置
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///travel_destinations.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Session配置
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    SESSION_COOKIE_NAME = 'travel_assistant_session'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
    SESSION_COOKIE_SAMESITE = 'Lax'

    # 开发模式标志
    DEBUG_MODE = os.environ.get('DEBUG_MODE', 'true').lower() == 'true'

    # 微信配置
    WECHAT_APP_ID = os.environ.get('WECHAT_APP_ID')
    WECHAT_APP_SECRET = os.environ.get('WECHAT_APP_SECRET')
    WECHAT_REDIRECT_URI = os.environ.get('WECHAT_REDIRECT_URI', 'http://127.0.0.1:5000/auth/wechat/callback')

    # QQ配置
    QQ_APP_ID = os.environ.get('QQ_APP_ID')
    QQ_APP_KEY = os.environ.get('QQ_APP_KEY')
    QQ_REDIRECT_URI = os.environ.get('QQ_REDIRECT_URI', 'http://127.0.0.1:5000/auth/qq/callback')

    # 微博配置
    WEIBO_APP_KEY = os.environ.get('WEIBO_APP_KEY')
    WEIBO_APP_SECRET = os.environ.get('WEIBO_APP_SECRET')
    WEIBO_REDIRECT_URI = os.environ.get('WEIBO_REDIRECT_URI', 'http://127.0.0.1:5000/auth/weibo/callback')

    # Redis配置
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
    REDIS_DB = int(os.environ.get('REDIS_DB', 0))
    REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD')

    # ==================== AI模型配置 ====================
    # 1. DeepSeek配置（首选）
    DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
    DEEPSEEK_MODEL = os.environ.get('DEEPSEEK_MODEL', 'deepseek-chat')
    DEEPSEEK_BASE_URL = os.environ.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com/v1')

    # 2. 火山方舟配置
    VOLCENGINE_API_KEY = os.environ.get('VOLCENGINE_API_KEY')
    VOLCENGINE_MODEL = os.environ.get('VOLCENGINE_MODEL', 'ep-20240101000000-xxxxx')
    VOLCENGINE_BASE_URL = os.environ.get('VOLCENGINE_BASE_URL', 'https://ark.cn-beijing.volces.com/api/v3')

    # 3. 智谱AI配置
    ZHIPU_API_KEY = os.environ.get('ZHIPU_API_KEY')
    ZHIPU_MODEL = os.environ.get('ZHIPU_MODEL', 'glm-4')
    ZHIPU_BASE_URL = os.environ.get('ZHIPU_BASE_URL', 'https://open.bigmodel.cn/api/paas/v4')

    # 4. 阿里云百炼配置
    TONGYI_API_KEY = os.environ.get('TONGYI_API_KEY')
    TONGYI_MODEL = os.environ.get('TONGYI_MODEL', 'qwen-turbo')
    TONGYI_BASE_URL = os.environ.get('TONGYI_BASE_URL', 'https://dashscope.aliyuncs.com/compatible-mode/v1')

    # OpenAI配置（备用）
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    OPENAI_BASE_URL = os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com/v1')
    OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-3.5-turbo')

    # Claude配置（备用）
    CLAUDE_API_KEY = os.environ.get('CLAUDE_API_KEY')
    CLAUDE_MODEL = os.environ.get('CLAUDE_MODEL', 'claude-3-sonnet-20240229')

    # 默认使用的AI提供商
    DEFAULT_AI_PROVIDER = os.environ.get('DEFAULT_AI_PROVIDER', 'deepseek')

    # 是否启用AI模式
    AI_MODE_ENABLED = os.environ.get('AI_MODE_ENABLED', 'false').lower() == 'true'

    # AI调用策略
    AI_CALL_STRATEGY = os.environ.get('AI_CALL_STRATEGY', 'sequential')

    # AI提供商调用顺序
    AI_PROVIDER_ORDER = [
        'deepseek',
        'volcengine',
        'zhipu',
        'tongyi',
        'openai',
        'claude'
    ]
