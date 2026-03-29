"""
extensions.py — Flask 扩展实例
统一管理 SQLAlchemy 等扩展，解决循环导入问题
"""
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO

db = SQLAlchemy()
socketio = SocketIO()
