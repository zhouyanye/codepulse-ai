# 配置与部署指南

## 环境要求

### 系统要求
- **操作系统**：Windows 10+, Linux (Ubuntu 18.04+), macOS 10.14+
- **Python版本**：3.10+ (推荐3.10或3.11)
- **内存要求**：至少4GB RAM (推荐8GB+)
- **存储空间**：至少2GB可用空间
- **Git版本**：2.20+ (用于仓库克隆)

### 可选依赖
- **Redis**：7.0+ (用于异步任务队列和缓存)
- **Docker**：20.10+ (用于容器化部署)
- **wkhtmltopdf**: 0.12.5+ (用于PDF转换)

## 快速配置

### 1. 环境变量配置

复制示例配置文件：

```bash
cp .env.example .env
```

编辑 `.env` 文件配置参数：

```env
# AI服务配置（至少配置一个）
DEEPSEEK_API_KEY=your_deepseek_api_key
KIMI_API_KEY=your_kimi_api_key
DOUBAO_API_KEY=your_doubao_api_key
OPENAI_API_KEY=your_openai_api_key

# 平台访问Token（可选）
GITHUB_TOKEN=your_github_token
GITEE_TOKEN=your_gitee_token

# Redis配置（异步模式需要）
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# 执行模式配置
ENABLE_CELERY_TASKS=True
ENABLE_SYNC_POLLING=True
AUTO_SELECT_EXECUTION_MODE=True

# 缓存配置
REDIS_CACHE_TTL=86400  # 24小时
REPO_CACHE_TTL=1800    # 30分钟

# 任务配置
MAX_TASK_CONCURRENCY=4
TASK_TIMEOUT=3600      # 1小时
```

### 2. AI服务提供商配置

#### DeepSeek配置
1. 访问 [DeepSeek平台](https://platform.deepseek.com/)
2. 创建API密钥
3. 在`.env`中设置 `DEEPSEEK_API_KEY`

#### Kimi配置
1. 访问 [Kimi开放平台](https://platform.moonshot.cn/)
2. 注册并创建API密钥
3. 在`.env`中设置 `KIMI_API_KEY`

#### 豆包(Doubao)配置
1. 访问 [豆包开发者平台](https://www.volcengine.com/product/doubao/)
2. 创建API密钥
3. 在`.env`中设置 `DOUBAO_API_KEY`

#### OpenAI配置
1. 访问 [OpenAI平台](https://platform.openai.com/)
2. 创建API密钥
3. 在`.env`中设置 `OPENAI_API_KEY`

## 部署模式

### 1. 开发模式（推荐）

仅使用同步轮询模式，无需Redis：

```env
ENABLE_CELERY_TASKS=False
ENABLE_SYNC_POLLING=True
AUTO_SELECT_EXECUTION_MODE=False
```

启动命令：
```bash
# 启动后端
python run.py --component fastapi

# 启动前端（新终端）
python run.py --component streamlit
```

### 2. 生产模式（推荐）

使用异步任务队列，需要Redis：

```env
ENABLE_CELERY_TASKS=True
ENABLE_SYNC_POLLING=False
AUTO_SELECT_EXECUTION_MODE=True
```

启动命令：
```bash
# 启动Redis（如果未运行）
redis-server &

# 启动后端
python run.py --component fastapi

# 启动Celery Worker（新终端）
python run.py --component celery

# 启动前端（新终端）
python run.py --component streamlit
```

### 3. 混合模式

同时启用两种模式，系统自动选择：

```env
ENABLE_CELERY_TASKS=True
ENABLE_SYNC_POLLING=True
AUTO_SELECT_EXECUTION_MODE=True
```

## Docker部署

### 1. Docker Compose部署

使用预配置的Docker Compose文件：

```bash
# 启动所有服务
docker-compose -f docker/docker-compose.yml up -d

# 查看服务状态
docker-compose -f docker/docker-compose.yml ps

# 停止服务
docker-compose -f docker/docker-compose.yml down
```

### 2. 自定义Docker配置

创建自定义 `docker-compose.yml`：

```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  fastapi:
    build: .
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://redis:6379/0
      - ENABLE_CELERY_TASKS=True
    depends_on:
      - redis

  celery:
    build: .
    command: python run.py --component celery
    environment:
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
      - fastapi

  streamlit:
    build: .
    ports:
      - "8501:8501"
    command: python run.py --component streamlit
    depends_on:
      - fastapi

volumes:
  redis_data:
```

## 配置详解

### AI提供商配置

#### 优先级设置
系统按照以下优先级使用AI提供商：
1. 用户在请求中指定的提供商
2. 环境变量中配置的默认提供商
3. 自动降级链中的下一个提供商

#### 成本控制配置
```env
# 设置成本阈值（RMB）
COST_THRESHOLD_HIGH=10.0    # 高成本阈值
COST_THRESHOLD_MEDIUM=1.0   # 中等成本阈值
COST_THRESHOLD_LOW=0.1      # 低成本阈值

# 成本估算缓存时间（秒）
COST_ESTIMATION_CACHE_TTL=300  # 5分钟
```

### 任务队列配置

#### Celery配置
```env
# Celery Broker配置
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# 任务配置
CELERY_TASK_SOFT_TIME_LIMIT=3600    # 1小时软超时
CELERY_TASK_TIME_LIMIT=7200         # 2小时硬超时
CELERY_WORKER_CONCURRENCY=2         # 工作进程数
CELERY_WORKER_MAX_TASKS_PER_CHILD=100 # 每个工作进程处理的任务数
```

#### 任务状态配置
```env
# 任务状态轮询间隔（秒）
TASK_POLLING_INTERVAL=2
TASK_POLLING_TIMEOUT=7200  # 2小时

# 任务结果缓存时间（秒）
TASK_RESULT_CACHE_TTL=86400  # 24小时
```

### 缓存配置

#### Redis缓存
```env
# Redis连接配置
REDIS_URL=redis://localhost:6379/0
REDIS_POOL_SIZE=10
REDIS_POOL_TIMEOUT=30

# 缓存TTL配置
REPO_CACHE_TTL=1800          # 仓库克隆缓存：30分钟
ANALYSIS_RESULT_CACHE_TTL=86400  # 分析结果缓存：24小时
API_RESPONSE_CACHE_TTL=300   # API响应缓存：5分钟
```

#### 本地缓存
```env
# 本地临时目录
TEMP_DIR=./temp
MAX_TEMP_SIZE=1073741824  # 1GB

# 仓库克隆缓存
CLONE_CACHE_ENABLED=True
CLONE_CACHE_DIR=./.repo_cache
CLONE_CACHE_MAX_SIZE=5368709120  # 5GB
```

## 高级配置

### 自定义分析规则

在 `utils/costrict.py` 中可以添加自定义分析规则：

```python
# 示例：自定义安全检查规则
CUSTOM_SECURITY_RULES = {
    'hardcoded_password': {
        'pattern': r'password\s*=\s*["\'][^"\']{3,}["\']',
        'severity': 'high',
        'description': '检测到硬编码密码'
    },
    'api_key_exposure': {
        'pattern': r'api[_-]?key\s*=\s*["\'][A-Za-z0-9_-]{20,}["\']',
        'severity': 'high',
        'description': '检测到API密钥'
    }
}
```

### 性能调优

#### 内存优化
```env
# 最大并发分析任务数
MAX_CONCURRENT_ANALYSIS=2

# 文件大小限制（MB）
MAX_FILE_SIZE=10
MAX_REPO_SIZE=100

# 分析深度限制
MAX_ANALYSIS_DEPTH=5  # 目录深度
MAX_FILES_PER_ANALYSIS=1000
```

#### 网络优化
```env
# 请求超时配置
HTTP_TIMEOUT=30
HTTP_MAX_RETRIES=3
HTTP_RETRY_DELAY=1

# 连接池配置
HTTP_POOL_SIZE=20
HTTP_POOL_TIMEOUT=60
```

### 安全配置

#### API安全
```env
# API密钥验证
API_KEY_REQUIRED=False  # 是否需要API密钥访问

# 速率限制
RATE_LIMIT_ENABLED=True
RATE_LIMIT_REQUESTS=100  # 每小时请求数
RATE_LIMIT_WINDOW=3600   # 时间窗口（秒）

# 访问控制
ALLOWED_ORIGINS=["*"]  # CORS配置
TRUSTED_HOSTS=["localhost", "127.0.0.1"]
```

## 监控配置

### 日志配置

#### 日志级别
```env
# 日志级别：DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=INFO
LOG_FORMAT=%(asctime)s - %(name)s - %(levelname)s - %(message)s
LOG_MAX_SIZE=10485760  # 10MB
LOG_BACKUP_COUNT=5
```

#### 日志输出
```env
# 控制台日志
CONSOLE_LOG_ENABLED=True

# 文件日志
FILE_LOG_ENABLED=True
LOG_FILE_PATH=./logs/app.log

# 结构化日志
STRUCTURED_LOGGING=False  # JSON格式日志
```

### 健康检查

#### 健康检查端点
```env
# 健康检查路径
HEALTH_CHECK_PATH=/health
HEALTH_CHECK_TIMEOUT=10

# 健康检查组件
HEALTH_CHECK_REDIS=True
HEALTH_CHECK_DATABASE=True
HEALTH_CHECK_AI_PROVIDERS=True
```

## 故障排除

### 常见问题

#### Redis连接问题
- **症状**：无法启动Celery Worker或异步任务失败
- **解决方案**：检查Redis服务是否运行，确认连接URL正确

#### AI API调用失败
- **症状**：分析任务失败，显示API错误
- **解决方案**：检查API密钥配置，确认配额未用完

#### 内存不足
- **症状**：大项目分析失败，系统变慢
- **解决方案**：增加内存限制，启用分批处理

### 调试配置

```env
# 调试模式
DEBUG=True
DEVELOPMENT_MODE=True

# 详细日志
VERBOSE_LOGGING=True

# 错误追踪
ERROR_TRACKING_ENABLED=True
ERROR_LOG_PATH=./logs/errors.log
```

## 生产环境最佳实践

### 安全建议
1. 使用HTTPS保护API端点
2. 定期轮换API密钥
3. 限制访问IP范围
4. 启用速率限制

### 性能建议
1. 根据负载调整并发数
2. 合理设置缓存TTL
3. 监控资源使用情况
4. 定期清理临时文件

### 备份策略
1. 定期备份SQLite数据库
2. 备份配置文件
3. 记录重要配置变更