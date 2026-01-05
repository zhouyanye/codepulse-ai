import logging
import os
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.core.config import settings
from models.analysis_models import (
    AnalysisResult,
    CodeQualityMetrics,
    CommunityHealthMetrics,
    DocumentationMetrics,
    MaintenanceMetrics,
    RiskAssessment
)
from services.github_service import GitHubService
from services.gitee_service import GiteeService
from services.ai_analyzer import AIAnalyzer
from services.static_scan_service import StaticScanner
from utils.git_utils import GitUtils
from utils.security_utils import SecurityUtils

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class AnalysisService:
    def __init__(self):
        try:
            self.github_service = GitHubService()
            self.gitee_service = GiteeService()
        except RuntimeError as e:
            logger.error(f"初始化服务失败，Git可能不可用: {e}")
            raise
        self.static_scanner = StaticScanner()

    def detect_platform(self, repo_url):
        repo_url = repo_url.lower()
        if "github.com" in repo_url:
            return "github"
        elif "gitee.com" in repo_url:
            return "gitee"
        return "github"

    def _create_error_result(self, repo_url, error_message):
        return AnalysisResult(
            repo_info={"full_name": repo_url, "error": error_message},
            code_quality=CodeQualityMetrics(),
            community_health=CommunityHealthMetrics(),
            documentation=DocumentationMetrics(),
            maintenance=MaintenanceMetrics(),
            risk_assessment=RiskAssessment(),
            recommendations=[{
                "title": "分析失败",
                "description": error_message,
                "severity": "critical",
                "id": 1
            }],
            overall_score=0
        )

    async def analyze_repository(self, request, progress_callback=None):
        logger.info(f"开始分析: {request.repo_url}")
        analysis_start_time = asyncio.get_event_loop().time()
        platform = self.detect_platform(request.repo_url)
        logger.info(f"检测到平台类型: {platform}")

        repo_path = None
        if platform == "gitee":
            actual_token = request.gitee_token
        else:
            actual_token = request.github_token
        try:
            timeout = settings.ANALYSIS_TIMEOUT  # 秒

            if progress_callback:
                await progress_callback(10, "正在克隆仓库代码...")

            # 克隆仓库
            git_utils = GitUtils()

            # 使用重试机制处理网络超时
            @retry(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=4, max=10),
                retry=retry_if_exception_type((asyncio.TimeoutError, ConnectionError, OSError))
            )
            async def clone_with_retry():
                return await asyncio.wait_for(
                    git_utils.clone_repo(request.repo_url, token=actual_token),
                    timeout=timeout
                )

            repo_path = await clone_with_retry()
            if not repo_path or not os.path.exists(repo_path):
                logger.warning(f"仓库克隆失败: {request.repo_url}")
                repo_path = None
            else:
                logger.info(f"仓库克隆成功: {repo_path}")

            if progress_callback:
                await progress_callback(25, "分析仓库结构与社区数据...")

            # 获取仓库数据
            if platform == "gitee":
                repo_data = await asyncio.wait_for(
                    self.gitee_service.get_comprehensive_repo_data(
                        request.repo_url,
                        repo_path=repo_path,
                        gitee_token=request.gitee_token
                    ),
                    timeout=timeout
                )
            else:
                repo_data = await asyncio.wait_for(
                    self.github_service.get_comprehensive_repo_data(
                        request.repo_url,
                        repo_path=repo_path,
                        github_token=request.github_token
                    ),
                    timeout=timeout
                )

            if repo_path:
                repo_data["local_path"] = repo_path

            if progress_callback:
                # 保持进度在较高水平，避免进度倒退
                await progress_callback(65, "正在进行AI分析准备...")

            # AI分析
            logger.info(f"开始AI分析，提供商: {request.ai_provider}")
            ai_analyzer = AIAnalyzer(request.ai_provider)
            ai_analysis_start_time = asyncio.get_event_loop().time()
            result = await asyncio.wait_for(
                ai_analyzer.analyze_repository(repo_data, progress_callback=progress_callback),
                timeout=timeout
            )
            ai_analysis_end_time = asyncio.get_event_loop().time()
            ai_analysis_duration = ai_analysis_end_time - ai_analysis_start_time
            logger.info(f"AI分析完成，耗时: {ai_analysis_duration:.2f}秒")

            # 静态扫描
            # CoStrict模式跳过静态扫描（只使用API数据评分）
            if request.include_static_scan and repo_path and request.ai_provider != "costrict":
                if progress_callback:
                    await progress_callback(85, "运行AI静态代码扫描...")

                # 检测项目的主要编程语言
                primary_languages = []
                repo_structure = repo_data.get("repo_structure", {})
                if repo_structure.get("languages"):
                    # 根据语言占比排序，获取主要语言
                    sorted_languages = sorted(
                        repo_structure["languages"].items(),
                        key=lambda x: x[1],
                        reverse=True
                    )
                    # 获取占比最高的前几种语言
                    primary_languages = [lang for lang, _ in sorted_languages[:3]]
                    logger.info(f"检测到项目主要编程语言: {primary_languages}")

                logger.info(f"开始静态扫描，提供商: {request.ai_provider}")
                static_scanner = StaticScanner(request.ai_provider)
                static_scan_start_time = asyncio.get_event_loop().time()
                logger.info(f"开始静态扫描: {repo_path}")

                static_scan_raw = await asyncio.wait_for(
                    static_scanner.run_full_scan_with_path(
                        repo_path=repo_path,
                        repo_url=request.repo_url,
                        primary_languages=primary_languages,
                        progress_callback=progress_callback
                    ),
                    timeout=timeout
                )

                static_scan_end_time = asyncio.get_event_loop().time()
                static_scan_duration = static_scan_end_time - static_scan_start_time
                logger.info(f"静态扫描完成，耗时: {static_scan_duration:.2f}秒")

                # 处理并合并静态扫描结果
                self._process_static_scan_results(result, static_scan_raw, static_scanner)
            elif request.ai_provider == "costrict":
                logger.info("CoStrict模式：跳过静态扫描（仅使用API数据评分）")

            if progress_callback:
                await progress_callback(95, "计算最终得分...")

            # 计算最终得分
            result.overall_score = result.calculate_overall_score()

            if progress_callback:
                await progress_callback(100, "分析完成")

            analysis_end_time = asyncio.get_event_loop().time()
            analysis_duration = analysis_end_time - analysis_start_time
            logger.info(f"分析完成，耗时: {analysis_duration:.2f}秒")

            return result

        except Exception as e:
            logger.error(f"分析失败: {e}")
            return self._create_error_result(request.repo_url, str(e))

    def _process_static_scan_results(self, result, static_scan_raw, static_scanner):
        """处理并格式化静态扫描结果"""
        # 格式化静态扫描结果
        formatted_static_results = {}

        # 从static_scan_raw中提取扫描结果
        raw_scans = static_scan_raw.get("static_scan_results", {})

        # 如果raw_scans是字典类型，处理它
        if isinstance(raw_scans, dict) and raw_scans:
            if "scans" in raw_scans:
                raw_scans = raw_scans["scans"]

            for tool_name, tool_data in raw_scans.items():
                if isinstance(tool_data, dict):
                    detailed_issues = tool_data.get("detailed_issues", [])
                    if not isinstance(detailed_issues, list):
                        detailed_issues = []

                    formatted_issues = []
                    for issue in detailed_issues:
                        if isinstance(issue, dict):
                            issue_text = issue.get("issue", issue.get("description", issue.get("message", "")))
                            recommendation = issue.get("recommendation", issue.get("suggestion", ""))
                            file_path = issue.get("file", issue.get("file_path", "未知文件"))

                            # 验证问题是否基于真实存在的文件，过滤AI生成的虚构问题
                            is_valid_issue = True
                            
                            languages = ['.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs', '.cpp', '.c', '.php',
                                 '.rb', '.kt', '.swift', '.html', '.css', '.vue', '.dart', '.sql', '.graphql', '.json',
                                 '.yaml', '.yml', '.xml', '.md', '.txt', '.dockerfile', '.dockerignore', '.makefile',
                                 '.cmake', '.ini', '.cfg', '.conf', '.toml', '.properties', '.lua', '.perl', '.pl',
                                 '.r', '.dart', '.groovy', '.vbs', '.vba', '.asm', '.s', '.svg', '.plist', '.xsd',
                                 '.xsl', '.xhtml', '.shtml', '.tmpl', '.tpl', '.erb', '.haml', '.slim', '.jade', '.pug',
                                 '.styl', '.sass', '.scss', '.less', '.coffee', '.litcoffee', '.vue', '.svelte', '.elm',
                                 '.erl', '.hrl', '.ex', '.exs', '.clj', '.cljs', '.cljc', '.edn', '.fs', '.fsi', '.fsx',
                                 '.fsscript', '.hs', '.lhs', '.ml', '.mli', '.mll', '.mly', '.hx', '.hxml', '.d', '.di',
                                 '.pde', '.wxs', '.wxl', '.xib', '.storyboard', '.pbxproj', '.lock', '.ipynb']
                            if file_path and file_path != "未知文件" and file_path != "system":
                                if "__init__.py" in file_path and "缺少" in issue_text and "配置" in issue_text:
                                    is_valid_issue = False  # 避免对空__init__.py文件报告配置问题                                
                                if ("缺少" in issue_text and "配置" in issue_text and 
                                    any(ext in file_path for ext in languages)):
                                    is_valid_issue = False                            
                            if (not issue_text or len(issue_text.strip()) <= 10 or 
                                issue_text.startswith("AI分析完成") or 
                                "placeholder" in issue_text.lower() or
                                "详见问题描述" in issue_text or
                                "详见分析" in issue_text or
                                "未提供" in issue_text or
                                "# 未提供代码片段" in issue_text or
                                "N/A" in issue_text or
                                "无" in issue_text):
                                is_valid_issue = False
                            


                            if is_valid_issue:
                                formatted_issues.append({
                                    "filename": file_path,
                                    "line_number": issue.get("line", 0),
                                    "issue_text": issue_text[:1000],
                                    "issue_severity": issue.get("severity", "info").lower(),
                                    "message": recommendation[:1000],
                                    "type": issue.get("category", issue.get("type", "代码质量")),
                                    "code": issue.get("code", "AI_STATIC_ANALYSIS"),
                                    "language": issue.get("language", "")
                                })

                    if formatted_issues:
                        formatted_static_results[tool_name] = {
                            "results": formatted_issues,
                            "summary": tool_data.get("summary", {}),
                            "issues_by_language": tool_data.get("issues_by_language", {})
                        }
                else:
                    tool_str = str(tool_data).strip()
                    if tool_str and len(tool_str) > 20 and tool_str.lower() not in ["none", "null", ""]:
                        formatted_static_results[tool_name] = {
                            "results": [{
                                "filename": "analysis_result.txt",
                                "line_number": 0,
                                "issue_text": tool_str[:1000],
                                "issue_severity": "info",
                                "message": "分析完成",
                                "type": "分析结果",
                                "code": "ANALYSIS_RESULT",
                                "language": ""
                            }],
                            "summary": {},
                            "issues_by_language": {}
                        }

        # 处理静态扫描结果中的安全问题
        static_scan_results = static_scan_raw.get("static_scan_results", {})
        if static_scan_results:
            scans = static_scan_results.get("scans", {})
            ai_static_scan = scans.get("ai_static_scan", {})
            detailed_issues = ai_static_scan.get("detailed_issues", [])

            if detailed_issues and isinstance(detailed_issues, list):
                logger.info(f"处理静态扫描发现的 {len(detailed_issues)} 个问题")
                security_issues_added = 0
                code_quality_issues_added = 0

                # 创建去重集合，使用 location 和 title 作为唯一标识
                existing_issues_keys = {
                    f"{issue.get('location', '')}:{issue.get('title', '')}"
                    for issue in result.code_quality.security_issues
                }

                for issue in detailed_issues:
                    if isinstance(issue, dict):
                        # 使用 SecurityUtils 判断是否为安全问题
                        if SecurityUtils.is_security_issue(issue):
                            # 构建location，如果行号为0或N/A，只显示文件名
                            file_name = str(issue.get("file", "未知文件"))
                            line_number = issue.get("line", 0)

                            # 如果行号为0，只显示文件名
                            if line_number == 0:
                                issue_location = file_name
                            else:
                                issue_location = f"{file_name}:{line_number}"

                            issue_title = str(issue.get("title", issue.get("issue", "安全问题"))).strip()[:100]
                            issue_analysis = str(issue.get("analysis", issue.get("description", "检测到潜在安全问题")))

                            # 提取或生成修复代码
                            issue_code = str(issue.get("issue_code", issue.get("code_snippet", ""))).strip()
                            fix_code = str(issue.get("fix_code", issue.get("fix", ""))).strip()
                            issue_type = str(issue.get("type", "安全漏洞"))

                            # 检查是否重复
                            issue_key = f"{issue_location}:{issue_title}"
                            if issue_key in existing_issues_keys:
                                logger.debug(f"[去重] 跳过重复安全问题: {issue_key}")
                                code_quality_issues_added += 1  # 即使是重复的安全问题，也要计入总数
                                continue

                            security_issue = {
                                "severity": str(issue.get("severity", "中")).capitalize(),
                                "title": issue_title,
                                "type": issue_type,
                                "location": issue_location,
                                "analysis": issue_analysis,
                                "impact": str(issue.get("impact", "潜在安全风险")),
                                "issue_code": issue_code if issue_code else "详见问题描述",
                                "fix_code": fix_code,
                                "recommendation": str(issue.get("recommendation", "请参考问题描述和修复建议"))
                            }
                            # 验证安全问题是否包含具体内容，过滤掉"详见问题描述"等占位符内容
                            if (issue_code and issue_code.strip() != "详见问题描述" and
                                    issue_code.strip() != "详见分析" and
                                    issue_code.strip() != "未提供" and
                                    issue_code.strip() != "# 未提供代码片段" and
                                    issue_code.strip() != "N/A" and
                                    issue_code.strip() != "无" and
                                    issue_code.strip() != ""):
                                result.code_quality.security_issues.append(security_issue)
                                existing_issues_keys.add(issue_key)  # 添加到去重集合
                                security_issues_added += 1
                            else:
                                code_quality_issues_added += 1
                        else:
                            code_quality_issues_added += 1

                logger.info(f"成功处理 {security_issues_added} 个安全问题和 {code_quality_issues_added} 个代码质量问题，总计 {security_issues_added + code_quality_issues_added} 个问题")
            else:
                if not result.code_quality.security_issues:
                    result.code_quality.security_issues = [{
                        "severity": "低",
                        "title": "静态扫描完成",
                        "type": "安全评估",
                        "location": "系统扫描",
                        "analysis": "未发现明显安全问题",
                        "impact": "无明显风险",
                        "issue_code": "无",
                        "fix_code": "无需修复",
                        "recommendation": "继续保持良好安全实践"
                    }]
        else:
            if not result.code_quality.security_issues:
                result.code_quality.security_issues = [{
                    "severity": "低",
                    "title": "静态扫描完成",
                    "type": "安全评估",
                    "location": "系统扫描",
                    "analysis": "未发现明显安全问题",
                    "impact": "无明显风险",
                    "issue_code": "无",
                    "fix_code": "无需修复",
                    "recommendation": "继续保持良好安全实践"
                }]

        # 设置static_scan_results
        if formatted_static_results:
            result.code_quality.static_scan_results = formatted_static_results
            logger.info(f"设置静态扫描结果: {list(formatted_static_results.keys())}")
        elif static_scan_results:
            result.code_quality.static_scan_results = static_scan_results
            logger.info("设置原始静态扫描结果")
        else:
            result.code_quality.static_scan_results = {
                "scans": {
                    "ai_static_scan": {
                        "summary": {"overall_quality_score": 75},
                        "detailed_issues": [{
                            "file": "system",
                            "line": 0,
                            "issue": "静态扫描完成",
                            "severity": "info",
                            "recommendation": "未发现明显的代码质量问题",
                            "type": "代码质量"
                        }],
                        "recommendations": []
                    }
                }
            }
            logger.info("设置默认静态扫描结果")

        # 安全评分
        if "security_score" in static_scan_raw and isinstance(static_scan_raw["security_score"], (int, float)):
            result.code_quality.security_score = static_scan_raw["security_score"]
        else:
            inner_results = static_scan_raw.get("static_scan_results", {})
            # 获取repo_info用于动态评分
            repo_info = result.repo_info if hasattr(result, 'repo_info') else {}
            result.code_quality.security_score = static_scanner.calculate_security_score(inner_results,
                                                                                         repo_info=repo_info)
        # 从静态扫描结果中提取安全问题并合并到安全漏洞分析中
        scan_results = result.code_quality.static_scan_results
        if isinstance(scan_results, dict):
            ai_scan_data = scan_results.get('ai_static_scan', {})
            if isinstance(ai_scan_data, dict):
                detailed_issues = ai_scan_data.get('detailed_issues', [])
                if isinstance(detailed_issues, list):
                    # 从静态扫描结果中筛选安全相关问题
                    static_security_issues = []
                    for issue in detailed_issues:
                        if isinstance(issue, dict):
                            issue_type = str(issue.get("type", "")).lower()
                            issue_analysis = str(issue.get("analysis", "")).lower()
                            issue_title = str(issue.get("title", "")).lower()

                            # 检查是否为安全问题
                            is_security_issue = (
                                    "security" in issue_type or
                                    "vulnerability" in issue_type or
                                    "漏洞" in issue_analysis or
                                    "安全" in issue_analysis or
                                    "hardcoded" in issue_analysis or
                                    "credential" in issue_analysis or
                                    "安全" in issue_title or
                                    "security" in issue_title or
                                    "vulnerability" in issue_title
                            )

                            if is_security_issue:
                                # 将静态扫描的安全问题转换为标准格式
                                static_security_issues.append({
                                    "severity": str(issue.get("severity", "中")).capitalize(),
                                    "title": str(issue.get("title", issue.get("issue", "安全问题"))),
                                    "type": str(issue.get("type", "安全漏洞")),
                                    "location": f"{issue.get('file', '未知文件')}:{issue.get('line', 0)}",
                                    "analysis": str(
                                        issue.get("analysis", issue.get("description", "检测到潜在安全问题"))),
                                    "impact": str(issue.get("impact", "潜在安全风险")),
                                    "issue_code": str(issue.get("issue_code", issue.get("code_snippet", ""))),
                                    "fix_code": str(issue.get("fix_code", issue.get("fix", ""))),
                                    "recommendation": str(issue.get("recommendation", "请参考问题描述和修复建议"))
                                })

                    # 将静态扫描发现的安全问题合并到现有的安全漏洞列表中
                    existing_security_issues = result.code_quality.security_issues or []
                    for static_issue in static_security_issues:
                        # 避免重复问题
                        is_duplicate = False
                        for existing_issue in existing_security_issues:
                            if (existing_issue.get("title") == static_issue["title"] and
                                    existing_issue.get("location") == static_issue["location"]):
                                is_duplicate = True
                                break

                        if not is_duplicate:
                            existing_security_issues.append(static_issue)
                    result.code_quality.security_issues = existing_security_issues

        # 合并 recommendations 并保证 ID 唯一
        existing_recs = result.recommendations or []
        new_recs = static_scan_raw.get("recommendations", [])
        rec_ids = {rec["id"] for rec in existing_recs}
        for rec in new_recs:
            if rec["id"] not in rec_ids:
                existing_recs.append(rec)
        result.recommendations = existing_recs
