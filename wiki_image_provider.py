#!/usr/bin/env python3
"""
维基百科图片提供者 - 从维基百科获取景点图片
"""
import requests
import json
import time
from pathlib import Path
from urllib.parse import quote
import hashlib

class WikiImageProvider:
    """维基百科图片提供者"""
    
    def __init__(self):
        self.cache_dir = Path(__file__).parent / "wiki_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_ttl = 86400  # 24小时缓存
        
    def _get_cache_key(self, query):
        """生成缓存键"""
        return hashlib.md5(query.encode()).hexdigest()
    
    def _get_cached_result(self, cache_key):
        """获取缓存结果"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if time.time() - data.get('timestamp', 0) < self.cache_ttl:
                    return data.get('image_url')
            except:
                pass
        return None
    
    def _set_cached_result(self, cache_key, image_url):
        """设置缓存结果"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'image_url': image_url,
                    'timestamp': time.time()
                }, f)
        except:
            pass
    
    def search_image(self, query, usage='cover'):
        """搜索图片"""
        if not query:
            return None
            
        # 生成缓存键
        cache_key = self._get_cache_key(f"{query}_{usage}")
        
        # 检查缓存
        cached_result = self._get_cached_result(cache_key)
        if cached_result:
            return cached_result
        
        try:
            # 使用维基百科API搜索
            search_url = "https://zh.wikipedia.org/api/rest_v1/page/summary/" + quote(query)
            
            response = requests.get(search_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                
                # 获取图片URL
                image_url = None
                if 'thumbnail' in data:
                    image_url = data['thumbnail'].get('source')
                elif 'originalimage' in data:
                    image_url = data['originalimage'].get('source')
                
                if image_url:
                    # 缓存结果
                    self._set_cached_result(cache_key, image_url)
                    return image_url
                    
        except Exception as e:
            print(f"维基百科图片搜索失败: {e}")
        
        return None
    
    def get_cover_image(self, attraction_name, city=None, usage='cover'):
        """获取景点封面图片"""
        # 构建搜索查询
        query = attraction_name
        if city:
            query = f"{attraction_name} {city}"
        
        return self.search_image(query, usage)

# 创建全局实例
wiki_image_provider = WikiImageProvider()