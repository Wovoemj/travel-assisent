"""
社交登录模块 - 提供微信、QQ、微博登录功能
"""
import uuid
import time
import json
from datetime import datetime, timedelta

# 尝试导入redis，如果不可用则使用内存存储
try:
    import redis
    redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    REDIS_AVAILABLE = True
except:
    REDIS_AVAILABLE = False
    # 内存存储作为后备
    _state_storage = {}

def generate_state():
    """生成随机state参数"""
    return str(uuid.uuid4())

def save_state(state, provider):
    """保存state到存储"""
    if REDIS_AVAILABLE:
        try:
            redis_client.setex(f"oauth_state:{state}", 600, provider)  # 10分钟过期
        except:
            _state_storage[state] = {'provider': provider, 'expire': time.time() + 600}
    else:
        _state_storage[state] = {'provider': provider, 'expire': time.time() + 600}

def verify_state(state, provider):
    """验证state参数"""
    if REDIS_AVAILABLE:
        try:
            saved_provider = redis_client.get(f"oauth_state:{state}")
            if saved_provider == provider:
                redis_client.delete(f"oauth_state:{state}")
                return True
        except:
            pass
    
    # 使用内存存储
    if state in _state_storage:
        data = _state_storage[state]
        if data['provider'] == provider and time.time() < data['expire']:
            del _state_storage[state]
            return True
    
    return False

class WeChatLogin:
    """微信登录"""
    
    @staticmethod
    def get_qr_code_url(state):
        """获取微信登录二维码URL"""
        from config import Config
        app_id = Config.WECHAT_APP_ID
        redirect_uri = Config.WECHAT_REDIRECT_URI
        scope = 'snsapi_login'
        
        url = f"https://open.weixin.qq.com/connect/qrconnect?appid={app_id}&redirect_uri={redirect_uri}&response_type=code&scope={scope}&state={state}#wechat_redirect"
        return url
    
    @staticmethod
    def get_access_token(code):
        """获取access_token"""
        from config import Config
        import requests
        
        url = "https://api.weixin.qq.com/sns/oauth2/access_token"
        params = {
            'appid': Config.WECHAT_APP_ID,
            'secret': Config.WECHAT_APP_SECRET,
            'code': code,
            'grant_type': 'authorization_code'
        }
        
        try:
            resp = requests.get(url, params=params, timeout=10)
            return resp.json()
        except Exception as e:
            print(f"获取微信access_token失败: {e}")
            return {'errcode': -1, 'errmsg': str(e)}
    
    @staticmethod
    def get_user_info(access_token, openid):
        """获取用户信息"""
        import requests
        
        url = "https://api.weixin.qq.com/sns/userinfo"
        params = {
            'access_token': access_token,
            'openid': openid,
            'lang': 'zh_CN'
        }
        
        try:
            resp = requests.get(url, params=params, timeout=10)
            return resp.json()
        except Exception as e:
            print(f"获取微信用户信息失败: {e}")
            return {}

class QQLogin:
    """QQ登录"""
    
    @staticmethod
    def get_qr_code_html(state):
        """获取QQ登录二维码HTML"""
        from config import Config
        app_id = Config.QQ_APP_ID
        redirect_uri = Config.QQ_REDIRECT_URI
        
        html = f"""
        <html>
        <head><title>QQ登录</title></head>
        <body>
            <script>
                window.location.href = "https://graph.qq.com/oauth2.0/authorize?response_type=code&client_id={app_id}&redirect_uri={encodeURIComponent('{redirect_uri}')}&state={state}&scope=get_user_info";
            </script>
        </body>
        </html>
        """
        return html
    
    @staticmethod
    def get_access_token(code):
        """获取access_token"""
        from config import Config
        import requests
        
        url = "https://graph.qq.com/oauth2.0/token"
        params = {
            'grant_type': 'authorization_code',
            'client_id': Config.QQ_APP_ID,
            'client_secret': Config.QQ_APP_KEY,
            'code': code,
            'redirect_uri': Config.QQ_REDIRECT_URI
        }
        
        try:
            resp = requests.get(url, params=params, timeout=10)
            # QQ返回的是query string格式
            result = {}
            for item in resp.text.split('&'):
                if '=' in item:
                    key, value = item.split('=', 1)
                    result[key] = value
            return result
        except Exception as e:
            print(f"获取QQ access_token失败: {e}")
            return {}
    
    @staticmethod
    def get_openid(access_token):
        """获取openid"""
        import requests
        
        url = f"https://graph.qq.com/oauth2.0/me?access_token={access_token}"
        
        try:
            resp = requests.get(url, timeout=10)
            # 解析返回的JSONP格式
            text = resp.text
            if 'callback' in text:
                import re
                match = re.search(r'callback\((.*?)\);', text)
                if match:
                    data = json.loads(match.group(1))
                    return data
            return {}
        except Exception as e:
            print(f"获取QQ openid失败: {e}")
            return {}
    
    @staticmethod
    def get_user_info(access_token, openid):
        """获取用户信息"""
        from config import Config
        import requests
        
        url = "https://graph.qq.com/user/get_user_info"
        params = {
            'access_token': access_token,
            'oauth_consumer_key': Config.QQ_APP_ID,
            'openid': openid
        }
        
        try:
            resp = requests.get(url, params=params, timeout=10)
            return resp.json()
        except Exception as e:
            print(f"获取QQ用户信息失败: {e}")
            return {}

class WeiBoLogin:
    """微博登录"""
    
    @staticmethod
    def get_qr_code_html(state):
        """获取微博登录二维码HTML"""
        from config import Config
        app_key = Config.WEIBO_APP_KEY
        redirect_uri = Config.WEIBO_REDIRECT_URI
        
        html = f"""
        <html>
        <head><title>微博登录</title></head>
        <body>
            <script>
                window.location.href = "https://api.weibo.com/oauth2/authorize?client_id={app_key}&response_type=code&redirect_uri={encodeURIComponent('{redirect_uri}')}&state={state}";
            </script>
        </body>
        </html>
        """
        return html
    
    @staticmethod
    def get_access_token(code):
        """获取access_token"""
        from config import Config
        import requests
        
        url = "https://api.weibo.com/oauth2/access_token"
        data = {
            'client_id': Config.WEIBO_APP_KEY,
            'client_secret': Config.WEIBO_APP_SECRET,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': Config.WEIBO_REDIRECT_URI
        }
        
        try:
            resp = requests.post(url, data=data, timeout=10)
            return resp.json()
        except Exception as e:
            print(f"获取微博access_token失败: {e}")
            return {}
    
    @staticmethod
    def get_user_info(access_token, uid):
        """获取用户信息"""
        import requests
        
        url = "https://api.weibo.com/2/users/show.json"
        params = {
            'access_token': access_token,
            'uid': uid
        }
        
        try:
            resp = requests.get(url, params=params, timeout=10)
            return resp.json()
        except Exception as e:
            print(f"获取微博用户信息失败: {e}")
            return {}