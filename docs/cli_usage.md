# CLI工具使用指南

## 概述

CodePulse AI 提供功能强大的命令行工具 (CLI)，支持批量分析、成本预估、报告生成等功能。CLI工具允许用户在无图形界面的环境下使用系统功能。

## 安装与配置

### 环境准备

确保已安装Python 3.10+并完成项目依赖安装：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --no-cache-dir
```

### 环境变量配置

CLI工具需要配置必要的环境变量，编辑 `.env` 文件：

```env
# AI服务配置（至少配置一个）
DEEPSEEK_API_KEY=your_deepseek_api_key
KIMI_API_KEY=your_kimi_api_key
DOUBAO_API_KEY=your_doubao_api_key
OPENAI_API_KEY=your_openai_api_key

# 平台Token（私有仓库需要）
GITHUB_TOKEN=your_github_token
GITEE_TOKEN=your_gitee_token
```

## 基本用法

### 查看帮助

```bash
python cli.py -h
```

### 支持的命令

- `analyze`：分析单个仓库
- `batch`：批量分析仓库
- `report`：生成分析报告
- `estimate`：预估分析成本

## 详细命令说明

### 1. analyze - 单仓库分析

分析单个GitHub或Gitee仓库：

```bash
# 基本用法
python cli.py analyze https://github.com/user/repo

# 指定AI提供商
python cli.py analyze https://github.com/user/repo --provider deepseek

# 指定输出格式
python cli.py analyze https://github.com/user/repo --format json

# 指定输出文件
python cli.py analyze https://github.com/user/repo --format json --output ./report.json

# 使用私有仓库Token
python cli.py analyze https://gitee.com/user/private-repo --gitee-token your_token
```

#### analyze 命令参数

| 参数 | 说明 | 默认值 | 示例 |
|------|------|--------|------|
| `url` | 仓库URL | 必需 | `https://github.com/user/repo` |
| `--provider` | AI提供商 | `deepseek` | `deepseek`, `kimi`, `doubao`, `openai`, `costrict` |
| `--github-token` | GitHub Token | 从环境变量读取 | `--github-token your_token` |
| `--gitee-token` | Gitee Token | 从环境变量读取 | `--gitee-token your_token` |
| `--format` | 报告格式 | 无 | `json`, `md` |
| `--output` | 输出文件路径 | 自动生成 | `./report.json` |

### 2. batch - 批量分析

批量分析多个仓库：

```bash
# 创建仓库列表文件 repos.txt
echo "https://github.com/user/repo1" > repos.txt
echo "https://github.com/user/repo2" >> repos.txt
echo "https://gitee.com/user/repo3" >> repos.txt

# 批量分析
python cli.py batch repos.txt

# 指定AI提供商和输出格式
python cli.py batch repos.txt --provider kimi --format json

# 指定输出目录
python cli.py batch repos.txt --format json --output ./reports/
```

#### batch 命令参数

| 参数 | 说明 | 默认值 | 示例 |
|------|------|--------|------|
| `file` | 包含仓库URL的文件 | 必需 | `repos.txt` |
| `--provider` | AI提供商 | `deepseek` | `deepseek`, `kimi`, `openai` |
| `--format` | 报告格式 | `json` | `json`, `md` |
| `--output` | 输出目录 | `./reports/` | `./my_reports/` |
| `--github-token` | GitHub Token | 从环境变量读取 | `--github-token your_token` |
| `--gitee-token` | Gitee Token | 从环境变量读取 | `--gitee-token your_token` |

### 3. report - 生成报告

为单个仓库生成分析报告：

```bash
# 生成JSON报告
python cli.py report https://github.com/user/repo --format json

# 生成Markdown报告
python cli.py report https://github.com/user/repo --format md

# 指定输出文件
python cli.py report https://github.com/user/repo --format json --output ./my_report.json
```

#### report 命令参数

| 参数 | 说明 | 默认值 | 示例 |
|------|------|--------|------|
| `url` | 仓库URL | 必需 | `https://github.com/user/repo` |
| `--provider` | AI提供商 | `deepseek` | `deepseek`, `kimi`, `doubao`, `openai` |
| `--format` | 报告格式 | `json` | `json`, `md` |
| `--output` | 输出文件路径 | 自动生成 | `./report.md` |
| `--github-token` | GitHub Token | 从环境变量读取 | `--github-token your_token` |
| `--gitee-token` | Gitee Token | 从环境变量读取 | `--gitee-token your_token` |

### 4. estimate - 成本预估

预估分析仓库所需的Token和成本：

```bash
# 预估成本
python cli.py estimate https://github.com/user/repo

# 指定AI提供商
python cli.py estimate https://github.com/user/repo --provider kimi

# 使用CoStrict模式（零成本）
python cli.py estimate https://github.com/user/repo --provider costrict
```

#### estimate 命令参数

| 参数 | 说明 | 默认值 | 示例 |
|------|------|--------|------|
| `url` | 仓库URL | 必需 | `https://github.com/user/repo` |
| `--provider` | AI提供商 | `deepseek` | `deepseek`, `kimi`, `doubao`, `openai`, `costrict` |
| `--github-token` | GitHub Token | 从环境变量读取 | `--github-token your_token` |
| `--gitee-token` | Gitee Token | 从环境变量读取 | `--gitee-token your_token` |

## 使用示例

### 示例1：分析GitHub仓库

```bash
# 分析公共仓库
python cli.py analyze https://github.com/facebook/react

# 分析并生成JSON报告
python cli.py analyze https://github.com/facebook/react --format json --output ./react_analysis.json

# 使用Kimi进行分析
python cli.py analyze https://github.com/facebook/react --provider kimi
```

### 示例2：分析Gitee仓库

```bash
# 分析Gitee仓库
python cli.py analyze https://gitee.com/organizations/owner/repo

# 使用私有仓库Token
python cli.py analyze https://gitee.com/owner/private-repo --gitee-token your_token
```

### 示例3：批量分析

```bash
# 创建仓库列表
cat > repos.txt << EOF
https://github.com/vuejs/vue
https://github.com/angular/angular
https://gitee.com/organizations/ant-design/ant-design
EOF

# 批量分析并生成JSON报告
python cli.py batch repos.txt --provider deepseek --format json --output ./batch_reports/
```

### 示例4：成本预估

```bash
# 预估大型项目成本
python cli.py estimate https://github.com/microsoft/vscode

# 预估成本并使用CoStrict模式
python cli.py estimate https://github.com/microsoft/vscode --provider costrict

# 比较不同提供商的成本
python cli.py estimate https://github.com/microsoft/vscode --provider deepseek
python cli.py estimate https://github.com/microsoft/vscode --provider kimi
```

## 输出格式说明

### JSON格式输出

JSON格式包含完整的分析结果：

```json
{
  "overall_score": 85,
  "repo_info": {
    "name": "repo-name",
    "description": "repo description",
    "language": "Python",
    "stars": 1000
  },
  "code_quality": {
    "score": 80,
    "security_score": 85,
    "issues": [...]
  },
  "community_health": {
    "score": 90,
    "contributors_count": 50,
    "recent_commits_30d": 100
  },
  "documentation": {
    "score": 75,
    "has_readme": true,
    "has_license": true
  },
  "maintenance": {
    "score": 88,
    "last_commit_date": "2023-12-01",
    "open_issues": 10
  },
  "recommendations": [...],
  "analysis_metadata": {
    "ai_provider": "deepseek",
    "analysis_time": "2023-12-05T10:30:00Z",
    "token_consumed": 15000
  }
}
```

### Markdown格式输出

Markdown格式适合人工阅读：

```markdown
# 仓库分析报告

**分析时间**: 2023-12-05 10:30:00

**仓库地址**: https://github.com/user/repo

## 总体评分: 85/100

### 各项评分

- 代码质量: 80/100
- 社区健康: 90/100
- 文档完整: 75/100
- 维护状况: 88/100
- 安全风险: 85/100

### 主要建议

- **提高测试覆盖率**
  严重程度: 中等
  描述: 项目测试覆盖率较低，建议增加单元测试和集成测试

- **修复安全漏洞**
  严重程度: 高
  描述: 发现潜在的安全漏洞，需要及时修复
```

## 高级功能

### 自定义配置

可以通过环境变量自定义CLI行为：

```bash
# 设置超时时间
export CLI_TIMEOUT=3600

# 设置并发数
export CLI_CONCURRENCY=2

# 设置缓存目录
export CLI_CACHE_DIR=./cli_cache
```

### 静默模式

使用静默模式减少输出：

```bash
# 静默模式（仅输出结果）
python cli.py analyze https://github.com/user/repo --format json > result.json
```

### 脚本集成

CLI工具适合集成到自动化脚本中：

```bash
#!/bin/bash
# 批量分析脚本示例

repos=(
  "https://github.com/vuejs/vue"
  "https://github.com/reactjs/react"
  "https://gitee.com/ant-design/ant-design"
)

for repo in "${repos[@]}"; do
  echo "分析仓库: $repo"
  python cli.py analyze "$repo" --provider costrict --format json --output "./reports/$(basename $repo).json"
  sleep 5  # 避免请求过于频繁
done
```

## 故障排除

### 常见问题

#### 1. API密钥错误

**症状**：分析失败，显示API错误
**解决方案**：检查环境变量中的API密钥配置

```bash
# 验证API密钥
echo $DEEPSEEK_API_KEY
```

#### 2. 网络连接问题

**症状**：仓库克隆失败或API调用超时
**解决方案**：检查网络连接，必要时配置代理

#### 3. 内存不足

**症状**：大项目分析失败
**解决方案**：增加系统内存或使用CoStrict模式

### 调试模式

启用详细日志输出：

```bash
# 启用调试日志
python -c "import logging; logging.basicConfig(level=logging.DEBUG)" && python cli.py analyze https://github.com/user/repo
```

## 性能优化

### 批量处理优化

1. **分批处理**：大列表分批处理避免内存溢出
2. **并发控制**：限制并发数避免API限流
3. **结果缓存**：重复分析使用缓存结果

### 成本控制

1. **使用CoStrict模式**：对于基础评分使用零成本模式
2. **成本预估**：分析前预估成本避免意外费用
3. **提供商选择**：根据需求选择性价比最高的提供商

## 最佳实践

### 1. 成本管理

```bash
# 分析前预估成本
python cli.py estimate https://github.com/user/repo

# 如果成本过高，使用CoStrict模式
python cli.py analyze https://github.com/user/repo --provider costrict
```

### 2. 批量分析

```bash
# 创建有序的仓库列表
# 按项目大小分组处理
# 使用适当的间隔避免API限流
```

### 3. 结果处理

```bash
# 将结果重定向到文件
python cli.py analyze https://github.com/user/repo --format json > result.json

# 使用jq等工具处理JSON结果
cat result.json | jq '.overall_score'
```

通过CLI工具，用户可以高效地进行仓库分析、批量处理和成本控制，特别适合集成到CI/CD流程或自动化脚本中。