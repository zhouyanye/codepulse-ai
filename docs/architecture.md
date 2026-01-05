# CodePulse AI 架构设计

## 概述

CodePulse AI 采用分层架构设计，支持同步和异步两种执行模式，以适应不同的部署环境和使用场景。系统包含前端界面、后端API、任务队列、AI分析引擎等多个组件。

## 整体架构

### 分层架构

```
┌─────────────────┐
│   用户界面层     │  Streamlit Web界面 / CLI工具
├─────────────────┤
│   API网关层     │  FastAPI统一接口
├─────────────────┤
│   业务逻辑层     │  分析服务、AI引擎、静态扫描
├─────────────────┤
│   数据访问层     │  Git工具、数据库、缓存
├─────────────────┤
│   AI服务层      │  多AI提供商客户端
└─────────────────┘
```

### 组件关系

- **Web界面**：Streamlit提供交互式分析界面
- **API服务**：FastAPI提供RESTful API接口
- **任务队列**：Celery + Redis处理异步任务
- **分析引擎**：AI驱动的代码分析服务
- **数据层**：SQLite存储分析历史，Redis缓存结果

## 双路径执行架构

### 设计理念

CodePulse AI 提供两条独立的执行路径，以适配不同的部署场景：

| 特性 | 异步路径 (生产环境) | 同步轮询路径 (开发/测试) |
|------|-------------------|----------------------|
| 技术栈 | Celery + Redis | 后台线程 + 内存字典 |
| 依赖 | 需要Redis | 零依赖 |
| 适用场景 | 高并发、断点续传 | 快速演示、本地调试 |
| 性能 | 高性能 | 中等性能 |

### 异步路径架构

```
客户端 → FastAPI → Celery Task Queue → Celery Worker → 执行分析 → Redis缓存 → 客户端轮询
```

**优点**：
- 高性能：支持大量并发任务
- 进度跟踪：实时任务进度更新
- 结果缓存：Redis缓存避免重复计算
- 断点续传：支持任务中断后恢复

**缺点**：
- 依赖Redis：需要额外部署
- 架构复杂：涉及多个组件

### 同步轮询路径架构

```
客户端 → FastAPI → 后台线程 → 执行分析 → 内存字典 → 客户端轮询
```

**优点**：
- 零依赖：无需Redis和Celery
- 轻量快速：单进程运行
- 易于调试：日志集中

**缺点**：
- 性能限制：受限于单机资源
- 内存存储：重启后结果丢失

### 自动路径选择

统一接口 `/api/v1/analyze` 实现智能路径选择：

```
请求 → AUTO_SELECT_EXECUTION_MODE? → 是 → 检查Celery可用性 → 可用 → 异步路径
                              → 否 → 根据async_mode参数 → 强制路径选择
```

## 核心组件

### 1. AnalysisService

核心分析服务，协调各模块工作：

```python
class AnalysisService:
    def analyze_repository(self, request: AnalysisRequest):
        # 1. 仓库克隆/获取
        # 2. 成本估算
        # 3. AI分析执行
        # 4. 结果聚合
        # 5. 评分计算
        # 6. 报告生成
```

### 2. AIAnalyzer

AI驱动的分析引擎：

- **多提供商支持**：DeepSeek、Kimi、Doubao、OpenAI
- **自动降级**：失败时自动切换提供商
- **上下文管理**：构建完整的分析上下文
- **结果验证**：验证AI输出的准确性

### 3. StaticScanService

静态代码扫描服务：

- **多语言支持**：Python、JavaScript、Java等
- **规则引擎**：内置安全和质量规则
- **模式匹配**：识别常见代码问题
- **性能优化**：大项目分批处理

### 4. GitHubService & GiteeService

代码托管平台服务：

- **API集成**：与GitHub/Gitee API集成
- **仓库分析**：获取仓库元数据
- **文件获取**：获取代码文件内容
- **缓存机制**：缓存API响应结果

## 数据流

### 分析流程数据流

```
用户请求 → 参数验证 → 缓存检查 → 无缓存 → 任务队列 → Celery Worker → AI分析 → 静态扫描 → 结果聚合 → 缓存存储 → 返回结果
         → 有缓存 → 直接返回缓存结果
```

### 任务状态管理

**异步模式**：
```
任务提交 → 生成Task ID → 存储初始状态 → 后台执行 → 更新进度 → 完成 → 存储结果 → 客户端轮询获取状态
```

**同步轮询模式**：
```
任务提交 → 生成Task ID → 启动后台线程 → 内存存储状态 → 更新进度 → 完成 → 内存存储结果 → 客户端轮询获取状态
```

## 配置管理

### 环境变量配置

```env
# AI服务配置
DEEPSEEK_API_KEY=your_key
KIMI_API_KEY=your_key

# 平台Token
GITHUB_TOKEN=your_token
GITEE_TOKEN=your_token

# Redis配置
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0

# 执行模式
ENABLE_CELERY_TASKS=True
ENABLE_SYNC_POLLING=False
AUTO_SELECT_EXECUTION_MODE=True
```

### 模式配置建议

| 部署场景 | ENABLE_CELERY_TASKS | ENABLE_SYNC_POLLING | AUTO_SELECT_EXECUTION_MODE |
|----------|-------------------|-------------------|-------------------------|
| 生产环境 | True | False | True |
| 开发环境(有Redis) | True | True | False |
| 开发环境(无Redis) | False | True | False |

## API设计

### 统一分析接口

```http
POST /api/v1/analyze?async_mode=auto|true|sync_polling|false
Content-Type: application/json

{
  "repo_url": "https://github.com/user/repo",
  "ai_provider": "deepseek",
  "include_static_scan": true,
  "github_token": "optional_token"
}
```

### 路径选择逻辑

- `async_mode=auto`：自动选择（默认）
- `async_mode=true`：强制异步路径
- `async_mode=sync_polling`：强制同步轮询路径
- `async_mode=false|sync_blocking`：同步阻塞模式

## 数据持久化

### 数据库设计

**SQLite存储**：
- 分析历史记录
- 任务执行结果
- 用户配置信息

**Redis缓存**：
- 分析结果缓存（24小时TTL）
- 任务状态管理
- 临时数据存储

### 缓存策略

1. **结果缓存**：分析结果缓存24小时
2. **进度缓存**：任务进度实时更新
3. **API响应缓存**：GitHub/Gitee API响应缓存
4. **临时文件缓存**：克隆仓库的临时缓存

## 错误处理

### 异常处理机制

1. **AI服务降级**：AI调用失败时自动降级
2. **网络重试**：网络请求失败时重试机制
3. **资源清理**：异常时清理临时资源
4. **状态恢复**：任务中断后状态恢复

### 错误恢复

- **临时文件清理**：分析完成后清理临时文件
- **连接池管理**：数据库和Redis连接池管理
- **内存管理**：避免内存泄漏和溢出
- **任务状态同步**：确保任务状态一致性

## 扩展性设计

### 模块化设计

- **插件化AI提供商**：易于添加新的AI服务
- **可配置分析维度**：支持自定义分析维度
- **扩展点设计**：预留扩展接口

### 性能优化

- **异步处理**：充分利用异步IO
- **连接池**：数据库和Redis连接池
- **缓存策略**：多级缓存机制
- **资源复用**：避免重复创建资源