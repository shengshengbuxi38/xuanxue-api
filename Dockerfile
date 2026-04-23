FROM python:3.12-slim

WORKDIR /app

# 安装依赖（预编译 wheel，无需 gcc）
COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制现有代码（零修改）
COPY modules/ ./modules/
COPY data/    ./data/

# 复制 API 层
COPY api/ ./api/

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
