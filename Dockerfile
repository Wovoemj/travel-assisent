# 智能旅游助手 - Docker配置
FROM python:3.11.7-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建数据库目录
RUN mkdir -p instance

# 暴露端口
EXPOSE 5000

# 设置环境变量
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

# 启动命令
CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "--bind", "0.0.0.0:5000", "app:app"]