"""
Gitee 服务模块。

提供 Gitee 仓库数据聚合、克隆、结构分析等功能，
用于支持代码健康扫描系统的 Gitee 平台集成。
"""

import logging
import os
import asyncio
from typing import Dict, Any, Optional
from urllib.parse import quote

from utils.gitee_client import GiteeClient
from utils.git_utils import GitUtils

logger = logging.getLogger(__name__)


class GiteeService:
    """
    封装高层 Gitee 仓库数据聚合逻辑，返回 AnalysisService 需要的标准结构。
    - 会使用 GiteeClient 提供的数据
    - 支持提供 repo_path（无需重复克隆）
    - 克隆时会在 https clone_url 中注入 token（如果提供并且为 https）
    """

    def __init__(self, token: Optional[str] = None):
        # token 可选：如果初始化时提供会作为默认 token
        self.gitee_client = GiteeClient(token=token)
        try:
            self.git_utils = GitUtils()
        except RuntimeError as e:
            logger.error(f"初始化GitUtils失败: {e}")
            self.git_utils = None
            raise

    async def get_repository_info(self, repo_url: str, token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """获取仓库基本信息"""
        return await self.gitee_client.get_repository_info(repo_url, gitee_token=token)

    async def _inject_token_into_clone_url(self, clone_url: str, gitee_token: Optional[str]) -> str:
        """
        如果 clone_url 是 https 并且提供了 token，则把 token 注入到 URL 中:
          https://gitee.com/owner/repo.git -> https://<token>@gitee.com/owner/repo.git
        使用 quote 对 token 做 URL-safe 编码。
        """
        if not gitee_token or not clone_url.startswith("https://"):
            return clone_url
        safe_token = quote(gitee_token, safe="")
        return clone_url.replace("https://", f"https://{safe_token}@", 1)

    def _enhance_repo_structure(self, repo_structure: dict, repo_path: str) -> dict:
        """
        对 repo_structure 增强：
        - 统计语言占比
        - 标记可能的入口文件
        - 自动识别项目框架/类型
        - 检测 CI/CD 配置文件
        """
        import os
        from collections import Counter

        lang_counter = Counter()
        for file_info in repo_structure.get("files", []):
            ext = os.path.splitext(file_info["path"])[1].lower()
            if ext:
                lang_counter[ext] += 1
        repo_structure["language_distribution"] = dict(lang_counter)

        entry_candidates = ["main.py", "app.py", "index.js", "index.html", "manage.py", "wsgi.py"]
        for file_info in repo_structure.get("files", []):
            file_info["is_entry"] = os.path.basename(file_info["path"]) in entry_candidates

        framework_hint = set()
        file_paths = [f["path"].lower() for f in repo_structure.get("files", [])]

        if "package.json" in file_paths:
            if any(p.endswith(".vue") for p in file_paths):
                framework_hint.add("Vue")
            elif any(p.endswith(".tsx") or p.endswith(".jsx") for p in file_paths):
                framework_hint.add("React")
            elif any("angular.json" in p for p in file_paths):
                framework_hint.add("Angular")
            else:
                framework_hint.add("Frontend")
        elif any(p.endswith(".html") for p in file_paths) and any(p.endswith(".js") for p in file_paths):
            framework_hint.add("Frontend")

        if "manage.py" in file_paths:
            framework_hint.add("Django")
        if "app.py" in file_paths or "wsgi.py" in file_paths:
            framework_hint.add("Flask/FastAPI")
        if "requirements.txt" in file_paths and any(p.endswith(".py") for p in file_paths):
            framework_hint.add("Python")
        if "pom.xml" in file_paths:
            framework_hint.add("Java-Maven")
        if "build.gradle" in file_paths:
            framework_hint.add("Java-Gradle")
        if "cargo.toml" in file_paths:
            framework_hint.add("Rust")
        if "go.mod" in file_paths:
            framework_hint.add("Go")

        repo_structure["framework_hint"] = list(framework_hint)

        # 检测 CI/CD 配置文件
        ci_cd_files = [
            '.gitlab-ci.yml',
            '.travis.yml',
            'circle.yml',
            'circle.config.yml',
            'Jenkinsfile',
            'azure-pipelines.yml',
            '.drone.yml',
            'bitbucket-pipelines.yml',
            'cloudbuild.yaml',
            'buildspec.yml',
            'appveyor.yml',
        ]
        has_ci_cd = False
        for file_path in file_paths:
            for ci_file in ci_cd_files:
                if ci_file in file_path:
                    has_ci_cd = True
                    break
            if has_ci_cd:
                break
        # 检查 .github/workflows 目录
        github_workflows_path = os.path.join(repo_path, '.github', 'workflows')
        if os.path.exists(github_workflows_path):
            has_ci_cd = True
        repo_structure["has_ci_cd"] = has_ci_cd

        return repo_structure

    async def _analyze_repo_structure(self, temp_dir: str) -> dict:
        """
        分析仓库结构并增强信息
        
        Args:
            temp_dir: 仓库本地路径
            
        Returns:
            增强后的仓库结构信息
        """
        repo_structure = {}
        if temp_dir:
            try:
                repo_structure = self.git_utils.analyze_repo_structure(temp_dir)
                repo_structure = self._enhance_repo_structure(repo_structure, temp_dir)
            except Exception as e:
                logger.warning(f"分析仓库结构时出错: {e}")
        return repo_structure

    async def _handle_repo_cloning(self, repo_info: dict, repo_path: Optional[str], token_to_use: Optional[str]) -> tuple:
        """
        处理仓库克隆逻辑
        
        Args:
            repo_info: 仓库信息
            repo_path: 本地仓库路径（如果有）
            token_to_use: 使用的token
            
        Returns:
            (temp_dir, used_local_path) 元组
        """
        if repo_path and isinstance(repo_path, str) and repo_path:
            temp_dir = repo_path
            used_local_path = True
            logger.info(f"使用外部提供的本地路径: {repo_path}")
        else:
            clone_url = repo_info.get("clone_url") or repo_info.get("html_url") + ".git"
            clone_url = await self._inject_token_into_clone_url(clone_url, token_to_use)
            logger.info(f"准备克隆: {clone_url[:200]} (token_in_url={'Yes' if token_to_use else 'No'})")
            temp_dir = await self.git_utils.clone_repo(clone_url, token=token_to_use)
            used_local_path = False
        return temp_dir, used_local_path

    async def _cleanup_temp_dir_if_needed(self, temp_dir: str, used_local_path: bool):
        """
        如果需要，清理临时目录
        
        Args:
            temp_dir: 临时目录路径
            used_local_path: 是否使用了外部提供的路径
        """
        if temp_dir and not used_local_path:
            try:
                await self.git_utils.cleanup_temp_dir(temp_dir)
            except Exception as e:
                logger.warning(f"清理临时目录失败: {e}")

    async def get_comprehensive_repo_data(self, repo_url: str, repo_path: Optional[str] = None,
                                          gitee_token: Optional[str] = None) -> Dict[str, Any]:
        """
        获取全面的仓库数据并返回统一结构：
        {
            "repo_info": {...},
            "community_metrics": {...},
            "issue_metrics": {...},
            "gitee_metrics": {...},
            "repo_structure": {...},
            "access_mode": "full" or "limited",
            "platform": "gitee"
        }
        """
        logger.info(f"开始全面分析Gitee仓库: {repo_url}")

        # parse owner/repo
        try:
            owner, repo = self.gitee_client.parse_repo_url(repo_url)
        except Exception as e:
            logger.warning(f"解析仓库路径失败: {repo_url} -> {e}")
            owner, repo = None, None

        # 优先使用传入的 token 覆盖客户端 token
        token_to_use = gitee_token or self.gitee_client.token

        try:
            # 1 repo info
            repo_info = await self.gitee_client.get_repository_info(owner, repo, gitee_token=token_to_use)
            if not repo_info:
                raise Exception("无法获取仓库基本信息或无权限访问")

            # 2 community / issues / gitee metrics
            community_metrics = await self.gitee_client.get_community_metrics(owner, repo, gitee_token=token_to_use) or {}
            issue_metrics = await self.gitee_client.get_issue_metrics(owner, repo, gitee_token=token_to_use) or {}
            gitee_metrics = await self.gitee_client.get_gitee_metrics(owner, repo, gitee_token=token_to_use) or {}

            # 3 处理仓库克隆
            temp_dir, used_local_path = await self._handle_repo_cloning(repo_info, repo_path, token_to_use)

            # 4 分析仓库结构
            repo_structure = await self._analyze_repo_structure(temp_dir)

            # 5 清理临时目录
            await self._cleanup_temp_dir_if_needed(temp_dir, used_local_path)

            # 如果API返回的language为None或未知，使用从仓库结构分析得到的主语言
            if not repo_info.get("language") or repo_info["language"] is None:
                main_language = repo_structure.get("main_language")
                if main_language:
                    repo_info["language"] = main_language

            return {
                "repo_info": repo_info,
                "community_metrics": community_metrics,
                "issue_metrics": issue_metrics,
                "gitee_metrics": gitee_metrics,
                "repo_structure": repo_structure,
                "access_mode": "full",
                "platform": "gitee"
            }

        except Exception as e:
            logger.warning(f"Gitee仓库分析失败，进入降级模式: {repo_url}, 错误: {e}")

        # 降级模式（尽可能利用本地 repo_path）
        full_name = repo_url.strip("/").split("gitee.com/")[-1].replace(".git", "")
        if "/" not in full_name:
            full_name = full_name.split(":", 1)[-1]
        logger.info(f"已切换为Gitee【本地有限分析模式】: {full_name}")

        # 降级模式下的仓库处理
        if repo_path and isinstance(repo_path, str) and repo_path:
            temp_dir = repo_path
            used_local_path = True
            logger.info(f"使用已提供的仓库路径进行降级分析: {repo_path}")
        else:
            temp_dir = None
            used_local_path = False
            try:
                clone_url = repo_url
                if token_to_use and clone_url.startswith("https://"):
                    clone_url = await self._inject_token_into_clone_url(clone_url, token_to_use)
                temp_dir = await self.git_utils.clone_repo(clone_url, token=token_to_use)
            except Exception:
                temp_dir = None

        # 分析仓库结构
        repo_structure = await self._analyze_repo_structure(temp_dir)

        # 清理临时目录
        await self._cleanup_temp_dir_if_needed(temp_dir, used_local_path)

        # 获取主语言 - 使用从仓库结构分析得到的语言
        main_language = repo_structure.get("main_language", "未知")

        repo_info = {
            "full_name": full_name,
            "private": True,
            "description": "此Gitee仓库为私有或无权限访问（降级模式）",
            "language": main_language,
            "stars": 0,
            "forks": 0,
            "open_issues": 0,
            "pushed_at": None,
            "license": None,
            "platform": "gitee"
        }

        return {
            "repo_info": repo_info,
            "community_metrics": {"contributors_count": 0, "top_contributors": []},
            "issue_metrics": {"open_count": 0, "closed_count": 0},
            "gitee_metrics": {},
            "repo_structure": repo_structure,
            "access_mode": "limited",
            "platform": "gitee",
            "error_hint": "私有仓库或无权限访问（降级模式）"
        }