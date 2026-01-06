"""
国际化（i18n）支持模块
支持中文（zh-CN）和英文（en-US）
"""

import streamlit as st
from typing import Dict, Any

# 语言字典 - 完整且结构正确的版本
TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "zh-CN": {
        # ============ 页面标题 ============
        "app_title": "CodePulse AI 开源项目健康扫描器",
        "app_subtitle": "AI驱动的代码质量分析工具，支持 GitHub 和 Gitee 平台",
        "main_header_text": "CodePulse AI",
        "main_subtitle": "开源项目全维度健康评估系统 · 专业 · 客观 · 全面",

        # ============ 输入区域 ============
        "input_section_title": "仓库地址",
        "input_placeholder": "输入 GitHub 或 Gitee 仓库地址（例如：https://github.com/owner/repo）",
        "token_section_title": "访问令牌（可选）",
        "token_placeholder": "GitHub/Gitee Personal Access Token（用于访问私有仓库）",
        "estimated_cost_title": "成本预估",
        "estimated_cost_notice": "分析前请确认预估成本",
        "estimated_cost_tip": "注：根据项目大小估算，实际时间可能因网络速度、AI服务响应时间而有所不同",
        "cost_high": "预估成本较高 (¥{cost:.2f})",
        "cost_medium": "预估成本适中 (¥{cost:.2f})",
        "cost_low": "预估成本较低 (¥{cost:.2f})",

        # ============ 按钮 ============
        "btn_estimate": "预估成本",
        "btn_confirm": "确认继续分析",
        "btn_cancel": "取消分析",
        "btn_confirm_cancel": "确认取消",
        "confirm_cancel_analysis": "确认取消分析？",
        "cancelling_analysis": "正在取消分析...",
        "cancel_request_sent": "取消请求已发送，可能需要几秒钟生效",
        "cancel_request_failed_polling": "取消请求发送失败，但已停止前端轮询",
        "cancel_request_failed_analysis": "取消请求发送失败，但已终止后续分析",
        "btn_generate_fix": "生成修复代码",
        "btn_generate_diff": "生成Diff",

        # ============ 错误提示 ============
        "error_empty_url": "请先输入仓库地址",
        "error_invalid_url_start": "仓库地址必须以 http:// 或 https:// 开头",
        "error_invalid_platform": "请输入有效的 GitHub 或 Gitee 仓库地址",
        "error_invalid_format": "仓库地址格式不正确，请提供完整的仓库URL（例如：https://github.com/owner/repo）",
        "error_unknown_platform": "检测到非 GitHub/Gitee 仓库地址，将尝试使用 GitHub 模式分析",
        "error_connection_backend": "连接后端失败：请检查后端服务是否已启动并在 http://localhost:8000 上运行",
        "error_start_analysis": "启动分析失败：{status} {text}",
        "error_cost_estimate": "成本估算失败：{status} - {text}",
        "error_failed": "失败",
        "error_connect_backend": "连接后端失败：{error}",
        "error_timeout": "请求超时：请检查网络连接或后端服务是否正常运行",
        "error_polling": "轮询出错：{error}",
        "error_failed_status": "获取任务状态失败：{status}",
        "error_load_failed": "加载失败: {error}",
        "error_load_history": "加载出错: {error}",
        "error_analysis_timeout": "分析超时：任务执行时间过长，可能仓库过大或网络连接缓慢",
        "error_clone_failed": "仓库克隆失败：请检查仓库地址或网络连接",
        "error_api_access": "API访问失败：请检查API密钥或访问权限",
        "error_permission": "访问权限不足：请检查访问令牌",
        "error_repo_not_found": "仓库未找到：请检查仓库地址是否正确",
        "error_network": "网络连接错误：请检查网络连接是否正常",
        "error_auto_fix_failed": "自动修复生成失败：{status} - {text}",
        "error_auto_fix_error": "自动修复生成出错：{error}",
        "error_diff_failed": "Diff生成失败：{status} - {text}",
        "error_diff_error": "Diff生成出错：{error}",

        # ============ 成功/信息提示 ============
        "success_analysis_complete": "分析完成",
        "success_auto_fix": "自动修复代码生成成功！",
        "success_diff": "Git Diff生成成功！",
        "success_history_loaded": "历史报告加载成功",
        "success_pdf": "PDF 生成成功",

        # ============ 警告提示 ============
        "warning_analysis_cancelled": "分析已取消",
        "warning_analysis_running": "检测到已有分析任务正在进行中，如需重新分析请先取消当前任务",
        "warning_high_cost": "预估成本较高 (¥{cost:.2f})，建议确认后再继续",
        "info_no_history": "暂无历史记录",
        "info_no_history_data": "无法获取历史记录",
        "info_no_scan": "静态代码分析未启用",
        "info_no_scan_issues": "静态代码扫描未发现明显问题",
        "info_no_issues": "未发现高危或中危安全漏洞，安全实践优秀",
        "info_low_risk_note": "注：部分历史兼容设计可能被标记为低风险，已忽略显示",
        "info_no_static_data": "暂无AI静态分析数据",
        "info_no_issues_found": "未发现任何问题，符合业界最佳安全实践",
        "info_support_platforms": "支持 GitHub 和 Gitee 平台；私有仓库未提供 Token 将启用有限分析模式",

        # ============ 分析状态 ============
        "status_analyzing": "正在分析仓库...",
        "status_cloning": "正在克隆仓库代码...",
        "status_structure": "分析仓库结构与社区数据...",
        "status_ai": "正在进行AI分析...",
        "status_static": "运行AI静态代码扫描...",
        "status_calculating": "计算最终得分...",

        # ============ 报告区域 ============
        "report_title": "项目健康度全维度可视化分析",

        # ============ 标签页 ============
        "tab_security": "安全漏洞分析",
        "tab_recommendations": "优化建议",
        "tab_static": "静态分析报告",
        "tab_export": "导出报告",

        # ============ 安全漏洞 ============
        "security_title": "安全漏洞详细分析",
        "security_high": "高危漏洞 ({count}个)",
        "security_medium": "中等风险 ({count}个)",
        "security_low": "低风险问题 ({count}个)",
        "security_type": "类型",
        "security_analysis": "分析",
        "security_impact": "影响",
        "security_issue_code": "问题代码",
        "security_fix_code": "修复代码",
        "security_recommendation": "建议",
        "security_no_code": "未提供代码片段",
        "security_manual_check": "请手动检查",
        "security_fix_soon": "建议及时修复",

        # ============ 优化建议 ============
        "recommendations_title": "优化建议",
        "priority_high": "高优先级 ({count}个)",
        "priority_medium": "中优先级 ({count}个)",
        "priority_low": "低优先级 ({count}个)",
        "rec_category": "类别",
        "rec_description": "描述",
        "rec_reason": "原因",
        "rec_impact": "影响",
        "rec_current_code": "当前代码",
        "rec_fix": "建议修复",
        "rec_recommendation": "建议",

        # ============ 静态分析 ============
        "static_title": "AI静态分析详细报告",
        "static_no_issues": "未发现任何问题，符合业界最佳安全实践",

        # ============ 导出报告 ============
        "export_title": "导出专业报告",
        "export_format": "输出格式",
        "export_pdf": "PDF",
        "export_md": "Markdown",
        "export_json": "JSON",
        "export_download": "点击下载 {format} 报告",
        "export_error": "PDF生成失败：{error}",

        # ============ 历史记录 ============
        "history_title": "分析历史",
        "history_recent": "最近分析记录",
        "history_created": "创建时间",
        "history_platform": "平台",
        "history_actions": "操作",
        "history_load": "加载",

        # ============ 页脚 ============
        "footer_copyright": "CodePulse AI © 2025",

        # ============ 其他 ============
        "unknown": "未知",
        "global": "全局",
        "repo_description": "描述",
        "repo_author": "作者",
        "repo_created": "创建时间",
        "repo_language": "主要编程语言",
        "repo_size": "仓库大小",

        # ============ 自动修复功能 ============
        "generating_fix": "正在生成自动修复代码...",
        "auto_fix_expander": "自动修复代码",
        "download_fix": "下载修复代码",
        "code_diff": "代码差异",
        "generating_diff": "正在生成Git Diff...",
        "diff_patch_expander": "Git Diff 补丁",
        "download_diff": "下载 Diff 补丁",
        "apply_command": "应用补丁命令",
        "affected_files": "影响的文件",
        "changes_count": "处修改",

        # ============ 侧边栏 ============
        "sidebar_config": "系统配置",
        "backend_url": "后端服务地址",
        "ai_engine": "AI 分析引擎",
        "enable_static_scan": "启用静态代码分析",

        # ============ 历史记录 ============
        "view_button": "查看",
        "loading_history": "正在加载历史报告...",
        "loading_failed": "加载失败",

        # ============ 成本估算 ============
        "scanning_cost": "正在扫描仓库并估算成本...",
        "cost_estimate_result": "成本估算结果",
        "estimated_tokens": "预估Token",
        "file_count_label": "文件数量",
        "code_lines_label": "代码行数",
        "estimated_cost_label": "预估成本",
        "estimated_time": "预估时间",
        "skipped_files_label": "跳过文件",
        "filtered_file_types": "过滤的文件类型",
        "blacklist_rules": "黑名单规则",
        "skipped_large_files": "跳过的大文件",
        "skipped_binary_files": "跳过的二进制文件",
        "large_files_list": "大文件列表",
        "confirm_continue": "确认继续分析",

        # ============ 主界面 ============
        "input_url_label": "请输入 GitHub 或 Gitee 仓库地址",
        "input_url_placeholder": "https://github.com/zhouyanye/codepulse-ai 或 https://gitee.com/zhou-yanye/houseSpider",
        "help_text": "请输入 GitHub 或 Gitee 仓库地址，如 https://github.com/zhouyanye/codepulse-ai或 https://gitee.com/zhou-yanye/houseSpider",
        "start_analysis_btn": "开始分析",
        "processing_label": "处理中",
        "error_occurred": "未知错误",

        # ============ 结果展示 ============
        "limited_analysis_mode": "{platform}私有仓库 · 本地有限分析模式",
        "author_label": "作者",
        "unknown_date": "未知",
        "created_at_label": "创建时间",
        "last_updated": "最后更新",
        "main_language_label": "主语言",
        "latest_release_label": "最新发布",
        "no_release_data": "无发布信息",
        "no_data": "无数据",
        "default_branch_label": "默认分支",
        "contributors_label": "贡献者",
        "people_unit": "人",
        "license_label": "许可证",
        "not_specified_label": "未指定",
        "topics_label": "标签",
        "no_topics": "无标签",
        "cicd_status_label": "CI/CD状态",
        "enabled": "已启用",
        "not_configured": "未配置",

        # ============ 图表 ============
        "overall_health_label": "总体健康度",
        "health_label": "健康度",
        "radar_chart_title": "多维度评分雷达图",
        "code_quality_label": "代码质量",
        "community_health_label": "社区健康",
        "documentation_label": "文档完整",
        "maintenance_label": "维护活跃",
        "score_label": "评分",
        "health_trend_title": "项目健康趋势",
        "score_word": "得分",
        "static_issues_title": "静态分析问题分布",
        "high_risk": "高危",
        "medium_risk": "中等",
        "low_risk_label": "低风险",
        "info_word": "提示",
        "issues_count_unit": "个",
        "records": "记录",
        "minutes_unit": "分钟",

        # ============ Markdown报告 ============
        "report_title_md": "# CodePulse AI 开源项目健康评估报告",
        "repo_link": "[{platform_name}仓库]({url})",
        "author_link": "[{owner}]({url})",
        "analysis_time": "**分析时间**",
        "analysis_mode": "**分析模式**",
        "ai_generated": "**AI生成标识**：本报告由人工智能（AI）生成，内容仅供参考。",
        "overall_score": "## 总体评分：{score}/100",
        "score_table": "| 评估维度   | 得分                        | 说明                     |",
        "code_quality_desc": "代码规范性与可维护性",
        "community_desc": "社区活跃度与协作情况",
        "documentation_desc": "文档质量与可读性",
        "maintenance_desc": "项目维护频率",
        "security_desc": "安全漏洞和风险评估",
        "score_explanation": "**评分占比说明：**",
        "code_quality_weight": "- 代码质量评分：占 **30%** 权重 - 核心功能代码的质量",
        "community_weight": "- 社区健康评分：占 **20%** 权重 - 基于stars、forks、issues",
        "security_weight": "- 安全漏洞评分：占 **20%** 权重 - 存在高危安全问题会大幅降低此分数",
        "documentation_weight": "- 文档完整评分：占 **15%** 权重 - 文档质量与可读性",
        "maintenance_weight": "- 维护活跃评分：占 **15%** 权重 - 项目维护频率",
        "score_note": "**注意：** 各维度评分范围为 0-100 分。分数越高表示该维度表现越优秀。总体评分是各个维度加权计算的结果。若某一维度评分较低，将显著影响总体评分。",
        "security_analysis_title": "## 安全漏洞分析",
        "high_vulnerabilities": "### 高危漏洞 ({count}个)",
        "medium_risks": "### 中等风险 ({count}个)",
        "low_issues": "### 低风险问题 ({count}个)",
        "unknown_issue": "未知安全问题",
        "unknown_location": "未知位置",
        "security_vulnerability": "安全漏洞",
        "requires_analysis": "需要进一步分析",
        "security_risk": "潜在安全风险",
        "issue_code_label": "**问题代码:**",
        "no_code_snippet": "# 未提供代码片段",
        "fix_code_label": "**修复代码:**",
        "check_manually": "# 请手动检查",
        "fix_prompt": "**建议**",
        "fix_soon": "建议及时修复",
        "no_security_issues": "\n 未检测到明显的安全漏洞\n",
        "static_scan_title": "\n## 静态扫描详细报告\n",
        "tool_section": "\n### {tool_name} ({count} 条记录)\n",
        "no_issues_best": "未发现任何问题，符合业界最佳安全实践",
        "position_label": "  - **位置**",
        "severity_label": "  - **严重程度**",
        "severity_high_word": "高危",
        "severity_medium_word": "中等",
        "severity_low_word": "低风险",
        "severity_general": "一般",
        "no_scan_result": "\n未进行静态扫描或扫描无结果\n",
        "optimization_title": "\n## 优化建议\n",
        "high_priority_section": "\n### 高优先级 ({count}个)",
        "medium_priority_section": "\n### 中优先级 ({count}个)",
        "low_priority_section": "\n### 低优先级 ({count}个)",
        "opt_suggestion": "优化建议",
        "code_optimization": "代码优化",
        "need_optimization": "需要优化",
        "improve_quality": "提高代码质量",
        "improve_project_quality": "改善项目质量",
        "current_code_label": "**当前代码:**",
        "suggested_fix_label": "**建议修复:**",
        "fix_as_above": "请按照上述方案修复",
        "expert_conclusion": "\n### 专家结论\n",
        "expert_point1": "- 此项目已达到业界顶尖水平，代码质量、安全性、架构设计均无可挑剔\n",
        "expert_point2": "- 社区活跃、文档完善、测试覆盖全面，属于标杆级开源项目\n",
        "expert_point3": "- 建议继续保持当前优秀实践与开发节奏\n",
        "platform_default": "代码托管平台",
        "limited_mode": "本地有限分析模式",
        "full_mode": "完整分析模式",

        # ============ 报告导出 ============
        "download_md": "下载 Markdown 报告",
        "generate_pdf_btn": "生成 PDF 报告",
        "generating_pdf": "正在生成 PDF...",
        "pdf_empty": "生成的PDF为空，请检查HTML内容或字体配置。",
    },

    "en-US": {
        # ============ Page Title ============
        "app_title": "CodePulse AI Open Source Project Health Scanner",
        "app_subtitle": "AI-driven code quality analysis tool, supports GitHub and Gitee platforms",
        "main_header_text": "CodePulse AI",
        "main_subtitle": "Open Source Project Comprehensive Health Assessment System · Professional · Objective · Comprehensive",

        # ============ Input Section ============
        "input_section_title": "Repository URL",
        "input_placeholder": "Enter GitHub or Gitee repository URL (e.g., https://github.com/owner/repo)",
        "token_section_title": "Access Token (Optional)",
        "token_placeholder": "GitHub/Gitee Personal Access Token (for private repositories)",
        "estimated_cost_title": "Cost Estimation",
        "estimated_cost_notice": "Please confirm the estimated cost before analysis",
        "estimated_cost_tip": "Note: Estimated based on project size, actual time may vary due to network speed and AI service response time",
        "cost_high": "High estimated cost (¥{cost:.2f})",
        "cost_medium": "Medium estimated cost (¥{cost:.2f})",
        "cost_low": "Low estimated cost (¥{cost:.2f})",

        # ============ Buttons ============
        "btn_estimate": "Estimate Cost",
        "btn_confirm": "Confirm & Analyze",
        "btn_cancel": "Cancel Analysis",
        "btn_generate_fix": "Generate Fix Code",
        "btn_generate_diff": "Generate Diff",

        # ============ Error Messages ============
        "error_empty_url": "Please enter a repository URL first",
        "error_invalid_url_start": "Repository URL must start with http:// or https://",
        "error_invalid_platform": "Please enter a valid GitHub or Gitee repository URL",
        "error_invalid_format": "Invalid repository URL format, please provide complete URL (e.g., https://github.com/owner/repo)",
        "error_unknown_platform": "Detected non-GitHub/Gitee repository URL, will attempt analysis using GitHub mode",
        "error_connection_backend": "Failed to connect to backend: Please check if backend service is running at http://localhost:8000",
        "error_start_analysis": "Failed to start analysis: {status} {text}",
        "error_cost_estimate": "Cost estimation failed: {status} - {text}",
        "error_failed": "Failed",
        "error_connect_backend": "Failed to connect to backend: {error}",
        "error_polling": "Polling error: {error}",
        "error_failed_status": "Failed to get task status: {status}",
        "error_load_failed": "Load failed: {error}",
        "error_load_history": "History load error: {error}",
        "error_auto_fix_failed": "Auto-fix generation failed: {status} - {text}",
        "error_auto_fix_error": "Auto-fix generation error: {error}",
        "error_diff_failed": "Diff generation failed: {status} - {text}",
        "error_diff_error": "Diff generation error: {error}",

        # ============ Success/Info Messages ============
        "success_analysis_complete": "Analysis Complete",
        "success_auto_fix": "Auto-fix code generated successfully!",
        "success_diff": "Git Diff generated successfully!",
        "success_history_loaded": "History report loaded successfully",
        "success_pdf": "PDF generated successfully",

        # ============ Warning Messages ============
        "warning_analysis_cancelled": "Analysis cancelled",
        "warning_high_cost": "High estimated cost (¥{cost:.2f}), please confirm before proceeding",
        "info_no_history": "No history records",
        "info_no_history_data": "Unable to fetch history records",
        "info_no_scan": "Static code analysis not enabled",
        "info_no_scan_issues": "Static code scan found no obvious issues",
        "info_no_issues": "No high or medium security vulnerabilities found, excellent security practices",
        "info_low_risk_note": "Note: Some legacy compatibility designs may be marked as low risk, ignored from display",
        "info_no_static_data": "No AI static analysis data available",
        "info_no_issues_found": "No issues found, meets industry best practices",
        "info_support_platforms": "Supports GitHub and Gitee platforms; Private repositories without Token will use limited analysis mode",

        # ============ Analysis Status ============
        "status_analyzing": "Analyzing repository...",
        "status_cloning": "Cloning repository code...",
        "status_structure": "Analyzing repository structure and community data...",
        "status_ai": "Performing AI analysis...",
        "status_static": "Running AI static code scanning...",
        "status_calculating": "Calculating final scores...",

        # ============ Report Section ============
        "report_title": "Project Health Multi-dimensional Visualization Analysis",

        # ============ Tabs ============
        "tab_security": "Security Vulnerabilities",
        "tab_recommendations": "Optimization Recommendations",
        "tab_static": "Static Analysis Report",
        "tab_export": "Export Report",

        # ============ Security Vulnerabilities ============
        "security_title": "Security Vulnerability Detailed Analysis",
        "security_high": "High Risk Vulnerabilities ({count})",
        "security_medium": "Medium Risk ({count})",
        "security_low": "Low Risk Issues ({count})",
        "security_type": "Type",
        "security_analysis": "Analysis",
        "security_impact": "Impact",
        "security_issue_code": "Issue Code",
        "security_fix_code": "Fix Code",
        "security_recommendation": "Recommendation",
        "security_no_code": "No code snippet provided",
        "security_manual_check": "Please check manually",
        "security_fix_soon": "Recommended to fix promptly",
        "security_placeholder_filtered": "Filtered placeholder security issues",

        # ============ Recommendations ============
        "recommendations_title": "Optimization Recommendations",
        "priority_high": "High Priority ({count})",
        "priority_medium": "Medium Priority ({count})",
        "priority_low": "Low Priority ({count})",
        "rec_category": "Category",
        "rec_description": "Description",
        "rec_reason": "Reason",
        "rec_impact": "Impact",
        "rec_current_code": "Current Code",
        "rec_fix": "Suggested Fix",
        "rec_recommendation": "Recommendation",

        # ============ Static Analysis ============
        "static_title": "AI Static Analysis Detailed Report",
        "static_no_issues": "No issues found, meets industry best practices",

        # ============ Export Report ============
        "export_title": "Export Professional Report",
        "export_format": "Output Format",
        "export_pdf": "PDF",
        "export_md": "Markdown",
        "export_json": "JSON",
        "export_download": "Click to download {format} report",
        "export_error": "PDF generation failed: {error}",

        # ============ History ============
        "history_title": "Analysis History",
        "history_recent": "Recent Analysis Records",
        "history_created": "Created",
        "history_platform": "Platform",
        "history_actions": "Actions",
        "history_load": "Load",

        # ============ Footer ============
        "footer_copyright": "CodePulse AI © 2025",

        # ============ Others ============
        "unknown": "Unknown",
        "global": "Global",
        "repo_description": "Description",
        "repo_author": "Author",
        "repo_created": "Created",
        "repo_language": "Primary Language",
        "repo_size": "Repository Size",

        # ============ Auto Fix Functions ============
        "generating_fix": "Generating auto-fix code...",
        "auto_fix_expander": "Auto Fix Code",
        "download_fix": "Download Fix Code",
        "code_diff": "Code Diff",
        "generating_diff": "Generating Git Diff...",
        "diff_patch_expander": "Git Diff Patch",
        "download_diff": "Download Diff Patch",
        "apply_command": "Apply Patch Command",
        "affected_files": "Affected Files",
        "changes_count": "changes",

        # ============ Sidebar ============
        "sidebar_config": "System Configuration",
        "backend_url": "Backend Service URL",
        "ai_engine": "AI Analysis Engine",
        "enable_static_scan": "Enable Static Code Analysis",

        # ============ History ============
        "view_button": "View",
        "loading_history": "Loading history report...",
        "loading_failed": "Load failed",

        # ============ Cost Estimation ============
        "scanning_cost": "Scanning repository and estimating cost...",
        "cost_estimate_result": "Cost Estimation Result",
        "estimated_tokens": "Estimated Tokens",
        "file_count_label": "File Count",
        "code_lines_label": "Code Lines",
        "estimated_cost_label": "Estimated Cost",
        "estimated_time": "Estimated Time",
        "skipped_files_label": "Skipped Files",
        "filtered_file_types": "Filtered File Types",
        "blacklist_rules": "Blacklist Rules",
        "skipped_large_files": "Skipped Large Files",
        "skipped_binary_files": "Skipped Binary Files",
        "large_files_list": "Large Files List",
        "confirm_continue": "Confirm & Continue Analysis",

        # ============ Units ============
        "minutes_unit": "minutes",

        # ============ Main Interface ============
        "input_url_label": "Please enter GitHub or Gitee repository URL",
        "input_url_placeholder": "https://github.com/psf/requests or https://gitee.com/eatmoreapple/juice/blob/main/handler.go",
        "help_text": "Please enter GitHub or Gitee repository URL, e.g., https://github.com/psf/requests or https://gitee.com/eatmoreapple/juice/blob/main/handler.go",
        "start_analysis_btn": "Start Analysis",
        "processing_label": "Processing",
        "error_occurred": "Unknown error",

        # ============ Result Display ============
        "limited_analysis_mode": "{platform} Private Repository · Local Limited Analysis Mode",
        "author_label": "Author",
        "unknown_date": "Unknown",
        "created_at_label": "Created",
        "last_updated": "Last Updated",
        "main_language_label": "Main Language",
        "latest_release_label": "Latest Release",
        "no_release_data": "No release information",
        "no_data": "No data",
        "default_branch_label": "Default Branch",
        "contributors_label": "Contributors",
        "people_unit": "people",
        "license_label": "License",
        "not_specified_label": "Not specified",
        "topics_label": "Topics",
        "no_topics": "No topics",
        "cicd_status_label": "CI/CD Status",
        "enabled": "Enabled",
        "not_configured": "Not configured",

        # ============ Charts ============
        "overall_health_label": "Overall Health",
        "health_label": "Health",
        "radar_chart_title": "Multi-dimensional Score Radar Chart",
        "code_quality_label": "Code Quality",
        "community_health_label": "Community Health",
        "documentation_label": "Documentation",
        "maintenance_label": "Maintenance",
        "score_label": "Score",
        "health_trend_title": "Project Health Trend",
        "score_word": "Score",
        "static_issues_title": "Static Analysis Issue Distribution",
        "high_risk": "High",
        "medium_risk": "Medium",
        "low_risk_label": "Low Risk",
        "info_word": "Info",
        "issues_count_unit": "issues",

        # ============ Report Export ============
        "download_md": "Download Markdown Report",
        "generate_pdf_btn": "Generate PDF Report",
        "generating_pdf": "Generating PDF...",
        "pdf_empty": "Generated PDF is empty, please check HTML content or font configuration.",

        # ============ Markdown Report ============
        "report_title_md": "# CodePulse AI Open Source Project Health Assessment Report",
        "repo_link": "[{platform_name} Repository]({url})",
        "author_link": "[{owner}]({url})",
        "analysis_time": "**Analysis Time**",
        "analysis_mode": "**Analysis Mode**",
        "ai_generated": "**AI Generated**: This report is generated by Artificial Intelligence (AI) and is for reference only.",
        "overall_score": "## Overall Score: {score}/100",
        "score_table": "| Assessment Dimension | Score | Description |",
        "code_quality_desc": "Code standardity and maintainability",
        "community_desc": "Community activity and collaboration",
        "documentation_desc": "Documentation quality and readability",
        "maintenance_desc": "Project maintenance frequency",
        "security_desc": "Security vulnerability and risk assessment",
        "score_explanation": "**Score Weight Explanation:**",
        "code_quality_weight": "- Code Quality Score: **30%** weight - Quality of core functionality code",
        "community_weight": "- Community Health Score: **20%** weight - Based on stars, forks, issues",
        "security_weight": "- Security Vulnerability Score: **20%** weight - High-risk security issues will significantly reduce this score",
        "documentation_weight": "- Documentation Completeness Score: **15%** weight - Documentation quality and readability",
        "maintenance_weight": "- Maintenance Activity Score: **15%** weight - Project maintenance frequency",
        "score_note": "**Note:** Each dimension score ranges from 0-100. Higher scores indicate better performance in that dimension. The overall score is the weighted result of all dimensions. If any dimension has a low score, it will significantly affect the overall score.",
        "security_analysis_title": "## Security Vulnerability Analysis",
        "high_vulnerabilities": "### High Risk Vulnerabilities ({count})",
        "medium_risks": "### Medium Risks ({count})",
        "low_issues": "### Low Risk Issues ({count})",
        "unknown_issue": "Unknown security issue",
        "unknown_location": "Unknown location",
        "security_vulnerability": "Security vulnerability",
        "requires_analysis": "Requires further analysis",
        "security_risk": "Potential security risk",
        "issue_code_label": "**Issue Code:**",
        "no_code_snippet": "# No code snippet provided",
        "fix_code_label": "**Fix Code:**",
        "check_manually": "# Please check manually",
        "fix_prompt": "**Recommendation**",
        "fix_soon": "Recommended to fix promptly",
        "no_security_issues": "\n No obvious security vulnerabilities detected\n",
        "static_scan_title": "\n## Static Scan Detailed Report\n",
        "tool_section": "\n### {tool_name} ({count} records)\n",
        "no_issues_best": "No issues found, meets industry best practices",
        "position_label": "  - **Location**",
        "severity_label": "  - **Severity**",
        "severity_high_word": "High",
        "severity_medium_word": "Medium",
        "severity_low_word": "Low Risk",
        "severity_general": "General",
        "no_scan_result": "\nStatic scan not performed or no scan results\n",
        "optimization_title": "\n## Optimization Recommendations\n",
        "high_priority_section": "\n### High Priority ({count})",
        "medium_priority_section": "\n### Medium Priority ({count})",
        "low_priority_section": "\n### Low Priority ({count})",
        "opt_suggestion": "Optimization suggestion",
        "code_optimization": "Code optimization",
        "need_optimization": "Needs optimization",
        "improve_quality": "Improve code quality",
        "improve_project_quality": "Improve project quality",
        "current_code_label": "**Current Code:**",
        "suggested_fix_label": "**Suggested Fix:**",
        "fix_as_above": "Please fix according to the above solution",
        "expert_conclusion": "\n### Expert Conclusion\n",
        "expert_point1": "- This project has reached industry-leading level, with impeccable code quality, security, and architecture design\n",
        "expert_point2": "- Active community, complete documentation, comprehensive testing coverage, belonging to a benchmark-level open source project\n",
        "expert_point3": "- Recommend maintaining current excellent practices and development rhythm\n",
        "platform_default": "Code hosting platform",
        "limited_mode": "Local limited analysis mode",
        "full_mode": "Complete analysis mode",
        "records": "records",
        "further_analysis": "Requires further analysis",
        "potential_risk": "Potential security risk",
    }
}


def get_locale() -> str:
    """
    获取当前语言设置
    默认使用中文，支持英文切换
    """
    # 从session state获取，如果没有则默认为中文
    if 'locale' not in st.session_state:
        st.session_state['locale'] = 'zh-CN'
    return st.session_state['locale']


def set_locale(locale: str):
    """
    设置当前语言
    :param locale: 语言代码，如 'zh-CN' 或 'en-US'
    """
    if locale in TRANSLATIONS:
        st.session_state['locale'] = locale
    else:
        st.warning(f"Unsupported language: {locale}, using default (zh-CN)")


def t(key: str, **kwargs) -> str:
    """
    翻译函数
    :param key: 翻译键
    :param kwargs: 格式化参数
    :return: 翻译后的文本
    """
    locale = get_locale()

    # 如果键不存在，返回键本身
    if locale not in TRANSLATIONS:
        return key

    if key not in TRANSLATIONS[locale]:
        # 尝试使用中文作为fallback
        if 'zh-CN' in TRANSLATIONS and key in TRANSLATIONS['zh-CN']:
            return TRANSLATIONS['zh-CN'][key].format(** kwargs) if kwargs else TRANSLATIONS['zh-CN'][key]
        return key

    translation = TRANSLATIONS[locale][key]

    # 支持格式化
    if kwargs:
        try:
            return translation.format(** kwargs)
        except KeyError as e:
            st.warning(f"Missing format parameter in translation: {e}")
            return translation

    return translation


def switch_language():
    """
    在侧边栏显示语言切换器
    """
    locale = get_locale()

    st.sidebar.markdown("---")
    st.sidebar.markdown("#### Language / 语言")

    col_zh, col_en = st.sidebar.columns(2)

    with col_zh:
        if st.button("中文", disabled=(locale == 'zh-CN'), use_container_width=True):
            set_locale('zh-CN')
            st.rerun()

    with col_en:
        if st.button("English", disabled=(locale == 'en-US'), use_container_width=True):
            set_locale('en-US')
            st.rerun()
    return st.session_state['locale']