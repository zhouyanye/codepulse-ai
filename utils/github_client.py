import os
import re
import ssl
import aiohttp
import asyncio
import warnings
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime, timedelta

from github import Github, GithubException
from github.Repository import Repository
import requests
from urllib3.exceptions import InsecureRequestWarning

logger = logging.getLogger(__name__)


class GitHubClient:
    def __init__(self, token: Optional[str] = None, timeout: int = 60, max_retries: int = 3, verify_ssl: bool = True):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.timeout = timeout
        self.max_retries = max_retries
        self.base_url = "https://api.github.com"
        self.verify_ssl = verify_ssl
        self._connector = None
        self.session = None  # 延迟初始化

        if not self.verify_ssl:
            warnings.filterwarnings('ignore', category=UserWarning, module='aiohttp.connector')
            warnings.filterwarnings('ignore', category=InsecureRequestWarning)
            
            # 子进程补丁：强制所有requests请求禁用SSL验证
            original_request = requests.Session.request
            def patched_request(self, method, url, **kwargs):
                kwargs['verify'] = False
                return original_request(self, method, url, **kwargs)
            requests.Session.request = patched_request

        self._init_github_client(self.token)
    
    async def _ensure_session(self):
        """确保 session 已初始化"""
        if self.session is None or self.session.closed:
            self._connector = aiohttp.TCPConnector(limit=10, limit_per_host=5, ssl=self.verify_ssl)
            self.session = aiohttp.ClientSession(connector=self._connector)
            logger.debug("GitHubClient aiohttp session 已初始化")
    
    def _init_github_client(self, token: Optional[str]):
        self.token = token
        try:
            if token:
                self.github = Github(
                    login_or_token=token,
                    timeout=self.timeout,
                    retry=self.max_retries,
                    pool_size=10,
                )
            else:
                logger.warning("未提供 GitHub Token，将以匿名模式访问")
                self.github = Github(
                    timeout=self.timeout,
                    retry=self.max_retries,
                    pool_size=10,
                )
        except Exception as e:
            logger.error(f"初始化 PyGithub 客户端失败: {e}")
            self.github = None

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("aiohttp.ClientSession 已关闭")
            self.session = None
        if self._connector and not self._connector.closed:
            await self._connector.close()
            logger.info("TCPConnector 已关闭")
            self._connector = None

    def parse_repo_url(self, repo_url: str) -> tuple[str, str]:
        repo_url = repo_url.strip().rstrip('/')
        if repo_url.endswith('.git'):
            repo_url = repo_url[:-4]
            
        match = re.search(r'github\.com[/:]([^/]+)/([^/]+)', repo_url)
        if match:
            return match.group(1), match.group(2)
            
        parts = repo_url.split('/')
        if len(parts) >= 2:
            return parts[-2], parts[-1]
            
        raise ValueError(f"无法解析仓库 URL: {repo_url}")

    async def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        await self._ensure_session()  # 确保 session 已初始化
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = {
            'User-Agent': 'GitHubClient-Python/1.0',
            'Accept': 'application/vnd.github.v3+json'
        }
        if self.token:
            headers['Authorization'] = f'token {self.token}'
            
        for attempt in range(self.max_retries):
            try:
                async with self.session.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    elif resp.status in (401, 403, 404):
                        logger.warning(f"请求失败，状态码: {resp.status} for URL: {url}")
                        return None
                    else:
                        logger.warning(f"请求失败，状态码: {resp.status}。正在重试... (尝试 {attempt + 1}/{self.max_retries})")
                        if attempt < self.max_retries - 1:
                            await asyncio.sleep(1.5 ** attempt)
            except Exception as e:
                logger.warning(f"请求异常: {e}。正在重试... (尝试 {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1.5 ** attempt)
                    
        logger.error(f"请求失败，已达到最大重试次数 ({self.max_retries}) for URL: {url}")
        return None

    def _apply_proxy_to_raw_url(self, raw_url: str) -> str:
        proxy_domain = "githubproxy.cc"
        if "raw.githubusercontent.com" in raw_url:
            return raw_url.replace("https://raw.githubusercontent.com/", f"https://{proxy_domain}/raw.githubusercontent.com/")
        return raw_url

    async def get_raw_file_content(self, owner: str, repo: str, file_path: str, ref: Optional[str] = None) -> Optional[str]:
        await self._ensure_session()  # 确保 session 已初始化
        if ref is None:
            repo_info = await self.get_repository_info(f"{owner}/{repo}")
            ref = repo_info.get("default_branch", "main") if repo_info else "main"
            
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{file_path.lstrip('/')}"
        
        if not self.verify_ssl:
            raw_url = self._apply_proxy_to_raw_url(raw_url)
            
        logger.info(f"正在从 {raw_url} 获取文件内容...")
        
        headers = {'User-Agent': 'GitHubClient-Python/1.0'}
        for attempt in range(self.max_retries):
            try:
                async with self.session.get(
                    raw_url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as resp:
                    if resp.status == 200:
                        content_length = resp.headers.get('Content-Length')
                        if content_length and int(content_length) > 10 * 1024 * 1024:
                            logger.error(f"文件过大，超过 10MB: {file_path}")
                            return None
                        return await resp.text()
                    elif resp.status == 404:
                        logger.warning(f"文件未找到: {file_path} 在分支 {ref}")
                        return None
                    else:
                        logger.warning(f"获取文件失败，状态码: {resp.status}。正在重试...")
                        if attempt < self.max_retries - 1:
                            await asyncio.sleep(1.5 ** attempt)
            except Exception as e:
                logger.warning(f"获取文件异常: {e}。正在重试...")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1.5 ** attempt)
                    
        return None

    async def get_file_tree(self, owner: str, repo: str, ref: Optional[str] = None) -> Optional[List[Dict]]:
        if ref is None:
            repo_info = await self.get_repository_info(f"{owner}/{repo}")
            ref = repo_info.get("default_branch", "main") if repo_info else "main"
            
        endpoint = f"repos/{owner}/{repo}/git/trees/{ref}"
        params = {"recursive": "1"}
        data = await self._make_request(endpoint, params)
        
        if not data or 'tree' not in data:
            return None
        return [{"path": t["path"], "type": t["type"], "size": t.get("size", 0)} for t in data["tree"]]

    async def get_repository_info(self, repo_url: str, github_token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if github_token and github_token != self.token:
            self._init_github_client(github_token)
            
        if not self.github:
            logger.error("PyGithub 客户端未初始化，无法获取仓库信息")
            return None
        
        try:
            owner, repo_name = self.parse_repo_url(repo_url)
            full_name = f"{owner}/{repo_name}"
            
            repo: Repository = await asyncio.get_event_loop().run_in_executor(
                None, self.github.get_repo, full_name
            )
            
            topics = await asyncio.get_event_loop().run_in_executor(None, repo.get_topics)
            
            return {
                "owner": owner, "name": repo_name, "full_name": full_name,
                "description": repo.description, "language": repo.language,
                "stars": repo.stargazers_count, "forks": repo.forks_count,
                "open_issues": repo.open_issues_count, "created_at": repo.created_at.isoformat(),
                "updated_at": repo.updated_at.isoformat(), "pushed_at": repo.pushed_at.isoformat() if repo.pushed_at else None,
                "license": repo.get_license().license.name if repo.get_license() else None,
                "topics": topics, "size": repo.size, "default_branch": repo.default_branch,
                "archived": repo.archived, "html_url": repo.html_url, "clone_url": repo.clone_url,
            }
        except Exception as e:
            logger.error(f"获取仓库信息失败 {repo_url}: {e}", exc_info=True)
            return None

    async def get_community_metrics(self, repo_url: str) -> Dict[str, Any]:
        if not self.github:
            logger.error("PyGithub 客户端未初始化，无法获取社区指标")
            return {}
        
        try:
            owner, repo_name = self.parse_repo_url(repo_url)
            full_name = f"{owner}/{repo_name}"
            
            repo: Repository = await asyncio.get_event_loop().run_in_executor(None, self.github.get_repo, full_name)
            
            contributors_future = asyncio.get_event_loop().run_in_executor(None, repo.get_contributors)
            since_date = datetime.now() - timedelta(days=30)
            commits_future = asyncio.get_event_loop().run_in_executor(None, lambda: repo.get_commits(since=since_date))
            open_issues_future = asyncio.get_event_loop().run_in_executor(None, lambda: repo.get_issues(state='open'))
            closed_issues_future = asyncio.get_event_loop().run_in_executor(None, lambda: repo.get_issues(state='closed', since=since_date))
            releases_future = asyncio.get_event_loop().run_in_executor(None, repo.get_releases)
            
            contributors, commits, open_issues, closed_issues, releases = await asyncio.gather(
                contributors_future, commits_future, open_issues_future, closed_issues_future, releases_future
            )
            
            open_issues_count = len([i for i in open_issues if not i.pull_request])
            closed_issues_count = len([i for i in closed_issues if not i.pull_request])
            
            releases_list = list(releases)
            return {
                "contributors_count": len(list(contributors)),
                "recent_commits_30d": len(list(commits)),
                "open_issues_count": open_issues_count,
                "closed_issues_count_30d": closed_issues_count,
                "releases_count": len(releases_list),
                "latest_release_tag": releases_list[0].tag_name if releases_list else None,
                "last_release_date": releases_list[0].created_at.isoformat() if releases_list else None,
                "top_contributors": [{"login": c.login, "contributions": c.contributions} for c in list(contributors)[:10]],
            }
            
        except Exception as e:
            logger.error(f"获取社区指标时出错 {repo_url}: {e}", exc_info=True)
            return {}
