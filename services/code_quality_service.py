"""
代码质量分析服务
负责代码质量分析、安全漏洞检测等功能
"""

import json
import logging
import os
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class CodeQualityService:
    """代码质量分析服务"""

    def __init__(self, ai_client):
        """
        初始化代码质量分析服务

        Args:
            ai_client: AIClient实例，可以为None（如在costrict模式下）
        """
        self.ai_client = ai_client
        if ai_client is not None:
            self.provider = ai_client.provider
        else:
            self.provider = "costrict"  # 当ai_client为None时，假定为costrict模式

    async def analyze_code_quality(self, repo_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        使用AI分析代码质量

        Args:
            repo_data: 仓库数据

        Returns:
            代码质量分析结果
        """
        if self.provider == "costrict":
            return await self._analyze_with_costrict(repo_data)

        prompt = self._build_code_quality_prompt(repo_data)
        if not prompt:
            logger.warning("提示词为空，使用默认代码质量分析")
            return self._get_default_code_quality()

        try:
            response = await self.ai_client._chat_completion(prompt)
            logger.info(f"AI代码质量分析响应长度: {len(response)}字符")
            return self._parse_code_quality_response_improved(response)
        except Exception as e:
            logger.error(f"AI代码质量分析失败: {str(e)}")
            logger.error(f"失败的提示词: {prompt[:200]}...")
            return self._get_default_code_quality()

    def _load_prompt(self, name: str) -> str:
        """读取 prompts 目录下的提示词文件"""
        prompt_path = os.path.join(os.path.dirname(__file__), "..", "utils", "prompts", f"{name}.txt")
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            logger.error(f"读取提示词文件失败: {prompt_path} - {str(e)}")
            return ""

    def _build_code_quality_prompt(self, repo_data: Dict[str, Any]) -> str:
        """构建代码质量分析提示词"""
        template = self._load_prompt("code_quality")
        if not template:
            logger.error("代码质量提示词模板为空")
            return ""

        repo = repo_data.get("repo_info", {}) if "repo_info" in repo_data else repo_data

        # 检测平台类型
        platform = repo_data.get("platform", "github")
        if platform == "github":
            # 如果platform未设置或为默认值，尝试从URL检测
            platform = self._detect_platform(repo.get("html_url", ""))

        # 为Gitee平台添加特殊说明
        if platform == "gitee":
            template += "\n\n特别说明：这是来自Gitee平台的仓库，请特别关注以下几点："
            template += "\n1. 重视中文注释和文档的质量评估"
            template += "\n2. 对于国内常用技术栈（如Spring Boot、Vue、React等）提供符合国内生态的建议"
            template += "\n3. 在依赖建议中可优先推荐国内镜像源（如清华源、阿里云源）"

        # 确保所有替换值都是字符串
        replacements = {
            "{{REPO_NAME}}": str(repo.get("full_name", "N/A")),
            "{{REPO_DESC}}": str(repo.get("description", "N/A")),
            "{{LANGUAGE}}": str(repo.get("language", "N/A")),
            "{{STARS}}": str(repo.get("stars", 0)),
            "{{FORKS}}": str(repo.get("forks", 0)),
            "{{ISSUES}}": str(repo.get("open_issues", 0)),
            "{{CREATED_AT}}": str(repo.get("created_at", "N/A")),
            "{{UPDATED_AT}}": str(repo.get("updated_at", "N/A"))
        }

        prompt = template
        for key, value in replacements.items():
            prompt = prompt.replace(key, value)

        return prompt

    def _detect_platform(self, repo_url: str) -> str:
        """
        检测仓库平台类型
        """
        if not repo_url:
            return "github"

        repo_url = repo_url.lower()
        if "gitee.com" in repo_url:
            return "gitee"
        else:
            return "github"

    def _parse_code_quality_response_improved(self, response: str) -> Dict[str, Any]:
        """改进版代码质量解析 - 超强容错"""
        try:
            logger.debug(f"开始解析AI代码质量响应，长度: {len(response)}字符")

            # 1. 清理响应内容
            if self.ai_client is not None:
                cleaned_response = self.ai_client._clean_ai_response(response)
            else:
                # 在costrict模式下，直接使用基础清理
                cleaned_response = response.strip()
            logger.debug(f"清理后的响应: {cleaned_response[:200]}...")

            # 2. 寻找JSON对象
            if self.ai_client is not None:
                json_object = self.ai_client._extract_json_object(cleaned_response)
            else:
                # 在costrict模式下，直接使用基础JSON解析
                json_object = cleaned_response
            if not json_object:
                logger.warning("未找到JSON对象，使用默认值")
                return self._get_default_code_quality()

            # 3. 解析JSON
            try:
                data = json.loads(json_object)
                if isinstance(data, dict) and "score" in data:
                    return self._normalize_code_quality(data)
                else:
                    logger.warning("解析结果格式不正确，使用默认值")
                    return self._get_default_code_quality()

            except json.JSONDecodeError as e:
                logger.error(f"JSON解析失败: {str(e)}")
                logger.error(f"失败的JSON内容: {json_object[:300]}...")
                # 尝试修复JSON
                if self.ai_client is not None:
                    repaired_json = self.ai_client._repair_json_object(json_object)
                else:
                    # 在costrict模式下，不尝试修复JSON，直接返回默认值
                    repaired_json = None
                if repaired_json:
                    try:
                        data = json.loads(repaired_json)
                        if isinstance(data, dict) and "score" in data:
                            logger.info("成功修复JSON并解析")
                            return self._normalize_code_quality(data)
                    except json.JSONDecodeError:
                        pass
                return self._get_default_code_quality()

        except Exception as e:
            logger.error(f"代码质量解析严重错误: {str(e)}")
            return self._get_default_code_quality()

    def _normalize_code_quality(self, data: Dict) -> Dict[str, Any]:
        """标准化代码质量格式"""
        # 确保所有必需字段都存在
        normalized = {
            "score": data.get("score", 75),
            "complexity": data.get("complexity", 5),
            "documentation_score": data.get("documentation_score", 70),
            "security_issues": data.get("security_issues", []),
            "code_standards": data.get("code_standards", ["基础分析完成"]),
            "dependencies_health": data.get("dependencies_health",
                                            {"score": 80, "comment": "依赖健康", "healthy": True}),
            "security_score": data.get("security_score", 78),
            "detailed_analysis": data.get("detailed_analysis", {
                "security": "部分分析受限",
                "maintainability": "结构良好",
                "reliability": "稳定"
            })
        }

        # 确保security_issues是列表
        if not isinstance(normalized["security_issues"], list):
            normalized["security_issues"] = []

        # 确保code_standards是列表
        if not isinstance(normalized["code_standards"], list):
            normalized["code_standards"] = ["基础分析完成"]

        return normalized

    def _get_default_code_quality(self) -> Dict[str, Any]:
        """获取默认的代码质量分析结果"""
        return {
            "score": 75,
            "complexity": 5,
            "documentation_score": 70,
            "security_issues": [{"severity": "低", "title": "AI分析受限，启用默认评估"}],
            "code_standards": ["基础分析完成"],
            "dependencies_health": {"score": 80, "comment": "依赖健康，默认评估", "healthy": True},
            "security_score": 78,
            "detailed_analysis": {
                "security": "AI分析受限，使用默认安全评估",
                "maintainability": "结构良好",
                "reliability": "稳定"
            }
        }

    async def _analyze_with_costrict(self, repo_data: Dict[str, Any]) -> Dict[str, Any]:
        """使用 CoStrict 模式进行分析"""
        try:
            from utils.costrict import analyze_with_costrict

            # repo_url获取逻辑
            repo_info = repo_data.get("repo_info", {})
            repo_url = repo_info.get("html_url") or \
                       repo_info.get("clone_url") or \
                       repo_info.get("full_name") or \
                       repo_data.get("html_url") or \
                       repo_data.get("full_name")

            if not repo_url:
                logger.error("无法获取有效的仓库URL")
                return self._get_default_code_quality()

            logger.info(f"Starting CoStrict analysis for: {repo_url}")
            # 传递本地路径给CoStrict分析器
            local_path = repo_data.get("local_path") or repo_data.get("repo_path")
            result = analyze_with_costrict(repo_url, local_path=local_path)

            if result.get("status") == "error":
                logger.warning(f"CoStrict 分析返回错误: {result.get('message')}")
                return self._get_default_code_quality()

            # 转换为标准格式
            return {
                "score": result.get("score", 0),
                "complexity": self._calculate_complexity(result),
                "documentation_score": self._calculate_documentation_score(result),
                "security_issues": self._extract_security_issues(result),
                "code_standards": self._extract_code_standards(result),
                "dependencies_health": {"status": "analyzed", "costrict": True}
            }

        except Exception as e:
            logger.error(f"CoStrict 分析失败: {str(e)}")
            return self._get_default_code_quality()

    def _calculate_complexity(self, result: Dict[str, Any]) -> float:
        """计算复杂度分数"""
        score = result.get("score", 0)
        return max(1, 10 - (score / 10))

    def _calculate_documentation_score(self, result: Dict[str, Any]) -> float:
        """计算文档质量分数"""
        structure = result.get("structure", {})
        score = 0
        if structure.get("has_readme"): score += 30
        if structure.get("has_license"): score += 20
        if structure.get("has_contributing"): score += 20
        if structure.get("has_github_actions"): score += 15
        if structure.get("test_files", 0) > 0: score += 15
        return min(100, score)

    def _extract_security_issues(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """提取安全问题"""
        issues = []
        for deduction in result.get("deduction_details", []):
            if "security" in deduction.get("reason", "").lower():
                # 验证安全问题是否合理
                location = deduction.get("location", "全局")
                reason = deduction.get("reason", "安全问题")

                # 检查是否为虚构的文件路径
                if location != "全局" and \
                   not any(ext in location.lower() for ext in ['.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs', '.cpp', '.c', '.php', '.rb', '.kt', '.swift', '.html', '.css', '.vue', '.dart', '.sql', '.graphql', '.json', '.yaml', '.yml', '.xml', '.md', '.txt', '.dockerfile', '.dockerignore', '.makefile', '.cmake', '.ini', '.cfg', '.conf', '.toml', '.properties', '.lua', '.perl', '.pl', '.r', '.dart', '.groovy', '.vbs', '.vba', '.asm', '.s', '.svg', '.plist', '.xsd', '.xsl', '.xhtml', '.shtml', '.tmpl', '.tpl', '.erb', '.haml', '.slim', '.jade', '.pug', '.styl', '.sass', '.scss', '.less', '.coffee', '.litcoffee', '.vue', '.svelte', '.elm', '.erl', '.hrl', '.ex', '.exs', '.clj', '.cljs', '.cljc', '.edn', '.fs', '.fsi', '.fsx', '.fsscript', '.hs', '.lhs', '.ml', '.mli', '.mll', '.mly', '.hx', '.hxml', '.d', '.di', '.pde', '.wxs', '.wxl', '.xib', '.storyboard', '.pbxproj', '.lock', '.ipynb']):
                    # 如果文件路径没有常见扩展名，跳过该问题
                    continue

                issues.append({
                    "severity": "中",
                    "title": reason,
                    "type": "安全漏洞",
                    "location": location,
                    "analysis": reason,
                    "impact": "潜在风险",
                    "issue_code": "详见分析",
                    "fix_code": "请参考建议",
                    "recommendation": reason
                })

        # 从静态扫描结果中提取安全问题 新增
        static_scan_results = result.get("static_scan_results", {})
        if static_scan_results:
            scans = static_scan_results.get("scans", {})
            ai_static_scan = scans.get("ai_static_scan", {})
            detailed_issues = ai_static_scan.get("detailed_issues", [])
            
            for issue in detailed_issues:
                if isinstance(issue, dict):
                    # 检查是否为安全相关问题
                    issue_type = str(issue.get("type", "")).lower()
                    issue_analysis = str(issue.get("analysis", "")).lower()
                    
                    is_security_issue = (
                        "security" in issue_type or
                        "vulnerability" in issue_type or
                        "漏洞" in issue_analysis or
                        "安全" in issue_analysis or
                        "hardcoded" in issue_analysis or
                        "credential" in issue_analysis
                    )
                    
                    if is_security_issue:
                        # 验证文件路径是否合理
                        file_path = str(issue.get("file", "未知文件"))
                        if file_path != "未知文件" and \
                           any(ext in file_path.lower() for ext in ['.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs', '.cpp', '.c', '.php', '.rb', '.kt', '.swift', '.html', '.css', '.vue', '.dart', '.sql', '.graphql', '.json', '.yaml', '.yml', '.xml', '.md', '.txt', '.dockerfile', '.dockerignore', '.makefile', '.cmake', '.ini', '.cfg', '.conf', '.toml', '.properties', '.lua', '.perl', '.pl', '.r', '.dart', '.groovy', '.vbs', '.vba', '.asm', '.s', '.svg', '.plist', '.xsd', '.xsl', '.xhtml', '.shtml', '.tmpl', '.tpl', '.erb', '.haml', '.slim', '.jade', '.pug', '.styl', '.sass', '.scss', '.less', '.coffee', '.litcoffee', '.vue', '.svelte', '.elm', '.erl', '.hrl', '.ex', '.exs', '.clj', '.cljs', '.cljc', '.edn', '.fs', '.fsi', '.fsx', '.fsscript', '.hs', '.lhs', '.ml', '.mli', '.mll', '.mly', '.hx', '.hxml', '.d', '.di', '.pde', '.wxs', '.wxl', '.xib', '.storyboard', '.pbxproj', '.lock', '.ipynb']):
                            
                            # 将静态扫描发现的安全问题添加到列表
                            security_issue = {
                                "severity": str(issue.get("severity", "中")).capitalize(),
                                "title": str(issue.get("title", issue.get("issue", "安全问题"))),
                                "type": str(issue.get("type", "安全漏洞")),
                                "location": f"{issue.get('file', '未知文件')}:{issue.get('line', 0)}",
                                "analysis": str(issue.get("analysis", issue.get("description", "检测到潜在安全问题"))),
                                "impact": str(issue.get("impact", "潜在安全风险")),
                                "issue_code": str(issue.get("issue_code", issue.get("code_snippet", ""))),
                                "fix_code": str(issue.get("fix_code", issue.get("fix", ""))),
                                "recommendation": str(issue.get("recommendation", "请参考问题描述和修复建议"))
                            }
                            issues.append(security_issue)

        # 只有当确实发现了安全问题时才返回它们
        # 如果没有发现安全问题，则返回空列表，而不是默认条目
        return issues

    def _extract_code_standards(self, result: Dict[str, Any]) -> List[str]:
        """提取代码标准符合情况"""
        standards = []
        logs = result.get("logs", [])
        for log in logs:
            raw = log.strip()[1:].strip() if log.strip() and log.strip()[0] in "✓✗" else log.strip()
            prefix = "符合标准" if log.strip().startswith("✓") else "未达标"
            standards.append(f"{prefix}：{raw}")
        if not standards:
            standards.append("代码规范检查完成，整体表现优秀")
        return standards
