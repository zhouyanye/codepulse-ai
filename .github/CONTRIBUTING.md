# 贡献指南

欢迎来到 CodePulse AI 项目！我们很高兴您有兴趣为我们的项目做出贡献。本文档旨在为您提供参与项目开发所需的所有信息。

## 开发环境设置

### 前提条件

- Python 3.10 或更高版本
- Git
- Redis (可选，用于异步任务)
- Docker (可选，用于容器化部署)

### 环境设置步骤

1. Fork 仓库到您的 GitHub 账户
2. 克隆仓库到本地：
   ```bash
   git clone https://github.com/YOUR_USERNAME/codepulse-ai.git
   cd codepulse-ai
   ```

3. 创建虚拟环境：
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # 或
   venv\Scripts\activate  # Windows
   ```

4. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

5. 复制环境变量文件：
   ```bash
   cp .env.example .env
   ```

6. 配置环境变量（至少配置一个AI服务提供商的API密钥）

## 项目结构

```
codepulse-ai/
├── app/                    # FastAPI后端应用
│   ├── api/               # API路由
│   ├── core/              # 核心配置
│   └── tasks/             # Celery异步任务
├── services/              # 业务逻辑服务
├── models/                 # 数据模型
├── utils/                  # 工具函数
├── web/                    # Streamlit前端
├── tests/                  # 测试文件
├── docker/                 # Docker配置
├── docs/                   # 项目文档
└── .github/                # GitHub配置文件
```

## 技术栈

- **后端**: FastAPI (Python 3.10+)
- **前端**: Streamlit
- **数据库**: SQLite (持久化) + Redis (缓存/任务队列)
- **异步任务**: Celery
- **可视化**: PyECharts

## 开发流程

### 启动开发服务器

1. 启动后端 (FastAPI):
   ```bash
   python run.py --component fastapi
   ```

2. 启动前端 (Streamlit) - 在新终端中:
   ```bash
   python run.py --component streamlit
   ```

3. 启动 Celery Worker (如果需要异步功能) - 在新终端中:
   ```bash
   python run.py --component celery
   ```

### 代码风格

- 遵循 PEP 8 代码规范
- 使用 Black 格式化代码 (`black .`)
- 使用 Flake8 检查代码质量
- 为新功能编写单元测试

### 测试

运行所有测试：
```bash
python -m pytest tests/
```

运行带覆盖率的测试：
```bash
python -m pytest tests/ --cov=app --cov=services --cov=models --cov=utils
```

## 贡献类型

我们欢迎以下类型的贡献：

- Bug 修复
- 新功能开发
- 文档改进
- 测试用例编写
- 性能优化
- 用户体验改进

## 提交拉取请求

1. 确保您的代码符合项目风格
2. 添加或更新相关测试
3. 运行测试以确保所有测试通过
4. 提交 PR 并描述您的更改

### PR 模板检查清单

- [ ] 代码遵循项目编码规范
- [ ] 新功能有相应测试
- [ ] 所有测试通过
- [ ] 代码有适当的注释
- [ ] 更新了相关文档

## 问题报告

当您发现 bug 或需要新功能时，请提交 issue。请提供尽可能多的相关信息，以帮助我们更快地解决问题。

## 联系方式

如果您有任何问题，请通过以下方式联系我们：

- 通过 GitHub Issues 提交问题
- 通过项目 Wiki 获取更多信息

感谢您对 CodePulse AI 的贡献！