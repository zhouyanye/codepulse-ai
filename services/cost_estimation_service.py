import logging
import os
import asyncio
import shutil
from typing import Dict, Any, Optional, List
from datetime import datetime

from utils.token_estimator import TokenEstimator
from services.github_service import GitHubService
from services.gitee_service import GiteeService
from utils.git_utils import GitUtils

logger = logging.getLogger(__name__)


class CostEstimationService:
    """成本估算服务"""

    def __init__(self):
        self.token_estimator = TokenEstimator()
        self.github_service = GitHubService()
        self.gitee_service = GiteeService()
        self.git_utils = GitUtils()
    
    async def close(self):
        """关闭所有异步资源"""
        if hasattr(self.github_service, 'github_client') and hasattr(self.github_service.github_client, 'close'):
            await self.github_service.github_client.close()
        if hasattr(self.gitee_service, 'gitee_client') and hasattr(self.gitee_service.gitee_client, 'close'):
            await self.gitee_service.gitee_client.close()

    def _extract_repo_name_from_url(self, repo_url: str) -> str:
        """从URL提取仓库名称"""
        import re

        # 移除查询参数和片段标识符
        # 移除URL中的查询参数（?后面的部分）和片段（#后面的部分）
        repo_url = repo_url.split('?')[0].split('#')[0]

        # 移除.git后缀
        if repo_url.endswith('.git'):
            repo_url = repo_url[:-4]

        # 移除末尾斜杠
        repo_url = repo_url.rstrip('/')

        # 使用正则表达式提取 owner/repo 部分，更准确地处理各种URL格式
        # 支持 https://github.com/owner/repo, https://gitee.com/owner/repo, git@github.com:owner/repo 等格式
        github_pattern = r'(?:https?://|git@)?(?:www\.)?github\.com[/:]([^/]+)/([^/]+)'
        gitee_pattern = r'(?:https?://|git@)?(?:www\.)?gitee\.com[/:]([^/]+)/([^/]+)'

        # 尝试匹配GitHub URL
        match = re.search(github_pattern, repo_url)
        if match:
            return f"{match.group(1)}/{match.group(2)}"

        # 尝试匹配Gitee URL
        match = re.search(gitee_pattern, repo_url)
        if match:
            return f"{match.group(1)}/{match.group(2)}"

        # 如果是 owner/repo 格式直接返回
        parts = repo_url.split('/')
        if len(parts) == 2 and '.' not in repo_url and 'github.com' not in repo_url and 'gitee.com' not in repo_url:  # 确保不是包含域名的URL
            return repo_url

        # 处理类似 https://github.com/owner 这样的情况
        if 'github.com' in repo_url or 'gitee.com' in repo_url:
            # 提取 github.com 或 gitee.com 后面的部分
            pattern = r'(?:github|gitee)\.com[/:]([^/]+)(?:/([^/]+))?'  # 匹配 owner 和可选的 repo
            match = re.search(pattern, repo_url)
            if match:
                owner = match.group(1)
                repo = match.group(2) if match.group(2) else ''
                if repo:
                    return f"{owner}/{repo}"
                else:
                    return owner  # 只有 owner 的情况

        # 如果是其他格式，回退到原始方法
        if len(parts) >= 2:
            return '/'.join(parts[-2:])

        return repo_url

    async def estimate_repository_cost(self,
                                       repo_url: str,
                                       include_static_scan: bool = True,
                                       ai_provider: str = "deepseek",
                                       github_token: Optional[str] = None,
                                       gitee_token: Optional[str] = None) -> Dict[str, Any]:
        """
        估算分析仓库的成本（优化版：优先使用API，避免克隆）

        优化策略:
        1. 优先使用GitHub/Gitee API获取仓库信息（不克隆）
        2. API获取失败时，才考虑轻量级浅克隆
        3. CoStrict模式直接返回0成本

        Args:
            repo_url: 仓库URL
            include_static_scan: 是否包含静态扫描
            ai_provider: AI服务提供商
            github_token: GitHub访问令牌
            gitee_token: Gitee访问令牌

        Returns:
            成本估算结果
        """
        try:
            logger.info(f"开始估算仓库分析成本（优化API优先）: {repo_url}")

            # 1. 尝试获取仓库基本信息（优先API，不克隆）
            repo_info = await self._get_repository_info(repo_url, github_token, gitee_token)
            if not repo_info:
                # API失败时使用基本信息
                repo_info = {
                    "full_name": self._extract_repo_name_from_url(repo_url),
                    "language": "未知",
                    "description": "无API访问权限"
                }
                logger.info(f"API获取信息失败，使用URL提取的基本信息: {repo_info['full_name']}")

            # 2. 尝试通过API获取文件统计信息（不克隆）
            file_stats = await self._get_file_statistics_from_api(repo_url, github_token, gitee_token, repo_info)

            # 3. 如果API无法获取详细信息，才进行轻量级浅克隆
            repo_path = None
            repo_size_mb = 1.0  # 默认1MB

            if not file_stats or file_stats.get("code", 0) == 0:
                logger.info(f"API无法获取文件统计，尝试轻量级浅克隆")
                repo_path = await self._clone_repository_lightweight(repo_url, github_token, gitee_token)
                if not repo_path:
                    # 克隆也失败，使用默认估算
                    logger.warning(f"克隆失败，使用默认成本估算")
                    file_stats = {
                        "code": 100,  # 假设100个代码文件
                        "code_lines": 5000,  # 假设5000行代码
                        "documentation": 10,
                        "configuration": 5,
                        "test": 20,
                        "other": 30,
                        "total_files": 165,
                        "skipped_files": 15
                    }
                    repo_size_mb = 2.0  # 默认2MB
                else:
                    # 克隆成功，分析本地文件
                    file_stats = self._analyze_repository_structure(repo_path)
                    repo_size_mb = self._calculate_repository_size(repo_path)
                    logger.info(f"浅克隆成功，文件统计: {file_stats}")
            else:
                # API获取成功，根据API信息估算大小
                repo_size_mb = self._estimate_repo_size_from_stats(file_stats, repo_info)
                logger.info(f"API获取成功，估算仓库大小: {repo_size_mb}MB")

            # 5. 应用黑名单过滤
            filtered_stats = self._apply_blacklist_filter(file_stats)

            # 6. 获取过滤文件详细信息
            filtered_files_details = self._get_filtered_files_details(repo_path)

            # 7. 估算Token消耗
            if ai_provider == "costrict":
                logger.info("CoStrict 模式：不使用 AI API，成本为 0")
                token_estimate = {
                    "total_estimated_tokens": 0,
                    "estimated_cost": {"cost_usd": 0.0, "cost_rmb": 0.0},
                    "analysis_overhead": 0
                }
            else:
                token_estimate = self.token_estimator.estimate_total_tokens(
                    repo_size_mb=repo_size_mb,
                    file_stats=filtered_stats,
                    provider=ai_provider
                )

            # 8. 添加静态扫描的额外开销
            if include_static_scan and ai_provider != "costrict":
                static_scan_overhead = self._estimate_static_scan_overhead(filtered_stats, repo_size_mb)
                token_estimate["total_estimated_tokens"] += static_scan_overhead
                token_estimate["analysis_overhead"] += static_scan_overhead
                token_estimate["estimated_cost"] = self.token_estimator._estimate_cost(
                    token_estimate["total_estimated_tokens"], ai_provider
                )

            # 9. 估算分析时间
            analysis_time_str = self._estimate_analysis_time(repo_size_mb, filtered_stats, include_static_scan)

            # 10. 添加详细分析信息
            estimate_result = {
                "success": True,
                "repository_url": repo_url,
                "repository_name": repo_info.get("full_name", "未知"),
                "repository_size_mb": round(repo_size_mb, 2),
                "file_statistics": filtered_stats,
                "blacklisted_files": self._get_blacklisted_count(file_stats),
                "filtered_files_details": filtered_files_details if repo_path else [],
                "filtered_files": filtered_files_details if repo_path else [],
                "token_estimate": token_estimate,
                "include_static_scan": include_static_scan,
                "ai_provider": ai_provider,
                "estimated_analysis_time": analysis_time_str,
                "recommended_analysis_mode": self._recommend_analysis_mode(repo_size_mb, filtered_stats),
                "warnings": self._generate_warnings(repo_size_mb, filtered_stats, token_estimate),
                "generated_at": datetime.now().isoformat(),
                "estimated_tokens": token_estimate.get("total_estimated_tokens", 0),
                "estimated_cost_rmb": token_estimate.get("estimated_cost", {}).get("cost_rmb", 0.0),
                "estimated_cost_usd": token_estimate.get("estimated_cost", {}).get("cost_usd", 0.0),
                "estimated_time_minutes": self._parse_analysis_time_to_minutes(analysis_time_str),
                "file_count": filtered_stats.get("total_files", 0),
                "total_lines": filtered_stats.get("code_lines", 0),
                "skipped_files_count": self._get_blacklisted_count(file_stats)
            }

            # 清理临时文件
            if repo_path:
                try:
                    shutil.rmtree(repo_path, ignore_errors=True)
                except Exception as e:
                    logger.warning(f"清理临时文件失败: {e}")

            logger.info(f"成本估算完成: {repo_url}")
            return estimate_result

        except Exception as e:
            logger.error(f"成本估算失败: {str(e)}")
            return self._create_error_estimate(f"成本估算失败: {str(e)}")

    async def _get_file_statistics_from_api(self, repo_url: str,
                                            github_token: Optional[str],
                                            gitee_token: Optional[str],
                                            existing_repo_info: Optional[Dict[str, Any]] = None) -> Dict[str, int]:
        """
        通过API获取文件统计信息（不克隆）
        
        GitHub/Gitee API限制：
        - 不提供准确的文件总数
        - 不提供代码行数
        - languages API只提供字节占比
        
        策略：根据语言占比估算文件数量
        """
        try:
            logger.info("尝试通过API获取文件统计信息")

            # 优先使用已有的repo_info中的语言信息
            if existing_repo_info and "languages" in existing_repo_info:
                languages = existing_repo_info["languages"]
                total_bytes = sum(languages.values()) if languages else 0

                if total_bytes > 0:
                    # 估算：假设平均每个文件为10KB
                    estimated_files = max(10, min(total_bytes // 10240, 10000))

                    # 按语言占比分配文件
                    file_stats = {"code": 0, "code_lines": 0, "documentation": 0,
                                  "configuration": 0, "test": 0, "other": 0,
                                  "total_files": estimated_files, "skipped_files": 0}

                    for lang, bytes_count in languages.items():
                        lang_files = int(estimated_files * (bytes_count / total_bytes))
                        lang_lower = lang.lower()

                        if lang_lower in ["python", "javascript", "typescript", "java", "go", "rust", "c++", "c", "php",
                                          "ruby"]:
                            file_stats["code"] += lang_files
                            # 假设平均每文件50行
                            file_stats["code_lines"] += lang_files * 50
                        elif lang_lower in ["markdown", "text"]:
                            file_stats["documentation"] += lang_files
                        elif lang_lower in ["json", "yaml", "xml", "ini"]:
                            file_stats["configuration"] += lang_files
                        elif "test" in lang_lower:
                            file_stats["test"] += lang_files
                        else:
                            file_stats["other"] += lang_files

                    logger.info(f"API估算文件统计成功: {file_stats}")
                    return file_stats

            # API获取失败，返回空字典触发克隆
            logger.warning("API无法获取语言信息，需要克隆分析")
            return {}

        except Exception as e:
            logger.error(f"通过API获取文件统计失败: {e}")
            return {}

    def _estimate_repo_size_from_stats(self, file_stats: Dict[str, int], repo_info: Dict[str, Any]) -> float:
        """
        根据文件统计估算仓库大小MB
        """
        try:
            # 优先使用repo_info中的size字段（如果有的话，单位通常是KB）
            if repo_info and "size" in repo_info:
                size_kb = repo_info["size"]
                return max(0.1, size_kb / 1024)  # KB转MB

            # 否则根据文件数量估算
            total_files = file_stats.get("total_files", 100)
            code_files = file_stats.get("code", 50)

            # 假设：代码文件平均20KB，其他文件平均5KB
            estimated_size = (code_files * 20 + (total_files - code_files) * 5) / 1024  # KB转MB

            return max(0.1, min(estimated_size, 500))  # 限制在0.1-500MB之间

        except Exception as e:
            logger.error(f"估算仓库大小失败: {e}")
            return 1.0  # 默认1MB

    async def _clone_repository_lightweight(self, repo_url: str, github_token: Optional[str],
                                            gitee_token: Optional[str]) -> Optional[str]:
        """
        轻量级克隆：仅用于成本估算时的快速分析
        
        优化:
        1. 使用最短超时（180秒）
        2. 浅克隆 --depth=1 --single-branch
        3. 失败即返回，不重试
        """
        try:
            from utils.git_utils import GitUtils
            git_utils = GitUtils()

            # 临时创建一个GitUtils实例，使用更短的超时
            original_timeout = git_utils.timeout
            git_utils.timeout = 180

            token = gitee_token if "gitee.com" in repo_url.lower() else github_token
            repo_path = await git_utils.clone_repo(repo_url, token=token)

            # 恢复原始超时
            git_utils.timeout = original_timeout

            return repo_path

        except Exception as e:
            logger.error(f"轻量级克隆失败: {e}")
            return None

    async def _get_repository_info(self, repo_url: str, github_token: Optional[str], gitee_token: Optional[str]) -> \
            Optional[Dict[str, Any]]:
        """获取仓库基本信息"""
        try:
            if "gitee.com" in repo_url.lower():
                return await self.gitee_service.get_repository_info(repo_url, gitee_token)
            else:
                return await self.github_service.get_repository_info(repo_url, github_token)
        except Exception as e:
            # API失败不影响成本估算，继续使用克隆的仓库
            logger.warning(f"获取仓库信息失败（可能需要token）: {e}，将使用克隆的仓库进行成本估算")
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

    def _analyze_repository_structure(self, repo_path: str) -> Dict[str, int]:
        """
        分析仓库结构，统计文件类型和数量
        
        返回字典包含:
        - code: 代码文件数量（不包含行数）
        - code_lines: 代码总行数
        - documentation: 文档文件数量
        - configuration: 配置文件数量
        - test: 测试文件数量
        - other: 其他文件数量
        - total_files: 总文件数量（不包含黑名单文件）
        - skipped_files: 被黑名单过滤的文件数量
        """
        file_stats = {
            "code": 0,
            "code_lines": 0,
            "documentation": 0,
            "configuration": 0,
            "test": 0,
            "other": 0,
            "total_files": 0,
            "skipped_files": 0
        }

        try:
            code_extensions = {
                '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs',
                '.cpp', '.c', '.h', '.hpp', '.php', '.rb', '.swift', '.kt',
                '.cs', '.scala', '.vb', '.pl', '.sh', '.bat', '.ps1', '.dart',
                '.lua', '.r', '.m', '.mm', '.swift', '.kt', '.kts'
            }
            doc_extensions = {'.md', '.markdown', '.txt', '.rst', '.doc', '.docx', '.pdf', '.adoc'}
            config_extensions = {
                '.json', '.yaml', '.yml', '.xml', '.ini', '.cfg', '.conf',
                '.toml', '.properties', '.env', '.config', '.gradle', '.pom'
            }
            test_extensions = {'.test', '.spec', '_test', '_spec', '.tests', 'tests'}

            for root, dirs, files in os.walk(repo_path):
                for file in files:
                    # 检查是否在黑名单中
                    if self._is_blacklisted_file(root, file):
                        file_stats["skipped_files"] += 1
                        continue

                    file_ext = os.path.splitext(file)[1].lower()
                    file_lower = file.lower()

                    file_stats["total_files"] += 1

                    # 统计代码文件数量和代码行数
                    if file_ext in code_extensions:
                        file_stats["code"] += 1  # 代码文件数量
                        try:
                            file_path_full = os.path.join(root, file)
                            with open(file_path_full, 'r', encoding='utf-8', errors='ignore') as f:
                                lines = len(f.readlines())
                                file_stats["code_lines"] += lines  # 累加代码行数
                        except:
                            pass
                    elif file_ext in doc_extensions:
                        file_stats["documentation"] += 1
                    elif file_ext in config_extensions:
                        file_stats["configuration"] += 1
                    elif any(test_ext in file_lower for test_ext in test_extensions):
                        file_stats["test"] += 1
                    else:
                        file_stats["other"] += 1

            logger.info(
                f"文件统计结果: 总文件={file_stats['total_files']}, 跳过={file_stats['skipped_files']}, 代码={file_stats['code']}, 代码行数={file_stats['code_lines']}")

            return file_stats

        except Exception as e:
            logger.error(f"分析仓库结构失败: {e}")
            return file_stats

    def _calculate_repository_size(self, repo_path: str) -> float:
        """计算仓库大小（MB）"""
        try:
            total_size = 0
            for root, dirs, files in os.walk(repo_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    if os.path.exists(file_path):
                        total_size += os.path.getsize(file_path)
            return total_size / (1024 * 1024)  # 转换为MB
        except Exception as e:
            logger.error(f"计算仓库大小失败: {e}")
            return 0.0

    def _is_blacklisted_file(self, root: str, file: str) -> bool:
        """
        检查文件是否在黑名单中（与static_scan_service完全同步）
        
        排除规则：
        - 版本控制：.gitlab, .bitbucket
        - CI/CD：.circleci, .travis, .drone
        - 构建产物：dist, build, target, out, site
        - Python缓存：.pyc, __pycache__
        - 虚拟环境：venv, env, .venv
        - 依赖包：node_modules, vendor, bower_components
        - IDE配置：.idea, .vscode
        - 临时文件：tmp, logs, cache, .cache
        - 静态资源：images, static, public, assets, media, img, fonts
        """
        EXCLUDE_DIRS = {".git", ".gitlab", ".bitbucket",  # 版本控制
                        ".circleci", ".travis", ".drone",  # CI配置
                        "site", "dist", "build", "target", "out", "release", "obj",  # 构建产物
                        "__pycache__", ".pyc", ".pytest_cache",  # Python缓存
                        "venv", "env", ".venv", ".env", "envs",  # 虚拟环境
                        "node_modules", "vendor", "bower_components", "jspm_packages",  # 依赖包
                        ".idea", ".vscode", ".vs", ".project", ".settings", ".metadata",  # IDE配置
                        "tmp", "logs", "cache", ".cache"}  # 临时文件 - 修复：移除"temp"，因为用户可能在系统temp目录中克隆仓库

        # 系统文件和锁定文件
        SYSTEM_FILES = {".ds_store", "thumbs.db",  # 系统文件
                        "package-lock.json", "yarn.lock", "gemfile.lock", "podfile.lock"}  # 锁定文件

        file_lower = file.lower()

        # 方法1：检查路径中是否包含排除目录（使用路径分隔符边界确保精确匹配）
        root_normalized = '/' + root.replace('\\', '/').lower() + '/'
        for exclude_dir in EXCLUDE_DIRS:
            # 在路径前后加上分隔符确保匹配完整目录名
            exclude_pattern = '/' + exclude_dir + '/'
            if exclude_pattern in root_normalized:
                return True

        # 方法2：检查文件名是否匹配排除模式
        if file_lower in SYSTEM_FILES:
            return True
        # 方法3：排除临时后缀文件
        if file_lower.endswith(('.log', '.tmp', '.bak')):
            return True

        return False

    def _apply_blacklist_filter(self, file_stats: Dict[str, int]) -> Dict[str, int]:
        """应用黑名单过滤"""
        filtered = file_stats.copy()
        # 确保skipped_files字段存在
        if "skipped_files" not in filtered:
            filtered["skipped_files"] = 0
        return filtered

    def _get_blacklisted_count(self, file_stats: Dict[str, int]) -> int:
        """获取被过滤的文件数量（从统计中直接读取）"""
        return file_stats.get("skipped_files", 0)

    def _estimate_static_scan_overhead(self, file_stats: Dict[str, int], repo_size_mb: float) -> int:
        """估算静态扫描的额外token开销"""
        # 基于文件数量和仓库大小估算静态扫描开销
        base_overhead = 2000  # 基础开销
        file_overhead = file_stats.get("code", 0) * 50  # 每个代码文件50 tokens
        size_overhead = int(repo_size_mb * 100)  # 每MB 100 tokens

        return base_overhead + file_overhead + size_overhead

    def _estimate_analysis_time(self, repo_size_mb: float, file_stats: Dict[str, int],
                                include_static_scan: bool) -> str:
        """
        估算分析时间范围（包含克隆时间、文件分析、API调用）
        
        Args:
            repo_size_mb: 仓库大小(MB)
            file_stats: 文件统计信息
            include_static_scan: 是否包含静态扫描
            
        Real-world observations:
        - 小仓库(<1MB): 3-8分钟 (克隆 30-60s + API 2-4s + 分析 1-5min)
        - 中仓库(1-10MB): 5-15分钟 (克隆 1-3min + API 3-8s + 分析 3-10min)
        - 大仓库(>10MB): 10-30分钟 (克隆 3-10min + API 5-15s + 分析 5-20min)
        """
        # 克隆时间：基于仓库大小估算（考虑缓存机制）
        # 有缓存：10-30秒（快速）
        # 无缓存：60-300秒（3-5分钟）
        clone_time_min = max(30, repo_size_mb * 3)  # 有缓存的情况
        clone_time_max = max(60, repo_size_mb * 15)  # 无缓存的情况（国内网络）

        # 文件分析时间：遍历和统计文件
        # 小仓库文件少，大仓库文件多
        analysis_time = file_stats.get("total_files", 0) * 0.1  # 每个文件0.1秒
        analysis_time = max(30, analysis_time)  # 至少30秒
        analysis_time = min(180, analysis_time)  # 最多3分钟

        # 静态扫描时间（如果启用）
        static_time = 0
        if include_static_scan and file_stats.get("code", 0) > 0:
            # 代码文件数量 * 0.5秒/文件（AI分析和工具扫描）
            static_time = file_stats.get("code", 0) * 0.5
            static_time = max(60, static_time)  # 至少1分钟
            static_time = min(600, static_time)  # 最多10分钟

        # AI API调用时间
        api_time_min = 5  # 快速响应（缓存命中/低负载）
        api_time_max = 15  # 慢速响应（高峰时段/重试）

        # CoStrict模式：跳过AI API调用
        if include_static_scan is False and file_stats.get("code", 0) == 0:
            api_time_min = 3
            api_time_max = 8

        # 总时间计算
        total_seconds_min = clone_time_min + analysis_time + static_time + api_time_min
        total_seconds_max = clone_time_max + analysis_time * 1.2 + static_time * 1.3 + api_time_max

        # 添加缓冲时间（网络波动、队列等待等）
        buffer_percent = 0.2  # 20%缓冲
        total_seconds_min *= (1 + buffer_percent)
        total_seconds_max *= (1 + buffer_percent * 1.5)

        # 格式化为时间范围
        if total_seconds_max < 60:
            min_val = int(max(10, total_seconds_min))
            max_val = int(total_seconds_max)
            return f"{min_val}-{max_val}秒"
        elif total_seconds_max < 3600:
            min_minutes = max(1, int(total_seconds_min / 60))
            max_minutes = int(total_seconds_max / 60)
            return f"{min_minutes}-{max_minutes}分钟"
        elif total_seconds_max < 7200:  # 2小时内
            min_minutes = int(total_seconds_min / 60)
            max_minutes = int(total_seconds_max / 60)
            return f"{min_minutes // 60}小时{min_minutes % 60}分-{max_minutes // 60}小时{max_minutes % 60}分"
        else:
            min_hours = int(total_seconds_min / 3600)
            max_hours = int(total_seconds_max / 3600)
            if min_hours == max_hours:
                return f"约{max_hours}小时"
            return f"{min_hours}-{max_hours}小时"

    def _parse_analysis_time_to_minutes(self, time_str: str) -> float:
        """将时间范围字符串转换为平均分钟数"""
        try:
            if "秒" in time_str:
                # 范围格式：10-20秒
                if "-" in time_str:
                    parts = time_str.replace("秒", "").split("-")
                    min_val, max_val = int(parts[0]), int(parts[1])
                    return round((min_val + max_val) / 2 / 60, 2)
                return round(int(time_str.replace("秒", "")) / 60, 2)
            elif "分钟" in time_str:
                # 范围格式：2-5分钟
                if "-" in time_str:
                    parts = time_str.replace("分钟", "").split("-")
                    min_val, max_val = int(parts[0]), int(parts[1])
                    return (min_val + max_val) / 2
                return float(int(time_str.replace("分钟", "")))
            elif "小时" in time_str:
                # 范围格式：1-2小时 或 约2小时
                if "-" in time_str:
                    parts = time_str.replace("小时", "").split("-")
                    min_val, max_val = int(parts[0]), int(parts[1])
                    return round((min_val + max_val) / 2 * 60, 2)
                elif "約" in time_str:
                    return round(int(time_str.replace("約", "").replace("小时", "")) * 60, 1)
                return round(int(time_str.replace("小时", "")) * 60, 2)
        except Exception:
            pass
        return 3.0  # 默认3分钟

    def _get_filtered_files_details(self, repo_path: str) -> Dict[str, Any]:
        """获取被过滤文件的详细信息"""
        details = {
            "blacklist_patterns": [
                'node_modules', 'venv', 'virtualenv', '__pycache__',
                '.pytest_cache', 'coverage', 'dist', 'build', 'target', '.DS_Store',
                'Thumbs.db', 'package-lock.json', 'yarn.lock', 'Gemfile.lock',
                'Pods', '.idea', '.vscode', '*.log', '*.tmp', '*.bak',
                '.env', '.env.local', '.env.*.local'
            ],
            "large_files": [],
            "binary_files": [],
            "skipped_files": []  # 添加跳过的文件列表
        }

        if not repo_path or not os.path.exists(repo_path):
            return details

        try:
            large_file_threshold_kb = 500  # 500KB以上算大文件
            binary_extensions = {'.exe', '.dll', '.so', '.dylib', '.bin', '.zip', '.tar', '.gz', '.rar', '.7z',
                                 '.pdf', '.jpg', '.png', '.gif', '.bmp', '.ico', '.mp3', '.mp4', '.avi', '.mov', '.wmv'}

            for root, dirs, files in os.walk(repo_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    if self._is_blacklisted_file(root, file):
                        # 记录跳过的文件
                        try:
                            if os.path.exists(file_path):
                                file_size_kb = os.path.getsize(file_path) / 1024
                                relative_path = file_path.replace(repo_path, "")
                                details["skipped_files"].append({
                                    "path": relative_path,
                                    "size_kb": round(file_size_kb, 2)
                                })
                                # 添加日志显示跳过的文件
                                # logger.info(f"跳过文件: {relative_path} ({file_size_kb:.2f}KB)")
                        except Exception as e:
                            logger.debug(f"获取跳过文件详情失败: {e}")
                    else:
                        # 检查是否为大文件或二进制文件
                        try:
                            if os.path.exists(file_path):
                                file_size_kb = os.path.getsize(file_path) / 1024
                                file_ext = os.path.splitext(file)[1].lower()

                                if file_size_kb > large_file_threshold_kb:
                                    details["large_files"].append({
                                        "path": file_path.replace(repo_path, ""),
                                        "size_kb": round(file_size_kb, 2)
                                    })

                                if file_ext in binary_extensions:
                                    details["binary_files"].append({
                                        "path": file_path.replace(repo_path, ""),
                                        "size_kb": round(file_size_kb, 2)
                                    })
                        except Exception as e:
                            logger.debug(f"获取单个过滤文件详情失败: {e}")

            # 如果跳过的文件过多，采用摘要式日志输出
            skipped_count = len(details["skipped_files"])
            if skipped_count > 10:
                logger.info(
                    f"跳过文件统计: 共跳过 {skipped_count} 个文件，仅显示前10个: {[f['path'] for f in details['skipped_files'][:10]]}...")
        except Exception as e:
            logger.warning(f"获取过滤文件详情失败: {e}")

        return details

    def _recommend_analysis_mode(self, repo_size_mb: float, file_stats: Dict[str, int]) -> str:
        """推荐分析模式"""
        total_score = repo_size_mb * 10 + file_stats.get("total_files", 0) * 0.5

        if total_score < 100:
            return "快速模式（推荐）"
        elif total_score < 500:
            return "标准模式（推荐）"
        else:
            return "深度模式（需要较长时间）"

    def _generate_warnings(self, repo_size_mb: float, file_stats: Dict[str, int], token_estimate: Dict[str, Any]) -> \
            List[str]:
        """生成警告信息"""
        warnings = []

        if repo_size_mb > 100:
            warnings.append(f"仓库较大 ({repo_size_mb:.1f}MB)，分析时间可能较长")

        if file_stats.get("total_files", 0) > 1000:
            warnings.append(f"文件数量较多 ({file_stats['total_files']}个)，建议分批分析")

        estimated_tokens = token_estimate.get("total_estimated_tokens", 0)
        if estimated_tokens > 100000:
            warnings.append(f"Token消耗较多 ({estimated_tokens:,}个)，成本较高")
        elif estimated_tokens > 50000:
            warnings.append(f"Token消耗中等 ({estimated_tokens:,}个)，请注意控制成本")

        if file_stats.get("code", 0) == 0:
            warnings.append("未检测到代码文件，请检查仓库结构")

        return warnings

    async def estimate_repository_cost_from_path(self,
                                                 repo_path: str,
                                                 repo_url: str,
                                                 include_static_scan: bool = True,
                                                 ai_provider: str = "deepseek") -> Dict[str, Any]:
        """
        基于已克隆的仓库路径评估成本（不再次克隆）
        
        适用场景：
        - 用户启动分析时先克隆仓库
        - 基于克隆内容准确评估成本
        - 用户确认后再继续分析
        
        Args:
            repo_path: 已克隆的仓库路径
            repo_url: 仓库URL
            include_static_scan: 是否包含静态扫描
            ai_provider: AI服务提供商
            
        Returns:
            成本估算结果
        """
        try:
            logger.info(f"基于已克隆路径评估成本: {repo_path}")

            # 验证路径存在
            if not repo_path or not os.path.exists(repo_path):
                raise ValueError(f"仓库路径不存在: {repo_path}")

            # 1. 分析本地文件结构
            file_stats = self._analyze_repository_structure(repo_path)

            # 2. 计算仓库大小
            repo_size_mb = self._calculate_repository_size(repo_path)

            # 3. 提取仓库名称
            repo_name = self._extract_repo_name_from_url(repo_url)

            # 4. 应用黑名单过滤
            filtered_stats = self._apply_blacklist_filter(file_stats)

            # 5. 获取过滤文件详细信息
            filtered_files_details = self._get_filtered_files_details(repo_path)

            # 6. 估算Token消耗
            if ai_provider == "costrict":
                logger.info("CoStrict 模式：不使用 AI API，成本为 0")
                token_estimate = {
                    "total_estimated_tokens": 0,
                    "estimated_cost": {"cost_usd": 0.0, "cost_rmb": 0.0},
                    "analysis_overhead": 0
                }
            else:
                token_estimate = self.token_estimator.estimate_total_tokens(
                    repo_size_mb=repo_size_mb,
                    file_stats=filtered_stats,
                    provider=ai_provider
                )

            # 7. 添加静态扫描的额外开销
            if include_static_scan and ai_provider != "costrict":
                static_scan_overhead = self._estimate_static_scan_overhead(filtered_stats, repo_size_mb)
                token_estimate["total_estimated_tokens"] += static_scan_overhead
                token_estimate["analysis_overhead"] += static_scan_overhead
                token_estimate["estimated_cost"] = self.token_estimator._estimate_cost(
                    token_estimate["total_estimated_tokens"], ai_provider
                )

            # 8. 估算分析时间
            analysis_time_str = self._estimate_analysis_time(repo_size_mb, filtered_stats, include_static_scan)

            # 9. 创建结果
            estimate_result = {
                "success": True,
                "repository_url": repo_url,
                "repository_name": repo_name,
                "repository_size_mb": round(repo_size_mb, 2),
                "file_statistics": filtered_stats,
                "blacklisted_files": self._get_blacklisted_count(file_stats),
                "filtered_files_details": filtered_files_details,
                "filtered_files": filtered_files_details,
                "token_estimate": token_estimate,
                "include_static_scan": include_static_scan,
                "ai_provider": ai_provider,
                "estimated_analysis_time": analysis_time_str,
                "recommended_analysis_mode": self._recommend_analysis_mode(repo_size_mb, filtered_stats),
                "warnings": self._generate_warnings(repo_size_mb, filtered_stats, token_estimate),
                "generated_at": datetime.now().isoformat(),
                "estimated_tokens": token_estimate.get("total_estimated_tokens", 0),
                "estimated_cost_rmb": token_estimate.get("estimated_cost", {}).get("cost_rmb", 0.0),
                "estimated_cost_usd": token_estimate.get("estimated_cost", {}).get("cost_usd", 0.0),
                "estimated_time_minutes": self._parse_analysis_time_to_minutes(analysis_time_str),
                "file_count": filtered_stats.get("total_files", 0),
                "total_lines": filtered_stats.get("code_lines", 0),
                "skipped_files_count": self._get_blacklisted_count(file_stats)
            }

            logger.info(f"成本估算完成: tokens={estimate_result.get('estimated_tokens', 0)}, "
                        f"cost={estimate_result.get('estimated_cost_rmb', 0):.4f} RMB")

            return estimate_result

        except Exception as e:
            logger.error(f"基于路径成本估算失败: {e}", exc_info=True)
            return self._create_error_estimate(f"成本估算失败: {str(e)}")

    def _create_error_estimate(self, error_message: str) -> Dict[str, Any]:
        """创建错误估算结果"""
        return {
            "success": False,
            "error": error_message,
            "token_estimate": {
                "total_estimated_tokens": 0,
                "estimated_cost": {
                    "cost_usd": 0,
                    "cost_rmb": 0
                }
            },
            "estimated_tokens": 0,
            "estimated_cost_rmb": 0.0,
            "estimated_cost_usd": 0.0,
            "estimated_time_minutes": 0.0,
            "generated_at": datetime.now().isoformat()
        }
