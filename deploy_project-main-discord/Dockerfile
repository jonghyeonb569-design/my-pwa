FROM python:3.11-slim

WORKDIR /app

# PostgreSQL 및 시스템 라이브러리 설치
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 종속성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 전체 소스 코드 복사
COPY . .

# 업로드 디렉토리 생성
RUN mkdir -p static/uploads

# Render.com은 동적 포트를 사용하므로 EXPOSE는 참고용으로만 사용됩니다.
EXPOSE 10000

# 핵심 수정: $PORT 환경 변수를 읽어서 gunicorn을 실행합니다.
# 실행 파일명이 app.py가 아닌 app_fixed_v3.py라면 아래 app:app 부분을 app_fixed_v3:app으로 변경해야 합니다.
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-10000} app:app"]
