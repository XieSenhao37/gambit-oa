# 使用官方 Python 运行时作为父镜像
FROM tiangolo/uwsgi-nginx-flask:python3.9

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV FLASK_APP=run.py
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# 复制项目文件到工作目录
COPY . .

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 创建证书目录
RUN mkdir -p /app/cert

# 创建 uwsgi.ini
COPY uwsgi.ini /app/uwsgi.ini

# 暴露端口
EXPOSE 8080

# 使用 uwsgi 启动
CMD ["uwsgi", "--ini", "/app/uwsgi.ini"]
