FROM python:3.10-alpine

ARG USE_CHINA_MIRROR=false
ARG BUILD_TARGET=all

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN if [ "$USE_CHINA_MIRROR" = "true" ]; then \
    sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories; \
    fi && \
    apk update && \
    apk add --no-cache \
    git git-lfs curl bash openssh ca-certificates \
    gcc musl-dev python3-dev libffi-dev openssl-dev \
    make g++ jpeg-dev zlib-dev freetype-dev lcms2-dev \
    libxml2-dev libxslt-dev cairo-dev pango-dev gdk-pixbuf-dev && \
    rm -rf /var/cache/apk/*

RUN if [ "$USE_CHINA_MIRROR" = "true" ]; then \
    pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple; \
    else \
    pip config set global.index-url https://pypi.org/simple; \
    fi

RUN pip install --upgrade pip setuptools wheel

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/temp_repos /app/logs /app/data /app/.streamlit && \
    addgroup -g 1000 codepulse && \
    adduser -D -u 1000 -G codepulse codepulse && \
    chown -R codepulse:codepulse /app

USER codepulse

EXPOSE 8000 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["python", "run.py", "--component", "fastapi"]