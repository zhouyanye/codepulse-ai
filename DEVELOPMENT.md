# CodePulse AI 开发指南

本文档为开发者提供项目开发相关的详细说明。

## 开发环境设置

### 环境要求

- Python 3.10 或更高版本
- Git
- Redis (可选，用于异步任务)
- Docker (可选，用于容器化部署)

### 快速设置

1. 克隆仓库：
   ```bash
   git clone https://github.com/zhouyanye/codepulse-ai.git
   cd codepulse-ai
   ```

2. 创建虚拟环境：
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # 或
   venv\Scripts\activate  # Windows
   ```

3. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

4. 安装开发工具：
   ```bash
   pip install pre-commit
   pre-commit install
   ```

## 开发工作流

### 代码质量检查

本项目使用多种工具确保代码质量：

- **Black**: 代码格式化
- **isort**: 导入排序
- **Flake8**: 代码风格检查
- **mypy**: 类型检查

在提交代码前，请确保通过所有检查：

```bash
# 格式化代码
black .
# 排序导入
isort .
# 检查代码风格
flake8 .
# 检查类型
mypy .
```

### 提交规范

本项目使用约定式提交规范。提交信息应遵循以下格式：

```
<type>(<scope>): <description>
```

常用类型：
- `feat`: 新功能
- `fix`: 修复bug
- `docs`: 文档更新
- `style`: 代码风格修改
- `refactor`: 代码重构
- `test`: 测试相关
- `chore`: 构建工具或辅助工具变动

## 项目架构

### 后端 (FastAPI)

- API路由: `app/api/endpoints/`
- 核心配置: `app/core/`
- 异步任务: `app/tasks/`

### 前端 (Streamlit)

- 主界面: `web/main.py`
- 国际化: `web/i18n.py`

### 服务层

- 分析服务: `services/analysis_service.py`
- AI分析器: `services/ai_analyzer.py`
- 静态扫描: `services/static_scan_service.py`
- GitHub服务: `services/github_service.py`
- Gitee服务: `services/gitee_service.py`

### 工具函数

- AI客户端: `utils/ai_client.py`
- Git工具: `utils/git_utils.py`
- 安全工具: `utils/security_utils.py`
- Token估算器: `utils/token_estimator.py`

## 测试

### 运行测试

```bash
# 运行所有测试
python -m pytest tests/

# 运行测试并查看覆盖率
python -m pytest tests/ --cov=app --cov=services --cov=models --cov=utils

# 运行特定测试文件
python -m pytest tests/test_analysis_service.py
```

### 测试结构

- 单元测试: 测试独立函数和类
- 集成测试: 测试组件间交互
- 端到端测试: 测试完整工作流

## 贡献流程

1. Fork 仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'feat: add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建拉取请求

## Docker 开发

### 构建开发镜像

```bash
docker build -f docker/Dockerfile --build-arg USE_CHINA_MIRROR=true --build-arg BUILD_TARGET=all -t codepulse-ai:dev .
```

### 使用 Docker Compose 开发

```bash
# 启动所有服务（包括Redis、FastAPI、Celery Worker、Streamlit）
docker-compose -f docker/docker-compose.yml up -d
```

## API 文档

- 本地API文档: http://localhost:8000/docs
- ReDoc文档: http://localhost:8000/redoc

## 常见开发任务

### 启动开发服务器

```bash
# 启动后端
python run.py --component fastapi

# 启动前端
python run.py --component streamlit

# 启动Celery Worker（如果需要异步功能）
python run.py --component celery
```

### 数据库操作

- SQLite数据库文件: `data/codepulse.db`
- 数据模型定义: `models/db_models.py`

### 环境变量

- 配置文件: `.env` (从 `.env.example` 复制)
- 重要变量: AI API密钥、GitHub/Gitee Token、Redis URL等

## 调试技巧

### 后端调试

- 使用 `DEBUG=True` 启用详细日志
- API端点: `app/api/endpoints/analysis.py`
- 日志配置: `app/main.py`

### 前端调试

- Streamlit组件: `web/main.py`
- 国际化: `web/i18n.py`
- 前端状态管理: 使用 `st.session_state`

## 性能优化

### 异步任务

- 使用Celery处理长时间运行的任务
- Redis作为任务队列和结果后端
- 任务状态轮询机制

### 缓存策略

- 分析结果缓存（24小时过期）
- API响应缓存
- Git仓库克隆缓存

## 部署

### 本地部署

```bash
python run.py --component all  # 启动所有组件
```

### 容器化部署

使用 `docker/docker-compose.yml` 文件部署所有服务。

### 云部署

支持部署到Render等云平台，配置文件见 `render.yaml`。