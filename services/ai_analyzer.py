import logging
import os
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from app.core.config import settings

from utils.ai_client import AIClient
from utils.ai_provider_utils import get_available_provider
from utils.security_utils import SecurityUtils
from services.code_quality_service import CodeQualityService
from services.recommendation_service import RecommendationService
from models.analysis_models import (
    CodeQualityMetrics,
    CommunityHealthMetrics,
    DocumentationMetrics,
    MaintenanceMetrics,
    RiskAssessment,
    AnalysisResult
)

logger = logging.getLogger(__name__)


class AIAnalyzer:
    def __init__(self, provider: Optional[str] = None):
        """
        初始化AIAnalyzer实例

        Args:
            provider: AI提供者名称，如果为None则使用默认提供者
        """
        # 使用降级机制获取可用提供商
        self.provider = get_available_provider(provider)
        self.ai_client = AIClient(self.provider)
        self.is_api_only_mode = (self.provider == "costrict")  # CoStrict模式：只使用API数据，不调用AI

        # 初始化服务（在costrict模式下，这些服务会自动处理不使用AI的情况）
        if not self.is_api_only_mode:
            self.code_quality_service = CodeQualityService(self.ai_client)
            self.recommendation_service = RecommendationService(self.ai_client)
        else:
            self.code_quality_service = None
            self.recommendation_service = None

        logger.info(f"初始化完成-提供者: {self.provider},仅API模式:{self.is_api_only_mode}")

    def _validate_repo_has_code(self, repo_path: Optional[str]) -> bool:
        """
        验证仓库路径是否包含源代码
        """
        if not repo_path or not os.path.exists(repo_path) or not os.path.isdir(repo_path):
            return False

        # 限制检查的文件数量
        validation_check_limit = 100  # 检查最多100个文件
        checked_count = 0

        # 扩展代码扩展名列表，支持更多语言
        code_extensions = {
            '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.go', '.rs',
            '.cpp', '.c', '.php', '.h', '.hpp', '.rb', '.kt', '.swift',
            '.html', '.css', '.vue', '.dart', '.sql', '.graphql'
        }

        for root, dirs, files in os.walk(repo_path):
            # 跳过排除的目录
            dirs[:] = [d for d in dirs if d not in {
                ".git", ".gitlab", ".bitbucket", ".circleci", ".travis", ".drone",
                "static", "site", "dist", "build", "target", "out", "__pycache__", ".pyc",
                "venv", "env", ".venv", "node_modules", "vendor", "bower_components",
                ".idea", ".vscode", ".vs", ".project", ".settings", ".metadata",
                "tmp", "logs", "cache", ".cache", "images", "static", "public", "assets", "media", "img",
                "fonts", "test", "__pycache__", ".pytest_cache"
            }]

            for file in files:
                if checked_count >= validation_check_limit:
                    logger.debug(f"已检查 {checked_count} 个文件，验证完成")
                    return True

                ext = os.path.splitext(file)[1].lower()
                if ext in code_extensions:
                    logger.debug(f"找到源代码文件: {os.path.join(root, file)}")
                    return True
                checked_count += 1

        logger.warning(f"仓库路径缺少源代码文件（已检查 {checked_count} 个文件）: {repo_path}")
        return False

    def _create_no_code_analysis_result(self, repo_info: Dict[str, Any]) -> AnalysisResult:
        """
        创建仓库无代码时的分析结果
        """
        logger.info(f"创建无代码分析结果: {repo_info.get('full_name')}")

        return AnalysisResult(
            repo_info=repo_info,
            code_quality=CodeQualityMetrics(
                score=0,
                complexity=0,
                documentation_score=0,
                security_issues=[],
                code_standards=["仓库中未检测到源代码文件"],
                dependencies_health={"score": 0, "comment": "无代码文件，无法分析依赖", "healthy": True},
                static_scan_results={},
                security_score=100  # 无代码则无安全问题
            ),
            community_health=CommunityHealthMetrics(
                score=20,  # 基础分数
                contributors_count=0,
                recent_activity={"commits": 0, "issues": 0},
                issue_health={
                    "open_issues": repo_info.get("open_issues", 0),
                    "closed_issues": 0,
                    "response_time": None
                },
                community_growth={
                    "stars": repo_info.get("stars", 0),
                    "forks": repo_info.get("forks", 0)
                }
            ),
            documentation=DocumentationMetrics(
                score=20,  # 基础文档分数
                readme_quality=0,
                has_contributing=False,
                has_license=bool(repo_info.get("license")),
                has_code_of_conduct=False,
                has_issue_template=False,
                has_pr_template=False,
                wiki_enabled=repo_info.get("has_wiki", False)
            ),
            maintenance=MaintenanceMetrics(
                score=20,  # 基础维护分数
                update_frequency=0,
                dependency_updates={},
                release_frequency=0,
                response_time=0.0
            ),
            risk_assessment=RiskAssessment(
                security=[],  # 无代码则无安全风险
                maintenance=["仓库中未检测到源代码文件"],
                community=[],
                license=[]
            ),
            recommendations=[{
                "id": 1,
                "category": "项目结构",
                "priority": "高",
                "title": "仓库中未检测到源代码文件",
                "location": "全局",
                "description": "分析过程中未在仓库中找到任何源代码文件，这可能是因为仓库为空或不包含支持的编程语言文件",
                "issue": "缺少源代码",
                "fix": "请确认仓库中包含有效的源代码文件",
                "reason": "仓库结构分析未发现任何源代码文件",
                "impact": "项目无法进行代码质量、安全和性能分析",
                "recommendation": "请检查仓库内容，确保包含有效的源代码文件"
            }],
            overall_score=20
        )

    async def analyze_repository(self, repo_data: Dict[str, Any], repo_path: Optional[str] = None,
                                 progress_callback=None) -> AnalysisResult:
        """
        综合分析仓库健康状况

        Args:
            repo_data: 仓库数据字典，包含仓库信息、结构、社区指标等
            repo_path: 本地仓库路径（可选）
            progress_callback: 进度回调函数（可选）

        Returns:
            AnalysisResult: 分析结果对象
        """

        repo_info = repo_data["repo_info"]
        repo_name = repo_info["full_name"]
        logger.info(f"开始分析仓库: {repo_name},提供者: {self.provider}")

        # 验证仓库路径是否有代码
        if repo_path and not self._validate_repo_has_code(repo_path):
            logger.warning(f"仓库路径没有源代码，使用默认分析结果: {repo_path}")
            return self._create_no_code_analysis_result(repo_info)

        # 检测平台类型
        platform = repo_data.get("platform")
        if not platform:
            platform = self._detect_platform(repo_info.get("html_url", ""))
        logger.info(f"检测到平台类型: {platform}")

        # CoStrict模式：只使用API数据，不调用AI
        if self.is_api_only_mode:
            logger.info(f"使用CoStrict模式（仅API数据评分）")
            # 使用默认AI分析结果（基于API数据）
            ai_code_analysis = self._get_default_ai_analysis(repo_data)
        else:
            # 更新进度回调
            if progress_callback:
                await progress_callback(72, "正在进行AI代码质量分析...")
            # 1. AI 代码质量分析
            ai_code_analysis = await self.code_quality_service.analyze_code_quality(repo_data)

        # 2. 计算各项指标
        if progress_callback:
            await progress_callback(75, "正在计算各项指标...")
        code_quality = self._calculate_code_quality_metrics(repo_data, ai_code_analysis, platform)
        community_health = self._calculate_community_health_metrics(repo_data)
        documentation = self._calculate_documentation_metrics(repo_data)
        maintenance = self._calculate_maintenance_metrics(repo_data)
        risk_assessment = self._assess_risks(repo_data, code_quality, community_health)

        # 3. 生成并标准化优化建议
        if progress_callback:
            await progress_callback(80, "正在生成优化建议...")
        intermediate_analysis = {
            "repo_info": repo_info,
            "code_quality": code_quality.dict(),
            "community_health": community_health.dict(),
            "documentation": documentation.dict(),
            "maintenance": maintenance.dict(),
            "risk_assessment": risk_assessment.dict()
        }

        if self.is_api_only_mode:
            # CoStrict模式：只提供评分，不生成优化建议
            raw_recommendations = []  # 返回空列表，不显示任何建议
        else:
            try:
                # 使用新服务生成优化建议
                raw_recommendations = await self.recommendation_service.generate_recommendations(intermediate_analysis)
                logger.info(
                    f"AI建议生成完成，原始建议数量: {len(raw_recommendations) if isinstance(raw_recommendations, list) else 1}")
                logger.debug(f"原始建议类型: {type(raw_recommendations)}")
                if isinstance(raw_recommendations, list) and len(raw_recommendations) > 0:
                    logger.debug(f"第一条建议: {raw_recommendations[0]}")
            except Exception as e:
                logger.warning(f"AI建议生成失败: {e}，使用兜底建议")
                raw_recommendations = ["项目整体表现良好"]

        recommendations = self._normalize_recommendations(raw_recommendations)
        logger.info(f"成功生成并标准化 {len(recommendations)} 条优化建议")
        if len(recommendations) > 0:
            logger.debug(f"标准化后第一条建议: {recommendations[0]}")

        # 4. 计算总分
        if progress_callback:
            await progress_callback(90, "正在计算总分...")
        overall_score = self._calculate_overall_score(
            code_quality.score,
            community_health.score,
            documentation.score,
            maintenance.score,
            code_quality.security_score
        )

        # 5. 组装最终结果
        if progress_callback:
            await progress_callback(95, "正在组装最终结果...")
        result = AnalysisResult(
            repo_info=repo_info,
            code_quality=code_quality,
            community_health=community_health,
            documentation=documentation,
            maintenance=maintenance,
            risk_assessment=risk_assessment,
            recommendations=recommendations,
            overall_score=overall_score
        )

        logger.info(f"Completed AI analysis for: {repo_name}")
        return result

    # 建议标准化
    def _recommendation_fallback(self, content: str = "项目整体表现良好") -> List[dict]:
        """
        生成默认的推荐建议（当AI建议生成失败时的备选方案）

        Args:
            content: 建议内容，默认为"项目整体表现良好"

        Returns:
            包含默认建议的列表
        """
        return [{
            "id": 1,
            "category": "综合评价",
            "priority": "中",
            "title": content[:60],
            "location": "全局分析",
            "description": content,
            "issue": "",
            "fix": "",
            "reason": "保持良好实践",
            "impact": "维持项目健康",
            "recommendation": content
        }]

    def _normalize_recommendations(self, recs: Any) -> List[dict]:
        """
        标准化建议格式，将不同格式的建议统一为标准格式

        Args:
            recs: 建议内容，可以是字符串、字典或列表

        Returns:
            标准化后的建议列表
        """
        if not recs:
            return self._recommendation_fallback()
        if isinstance(recs, str):
            recs = [recs]

        normalized = []
        # 使用 enumerate 生成 id，逻辑更清晰
        for i, rec in enumerate(recs, 1):
            try:
                if isinstance(rec, dict) and rec:
                    # 清理location字段
                    raw_location = str(rec.get("location", "全局建议") or "全局建议")
                    cleaned_location = self._clean_location(raw_location)

                    # 验证location是否为合理的文件路径
                    is_valid_location = True

                    # 检查是否为合理的文件路径
                    if cleaned_location != "未知位置" and not self._is_reasonable_file_path(cleaned_location):
                        # 如果文件路径不合理，跳过该建议
                        is_valid_location = False
                        logger.debug(f"[建议验证] 跳过不合理的文件路径: {cleaned_location}")

                    if not is_valid_location:
                        continue

                    normalized.append({
                        "id": int(rec.get("id", i)),
                        "category": str(rec.get("category", "通用优化") or "通用优化"),
                        "priority": str(rec.get("priority", "中") or "中"),
                        "title": str(rec.get("title") or rec.get("description") or "优化建议")[:100],
                        "location": cleaned_location,
                        "description": str(rec.get("description", "") or str(rec))[:500],
                        "issue": str(rec.get("issue", "") or ""),
                        "fix": str(rec.get("fix", "") or ""),
                        "reason": str(rec.get("reason", "提升项目质量") or "提升项目质量"),
                        "impact": str(rec.get("impact", "改善整体质量") or "改善整体质量"),
                        "recommendation": str(rec.get("recommendation", "") or str(rec))[:500]
                    })
                elif isinstance(rec, str) and rec.strip():
                    clean = rec.strip()

                    parsed_suggestions = self._parse_markdown_suggestions(clean)
                    if parsed_suggestions:
                        for suggestion in parsed_suggestions:
                            suggestion["id"] = len(normalized) + 1
                            normalized.append(suggestion)
                    else:
                        normalized.append({
                            "id": len(normalized) + 1,
                            "category": "代码质量",
                            "priority": "中",
                            "title": clean[:60] + ("..." if len(clean) > 60 else ""),
                            "location": "全局分析",
                            "description": clean,
                            "issue": "",
                            "fix": "",
                            "reason": "优化建议",
                            "impact": "提升项目质量",
                            "recommendation": clean
                        })
            except Exception as e:
                logger.error(f"标准化建议失败: {e}, 原内容: {rec}")
                continue

        return normalized if normalized else self._recommendation_fallback()

    def _parse_markdown_suggestions(self, markdown_text: str) -> List[Dict]:
        """
        解析Markdown格式的建议文本

        Args:
            markdown_text: Markdown格式的建议文本

        Returns:
            解析后的建议列表
        """
        try:
            import re
            suggestions = []
            category_pattern = r'^###\s+(.*)$'
            categories = re.findall(category_pattern, markdown_text, re.MULTILINE)
            if not categories:
                return []

            sections = re.split(category_pattern, markdown_text, flags=re.MULTILINE)[1:]
            for i in range(0, len(sections), 2):
                category = sections[i].strip()
                section = sections[i + 1] if i + 1 < len(sections) else ""
                item_pattern = r'####\s+(.*?)\s*(?=\n|$)'
                items = re.findall(item_pattern, section)
                if items:
                    for item in items:
                        suggestions.append({
                            "id": 0,
                            "category": category,
                            "priority": "高" if "高危" in category else "中" if "中等" in category else "低",
                            "title": item.strip(),
                            "location": "全局分析",
                            "description": section.strip(),
                            "issue": "",
                            "fix": "",
                            "reason": "AI建议",
                            "impact": "改善项目健康",
                            "recommendation": section.strip()
                        })
                else:
                    suggestions.append({
                        "id": 0,
                        "category": category,
                        "priority": "中",
                        "title": category,
                        "location": "全局分析",
                        "description": section.strip(),
                        "issue": "",
                        "fix": "",
                        "reason": "AI建议",
                        "impact": "改善项目健康",
                        "recommendation": section.strip()
                    })
            return suggestions
        except Exception as e:
            logger.error(f"解析Markdown建议失败: {e}")
            return []

    # 安全问题
    def _default_security_issue(self, title: str = "安全扫描完成", analysis: str = "未发现明显安全问题") -> List[dict]:
        """
        生成默认的安全问题（当没有检测到安全问题时）

        Args:
            title: 安全问题标题
            analysis: 安全分析描述

        Returns:
            包含默认安全问题的列表
        """
        return [{
            "severity": "低",
            "title": title,
            "type": "安全评估",
            "location": "系统扫描",
            "analysis": analysis,
            "impact": "无明显风险",
            "issue_code": "无",
            "fix_code": "无需修复",
            "recommendation": "继续保持良好安全实践"
        }]

    # 平台检测
    def _detect_platform(self, repo_url: str) -> str:
        """
        检测仓库平台类型

        Args:
            repo_url: 仓库URL

        Returns:
            平台类型字符串 ("github" 或 "gitee")
        """
        if not repo_url:
            return "github"
        repo_url = repo_url.lower()
        if "gitee.com" in repo_url:
            return "gitee"
        return "github"

    # Location清理
    def _clean_location(self, location: str) -> str:
        """
        清理location字段，去除占位符

        Args:
            location: 原始location字符串

        Returns:
            清理后的location字符串
        """
        if not location:
            return "未知位置"

        # 去除常见的占位符
        placeholders = ["行号范围", "未知", "unknown", "N/A", "n/a", "全局", "多个文件"]
        for placeholder in placeholders:
            if placeholder in location:
                # 如果location只是占位符，返回文件路径
                if location.strip() == placeholder:
                    return "未知位置"
                # 如果location包含占位符，尝试提取文件路径
                if ":" in location:
                    parts = location.split(":")
                    if len(parts) >= 2:
                        file_path = parts[0].strip()
                        if file_path and file_path not in placeholders:
                            return file_path

        # 如果location包含中文冒号，替换为英文冒号
        location = location.replace("：", ":")
        # 如果location格式正确（文件路径:行号），直接返回
        if ":" in location and not any(p in location for p in placeholders):
            return location
        # 如果location只是文件路径，直接返回
        if "." in location and "/" in location:
            return location

        # 其他情况，返回原始值
        return location

    def _is_reasonable_file_path(self, file_path: str) -> bool:
        """
        验证文件路径是否合理，防止AI幻觉

        Args:
            file_path: 文件路径字符串

        Returns:
            True表示合理的文件路径，False表示可能不合理的路径
        """
        if not file_path or file_path == "未知位置":
            return False

        file_path_lower = file_path.lower()

        # 1. 检查是否有常见扩展名或常见文件名
        common_extensions = [
            '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs', '.cpp', '.c', '.php', '.rb', '.kt', '.swift',
            '.html', '.css', '.vue', '.dart', '.sql', '.graphql', '.json', '.yaml', '.yml', '.xml', '.md', '.txt',
            '.dockerfile', '.dockerignore', '.makefile', '.cmake', '.ini', '.cfg', '.conf', '.toml', '.properties',
            '.lua', '.perl', '.pl', '.r', '.dart', '.groovy', '.vbs', '.vba', '.asm', '.s', '.svg', '.plist',
            '.xsd', '.xsl', '.xhtml', '.shtml', '.tmpl', '.tpl', '.erb', '.haml', '.slim', '.jade', '.pug',
            '.styl', '.sass', '.scss', '.less', '.coffee', '.litcoffee', '.vue', '.svelte', '.elm', '.erl', '.hrl',
            '.ex', '.exs', '.clj', '.cljs', '.cljc', '.edn', '.fs', '.fsi', '.fsx', '.fsscript', '.hs', '.lhs',
            '.ml', '.mli', '.mll', '.mly', '.hx', '.hxml', '.d', '.di', '.pde', '.wxs', '.wxl', '.xib', '.storyboard',
            '.pbxproj', '.lock', '.ipynb'
        ]

        # 常见文件名
        common_filenames = [
            'dockerfile', 'makefile', 'readme', 'license', 'contributing', 'code_of_conduct',
            'changelog', 'authors', 'todo', 'notes'
        ]

        # 检查是否有扩展名
        has_extension = any(ext in file_path_lower for ext in common_extensions)

        # 检查是否是常见文件名
        filename = file_path_lower.split('/')[-1].split('\\')[-1].split('.')[0]
        is_common_filename = filename in common_filenames

        # 2. 检查路径是否包含明显的占位符或示例内容
        path_segments = file_path_lower.replace('\\', '/').split('/')
        has_placeholder = False
        for segment in path_segments:
            segment_clean = segment.split('.')[0]  # 移除扩展名
            if segment_clean in ['example', 'sample', 'test', 'placeholder', 'template', 'dummy', 'mock', 'fake']:
                has_placeholder = True
                break

        # 3. 检查路径格式是否合理
        # 对于根目录文件（如README.md），可能没有目录分隔符
        has_valid_format = True
        # 因为这是AI幻觉的典型例子
        is_known_hallucination = False

        return (has_extension or is_common_filename) and not has_placeholder and not is_known_hallucination

    def _calculate_project_protection_level(self, repo_info: Dict[str, Any]) -> tuple:
        """
        计算项目的保护等级和评分保护因子
        """
        stars = repo_info.get("stars", 0)
        forks = repo_info.get("forks", 0)
        if stars > 10000 or (stars > 5000 and forks > 2000):
            return 3, 75, 20
        if stars > 5000 or (stars > 1000 and forks > 500):
            return 2, 60, 30
        if stars > 500 or forks > 50:
            return 1, 50, 40

        return 0, 30, 50

    # 代码质量指标
    def _calculate_code_quality_metrics(self, repo_data: Dict[str, Any],
                                        ai_analysis: Dict[str, Any],
                                        platform: str = "github") -> CodeQualityMetrics:
        """
        计算代码质量指标

        Args:
            repo_data: 仓库数据
            ai_analysis: AI分析结果
            platform: 平台类型（github或gitee）

        Returns:
            CodeQualityMetrics: 代码质量指标对象
        """
        repo_info = repo_data["repo_info"]
        structure = repo_data["repo_structure"]

        # 计算项目保护等级
        protection_level, min_security_score, max_security_deduction = self._calculate_project_protection_level(
            repo_info)

        base_score = ai_analysis.get("score", 70)  # 默认基准分
        security_score = ai_analysis.get("security_score", base_score)

        adjustments = 0
        if structure.get("file_count", 0) > 0:
            test_files = sum(
                1 for p in structure.get("main_language_files", []) if "test" in p.lower() or "spec" in p.lower())
            if test_files > 0:
                adjustments += 5
        if structure.get("has_github_actions"):
            adjustments += 5
        if structure.get("has_requirements"):
            adjustments += 3

        final_score = min(100, base_score + adjustments)

        # 安全问题处理
        security_issues = []
        raw_issues = ai_analysis.get("security_issues", [])
        if raw_issues:
            for issue in (raw_issues if isinstance(raw_issues, list) else [raw_issues]):
                if isinstance(issue, dict):
                    # 清理location字段，去除占位符
                    raw_location = str(issue.get("location", "未知位置"))
                    cleaned_location = self._clean_location(raw_location)

                    # 验证安全问题是否基于实际代码证据
                    is_valid_issue = True

                    # 检查文件路径是否合理
                    if cleaned_location != "未知位置" and not self._is_reasonable_file_path(cleaned_location):
                        # 如果文件路径不合理，跳过该问题
                        is_valid_issue = False
                        logger.debug(f"[安全验证] 跳过不合理的文件路径: {cleaned_location}")

                    if is_valid_issue:
                        # 验证安全问题是否包含具体内容，过滤掉"详见问题描述"等占位符内容
                        issue_code = str(issue.get("issue_code", "未提供"))
                        if (issue_code and issue_code.strip() != "详见问题描述" and
                                issue_code.strip() != "详见分析" and
                                issue_code.strip() != "未提供" and
                                issue_code.strip() != "# 未提供代码片段" and
                                issue_code.strip() != "N/A" and
                                issue_code.strip() != "无" and
                                issue_code.strip() != ""):
                            security_issues.append({
                                "severity": str(issue.get("severity", "中")),
                                "title": str(issue.get("title", "未知安全问题")),
                                "type": str(issue.get("type", "安全漏洞")),
                                "location": cleaned_location,
                                "analysis": str(issue.get("analysis", "需进一步评估")),
                                "impact": str(issue.get("impact", "潜在风险")),
                                "issue_code": issue_code,
                                "fix_code": str(issue.get("fix_code", "请手动检查")),
                                "recommendation": str(issue.get("recommendation", "建议修复"))
                            })
                        elif issue_code and issue_code.strip() != "未提供" and issue_code.strip() != "":
                            # 如果没有具体的代码片段，但有标题和分析内容，仍然保留问题，但使用标题作为代码片段
                            security_issues.append({
                                "severity": str(issue.get("severity", "中")),
                                "title": str(issue.get("title", "未知安全问题")),
                                "type": str(issue.get("type", "安全漏洞")),
                                "location": cleaned_location,
                                "analysis": str(issue.get("analysis", "需进一步评估")),
                                "impact": str(issue.get("impact", "潜在风险")),
                                "issue_code": str(issue.get("title", "未知安全问题")),
                                "fix_code": str(issue.get("fix_code", "请手动检查")),
                                "recommendation": str(issue.get("recommendation", "建议修复"))
                            })
                        else:
                            logger.debug("跳过内容不完整的问题")
                    else:
                        logger.debug("跳过可能虚构的安全问题")
                elif isinstance(issue, str) and issue.strip():
                    # 对于字符串类型的issue，也验证其内容
                    issue_content = issue.strip()
                    if issue_content and issue_content != "详见问题描述" and issue_content != "详见分析" and issue_content != "未提供":
                        security_issues.append({
                            "severity": "中",
                            "title": f"检测到问题: {issue[:40]}...",
                            "type": "安全问题",
                            "location": "全局",
                            "analysis": issue_content,
                            "impact": "潜在风险",
                            "issue_code": "详见分析",
                            "fix_code": "请参考建议",
                            "recommendation": issue_content
                        })
                    else:
                        logger.debug("跳过内容不完整的字符串问题")
        else:
            security_issues.extend(self._default_security_issue())

        # 根据发现的安全问题调整代码质量评分
        security_adjustment = 0
        total_security_deduction = 0

        for issue in security_issues:
            # 验证安全问题是否真实有效
            location = issue.get("location", "")
            title = issue.get("title", "")
            analysis = issue.get("analysis", "")

            # 检查文件路径是否合理
            is_valid_issue = True
            if location and location != "未知位置" and not self._is_reasonable_file_path(location):
                # 如果文件路径不合理，跳过该问题
                is_valid_issue = False
                logger.debug(f"跳过不合理的文件路径: {location}")

            if not is_valid_issue:
                continue

            if total_security_deduction >= max_security_deduction:
                break  # 达到最大扣分限制，停止扣分

            severity = issue.get("severity", "").lower()
            deduction = SecurityUtils.calculate_severity_score(severity)

            if total_security_deduction + deduction <= max_security_deduction:
                total_security_deduction += deduction
            else:
                # 如果加上本次扣分会超过限制，则只扣到上限
                total_security_deduction = max_security_deduction

        security_adjustment = -total_security_deduction

        # 应用安全调整到最终评分
        final_score = max(min_security_score, final_score + security_adjustment)  # 使用项目保护的最小分

        # 安全评分
        security_score = min(security_score, final_score)
        security_score = max(min_security_score, security_score)  # 应用项目保护机制

        if protection_level >= 2:
            if security_score < 85:
                security_score = min(90, security_score + 15)

        # code_standards
        standards_raw = ai_analysis.get("code_standards", [])
        code_standards = standards_raw if isinstance(standards_raw, list) else [
            str(standards_raw)] if standards_raw else ["检查完成"]
        # 依赖健康度
        dep = ai_analysis.get("dependencies_health", {})
        if isinstance(dep, str):
            text = dep.lower()
            if any(k in text for k in ["无依赖", "没有检测到", "不存在", "无第三方"]):
                dep = {"score": 95, "comment": "无外部依赖，风险极低", "healthy": True}
            elif any(k in text for k in ["漏洞", "高危", "严重"]):
                dep = {"score": 30, "comment": dep[:150], "healthy": False}
            elif "过时" in text or "outdated" in text:
                dep = {"score": 40, "comment": dep[:150], "healthy": False}
            else:
                dep = {"score": 65, "comment": dep[:150], "healthy": None}
        dep.setdefault("score", 70)
        dep.setdefault("comment", "依赖状态正常")

        # 对于Gitee平台，添加特殊说明
        if platform == "gitee":
            code_standards.append("已针对Gitee平台特性进行了优化分析")

        return CodeQualityMetrics(
            score=final_score,
            complexity=ai_analysis.get("complexity", 5),
            documentation_score=ai_analysis.get("documentation_score", 50),
            security_issues=security_issues,
            code_standards=code_standards,
            dependencies_health=dep,
            static_scan_results=repo_data.get("static_scan_results", {}),
            security_score=security_score
        )

    # 社区健康度
    def _calculate_community_health_metrics(self, repo_data: Dict[str, Any]) -> CommunityHealthMetrics:
        """
        计算社区健康度指标

        Args:
            repo_data: 仓库数据

        Returns:
            CommunityHealthMetrics: 社区健康度指标对象
        """
        repo_info = repo_data["repo_info"]
        community = repo_data["community_metrics"]
        issues = repo_data["issue_metrics"]
        score = 20

        stars = repo_info.get("stars", 0)
        forks = repo_info.get("forks", 0)
        contributors_count = community.get("contributors_count", 0)
        recent_commits = community.get("recent_commits", 0)
        avg_response_time = None  #

        is_low_data_repo = (stars < 10 and forks < 3 and contributors_count < 3 and recent_commits < 5)
        if is_low_data_repo:
            logger.info(f"检测到低数据仓库（新项目/个人项目）: {repo_info.get('full_name')}")
            score = 30
            if recent_commits > 0: score += 10
            if contributors_count >= 1: score += 5
            if stars > 0: score += 3
            if forks > 0: score += 2
        else:
            if contributors_count > 15:
                score += 25
            elif contributors_count > 10:
                score += 20
            elif contributors_count > 5:
                score += 10
            elif contributors_count > 1:
                score += 5
            if recent_commits > 30:
                score += 20
            elif recent_commits > 20:
                score += 15
            elif recent_commits > 10:
                score += 10
            elif recent_commits > 3:
                score += 5
            if issues.get("closed_count", 0) > issues.get("open_count", 0) * 3:
                score += 20
            elif issues.get("closed_count", 0) > issues.get("open_count", 0) * 2:
                score += 15
            elif issues.get("closed_count", 0) > issues.get("open_count", 0):
                score += 10
            if stars > 1000:
                score += 15
            elif stars > 500:
                score += 10
            elif stars > 100:
                score += 5
            elif stars > 10:
                score += 2
            # 处理平均响应时间
            avg_response_time = issues.get("avg_response_time_hours")
            try:
                if avg_response_time is not None and float(avg_response_time) < 6:
                    score += 15
                elif avg_response_time is not None and float(avg_response_time) < 12:
                    score += 10
                elif avg_response_time is not None and float(avg_response_time) < 24:
                    score += 5
            except (ValueError, TypeError):
                pass

        score = min(100, max(0, score))

        return CommunityHealthMetrics(
            score=score,
            contributors_count=contributors_count,
            recent_activity={"commits": recent_commits, "issues": issues.get("total_count", 0)},
            issue_health={
                "open_issues": issues.get("open_count", 0),
                "closed_issues": issues.get("closed_count", 0),
                "response_time": avg_response_time
            },
            community_growth={"stars": stars, "forks": forks}
        )

    # 文档完整性
    def _calculate_documentation_metrics(self, repo_data: Dict[str, Any]) -> DocumentationMetrics:
        """
        计算文档完整性指标

        Args:
            repo_data: 仓库数据

        Returns:
            DocumentationMetrics: 文档完整性指标对象
        """
        structure = repo_data["repo_structure"]
        repo_info = repo_data["repo_info"]
        score = 0

        if structure.get("has_readme"): score += 30
        if repo_info.get("description") and len(repo_info["description"]) > 50: score += 10
        if structure.get("has_contributing"): score += 15
        if structure.get("has_license"): score += 15
        if structure.get("has_code_of_conduct"): score += 10
        if structure.get("has_github_actions"): score += 10
        if repo_info.get("topics") and len(repo_info["topics"]) > 0: score += 10

        score = min(100, score)

        return DocumentationMetrics(
            score=score,
            readme_quality=40 if structure.get("has_readme") else 0,
            has_contributing=structure.get("has_contributing", False),
            has_license=structure.get("has_license", False),
            has_code_of_conduct=structure.get("has_code_of_conduct", False),
            has_issue_template=structure.get("has_issue_template", False),
            has_pr_template=structure.get("has_pr_template", False),
            wiki_enabled=repo_info.get("has_wiki", False)
        )

    # 维护活跃度
    def _calculate_maintenance_metrics(self, repo_data: Dict[str, Any]) -> MaintenanceMetrics:
        """
        计算维护活跃度指标

        Args:
            repo_data: 仓库数据

        Returns:
            MaintenanceMetrics: 维护活跃度指标对象
        """
        repo_info = repo_data["repo_info"]
        community = repo_data["community_metrics"]
        issues = repo_data["issue_metrics"]
        score = 20

        if repo_info.get("pushed_at"):
            last_push = datetime.fromisoformat(repo_info["pushed_at"].replace('Z', '+00:00'))
            days_since_update = (datetime.now(timezone.utc) - last_push).days
            if days_since_update < 2:
                score += 35
            elif days_since_update < 5:
                score += 25
            elif days_since_update < 10:
                score += 15
            elif days_since_update < 30:
                score += 5
            elif days_since_update > 365:
                score -= 20

        releases_count = community.get("releases_count", 0)
        if releases_count > 20:
            score += 25
        elif releases_count > 10:
            score += 20
        elif releases_count > 5:
            score += 10
        elif releases_count > 0:
            score += 5

        avg_response = issues.get("avg_response_time_hours")
        try:
            if avg_response and float(avg_response) < 12:
                score += 20
            elif avg_response and float(avg_response) < 24:
                score += 10
            elif avg_response and float(avg_response) < 48:
                score += 5
        except Exception:
            pass

        score = min(100, max(0, score))
        try:
            response_time = float(avg_response) if avg_response is not None else 0.0
        except (ValueError, TypeError):
            response_time = 0.0

        return MaintenanceMetrics(
            score=score,
            update_frequency=community.get("recent_commits", 0),
            dependency_updates={},
            release_frequency=releases_count,
            response_time=response_time
        )

    # 风险评估
    def _assess_risks(self, repo_data: Dict[str, Any], code_quality: CodeQualityMetrics,
                      community_health: CommunityHealthMetrics) -> RiskAssessment:
        """
        评估仓库风险

        Args:
            repo_data: 仓库数据
            code_quality: 代码质量指标
            community_health: 社区健康度指标

        Returns:
            RiskAssessment: 风险评估对象
        """
        repo_info = repo_data["repo_info"]
        security_risks = []
        maintenance_risks = []
        community_risks = []
        license_risks = []

        # 安全风险
        if code_quality.security_issues:
            for issue in code_quality.security_issues:
                security_risks.append(issue.get("title", "未知安全问题"))

        # 维护风险
        maintenance = repo_data.get("community_metrics", {})
        last_push = repo_info.get("pushed_at")
        if last_push:
            last_push_dt = datetime.fromisoformat(last_push.replace("Z", "+00:00"))
            days_since_push = (datetime.now(timezone.utc) - last_push_dt).days
            if days_since_push > 365:
                maintenance_risks.append(f"超过一年未更新 ({days_since_push}天)")

        # 社区风险
        contrib_count = community_health.contributors_count
        if contrib_count < 1:
            community_risks.append("贡献者过少，社区活跃度低")

        # 许可证风险
        license_type = repo_info.get("license")
        if not license_type:
            license_risks.append("缺少许可证信息")

        return RiskAssessment(
            security=security_risks,
            maintenance=maintenance_risks,
            community=community_risks,
            license=license_risks
        )

    # CoStrict模式专用方法
    def _get_default_ai_analysis(self, repo_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        CoStrict模式：基于API数据返回默认的AI分析结果
        不调用AI，只使用GitHub/Gitee API获取的数据
        不生成安全漏洞分析
        """
        repo_info = repo_data["repo_info"]

        # 基于API数据计算基础分数
        stars = repo_info.get("stars", 0)
        forks = repo_info.get("forks", 0)
        issues = repo_info.get("open_issues", 0)

        # 基础分数计算
        base_score = 70  # 默认基准分

        # 根据stars调整分数
        if stars > 1000:
            base_score += 10
        elif stars > 100:
            base_score += 5

        # 根据forks调整分数
        if forks > 100:
            base_score += 5
        elif forks > 10:
            base_score += 3

        # 根据issues调整分数（issues太多扣分）
        if issues > 100:
            base_score -= 10
        elif issues > 50:
            base_score -= 5

        # 确保分数在0-100之间
        base_score = max(0, min(100, base_score))

        logger.info(f"CoStrict模式：基于API数据计算基础分数 {base_score} for {repo_info.get('full_name')}")

        return {
            "score": base_score,
            "complexity": 5,
            "documentation_score": base_score - 10 if base_score > 10 else base_score,
            "security_issues": [],  # CoStrict模式不进行安全分析
            "code_standards": ["基于API数据的代码结构分析"],
            "dependencies_health": {
                "score": base_score,
                "comment": "基于API数据的依赖健康评估",
                "healthy": True
            },
            # 将计算逻辑分组
            "security_score": max(10, (base_score - 15)) if base_score > 15 else max(10, base_score),
            "detailed_analysis": {
                "syntax_logic": "CoStrict模式：基于API数据的语法分析",
                "refactoring_opportunities": "CoStrict模式：基于API数据的重构建议",
                "performance_issues": "CoStrict模式：基于API数据的性能评估",
                "security_concerns": "CoStrict模式：未进行安全漏洞分析",
                "best_practices": "CoStrict模式：基于API数据的最佳实践评估"
            },
            "language_specific_issues": {
                "detected_patterns": [],
                "framework_concerns": [],
                "library_usage": []
            }
        }

    # 总分计算
    def _calculate_overall_score(self, code_score: float, community_score: float,
                                 doc_score: float, maintenance_score: float, security_score: float) -> float:
        """
        计算总体评分（加权平均）

        Args:
            code_score: 代码质量分数
            community_score: 社区健康度分数
            doc_score: 文档完整性分数
            maintenance_score: 维护活跃度分数
            security_score: 安全分数

        Returns:
            float: 总体评分
        """
        overall = (
                code_score * settings.SCORE_WEIGHT_CODE +  # 代码质量权重
                community_score * settings.SCORE_WEIGHT_COMMUNITY +  # 社区健康权重
                doc_score * settings.SCORE_WEIGHT_DOC +  # 文档完整性权重
                maintenance_score * settings.SCORE_WEIGHT_MAINTENANCE +  # 维护活跃度权重
                security_score * settings.SCORE_WEIGHT_SECURITY  # 安全分数权重
        )

        # 保留2位小数
        return round(overall, 2)
