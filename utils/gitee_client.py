import os
import aiohttp
import asyncio
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class GiteeClient:
    """
    稳定的 Gitee API 客户端（async）。
    - 所有请求通过 _make_request 统一构建 params（不会包含 None）
    - 支持按调用覆盖 token（方法参数 gitee_token）
    - 提供以下方法：
        - parse_repo_url(repo_url) -> (owner, repo)
        - get_repository_info(owner, repo / repo_url, token)
        - get_gitee_metrics(owner, repo, token)
        - get_community_metrics(owner, repo, token)
        - get_issue_metrics(owner, repo, token)
        - get_raw_file_content(owner, repo, file_path, ref, token)
        - get_file_tree(owner, repo, ref, token)
    """

    def __init__(self, token: Optional[str] = None, timeout: int = 30, max_retries: int = 3):
        self.token = token or os.getenv("GITEE_TOKEN")
        self.timeout = timeout
        self.max_retries = max_retries
        self.base_url = "https://gitee.com/api/v5"
        self._session: Optional[aiohttp.ClientSession] = None
        logger.debug(f"GiteeClient initialized (token present: {'Yes' if self.token else 'No'})")

    def _mask_token(self, token: Optional[str]) -> str:
        if not token:
            return "NoToken"
        return token[:4] + "..." + token[-4:]

    async def _ensure_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

    def parse_repo_url(self, repo_url: str) -> tuple[str, str]:
        """
        从各种形式的 repo_url 提取 owner 和 repo。
        支持:
          - https://gitee.com/owner/repo(.git)
          - git@gitee.com:owner/repo.git
          - owner/repo
        """
        url = repo_url.strip()
        # git@...:owner/repo.git
        if url.startswith("git@"):
            try:
                path = url.split(":", 1)[1]
            except Exception:
                path = url
        elif "gitee.com" in url:
            # https://gitee.com/owner/repo(.git)
            path = url.split("gitee.com", 1)[1].lstrip("/").split("?", 1)[0]
        else:
            path = url

        path = path.rstrip("/").rstrip(".git")
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 2:
            owner = parts[0]
            repo = parts[1]
        else:
            raise ValueError(f"无法解析仓库路径: {repo_url}")
        return owner, repo

    async def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None,
                            gitee_token: Optional[str] = None, method: str = "GET",
                            stream: bool = False) -> Optional[Any]:
        """
        统一请求函数。
        - endpoint: 不带 base_url 的路径，比如 "repos/owner/repo"
        - params: dict 查询参数（None 值会被过滤）
        - gitee_token: 如提供则覆盖实例 token（不会在日志中打印完整 token）
        - method: GET/POST 等
        - stream: 如果为 True，返回原始 response（用于下载 raw 内容）
        """
        await self._ensure_session()
        token_to_use = gitee_token or self.token
        final_params = {}

        if params:
            # 过滤 None 值
            final_params.update({k: v for k, v in params.items() if v is not None})

        if token_to_use:
            final_params["access_token"] = token_to_use

        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        masked = self._mask_token(token_to_use)
        logger.debug(f"GiteeRequest: {method} {url} params={{{', '.join(final_params.keys())}}} token_present={masked}")

        backoff = 1
        for attempt in range(1, self.max_retries + 1):
            try:
                async with self._session.request(method, url, params=final_params, timeout=aiohttp.ClientTimeout(total=self.timeout)) as resp:
                    status = resp.status
                    if status == 200:
                        if stream:
                            return resp
                        # 常规JSON响应
                        try:
                            return await resp.json()
                        except Exception:
                            text = await resp.text()
                            logger.debug(f"非 JSON 响应: {text[:500]}")
                            return None
                    elif status == 204:
                        # no content
                        return None
                    elif status in (401, 403):
                        # 无权限或 token 错误 / 速率限制 或 组织访问受限
                        # 如果有 Retry-After -> sleep
                        retry_after = resp.headers.get("Retry-After")
                        if retry_after:
                            try:
                                wait = int(retry_after)
                                logger.warning(f"Gitee rate-limited, Retry-After={wait}s")
                                await asyncio.sleep(wait)
                                continue
                            except Exception:
                                pass
                        # 对 401/403 不继续盲目重试（可能是权限问题）
                        logger.error(f"Gitee API {status} for {url} (token_present={masked})")
                        return None
                    elif status in (500, 502, 503, 504):
                        # 服务端错误，重试
                        logger.warning(f"Gitee server error {status} on {url}, attempt {attempt}/{self.max_retries}")
                    else:
                        # 其他错误：记录并返回 None
                        logger.warning(f"Gitee unexpected status {status} for {url}")
                        try:
                            body = await resp.text()
                            logger.debug(f"Response body: {body[:500]}")
                        except Exception:
                            pass
                        return None
            except asyncio.TimeoutError:
                logger.warning(f"Gitee request timeout: {url} (attempt {attempt})")
            except aiohttp.ClientError as e:
                logger.warning(f"Gitee network error: {e} (attempt {attempt})")
            # 指数退避
            await asyncio.sleep(backoff)
            backoff *= 2
        logger.error(f"Gitee request failed after {self.max_retries} attempts: {url}")
        return None


    # API helper methods
    async def get_repository_info(self, owner_or_repo: str, repo: Optional[str] = None,
                                  gitee_token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        接口灵活：
          - 如果传入 owner 和 repo（两个参数），则 owner_or_repo=owner, repo=repo
          - 如果只传入 owner_or_repo（例如 "owner/repo" 或完整 url），会智能解析
        返回标准化的仓库信息字典或 None。
        """
        # 允许传入 repo_url 或 owner + repo 两种形式
        if repo is None:
            # owner_or_repo 可能是 url 或 "owner/repo"
            owner, repo_name = self.parse_repo_url(owner_or_repo)
        else:
            owner = owner_or_repo
            repo_name = repo

        data = await self._make_request(f"repos/{owner}/{repo_name}", gitee_token=gitee_token)
        if not data:
            return None

        # 标准化字段（与 GitHub 类似）
        normalized = dict(data)  # shallow copy
        normalized["stars"] = data.get("stargazers_count", data.get("watchers_count", 0))
        normalized["open_issues"] = data.get("open_issues_count", 0)
        normalized["forks"] = data.get("forks_count", 0)
        normalized["full_name"] = data.get("full_name", f"{owner}/{repo_name}")
        normalized["html_url"] = data.get("html_url", f"https://gitee.com/{owner}/{repo_name}")
        normalized["clone_url"] = data.get("clone_url") or normalized["html_url"] + ".git"
        return normalized

    async def get_gitee_metrics(self, owner: str, repo: str, gitee_token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        获取 Gitee 指数并映射为更友好的字段
        """
        data = await self._make_request(f"repos/{owner}/{repo}/git/gitee_metrics", gitee_token=gitee_token)
        if not data:
            return None

        # 原始字段直接保留，另外做映射
        mapped = {
            "activity_score": data.get("vitality"),
            "activity_percent": data.get("vitality_percent"),
            "community_score": data.get("community"),
            "community_percent": data.get("community_percent"),
            "stability_score": data.get("health"),
            "stability_percent": data.get("health_percent"),
            "trend_score": data.get("trend"),
            "trend_percent": data.get("trend_percent"),
            "popularity_score": data.get("influence"),
            "popularity_percent": data.get("influence_percent"),
            "total_score": data.get("total_score"),
            "created_at": data.get("created_at"),
            "raw": data
        }
        return mapped

    async def get_community_metrics(self, owner: str, repo: str, gitee_token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        使用 contributors API 统计贡献者/活跃信息。
        注意: contributors 可能是分页，这里只抓取第一页（常见场景已足够）。
        """
        contributors = await self._make_request(f"repos/{owner}/{repo}/contributors", gitee_token=gitee_token)
        if contributors is None:
            return None

        # contributors 元素在 Gitee 上通常包含 name/login 和 commits 字段
        contributors_list = contributors if isinstance(contributors, list) else []
        top = []
        for c in contributors_list[:10]:
            top.append({
                "login": c.get("name") or c.get("login"),
                "commits": c.get("commits", 0),
                "url": c.get("url")
            })
        return {
            "contributors_count": len(contributors_list),
            "top_contributors": top
        }

    async def get_issue_metrics(self, owner: str, repo: str, gitee_token: Optional[str] = None) -> Optional[Dict[str, int]]:
        """
        统计 open / closed issues 数量（不分页统计全部，只统计第一页的数量，若需要可改为分页）
        """
        open_issues = await self._make_request(f"repos/{owner}/{repo}/issues", params={"state": "open"}, gitee_token=gitee_token)
        closed_issues = await self._make_request(f"repos/{owner}/{repo}/issues", params={"state": "closed"}, gitee_token=gitee_token)

        # 计算平均响应时间（简化版）
        avg_response_time = 0.0  # 默认值
        
        # 如果需要计算平均响应时间，可以从closed_issues中提取数据
        # 但由于API限制，我们暂时使用默认值

        return {
            "open_count": len(open_issues or []),
            "closed_count": len(closed_issues or []),
            "avg_response_time_hours": avg_response_time
        }

    async def get_raw_file_content(self, owner: str, repo: str, file_path: str, ref: Optional[str] = None,
                                   gitee_token: Optional[str] = None) -> Optional[str]:
        """
        获取 raw 文件内容（文本），注意文件较大时返回 None
        """
        params = {}
        if ref:
            params["ref"] = ref

        resp = await self._make_request(f"repos/{owner}/{repo}/raw/{file_path}", params=params, gitee_token=gitee_token, stream=True)
        if resp is None:
            return None

        # resp is aiohttp.ClientResponse
        try:
            # 检查 Content-Length
            content_length = resp.headers.get("Content-Length")
            if content_length and int(content_length) > 100 * 1024 * 1024:
                logger.warning(f"文件过大({content_length} bytes)，跳过: {file_path}")
                await resp.release()
                return None
            text = await resp.text()
            await resp.release()
            return text
        except Exception as e:
            logger.warning(f"读取 raw 内容出错: {e}")
            try:
                await resp.release()
            except Exception:
                pass
            return None

    async def get_file_tree(self, owner: str, repo: str, ref: Optional[str] = None, gitee_token: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        params = {}
        if ref:
            params["ref"] = ref
        else:
            # 尝试获取 default_branch
            repo_info = await self.get_repository_info(owner, repo, gitee_token=gitee_token)
            if repo_info and repo_info.get("default_branch"):
                params["ref"] = repo_info["default_branch"]

        tree = await self._make_request(f"repos/{owner}/{repo}/git/trees", params=params, gitee_token=gitee_token)
        if not tree or "tree" not in tree:
            return None
        return tree.get("tree", [])

    #  新增Gitee API方法 
    
    async def get_subscribers(self, owner: str, repo: str, page: int = 1, per_page: int = 30,
                             gitee_token: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """
        获取仓库订阅者列表
        API: GET /repos/{owner}/{repo}/subscribers
        """
        params = {"page": page, "per_page": per_page}
        return await self._make_request(f"repos/{owner}/{repo}/subscribers", params=params, gitee_token=gitee_token)

    async def get_branches(self, owner: str, repo: str, page: int = 1, per_page: int = 30,
                          gitee_token: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """
        获取仓库分支列表
        API: GET /repos/{owner}/{repo}/branches
        """
        params = {"page": page, "per_page": per_page}
        return await self._make_request(f"repos/{owner}/{repo}/branches", params=params, gitee_token=gitee_token)

    async def get_commits(self, owner: str, repo: str, page: int = 1, per_page: int = 30,
                         sha: Optional[str] = None, since: Optional[str] = None, until: Optional[str] = None,
                         gitee_token: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """
        获取提交历史
        API: GET /repos/{owner}/{repo}/commits
        """
        params = {"page": page, "per_page": per_page}
        if sha:
            params["sha"] = sha
        if since:
            params["since"] = since
        if until:
            params["until"] = until
        return await self._make_request(f"repos/{owner}/{repo}/commits", params=params, gitee_token=gitee_token)

    async def get_pull_requests(self, owner: str, repo: str, state: str = "open", page: int = 1, per_page: int = 30,
                               gitee_token: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """
        获取Pull Request列表
        API: GET /repos/{owner}/{repo}/pulls
        state: open, closed, all
        """
        params = {"state": state, "page": page, "per_page": per_page}
        return await self._make_request(f"repos/{owner}/{repo}/pulls", params=params, gitee_token=gitee_token)

    async def get_releases(self, owner: str, repo: str, page: int = 1, per_page: int = 30,
                          gitee_token: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """
        获取发布版本列表
        API: GET /repos/{owner}/{repo}/releases
        """
        params = {"page": page, "per_page": per_page}
        return await self._make_request(f"repos/{owner}/{repo}/releases", params=params, gitee_token=gitee_token)

    async def get_languages(self, owner: str, repo: str, gitee_token: Optional[str] = None) -> Optional[Dict[str, int]]:
        """
        获取仓库语言统计
        API: GET /repos/{owner}/{repo}/languages
        返回: {"Python": 12345, "JavaScript": 6789, ...}
        """
        return await self._make_request(f"repos/{owner}/{repo}/languages", gitee_token=gitee_token)

    async def get_stargazers(self, owner: str, repo: str, page: int = 1, per_page: int = 30,
                           gitee_token: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """
        获取Star用户列表
        API: GET /repos/{owner}/{repo}/stargazers
        """
        params = {"page": page, "per_page": per_page}
        return await self._make_request(f"repos/{owner}/{repo}/stargazers", params=params, gitee_token=gitee_token)

    async def get_forks(self, owner: str, repo: str, page: int = 1, per_page: int = 30,
                       gitee_token: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """
        获取Fork仓库列表
        API: GET /repos/{owner}/{repo}/forks
        """
        params = {"page": page, "per_page": per_page}
        return await self._make_request(f"repos/{owner}/{repo}/forks", params=params, gitee_token=gitee_token)

    async def get_issues_list(self, owner: str, repo: str, state: str = "open", sort: str = "created",
                            direction: str = "desc", page: int = 1, per_page: int = 30,
                            gitee_token: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """
        获取Issues列表（增强版，支持更多参数）
        API: GET /repos/{owner}/{repo}/issues
        state: open, closed, all
        sort: created, updated, comments
        direction: asc, desc
        """
        params = {"state": state, "sort": sort, "direction": direction, "page": page, "per_page": per_page}
        return await self._make_request(f"repos/{owner}/{repo}/issues", params=params, gitee_token=gitee_token)

    async def get_commit_stats(self, owner: str, repo: str, sha: str,
                              gitee_token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        获取单个提交的详细统计信息
        API: GET /repos/{owner}/{repo}/commits/{sha}
        """
        return await self._make_request(f"repos/{owner}/{repo}/commits/{sha}", gitee_token=gitee_token)

    async def get_readme(self, owner: str, repo: str, ref: Optional[str] = None,
                        gitee_token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        获取README文件内容
        API: GET /repos/{owner}/{repo}/readme
        """
        params = {}
        if ref:
            params["ref"] = ref
        return await self._make_request(f"repos/{owner}/{repo}/readme", params=params, gitee_token=gitee_token)

    async def get_tags(self, owner: str, repo: str, page: int = 1, per_page: int = 30,
                      gitee_token: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """
        获取仓库标签列表
        API: GET /repos/{owner}/{repo}/tags
        """
        params = {"page": page, "per_page": per_page}
        return await self._make_request(f"repos/{owner}/{repo}/tags", params=params, gitee_token=gitee_token)

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
