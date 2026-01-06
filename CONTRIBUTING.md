# 贡献指南

感谢您有兴趣为 CodePulse AI 项目做贡献！我们欢迎各种形式的贡献，包括但不限于代码、文档、bug 报告和功能建议。

## 如何贡献

### 报告 Bug

如果您发现了 bug，请在 GitHub Issues 中提交一个详细的问题报告，包括：

1. 清晰简洁的标题
2. 描述问题的详细步骤
3. 预期的行为和实际的行为
4. 截图（如果适用）
5. 您的环境信息（操作系统、Python 版本等）

### 提交功能建议

如果您有新的功能想法，请在 GitHub Issues 中提交一个功能请求，包括：

1. 功能的清晰描述
2. 解决的问题或带来的价值
3. 可能的实现思路（如果有的话）

### 提交 Pull Request

1. Fork 项目仓库
2. 创建一个新的分支 (`git checkout -b feature/AmazingFeature`)
3. 提交您的修改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启一个 Pull Request

## 开发环境设置

1. 克隆仓库: `git clone https://github.com/zhouyanye/codepulse-ai.git`
2. 创建虚拟环境: `python -m venv venv`
3. 激活虚拟环境:
   - Windows: `venv\Scripts\activate`
   - macOS/Linux: `source venv/bin/activate`
4. 安装依赖: `pip install -r requirements.txt`

## 代码规范

- 遵循 PEP8 代码规范
- 使用 Black 格式化代码
- 添加适当的注释和文档字符串
- 编写单元测试以确保代码质量

## 测试

在提交 Pull Request 之前，请确保所有的测试都能通过：

```bash
python -m pytest tests/
```

## 代码审查

所有提交的 Pull Request 都会经过代码审查过程。请耐心等待维护者的反馈，并根据反馈进行相应的修改。

## 行为准则

请遵守我们的行为准则，共同营造一个友好、包容的社区环境。

感谢您的贡献！