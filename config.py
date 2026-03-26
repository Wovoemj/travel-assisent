# config.py
import os
from datetime import timedelta


class Config:
    # Flask配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-string-change-in-production'

    # 数据库配置
    SQLALCHEMY_DATABASE_URI = 'sqlite:///travel_destinations.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Session配置
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    SESSION_COOKIE_NAME = 'travel_assistant_session'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = False  # 开发环境设为False，生产环境设为True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # 开发模式标志
    DEBUG_MODE = True  # True=使用模拟登录，False=使用真实登录

    # 微信配置（测试号）
    WECHAT_APP_ID = os.environ.get('WECHAT_APP_ID') or 'wx6b8c1a2d3e4f5g6h'  # 测试号AppID
    WECHAT_APP_SECRET = os.environ.get('WECHAT_APP_SECRET') or 'your_test_app_secret'
    WECHAT_REDIRECT_URI = 'http://127.0.0.1:5000/auth/wechat/callback'

    # QQ配置
    QQ_APP_ID = os.environ.get('QQ_APP_ID') or '101234567'  # 9-10位数字
    QQ_APP_KEY = os.environ.get('QQ_APP_KEY') or 'e38638289ac74edab123456789abcdef'  # 32位
    QQ_REDIRECT_URI = 'http://127.0.0.1:5000/auth/qq/callback'

    # 微博配置
    WEIBO_APP_KEY = os.environ.get('WEIBO_APP_KEY') or 'your_weibo_app_key'
    WEIBO_APP_SECRET = os.environ.get('WEIBO_APP_SECRET') or 'your_weibo_app_secret'
    WEIBO_REDIRECT_URI = 'http://127.0.0.1:5000/auth/weibo/callback'

    # Redis配置（用于存储临时状态）
    REDIS_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'
    REDIS_HOST = 'localhost'
    REDIS_PORT = 6379
    REDIS_DB = 0
    REDIS_PASSWORD = None
    
    # ==================== AI模型配置 ====================
    # 1. DeepSeek配置（首选）
    DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY') or None
    DEEPSEEK_MODEL = os.environ.get('DEEPSEEK_MODEL') or 'deepseek-chat'
    DEEPSEEK_BASE_URL = 'https://api.deepseek.com/v1'
    
    # 2. 火山方舟配置（字节跳动）
    VOLCENGINE_API_KEY = os.environ.get('VOLCENGINE_API_KEY') or None
    VOLCENGINE_MODEL = os.environ.get('VOLCENGINE_MODEL') or 'ep-20240101000000-xxxxx'
    VOLCENGINE_BASE_URL = 'https://ark.cn-beijing.volces.com/api/v3'
    
    # 3. 智谱AI配置
    ZHIPU_API_KEY = os.environ.get('ZHIPU_API_KEY') or None
    ZHIPU_MODEL = os.environ.get('ZHIPU_MODEL') or 'glm-4'
    ZHIPU_BASE_URL = 'https://open.bigmodel.cn/api/paas/v4'
    
    # 4. 阿里云百炼配置（通义千问）
    TONGYI_API_KEY = os.environ.get('TONGYI_API_KEY') or None
    TONGYI_MODEL = os.environ.get('TONGYI_MODEL') or 'qwen-turbo'
    TONGYI_BASE_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
    
    # OpenAI配置（备用）
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY') or None
    OPENAI_BASE_URL = os.environ.get('OPENAI_BASE_URL') or 'https://api.openai.com/v1'
    OPENAI_MODEL = os.environ.get('OPENAI_MODEL') or 'gpt-3.5-turbo'
    
    # Claude配置（备用）
    CLAUDE_API_KEY = os.environ.get('CLAUDE_API_KEY') or None
    CLAUDE_MODEL = os.environ.get('CLAUDE_MODEL') or 'claude-3-sonnet-20240229'
    
    # 默认使用的AI提供商
    DEFAULT_AI_PROVIDER = os.environ.get('DEFAULT_AI_PROVIDER') or 'deepseek'
    
    # 是否启用AI模式（True=使用AI大模型，False=使用规则匹配）
    AI_MODE_ENABLED = os.environ.get('AI_MODE_ENABLED', 'false').lower() == 'true'
    
    # AI调用策略：sequential=顺序调用，fallback=失败切换
    AI_CALL_STRATEGY = os.environ.get('AI_CALL_STRATEGY') or 'sequential'
    
    # AI提供商调用顺序（按优先级排列）
    AI_PROVIDER_ORDER = [
        'deepseek',      # 1. DeepSeek
        'volcengine',    # 2. 火山方舟
        'zhipu',         # 3. 智谱AI
        'tongyi',        # 4. 阿里云百炼
        'openai',        # 5. OpenAI（备用）
        'claude'         # 6. Claude（备用）
    ]
