"""
AI大模型管理器
支持多种AI模型：OpenAI、Claude、文心一言、通义千问、智谱AI等
"""

import os
import json
import time
import requests
from typing import List, Dict, Optional, Generator
from abc import ABC, abstractmethod


class BaseModelProvider(ABC):
    """AI模型基类"""
    
    def __init__(self, api_key: str, model: str = None):
        self.api_key = api_key
        self.model = model
        self.provider_name = self.__class__.__name__
    
    @abstractmethod
    def chat(self, messages: List[Dict], **kwargs) -> str:
        """同步对话"""
        pass
    
    @abstractmethod
    def chat_stream(self, messages: List[Dict], **kwargs) -> Generator[str, None, None]:
        """流式对话"""
        pass
    
    def validate_config(self) -> bool:
        """验证配置是否有效"""
        return bool(self.api_key)


class OpenAIProvider(BaseModelProvider):
    """OpenAI模型提供商"""
    
    def __init__(self, api_key: str, model: str = "gpt-3.5-turbo", base_url: str = None):
        super().__init__(api_key, model)
        self.base_url = base_url or "https://api.openai.com/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def chat(self, messages: List[Dict], **kwargs) -> str:
        """同步对话"""
        try:
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": kwargs.get('temperature', 0.7),
                "max_tokens": kwargs.get('max_tokens', 2000),
                "top_p": kwargs.get('top_p', 1.0),
                "frequency_penalty": kwargs.get('frequency_penalty', 0),
                "presence_penalty': kwargs.get('presence_penalty', 0)
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                error_msg = f"OpenAI API错误: {response.status_code} - {response.text}"
                print(error_msg)
                return error_msg
                
        except Exception as e:
            error_msg = f"OpenAI调用失败: {str(e)}"
            print(error_msg)
            return error_msg
    
    def chat_stream(self, messages: List[Dict], **kwargs) -> Generator[str, None, None]:
        """流式对话"""
        try:
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": kwargs.get('temperature', 0.7),
                "max_tokens": kwargs.get('max_tokens', 2000),
                "stream": True
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                stream=True,
                timeout=60
            )
            
            if response.status_code == 200:
                for line in response.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        if line.startswith('data: '):
                            data = line[6:]
                            if data.strip() == '[DONE]':
                                break
                            try:
                                chunk = json.loads(data)
                                if 'choices' in chunk and len(chunk['choices']) > 0:
                                    delta = chunk['choices'][0].get('delta', {})
                                    if 'content' in delta:
                                        yield delta['content']
                            except json.JSONDecodeError:
                                continue
            else:
                yield f"OpenAI API错误: {response.status_code}"
                
        except Exception as e:
            yield f"OpenAI流式调用失败: {str(e)}"


class ClaudeProvider(BaseModelProvider):
    """Claude模型提供商"""
    
    def __init__(self, api_key: str, model: str = "claude-3-sonnet-20240229"):
        super().__init__(api_key, model)
        self.base_url = "https://api.anthropic.com/v1"
        self.headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
    
    def chat(self, messages: List[Dict], **kwargs) -> str:
        """同步对话"""
        try:
            # 转换消息格式
            system_message = ""
            user_messages = []
            
            for msg in messages:
                if msg['role'] == 'system':
                    system_message = msg['content']
                else:
                    user_messages.append(msg)
            
            payload = {
                "model": self.model,
                "max_tokens": kwargs.get('max_tokens', 2000),
                "messages": user_messages
            }
            
            if system_message:
                payload["system"] = system_message
            
            response = requests.post(
                f"{self.base_url}/messages",
                headers=self.headers,
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['content'][0]['text']
            else:
                error_msg = f"Claude API错误: {response.status_code} - {response.text}"
                print(error_msg)
                return error_msg
                
        except Exception as e:
            error_msg = f"Claude调用失败: {str(e)}"
            print(error_msg)
            return error_msg
    
    def chat_stream(self, messages: List[Dict], **kwargs) -> Generator[str, None, None]:
        """流式对话"""
        # Claude的流式API需要特殊处理，这里简化实现
        response = self.chat(messages, **kwargs)
        # 模拟流式输出
        for char in response:
            yield char
            time.sleep(0.02)


class TongyiProvider(BaseModelProvider):
    """通义千问模型提供商"""
    
    def __init__(self, api_key: str, model: str = "qwen-turbo"):
        super().__init__(api_key, model)
        self.base_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def chat(self, messages: List[Dict], **kwargs) -> str:
        """同步对话"""
        try:
            payload = {
                "model": self.model,
                "input": {
                    "messages": messages
                },
                "parameters": {
                    "temperature": kwargs.get('temperature', 0.7),
                    "top_p": kwargs.get('top_p', 0.8),
                    "max_tokens": kwargs.get('max_tokens', 2000)
                }
            }
            
            response = requests.post(
                self.base_url,
                headers=self.headers,
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['output']['text']
            else:
                error_msg = f"通义千问API错误: {response.status_code} - {response.text}"
                print(error_msg)
                return error_msg
                
        except Exception as e:
            error_msg = f"通义千问调用失败: {str(e)}"
            print(error_msg)
            return error_msg
    
    def chat_stream(self, messages: List[Dict], **kwargs) -> Generator[str, None, None]:
        """流式对话"""
        response = self.chat(messages, **kwargs)
        # 模拟流式输出
        for char in response:
            yield char
            time.sleep(0.02)


class DeepSeekProvider(BaseModelProvider):
    """DeepSeek模型提供商"""
    
    def __init__(self, api_key: str, model: str = "deepseek-chat", base_url: str = None):
        super().__init__(api_key, model)
        self.base_url = base_url or "https://api.deepseek.com/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def chat(self, messages: List[Dict], **kwargs) -> str:
        """同步对话"""
        try:
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": kwargs.get('temperature', 0.7),
                "max_tokens": kwargs.get('max_tokens', 2000),
                "stream": False
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                error_msg = f"DeepSeek API错误: {response.status_code} - {response.text}"
                print(error_msg)
                return error_msg
                
        except Exception as e:
            error_msg = f"DeepSeek调用失败: {str(e)}"
            print(error_msg)
            return error_msg
    
    def chat_stream(self, messages: List[Dict], **kwargs) -> Generator[str, None, None]:
        """流式对话"""
        try:
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": kwargs.get('temperature', 0.7),
                "max_tokens": kwargs.get('max_tokens', 2000),
                "stream": True
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                stream=True,
                timeout=60
            )
            
            if response.status_code == 200:
                for line in response.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        if line.startswith('data: '):
                            data = line[6:]
                            if data.strip() == '[DONE]':
                                break
                            try:
                                chunk = json.loads(data)
                                if 'choices' in chunk and len(chunk['choices']) > 0:
                                    delta = chunk['choices'][0].get('delta', {})
                                    if 'content' in delta:
                                        yield delta['content']
                            except json.JSONDecodeError:
                                continue
            else:
                yield f"DeepSeek API错误: {response.status_code}"
                
        except Exception as e:
            yield f"DeepSeek流式调用失败: {str(e)}"


class VolcengineProvider(BaseModelProvider):
    """火山方舟模型提供商（字节跳动）"""
    
    def __init__(self, api_key: str, model: str, base_url: str = None):
        super().__init__(api_key, model)
        self.base_url = base_url or "https://ark.cn-beijing.volces.com/api/v3"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def chat(self, messages: List[Dict], **kwargs) -> str:
        """同步对话"""
        try:
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": kwargs.get('temperature', 0.7),
                "max_tokens": kwargs.get('max_tokens', 2000)
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                error_msg = f"火山方舟 API错误: {response.status_code} - {response.text}"
                print(error_msg)
                return error_msg
                
        except Exception as e:
            error_msg = f"火山方舟调用失败: {str(e)}"
            print(error_msg)
            return error_msg
    
    def chat_stream(self, messages: List[Dict], **kwargs) -> Generator[str, None, None]:
        """流式对话"""
        response = self.chat(messages, **kwargs)
        # 模拟流式输出
        for char in response:
            yield char
            time.sleep(0.02)


class ZhipuProvider(BaseModelProvider):
    """智谱AI模型提供商"""
    
    def __init__(self, api_key: str, model: str = "glm-4", base_url: str = None):
        super().__init__(api_key, model)
        self.base_url = base_url or "https://open.bigmodel.cn/api/paas/v4"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def chat(self, messages: List[Dict], **kwargs) -> str:
        """同步对话"""
        try:
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": kwargs.get('temperature', 0.7),
                "top_p": kwargs.get('top_p', 0.8),
                "max_tokens": kwargs.get('max_tokens', 2000)
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                error_msg = f"智谱AI API错误: {response.status_code} - {response.text}"
                print(error_msg)
                return error_msg
                
        except Exception as e:
            error_msg = f"智谱AI调用失败: {str(e)}"
            print(error_msg)
            return error_msg
    
    def chat_stream(self, messages: List[Dict], **kwargs) -> Generator[str, None, None]:
        """流式对话"""
        response = self.chat(messages, **kwargs)
        # 模拟流式输出
        for char in response:
            yield char
            time.sleep(0.02)


class TongyiProvider(BaseModelProvider):
    """通义千问模型提供商（阿里云百炼）"""
    
    def __init__(self, api_key: str, model: str = "qwen-turbo", base_url: str = None):
        super().__init__(api_key, model)
        self.base_url = base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def chat(self, messages: List[Dict], **kwargs) -> str:
        """同步对话"""
        try:
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": kwargs.get('temperature', 0.7),
                "max_tokens": kwargs.get('max_tokens', 2000)
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                error_msg = f"通义千问 API错误: {response.status_code} - {response.text}"
                print(error_msg)
                return error_msg
                
        except Exception as e:
            error_msg = f"通义千问调用失败: {str(e)}"
            print(error_msg)
            return error_msg
    
    def chat_stream(self, messages: List[Dict], **kwargs) -> Generator[str, None, None]:
        """流式对话"""
        response = self.chat(messages, **kwargs)
        # 模拟流式输出
        for char in response:
            yield char
            time.sleep(0.02)


class AIModelManager:
    """AI模型管理器 - 支持顺序调用和自动切换"""
    
    def __init__(self):
        self.providers = {}
        self.default_provider = None
        self.provider_order = []  # 提供商调用顺序
        self.current_provider_index = 0  # 当前使用的提供商索引
        self._initialize_providers()
    
    def _initialize_providers(self):
        """初始化所有可用的模型提供商"""
        from config import Config
        
        # 获取配置的提供商顺序
        self.provider_order = getattr(Config, 'AI_PROVIDER_ORDER', [
            'deepseek', 'volcengine', 'zhipu', 'tongyi', 'openai', 'claude'
        ])
        
        # 1. DeepSeek（首选）
        deepseek_key = os.environ.get('DEEPSEEK_API_KEY') or getattr(Config, 'DEEPSEEK_API_KEY', None)
        if deepseek_key:
            deepseek_model = os.environ.get('DEEPSEEK_MODEL') or getattr(Config, 'DEEPSEEK_MODEL', 'deepseek-chat')
            deepseek_base_url = getattr(Config, 'DEEPSEEK_BASE_URL', None)
            self.providers['deepseek'] = DeepSeekProvider(deepseek_key, deepseek_model, deepseek_base_url)
        
        # 2. 火山方舟（字节跳动）
        volcengine_key = os.environ.get('VOLCENGINE_API_KEY') or getattr(Config, 'VOLCENGINE_API_KEY', None)
        if volcengine_key:
            volcengine_model = os.environ.get('VOLCENGINE_MODEL') or getattr(Config, 'VOLCENGINE_MODEL', 'ep-20240101000000-xxxxx')
            volcengine_base_url = getattr(Config, 'VOLCENGINE_BASE_URL', None)
            self.providers['volcengine'] = VolcengineProvider(volcengine_key, volcengine_model, volcengine_base_url)
        
        # 3. 智谱AI
        zhipu_key = os.environ.get('ZHIPU_API_KEY') or getattr(Config, 'ZHIPU_API_KEY', None)
        if zhipu_key:
            zhipu_model = os.environ.get('ZHIPU_MODEL') or getattr(Config, 'ZHIPU_MODEL', 'glm-4')
            zhipu_base_url = getattr(Config, 'ZHIPU_BASE_URL', None)
            self.providers['zhipu'] = ZhipuProvider(zhipu_key, zhipu_model, zhipu_base_url)
        
        # 4. 阿里云百炼（通义千问）
        tongyi_key = os.environ.get('TONGYI_API_KEY') or getattr(Config, 'TONGYI_API_KEY', None)
        if tongyi_key:
            tongyi_model = os.environ.get('TONGYI_MODEL') or getattr(Config, 'TONGYI_MODEL', 'qwen-turbo')
            tongyi_base_url = getattr(Config, 'TONGYI_BASE_URL', None)
            self.providers['tongyi'] = TongyiProvider(tongyi_key, tongyi_model, tongyi_base_url)
        
        # 6. OpenAI（备用）
        openai_key = os.environ.get('OPENAI_API_KEY') or getattr(Config, 'OPENAI_API_KEY', None)
        if openai_key:
            openai_base_url = os.environ.get('OPENAI_BASE_URL') or getattr(Config, 'OPENAI_BASE_URL', None)
            openai_model = os.environ.get('OPENAI_MODEL') or getattr(Config, 'OPENAI_MODEL', 'gpt-3.5-turbo')
            self.providers['openai'] = OpenAIProvider(openai_key, openai_model, openai_base_url)
        
        # 7. Claude（备用）
        claude_key = os.environ.get('CLAUDE_API_KEY') or getattr(Config, 'CLAUDE_API_KEY', None)
        if claude_key:
            claude_model = os.environ.get('CLAUDE_MODEL') or getattr(Config, 'CLAUDE_MODEL', 'claude-3-sonnet-20240229')
            self.providers['claude'] = ClaudeProvider(claude_key, claude_model)
        
        # 按照配置的顺序设置默认提供商
        for provider_name in self.provider_order:
            if provider_name in self.providers:
                self.default_provider = provider_name
                break
        
        print(f"✅ 已初始化 {len(self.providers)} 个AI模型提供商")
        print(f"📋 调用顺序: {self.provider_order}")
        print(f"🎯 当前使用: {self.default_provider}")
    
    def get_provider(self, provider_name: str = None) -> Optional[BaseModelProvider]:
        """获取指定的模型提供商"""
        if provider_name and provider_name in self.providers:
            return self.providers[provider_name]
        elif self.default_provider:
            return self.providers.get(self.default_provider)
        elif self.providers:
            return list(self.providers.values())[0]
        else:
            return None
    
    def get_next_provider(self) -> Optional[BaseModelProvider]:
        """获取下一个可用的提供商（用于顺序调用）"""
        available_providers = [p for p in self.provider_order if p in self.providers]
        
        if not available_providers:
            return None
        
        # 找到当前提供商的位置
        current_name = self.default_provider
        if current_name in available_providers:
            current_index = available_providers.index(current_name)
            # 尝试下一个提供商
            next_index = (current_index + 1) % len(available_providers)
            next_name = available_providers[next_index]
            return self.providers.get(next_name)
        
        # 如果当前提供商不在可用列表中，返回第一个可用的
        return self.providers.get(available_providers[0])
    
    def chat(self, messages: List[Dict], provider_name: str = None, **kwargs) -> str:
        """使用指定模型进行对话（支持顺序调用和自动切换）"""
        from config import Config
        
        strategy = getattr(Config, 'AI_CALL_STRATEGY', 'sequential')
        
        if strategy == 'sequential':
            # 顺序调用模式：尝试所有提供商直到成功
            providers_to_try = []
            if provider_name and provider_name in self.providers:
                providers_to_try = [provider_name]
            else:
                providers_to_try = [p for p in self.provider_order if p in self.providers]
            
            last_error = None
            for p_name in providers_to_try:
                provider = self.providers.get(p_name)
                if not provider:
                    continue
                
                try:
                    result = provider.chat(messages, **kwargs)
                    # 检查是否是额度用完的错误
                    if any(error_keyword in result for error_keyword in ['quota', 'limit', 'exceeded', '额度', '限制', '429', '403']):
                        print(f"⚠️ {p_name} 额度用完，切换到下一个提供商")
                        continue
                    
                    # 成功调用，更新当前提供商
                    self.default_provider = p_name
                    return result
                except Exception as e:
                    last_error = str(e)
                    print(f"⚠️ {p_name} 调用失败: {e}")
                    continue
            
            return f"❌ 所有AI模型提供商均不可用。最后错误: {last_error}"
        
        else:
            # 默认模式：使用指定或默认提供商
            provider = self.get_provider(provider_name)
            if not provider:
                return "❌ 未找到可用的AI模型提供商，请配置API密钥"
            
            try:
                return provider.chat(messages, **kwargs)
            except Exception as e:
                error_msg = f"AI模型调用失败: {str(e)}"
                print(error_msg)
                return error_msg
    
    def chat_stream(self, messages: List[Dict], provider_name: str = None, **kwargs) -> Generator[str, None, None]:
        """使用指定模型进行流式对话"""
        provider = self.get_provider(provider_name)
        if not provider:
            yield "❌ 未找到可用的AI模型提供商，请配置API密钥"
            return
        
        try:
            yield from provider.chat_stream(messages, **kwargs)
        except Exception as e:
            yield f"AI模型流式调用失败: {str(e)}"
    
    def get_available_providers(self) -> List[str]:
        """获取所有可用的模型提供商列表"""
        return list(self.providers.keys())
    
    def get_provider_info(self) -> Dict:
        """获取所有提供商的详细信息"""
        info = {}
        for name, provider in self.providers.items():
            info[name] = {
                'provider': provider.provider_name,
                'model': provider.model,
                'available': provider.validate_config(),
                'in_order': name in self.provider_order
            }
        return info
    
    def switch_default_provider(self, provider_name: str) -> bool:
        """切换默认模型提供商"""
        if provider_name in self.providers:
            self.default_provider = provider_name
            print(f"✅ 已切换默认模型提供商为: {provider_name}")
            return True
        return False
    
    def get_call_status(self) -> Dict:
        """获取调用状态信息"""
        return {
            'current_provider': self.default_provider,
            'provider_order': self.provider_order,
            'available_providers': list(self.providers.keys()),
            'total_providers': len(self.providers)
        }


# 全局AI模型管理器实例
ai_model_manager = AIModelManager()


def get_ai_response(message: str, context: List[Dict] = None, provider: str = None) -> str:
    """获取AI响应（便捷函数）"""
    messages = context or []
    
    # 添加系统提示
    system_prompt = {
        "role": "system",
        "content": """你是智能旅游助手，专门为中国游客提供旅游相关的帮助。你的主要职责包括：

1. 景点推荐和介绍
2. 旅游行程规划
3. 天气查询和穿衣建议
4. 美食推荐
5. 交通和住宿建议
6. 旅游注意事项和实用信息

请用友好、专业的语气回答用户的问题，并尽可能提供详细、实用的建议。
如果用户的问题超出旅游范围，请礼貌地引导用户回到旅游相关话题。"""
    }
    
    # 确保系统提示在最前面
    if not messages or messages[0].get('role') != 'system':
        messages.insert(0, system_prompt)
    
    # 添加用户消息
    messages.append({"role": "user", "content": message})
    
    # 保持对话历史在合理长度（保留最近10轮对话）
    if len(messages) > 21:  # 系统提示 + 10轮对话（每轮2条消息）
        messages = [messages[0]] + messages[-20:]
    
    return ai_model_manager.chat(messages, provider)


def get_ai_response_stream(message: str, context: List[Dict] = None, provider: str = None) -> Generator[str, None, None]:
    """获取AI流式响应（便捷函数）"""
    messages = context or []
    
    # 添加系统提示
    system_prompt = {
        "role": "system",
        "content": """你是智能旅游助手，专门为中国游客提供旅游相关的帮助。你的主要职责包括：

1. 景点推荐和介绍
2. 旅游行程规划
3. 天气查询和穿衣建议
4. 美食推荐
5. 交通和住宿建议
6. 旅游注意事项和实用信息

请用友好、专业的语气回答用户的问题，并尽可能提供详细、实用的建议。
如果用户的问题超出旅游范围，请礼貌地引导用户回到旅游相关话题。"""
    }
    
    # 确保系统提示在最前面
    if not messages or messages[0].get('role') != 'system':
        messages.insert(0, system_prompt)
    
    # 添加用户消息
    messages.append({"role": "user", "content": message})
    
    # 保持对话历史在合理长度
    if len(messages) > 21:
        messages = [messages[0]] + messages[-20:]
    
    yield from ai_model_manager.chat_stream(messages, provider)


if __name__ == "__main__":
    # 测试代码
    print("🧪 测试AI模型管理器...")
    
    # 获取可用提供商
    providers = ai_model_manager.get_available_providers()
    print(f"可用提供商: {providers}")
    
    # 获取提供商信息
    info = ai_model_manager.get_provider_info()
    for name, detail in info.items():
        print(f"  {name}: {detail}")
    
    # 测试对话
    if providers:
        test_message = "你好，请推荐北京的三个必去景点"
        print(f"\n测试消息: {test_message}")
        response = get_ai_response(test_message)
        print(f"AI响应: {response}")
    else:
        print("⚠️ 未配置任何AI模型API密钥")