FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN mkdir -p /data/pdf

EXPOSE 8000

# 启动时自动确保管理员存在，然后起服务
CMD ["sh", "-c", "python -m app.cli ensure-admin && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
