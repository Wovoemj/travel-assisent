"""
models/__init__.py — 模型包入口
统一导出所有模型，便于外部 import
"""
from models.core import (
    Destination, User, Conversation, Admin,
    Trip, TripItem, TripShare, NearbyPOI,
    UserLike, UserFollow, UserCheckin
)

__all__ = [
    'Destination', 'User', 'Conversation', 'Admin',
    'Trip', 'TripItem', 'TripShare', 'NearbyPOI',
    'UserLike', 'UserFollow', 'UserCheckin',
]
