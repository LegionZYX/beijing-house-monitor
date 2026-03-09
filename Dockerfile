FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY . .

# 创建数据目录（Railway 使用卷挂载）
RUN mkdir -p /app/data /app/logs

# 暴露端口
EXPOSE 8080

# 启动命令（支持 Railway 多进程）
CMD python src/scheduler.py & python web/app.py
