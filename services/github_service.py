import logging
from typing import Dict, Any, Optional, List
from utils.github_client import GitHubClient
from utils.git_utils import GitUtils
import os

logger = logging.getLogger(__name__)


class GitHubService:
    def __init__(self):
        self.github_client = GitHubClient()
        try:
            self.git_utils = GitUtils()
        except RuntimeError as e:
            logger.error(f"初始化GitUtils失败: {e}")
            self.git_utils = None
            raise

    async def get_repository_info(self, repo_url: str, token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """获取仓库基本信息"""
        return await self.github_client.get_repository_info(repo_url, token)

    async def get_comprehensive_repo_data(
            self, repo_url: str, repo_path: Optional[str] = None, github_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取仓库的全面数据（基础信息 + 社区指标 + issue指标 + 文件结构）
        并自动生成 LANGUAGES_FOUND 和 FILE_INFO 供静态分析使用
        """
        logger.info(f"开始全面分析仓库: {repo_url}")

        try:
            # 获取基础信息
            repo_info = await self.github_client.get_repository_info(repo_url, github_token)
            if not repo_info:
                raise ValueError(f"无法获取仓库信息: {repo_url}")

            # 获取社区指标
            if github_token and github_token != self.github_client.token:
                # 如果提供了不同的token，重新初始化客户端
                self.github_client._init_github_client(github_token)
            community_metrics = await self.github_client.get_community_metrics(repo_url)
            
            # 从社区指标中提取issue指标
            issue_metrics = {
                "open_count": community_metrics.get("open_issues_count", 0),
                "closed_count": community_metrics.get("closed_issues_count_30d", 0),
                "total_count": community_metrics.get("open_issues_count", 0) + community_metrics.get("closed_issues_count_30d", 0)
            }

            # 克隆并分析仓库
            result = await self._process_repository(repo_url, repo_info, repo_path, github_token, full_access=True)
            
            # 如果API返回的language为None或未知，使用从仓库结构分析得到的主语言
            repo_structure = result["repo_structure"]
            if not repo_info.get("language") or repo_info["language"] is None:
                main_language = repo_structure.get("main_language")
                if main_language:
                    repo_info["language"] = main_language

            return {
                "repo_info": repo_info,
                "community_metrics": community_metrics or {},
                "issue_metrics": issue_metrics or {},
                "repo_structure": result["repo_structure"],
                "languages_found": result["languages_found"],
                "file_info": result["file_info"],
                "access_mode": "full"
            }

        except Exception as e:
            logger.warning(f"仓库分析失败，进入降级模式: {repo_url}, 错误: {str(e)}")
            return await self._handle_degraded_mode(repo_url, repo_path, github_token)

    async def _process_repository(self, repo_url: str, repo_info: dict, repo_path: Optional[str],
                                  github_token: Optional[str], full_access: bool = False) -> Dict[str, Any]:
        """
        处理仓库克隆和分析的通用逻辑
        """
        # 克隆或使用已提供的 repo_path
        if repo_path and isinstance(repo_path, str) and len(repo_path) > 0:
            logger.info(f"使用已提供的仓库路径: {repo_path}")
            temp_dir = repo_path
            used_local_path = True
        else:
            clone_url = repo_info["clone_url"]
            if github_token and clone_url.startswith("https://"):
                clone_url = clone_url.replace("https://", f"https://{github_token}@")
            temp_dir = await self.git_utils.clone_repo(clone_url)
            used_local_path = False

        repo_structure = {}
        file_info_list = []
        languages_found = []

        if temp_dir:
            try:
                # 分析文件结构
                repo_structure = self.git_utils.analyze_repo_structure(temp_dir)
                repo_structure = self._enhance_repo_structure(repo_structure, temp_dir)

                # 自动生成 LANGUAGES_FOUND
                languages_found = list(repo_structure.get("language_distribution", {}).keys())

                # 自动生成 FILE_INFO
                file_info_list = await self._collect_file_info(repo_structure, temp_dir)

            finally:
                if not used_local_path:
                    await self.git_utils.cleanup_temp_dir(temp_dir)

        return {
            "repo_structure": repo_structure,
            "languages_found": languages_found,
            "file_info": file_info_list
        }

    async def _handle_degraded_mode(self, repo_url: str, repo_path: Optional[str],
                                    github_token: Optional[str]) -> Dict[str, Any]:
        """
        处理降级模式的通用逻辑
        当GitHub API失败时（token过期/无效），从本地克隆的仓库提取真实信息
        """
        full_name = repo_url.strip("/").split("github.com/")[-1].replace(".git", "")
        if "/" not in full_name:
            full_name = full_name.split(":",1)[-1]
        logger.info(f"已切换为本地有限分析模式: {full_name}")

        # 尝试使用现有路径或克隆仓库
        result = await self._process_repository(repo_url, {}, repo_path, github_token, full_access=False)

        # 从本地仓库提取真实信息
        repo_structure = result.get("repo_structure", {})
        languages_found = result.get("languages_found", [])
        file_info = result.get("file_info", [])

        # 获取主语言 - 优先使用仓库结构分析得到的语言，然后是languages_found列表第一个，最后是'未知'
        main_language = repo_structure.get("main_language")
        if not main_language:
            main_language = languages_found[0] if languages_found else "未知"

        # 计算文件总数和代码行数
        total_files = len(file_info)
        total_lines = sum(f.get("lines", 0) for f in file_info)

        # 尝试从Git获取默认分支
        default_branch = "main"
        if repo_path and isinstance(repo_path, str):
            try:
                default_branch = self.git_utils.get_default_branch(repo_path) or "main"
            except Exception:
                pass

        # 构建仓库作者信息
        author = full_name.split("/")[0] if "/" in full_name else "未知"

        # 使用更准确的描述
        description = f"{full_name} 项目（本地分析模式，GitHub API访问失败）"
        if main_language != "未知":
            description += f"\n主要编程语言：{main_language}"
        if total_files > 0:
            description += f"\n分析文件数：{total_files}"

        return {
            "repo_info": {
                "full_name": full_name,
                "private": False,  # API失败不代表仓库是私有的
                "description": description,
                "language": main_language,
                "stars": "N/A",  # GitHub API失败，无法获取
                "forks": "N/A",
                "open_issues": "N/A",
                "pushed_at": "未知",
                "default_branch": default_branch,
                "watchers": "N/A",
                "latest_release": "无发布信息",
                "license": "未指定",
                "topics": [],
                "created_at": "未知",
                "updated_at": "未知",
                "contributors": total_files,
            },
            "community_metrics": {
                "contributors_count": total_files,
                "recent_commits": 0
            },
            "issue_metrics": {"open_count": 0, "closed_count": 0},
            "repo_structure": repo_structure,
            "languages_found": languages_found,
            "file_info": file_info,
            "access_mode": "limited",
            "error_hint": "GitHub API访问失败（token可能过期），已切换到本地分析模式"
        }

    async def get_file_content(self, owner: str, repo: str, file_path: str, ref: Optional[str] = None) -> Optional[str]:
        return await self.github_client.get_raw_file_content(owner, repo, file_path, ref)

    async def get_repo_tree(self, owner: str, repo: str, ref: Optional[str] = None) -> Optional[list]:
        return await self.github_client.get_file_tree(owner, repo, ref)

    async def _collect_file_info(self, repo_structure: dict, repo_path: str, max_lines: int = 1000) -> List[dict]:
        """
        生成静态分析所需的 FILE_INFO 列表
        """
        file_info_list = []
        for f in repo_structure.get("files", []):
            file_path = os.path.join(repo_path, f["path"])
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as file:
                    lines = []
                    for i, line in enumerate(file):
                        lines.append(line)
                        if i +1 >= max_lines:
                            break
                file_info_list.append({
                    "path": f["path"],
                    "type": os.path.splitext(f["path"])[1].lower(),
                    "content": "".join(lines),
                    "lines": len(lines)
                })
            except Exception as e:
                logger.warning(f"无法读取文件内容 {file_path}: {str(e)}")
        return file_info_list

    def _enhance_repo_structure(self, repo_structure: dict, repo_path: str) -> dict:
        """
        对 repo_structure 增强：
        - 统计语言占比
        - 标记可能的入口文件
        - 自动识别项目框架/类型
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
        import os
        github_workflows_path = os.path.join(repo_path, '.github', 'workflows')
        if os.path.exists(github_workflows_path):
            has_ci_cd = True
        repo_structure["has_ci_cd"] = has_ci_cd

        return repo_structure
