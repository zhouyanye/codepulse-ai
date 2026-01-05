import logging
import os
import re
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from utils.token_estimator import TokenEstimator
from services.cost_estimation_service import CostEstimationService
from services.github_service import GitHubService
from services.gitee_service import GiteeService
from utils.git_utils import GitUtils

logger = logging.getLogger(__name__)


class PreprocessingService:
    """预处理服务 - 分析前的文件扫描和成本检查"""

    def __init__(self):
        self.token_estimator = TokenEstimator()
        self.cost_estimation_service = CostEstimationService()
        self.github_service = GitHubService()
        self.gitee_service = GiteeService()
        self.git_utils = GitUtils()

        # 黑名单文件和目录模式
        self.blacklist_patterns = [
            # 版本控制
            '.git',
            '.gitignore',
            '.gitmodules',
            '.gitattributes',
            '.svn',
            '.hg',
            '.bzr',
            # 常见的依赖目录
            'node_modules',
            'venv',
            'virtualenv',
            '.venv',
            'env',
            'envs',
            '__pycache__',
            '.pytest_cache',
            '.tox',
            'coverage',
            '.coverage',
            'nosetests.xml',
            # 构建输出目录
            'dist',
            'build',
            'target',
            'bin',
            'obj',
            'out',
            # IDE和编辑器文件
            '.idea',
            '.vscode',
            '.vs',
            '*.swp',
            '*.swo',
            '*~',
            '.DS_Store',
            'Thumbs.db',
            # 锁文件
            'package-lock.json',
            'yarn.lock',
            'Gemfile.lock',
            'Pipfile.lock',
            'poetry.lock',
            'Cargo.lock',
            # macOS和Windows系统文件
            '.DS_Store',
            'Thumbs.db',
            'desktop.ini',
            # 日志和临时文件
            '*.log',
            '*.tmp',
            '*.bak',
            '*.swp',
            '*.swo',
            # 环境配置文件
            '.env',
            '.env.local',
            '.env.development.local',
            '.env.test.local',
            '.env.production.local',
            '.env.*.local',
            # 缓存目录
            '.cache',
            '.npm',
            '.m2',
            '.gradle',
            '.cabal',
            'Pods',
            'vendor',
            # 测试覆盖率目录
            '.nyc_output',
            'coverage',
            '.coverage',
            # 其他
            '.next',
            '.nuxt',
            '.output',
            'public',
            'static',
        ]

        # 大文件阈值 (MB)
        self.large_file_threshold = 5.0

        # 支持的代码文件扩展名
        self.code_extensions = {
            '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs', '.cpp', '.c', '.h',
            '.hpp', '.cc', '.cxx', '.php', '.rb', '.cs', '.vb', '.swift', '.kt', '.scala',
            '.r', '.m', '.pl', '.lua', '.sh', '.sql', '.html', '.css', '.scss', '.less'
        }

    async def analyze_repository_structure(self,
                                           repo_url: str,
                                           include_static_scan: bool = True,
                                           ai_provider: str = "deepseek",
                                           github_token: Optional[str] = None,
                                           gitee_token: Optional[str] = None) -> Dict[str, Any]:
        """
        分析仓库结构，提供详细的预处理信息
        
        Args:
            repo_url: 仓库URL
            include_static_scan: 是否包含静态扫描
            ai_provider: AI服务提供商
            github_token: GitHub访问令牌
            gitee_token: Gitee访问令牌
            
        Returns:
            预处理分析结果
        """
        try:
            logger.info(f"开始预处理分析: {repo_url}")

            # 1. 获取仓库基本信息
            repo_info = await self._get_repository_info(repo_url, github_token, gitee_token)
            if not repo_info:
                return self._create_error_result("无法获取仓库信息")

            # 2. 克隆仓库
            repo_path = await self._clone_repository(repo_url, github_token, gitee_token)
            if not repo_path:
                return self._create_error_result("无法克隆仓库")

            # 3. 详细文件分析
            file_analysis = self._detailed_file_analysis(repo_path)

            # 4. 成本估算
            cost_estimate = await self.cost_estimation_service.estimate_repository_cost(
                repo_url=repo_url,
                include_static_scan=include_static_scan,
                ai_provider=ai_provider,
                github_token=github_token,
                gitee_token=gitee_token
            )

            # 5. 风险评估
            risk_assessment = self._assess_analysis_risks(file_analysis, cost_estimate)

            # 6. 生成建议
            recommendations = self._generate_preprocessing_recommendations(file_analysis, cost_estimate,
                                                                           risk_assessment)

            # 7. 构建结果
            result = {
                "success": True,
                "repository_url": repo_url,
                "repository_info": repo_info,
                "file_analysis": file_analysis,
                "cost_estimate": cost_estimate,
                "risk_assessment": risk_assessment,
                "recommendations": recommendations,
                "analysis_settings": {
                    "include_static_scan": include_static_scan,
                    "ai_provider": ai_provider,
                    "estimated_duration": cost_estimate.get("estimated_analysis_time", "未知"),
                    "recommended_mode": cost_estimate.get("recommended_analysis_mode", "标准模式")
                },
                "blacklist_summary": self._generate_blacklist_summary(file_analysis),
                "generated_at": datetime.now().isoformat()
            }

            # 清理临时文件
            if repo_path:
                import shutil
                try:
                    shutil.rmtree(repo_path, ignore_errors=True)
                except Exception as e:
                    logger.warning(f"清理临时文件失败: {e}")

            logger.info(f"预处理分析完成: {repo_url}")
            return result

        except Exception as e:
            logger.error(f"预处理分析失败: {str(e)}")
            return self._create_error_result(f"预处理分析失败: {str(e)}")

    async def _get_repository_info(self, repo_url: str, github_token: Optional[str], gitee_token: Optional[str]) -> \
            Optional[Dict[str, Any]]:
        """获取仓库基本信息"""
        try:
            if "gitee.com" in repo_url.lower():
                return await self.gitee_service.get_repository_info(repo_url, gitee_token)
            else:
                return await self.github_service.get_repository_info(repo_url, github_token)
        except Exception as e:
            logger.error(f"获取仓库信息失败: {e}")
            return None

    async def _clone_repository(self, repo_url: str, github_token: Optional[str], gitee_token: Optional[str]) -> \
            Optional[str]:
        """克隆仓库"""
        try:
            token = gitee_token if "gitee.com" in repo_url.lower() else github_token
            return await self.git_utils.clone_repo(repo_url, token=token)
        except Exception as e:
            logger.error(f"克隆仓库失败: {e}")
            return None

    def _detailed_file_analysis(self, repo_path: str) -> Dict[str, Any]:
        """详细的文件分析"""
        analysis = {
            "total_files": 0,
            "analyzed_files": 0,
            "blacklisted_files": 0,
            "large_files": 0,
            "empty_files": 0,
            "binary_files": 0,
            "file_statistics": {
                "by_extension": {},
                "by_category": {
                    "code": 0,
                    "documentation": 0,
                    "configuration": 0,
                    "test": 0,
                    "other": 0
                },
                "by_size": {
                    "small": 0,  # < 1KB
                    "medium": 0,  # 1KB - 10KB
                    "large": 0,  # 10KB - 100KB
                    "huge": 0  # > 100KB
                }
            },
            "problematic_files": [],
            "skipped_patterns": [],
            "repository_size_mb": 0.0
        }

        try:
            # 遍历所有文件
            for root, dirs, files in os.walk(repo_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, repo_path)

                    analysis["total_files"] += 1

                    # 检查是否在黑名单中
                    if self._is_blacklisted_file(root, file):
                        analysis["blacklisted_files"] += 1
                        continue

                    # 检查文件大小
                    try:
                        file_size = os.path.getsize(file_path)
                    except OSError:
                        continue

                    # 检查是否为大文件
                    if file_size > self.large_file_threshold * 1024 * 1024:
                        analysis["large_files"] += 1
                        analysis["problematic_files"].append({
                            "path": relative_path,
                            "issue": "大文件",
                            "size_mb": round(file_size / (1024 * 1024), 2),
                            "recommendation": "建议排除或分片处理"
                        })
                        continue

                    # 检查是否为空文件
                    if file_size == 0:
                        analysis["empty_files"] += 1
                        continue

                    # 检查是否为二进制文件
                    if self._is_binary_file(file_path):
                        analysis["binary_files"] += 1
                        continue

                    # 统计文件扩展名
                    file_ext = os.path.splitext(file)[1].lower()
                    if file_ext:
                        analysis["file_statistics"]["by_extension"][file_ext] = \
                            analysis["file_statistics"]["by_extension"].get(file_ext, 0) + 1

                    # 按类别统计
                    category = self._categorize_file(file, file_ext)
                    analysis["file_statistics"]["by_category"][category] += 1

                    # 按大小统计
                    size_category = self._categorize_file_size(file_size)
                    analysis["file_statistics"]["by_size"][size_category] += 1

                    analysis["analyzed_files"] += 1

            # 计算仓库大小
            analysis["repository_size_mb"] = self._calculate_repository_size(repo_path)

            # 生成黑名单模式总结
            analysis["skipped_patterns"] = self._get_skipped_patterns(repo_path)

            return analysis

        except Exception as e:
            logger.error(f"详细文件分析失败: {e}")
            return analysis

    def _is_blacklisted_file(self, root: str, file: str) -> bool:
        """检查文件是否在黑名单中"""
        full_path = os.path.join(root, file).lower()
        file_lower = file.lower()

        for pattern in self.blacklist_patterns:
            # 处理通配符模式
            if '*' in pattern:
                import fnmatch
                if fnmatch.fnmatch(file_lower, pattern.lower()) or fnmatch.fnmatch(full_path, pattern.lower()):
                    return True
            elif pattern.lower() in full_path or file_lower == pattern.lower():
                return True

        return False

    def _is_binary_file(self, file_path: str) -> bool:
        """检查是否为二进制文件"""
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(1024)
                # 检查是否包含null字节（二进制文件的典型特征）
                if b'\x00' in chunk:
                    return True

                # 检查是否为图片、视频等常见二进制格式
                file_ext = os.path.splitext(file_path)[1].lower()
                binary_extensions = {
                    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.svg',
                    '.mp4', '.avi', '.mov', '.wmv', '.flv',
                    '.mp3', '.wav', '.ogg', '.flac',
                    '.zip', '.rar', '.7z', '.tar', '.gz',
                    '.exe', '.dll', '.so', '.dylib',
                    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx'
                }

                return file_ext in binary_extensions
        except Exception:
            return True  # 如果无法读取，默认认为是二进制文件

    def _categorize_file(self, file: str, extension: str) -> str:
        """文件分类"""
        file_lower = file.lower()

        # 代码文件
        if extension in self.code_extensions:
            if any(test_ext in file_lower for test_ext in ['.test', '.spec', '_test', '_spec', 'tests']):
                return 'test'
            return 'code'

        # 文档文件
        doc_extensions = {'.md', '.txt', '.rst', '.doc', '.docx', '.pdf', '.adoc'}
        if extension in doc_extensions:
            return 'documentation'

        # 配置文件
        config_extensions = {
            '.json', '.yaml', '.yml', '.xml', '.ini', '.cfg', '.conf', '.toml',
            '.env', '.properties', '.plist', '.makefile', 'dockerfile'
        }
        if extension in config_extensions or 'dockerfile' in file_lower or 'makefile' in file_lower:
            return 'configuration'

        return 'other'

    def _categorize_file_size(self, size_bytes: int) -> str:
        """按大小分类文件"""
        if size_bytes < 1024:
            return 'small'
        elif size_bytes < 10240:  # 10KB
            return 'medium'
        elif size_bytes < 102400:  # 100KB
            return 'large'
        else:
            return 'huge'

    def _calculate_repository_size(self, repo_path: str) -> float:
        """计算仓库大小（MB）"""
        try:
            total_size = 0
            for root, dirs, files in os.walk(repo_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    if os.path.exists(file_path):
                        try:
                            total_size += os.path.getsize(file_path)
                        except OSError:
                            continue
            return total_size / (1024 * 1024)  # 转换为MB
        except Exception as e:
            logger.error(f"计算仓库大小失败: {e}")
            return 0.0

    def _get_skipped_patterns(self, repo_path: str) -> List[str]:
        """获取实际跳过的模式列表"""
        skipped_patterns = set()

        try:
            for root, dirs, files in os.walk(repo_path):
                for file in files:
                    if self._is_blacklisted_file(root, file):
                        # 确定匹配的模式
                        full_path = os.path.join(root, file).lower()
                        for pattern in self.blacklist_patterns:
                            if pattern.lower() in full_path:
                                skipped_patterns.add(pattern)
                                break
        except Exception as e:
            logger.error(f"获取跳过模式失败: {e}")

        return sorted(list(skipped_patterns))

    def _assess_analysis_risks(self, file_analysis: Dict[str, Any], cost_estimate: Dict[str, Any]) -> Dict[str, Any]:
        """评估分析风险"""
        risks = {
            "cost_risk": "low",
            "time_risk": "low",
            "accuracy_risk": "low",
            "overall_risk": "low",
            "risk_factors": [],
            "mitigation_suggestions": []
        }

        # 成本风险评估
        estimated_tokens = cost_estimate.get("token_estimate", {}).get("total_estimated_tokens", 0)
        if estimated_tokens > 100000:
            risks["cost_risk"] = "high"
            risks["risk_factors"].append(f"Token消耗较高 ({estimated_tokens:,})")
            risks["mitigation_suggestions"].append("考虑禁用静态扫描或限制分析范围")
        elif estimated_tokens > 50000:
            risks["cost_risk"] = "medium"
            risks["risk_factors"].append(f"Token消耗中等 ({estimated_tokens:,})")
            risks["mitigation_suggestions"].append("注意监控成本消耗")

        # 时间风险评估
        analyzed_files = file_analysis.get("analyzed_files", 0)
        if analyzed_files > 500:
            risks["time_risk"] = "high"
            risks["risk_factors"].append(f"文件数量较多 ({analyzed_files}个)")
            risks["mitigation_suggestions"].append("建议使用异步模式或分批分析")
        elif analyzed_files > 200:
            risks["time_risk"] = "medium"
            risks["risk_factors"].append(f"文件数量中等 ({analyzed_files}个)")
            risks["mitigation_suggestions"].append("建议设置合适的超时时间")

        # 准确性风险评估
        blacklisted_files = file_analysis.get("blacklisted_files", 0)
        total_files = file_analysis.get("total_files", 1)
        blacklisted_ratio = blacklisted_files / total_files

        if blacklisted_ratio > 0.7:
            risks["accuracy_risk"] = "high"
            risks["risk_factors"].append(f"大量文件被过滤器排除 ({blacklisted_ratio:.1%})")
            risks["mitigation_suggestions"].append("检查黑名单配置是否过于严格")
        elif blacklisted_ratio > 0.5:
            risks["accuracy_risk"] = "medium"
            risks["risk_factors"].append(f"部分文件被过滤器排除 ({blacklisted_ratio:.1%})")
            risks["mitigation_suggestions"].append("确认排除的文件确实不需要分析")

        # 综合风险评估
        high_risks = sum(
            1 for risk in [risks["cost_risk"], risks["time_risk"], risks["accuracy_risk"]] if risk == "high")
        medium_risks = sum(
            1 for risk in [risks["cost_risk"], risks["time_risk"], risks["accuracy_risk"]] if risk == "medium")

        if high_risks >= 2 or (high_risks >= 1 and medium_risks >= 1):
            risks["overall_risk"] = "high"
        elif high_risks >= 1 or medium_risks >= 2:
            risks["overall_risk"] = "medium"
        else:
            risks["overall_risk"] = "low"

        return risks

    def _generate_preprocessing_recommendations(self, file_analysis: Dict[str, Any], cost_estimate: Dict[str, Any],
                                                risk_assessment: Dict[str, Any]) -> List[str]:
        """生成预处理建议"""
        recommendations = []

        # 基于文件分析的建议
        analyzed_files = file_analysis.get("analyzed_files", 0)
        if analyzed_files == 0:
            recommendations.append("未检测到可分析的代码文件，请检查仓库结构")
        elif analyzed_files < 10:
            recommendations.append("代码文件较少，建议检查是否包含所有相关文件。")
        elif analyzed_files > 1000:
            recommendations.append("文件数量较多，建议考虑分批次分析。")

        # 基于成本估算的建议
        estimated_cost = cost_estimate.get("token_estimate", {}).get("estimated_cost", {})
        cost_cny = estimated_cost.get("cost_cny", 0)
        if cost_cny > 1.0:
            recommendations.append(f"预计成本较高 (¥{cost_cny:.2f})，建议确认后继续")
        elif cost_cny > 0.5:
            recommendations.append(f"预计成本中等 (¥{cost_cny:.2f})，建议控制分析范围")

        # 基于风险评估的建议
        if risk_assessment["overall_risk"] == "high":
            recommendations.append("分析风险较高，建议仔细评估后续步骤。")
        elif risk_assessment["overall_risk"] == "medium":
            recommendations.append("存在一定风险，建议采取相应预防措施。")

        # 基于问题文件的建议
        problematic_files = file_analysis.get("problematic_files", [])
        if problematic_files:
            recommendations.append(f"发现 {len(problematic_files)} 个问题文件，建议查看详细信息。")

        return recommendations

    def _generate_blacklist_summary(self, file_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """生成黑名单统计摘要"""
        total_files = file_analysis.get("total_files", 0)
        blacklisted_files = file_analysis.get("blacklisted_files", 0)

        if total_files == 0:
            return {"percentage": 0, "efficiency": "无数据"}

        percentage = (blacklisted_files / total_files) * 100

        if percentage > 70:
            efficiency = "高效"
        elif percentage > 40:
            efficiency = "良好"
        else:
            efficiency = "一般"

        return {
            "total_files": total_files,
            "blacklisted_files": blacklisted_files,
            "percentage": round(percentage, 1),
            "efficiency": efficiency,
            "skipped_patterns": file_analysis.get("skipped_patterns", [])
        }

    def _create_error_result(self, error_message: str) -> Dict[str, Any]:
        """创建错误结果"""
        return {
            "success": False,
            "error": error_message,
            "generated_at": datetime.now().isoformat()
        }
