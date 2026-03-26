#!/usr/bin/env python3
"""
高德地图API管理器
"""
import requests
import json
import time
from typing import Optional, Dict, Any

class GaodeAPIManager:
    """高德地图API管理器"""
    
    def __init__(self, api_key: str, max_qps: int = 5):
        self.api_key = api_key
        self.max_qps = max_qps
        self.last_request_time = 0
        
    def _wait_for_rate_limit(self):
        """等待速率限制"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        min_interval = 1.0 / self.max_qps
        
        if time_since_last < min_interval:
            time.sleep(min_interval - time_since_last)
        
        self.last_request_time = time.time()
    
    def geocode(self, address: str) -> Optional[Dict[str, Any]]:
        """地理编码 - 地址转坐标"""
        if not address:
            return None
            
        self._wait_for_rate_limit()
        
        try:
            url = "https://restapi.amap.com/v3/geocode/geo"
            params = {
                'key': self.api_key,
                'address': address,
                'city': '',
                'output': 'JSON'
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == '1' and data.get('geocodes'):
                    geocode = data['geocodes'][0]
                    location = geocode.get('location', '').split(',')
                    if len(location) == 2:
                        return {
                            'longitude': float(location[0]),
                            'latitude': float(location[1]),
                            'formatted_address': geocode.get('formatted_address', ''),
                            'province': geocode.get('province', ''),
                            'city': geocode.get('city', ''),
                            'district': geocode.get('district', '')
                        }
        except Exception as e:
            print(f"地理编码失败: {e}")
        
        return None
    
    def reverse_geocode(self, longitude: float, latitude: float) -> Optional[Dict[str, Any]]:
        """逆地理编码 - 坐标转地址"""
        if not longitude or not latitude:
            return None
            
        self._wait_for_rate_limit()
        
        try:
            url = "https://restapi.amap.com/v3/geocode/regeo"
            params = {
                'key': self.api_key,
                'location': f"{longitude},{latitude}",
                'poitype': '',
                'radius': 1000,
                'extensions': 'base',
                'batch': 'false',
                'roadlevel': 0
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == '1':
                    regeocode = data.get('regeocode', {})
                    address_component = regeocode.get('addressComponent', {})
                    
                    return {
                        'formatted_address': regeocode.get('formatted_address', ''),
                        'province': address_component.get('province', ''),
                        'city': address_component.get('city', ''),
                        'district': address_component.get('district', ''),
                        'township': address_component.get('township', ''),
                        'street': address_component.get('streetNumber', {}).get('street', ''),
                        'number': address_component.get('streetNumber', {}).get('number', '')
                    }
        except Exception as e:
            print(f"逆地理编码失败: {e}")
        
        return None
    
    def search_pois(self, keywords: str, city: str = '', types: str = '', 
                   page: int = 1, offset: int = 20) -> Optional[Dict[str, Any]]:
        """POI搜索"""
        if not keywords:
            return None
            
        self._wait_for_rate_limit()
        
        try:
            url = "https://restapi.amap.com/v3/place/text"
            params = {
                'key': self.api_key,
                'keywords': keywords,
                'types': types,
                'city': city,
                'citylimit': 'false',
                'children': '1',
                'offset': offset,
                'page': page,
                'extensions': 'all'
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == '1':
                    return {
                        'count': int(data.get('count', 0)),
                        'pois': data.get('pois', [])
                    }
        except Exception as e:
            print(f"POI搜索失败: {e}")
        
        return None
    
    def get_weather(self, city: str) -> Optional[Dict[str, Any]]:
        """获取天气信息"""
        if not city:
            return None
            
        self._wait_for_rate_limit()
        
        try:
            url = "https://restapi.amap.com/v3/weather/weatherInfo"
            params = {
                'key': self.api_key,
                'city': city,
                'extensions': 'all'
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == '1':
                    return data
        except Exception as e:
            print(f"天气查询失败: {e}")
        
        return None

def extract_lat_lng_from_text(text: str) -> Optional[tuple]:
    """从文本中提取经纬度"""
    if not text:
        return None
    
    import re
    
    # 尝试匹配经纬度格式
    patterns = [
        r'(\d+\.\d+),\s*(\d+\.\d+)',
        r'经度[：:]\s*(\d+\.\d+).*纬度[：:]\s*(\d+\.\d+)',
        r'纬度[：:]\s*(\d+\.\d+).*经度[：:]\s*(\d+\.\d+)',
        r'lng[：:]\s*(\d+\.\d+).*lat[：:]\s*(\d+\.\d+)',
        r'lat[：:]\s*(\d+\.\d+).*lng[：:]\s*(\d+\.\d+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                lat = float(match.group(1))
                lng = float(match.group(2))
                
                # 验证坐标范围（中国境内）
                if 3 <= lat <= 54 and 73 <= lng <= 136:
                    return (lat, lng)
            except ValueError:
                continue
    
    return None