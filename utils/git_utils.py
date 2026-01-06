import asyncio
import sys
import time

# 修复 Windows 事件循环策略兼容性问题
if sys.platform == 'win32':
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except AttributeError:
        # 在较新的 Python 版本中，WindowsSelectorEventLoopPolicy 已被移除
        # 直接使用默认策略即可
        pass

import os
import re
import tempfile
import shutil
import logging
import subprocess
from typing import Optional, List, Dict, Any, Tuple
import aiohttp
try:
    from git import Repo, GitCommandError
    GIT_AVAILABLE = True
except ImportError:
    Repo = None
    GitCommandError = None
    GIT_AVAILABLE = False
    print("警告: Git未安装或不可用。某些功能（如仓库克隆）将不可用。")
    print("请安装Git并确保其在系统PATH中。")
from app.core.config import settings
logger = logging.getLogger(__name__)


class GitUtils:
    """
    支持GitHub和Gitee的代码仓库下载器，异步、多策略、国内镜像兼容（缓存优化版）

    克隆策略:
    1. SSH克隆优先（最快，有密钥时）
    2. 反向代理加速（替换 github.com 为代理域名）
    3. 镜像下载ZIP
    4. HTTPS克隆（最后备选）
    """

    # 缓存机制优化
    _repo_cache: Dict[str, Tuple[str, float]] = {}
    _cache_lock = None
    CACHE_EXPIRE_SECONDS = 300  # 缓存过期时间：5分钟（活跃仓库更新频率高）

    def __init__(self):
        if not GIT_AVAILABLE:
            logger.error("Git未安装或不可用。某些功能（如仓库克隆）将不可用。")
            logger.error("请安装Git并确保其在系统PATH中。")
            raise RuntimeError("Git未安装或不可用。请安装Git并确保其在系统PATH中。")
        
        self.timeout = settings.GIT_TIMEOUT
        self.max_retries = settings.GIT_MAX_RETRIES
        self.use_shallow_clone = True  # 默认使用浅克隆加快速度
        self.base_temp_dir = tempfile.mkdtemp(prefix="repo_analysis_")
        self.last_cloned: Optional[str] = None

        # 初始化缓存锁（如果是首次使用）
        if GitUtils._cache_lock is None:
            GitUtils._cache_lock = asyncio.Lock()

    def _apply_proxy_domain(self, url: str) -> str:
        """
        将GitHub URL转换为反向代理加速的URL
        
        例如：
        - https://github.com/user/repo.git → https://githubproxy.cc/user/repo.git
        - https://raw.githubusercontent.com/user/file → https://githubproxy.cc/raw.githubusercontent.com/user/file
        """
        for proxy_domain in settings.GIT_MIRRORS:
            if f"https://github.com/" in url:
                url = url.replace(f"https://github.com/", f"https://{proxy_domain}/")
            elif f"https://raw.githubusercontent.com/" in url:
                url = url.replace(f"https://raw.githubusercontent.com/", f"https://{proxy_domain}/")
        return url

    def normalize_url(self, repo_url: str) -> Dict[str, str]:
        """统一URL标准化方法，支持GitHub和Gitee"""
        repo_url = repo_url.strip().rstrip('/')
        if repo_url.endswith('.git'):
            repo_url = repo_url[:-4]

        result = {
            'original': repo_url,
            'platform': 'unknown',
            'owner': '',
            'repo': '',
            'https_url': '',
            'proxy_url': '',         # 新增：代理加速URL
            'ssh_url': '',
            'clone_url': ''
        }

        # GitHub
        if 'github.com' in repo_url:
            result['platform'] = 'github'
            match = re.search(r'github\.com[/:]([^/]+)/([^/]+)', repo_url)
            if match:
                result['owner'], result['repo'] = match.group(1), match.group(2)
                result['https_url'] = f"https://github.com/{result['owner']}/{result['repo']}.git"
                result['ssh_url'] = f"git@github.com:{result['owner']}/{result['repo']}.git"
                result['clone_url'] = result['https_url']
                # 应用代理加速
                result['proxy_url'] = self._apply_proxy_domain(result['https_url'])
                result['proxy_ssh_url'] = self._apply_proxy_domain(result['ssh_url'])

        # Gitee
        elif 'gitee.com' in repo_url:
            result['platform'] = 'gitee'
            match = re.search(r'gitee\.com[/:]([^/]+)/([^/]+)', repo_url)
            if match:
                result['owner'], result['repo'] = match.group(1), match.group(2)
                result['https_url'] = f"https://gitee.com/{result['owner']}/{result['repo']}.git"
                result['ssh_url'] = f"git@gitee.com:{result['owner']}/{result['repo']}.git"
                result['clone_url'] = result['https_url']
                result['proxy_url'] = result['https_url']
                result['proxy_ssh_url'] = result['ssh_url']

        # owner/repo 简写
        elif '/' in repo_url and 'http' not in repo_url:
            parts = repo_url.split('/')
            if len(parts) == 2:
                result['owner'], result['repo'] = parts
                result['platform'] = 'github'
                result['https_url'] = f"https://github.com/{parts[0]}/{parts[1]}.git"
                result['ssh_url'] = f"git@github.com:{parts[0]}/{parts[1]}.git"
                result['clone_url'] = result['https_url']
                # 应用代理加速
                result['proxy_url'] = self._apply_proxy_domain(result['https_url'])
                result['proxy_ssh_url'] = self._apply_proxy_domain(result['ssh_url'])

        return result

    def _is_cached_valid(self, cached_path: str, create_time: float) -> bool:
        """
        验证缓存是否有效：
        1. 未过期（默认5分钟）
        2. 路径存在
        3. 目录内有有效代码文件（非.git目录）
        """
        # 1. 检查缓存是否过期
        if time.time() - create_time > self.CACHE_EXPIRE_SECONDS:
            logger.debug(f"缓存过期：{cached_path}（创建时间：{time.ctime(create_time)}）")
            return False

        # 2. 检查路径是否存在
        if not os.path.exists(cached_path):
            logger.debug(f"缓存路径不存在：{cached_path}")
            return False

        # 3. 检查是否有有效代码文件（排除仅含.git的情况）
        try:
            repo_contents = os.listdir(cached_path)
            non_git_contents = [item for item in repo_contents if item != ".git"]
            if not non_git_contents:
                logger.debug(f"缓存目录无有效代码文件：{cached_path}")
                return False
        except Exception as e:
            logger.error(f"验证缓存目录失败：{cached_path}，错误：{e}")
            return False

        return True

    async def clone_repo(self, repo_url: str, branches: Optional[List[str]] = None,
                         token: Optional[str] = None, cancel_callback: Optional[callable] = None) -> Optional[str]:
        """
        克隆仓库：SSH优先，代理加速，镜像下载，最后HTTPS

        优化策略：
        1. SSH克隆最优先（有密钥时）
        2. 反向代理加速 github.com → githubproxy.cc
        3. 镜像ZIP下载
        4. 最后尝试HTTPS克隆

        参数:
            cancel_callback: 可选的取消检查函数，返回True表示应该取消
        """
        # 标准化URL用于缓存键
        url_info = self.normalize_url(repo_url)
        if not url_info['owner'] or not url_info['repo']:
            logger.error(f"无法解析仓库URL: {repo_url}")
            return None

        cache_key = f"{url_info['platform']}_{url_info['owner']}_{url_info['repo']}"
        cached_path: Optional[str] = None

        # 缓存检查（加锁保证并发安全）
        async with GitUtils._cache_lock:
            if cache_key in GitUtils._repo_cache:
                cached_path, create_time = GitUtils._repo_cache[cache_key]
                # 验证缓存有效性
                if self._is_cached_valid(cached_path, create_time):
                    logger.info(f"使用有效缓存：{cached_path}（缓存键：{cache_key}）")
                    self.last_cloned = cached_path
                    return cached_path
                else:
                    # 无效缓存，立即删除
                    del GitUtils._repo_cache[cache_key]
                    logger.warning(f"删除无效缓存：{cache_key} -> {cached_path}")

        # 获取可用分支列表
        if branches is None:
            branches = await self._get_default_branch_list(repo_url, token)
            if not branches:
                branches = ["main", "master"]

        temp_dir = tempfile.mkdtemp(prefix=f"repo_analysis_{url_info['platform']}_")
        logger.info(f"准备克隆仓库: {url_info['owner']}/{url_info['repo']}, 分支: {branches[0]}")

        try:
            # 根据平台选择克隆策略
            if url_info['platform'] == 'gitee':
                # Gitee: HTTPS -> SSH -> 镜像下载
                result = await self._try_https_clone(url_info['proxy_url'] if url_info.get('proxy_url') else url_info['https_url'], branches, temp_dir, token)
                if result:
                    pass  # 如果HTTPS成功，继续使用该结果
                else:
                    result = await self._try_ssh_clone(url_info['proxy_ssh_url'] if url_info.get('proxy_ssh_url') else url_info['ssh_url'], branches, temp_dir)
                    if result:
                        pass  # 如果SSH成功，继续使用该结果
                    else:
                        result = await self._download_gitee_zip(url_info, branches, temp_dir)
            else:
                # GitHub: SSH优先，代理加速，镜像下载，最后HTTPS
                logger.info(f"GitHub仓库，使用SSH优先+代理加速策略")
                
                # 检查取消状态
                if cancel_callback and cancel_callback():
                    logger.info(f"用户取消克隆，停止GitHub仓库下载")
                    await self.cleanup_temp_dir(temp_dir, cache_key=cache_key)
                    return None
                
                # 1. 首先尝试SSH克隆（最快，有密钥的情况下）
                result = await self._try_ssh_clone(url_info['proxy_ssh_url'] if url_info.get('proxy_ssh_url') else url_info['ssh_url'], branches, temp_dir, cancel_callback)
                if result:
                    logger.info(f"SSH克隆成功")
                else:
                    # 再次检查取消状态
                    if cancel_callback and cancel_callback():
                        logger.info(f"用户取消克隆，停止代理下载")
                        await self.cleanup_temp_dir(temp_dir, cache_key=cache_key)
                        return None
                    
                    # 2. SSH失败，尝试代理加速的镜像下载
                    logger.info(f"SSH克隆失败，尝试代理加速镜像下载")
                    result = await self._download_from_proxies(url_info, branches, temp_dir, cancel_callback)
                    
                    if not result and not (cancel_callback and cancel_callback()):
                        # 3. 镜像失败且未取消，尝试HTTPS克隆（带重试）
                        logger.info(f"镜像下载失败，尝试HTTPS克隆")
                        result = await self._try_https_clone(url_info['proxy_url'] if url_info.get('proxy_url') else url_info['https_url'], branches, temp_dir, token, cancel_callback)

            if result:
                self.last_cloned = temp_dir
                # 写入缓存（加锁保证并发安全）
                async with GitUtils._cache_lock:
                    GitUtils._repo_cache[cache_key] = (temp_dir, time.time())
                logger.info(f"克隆成功，已缓存仓库: {cache_key} -> {temp_dir}")
                return temp_dir
            else:
                await self.cleanup_temp_dir(temp_dir, cache_key=cache_key)  # 克隆失败，清理目录+缓存
                logger.error(f"所有克隆策略都失败了: {repo_url}")
                return None

        except Exception as e:
            logger.error(f"克隆仓库失败: {e}", exc_info=True)
            await self.cleanup_temp_dir(temp_dir, cache_key=cache_key)  # 异常时，清理目录+缓存
            return None

    async def _get_default_branch_list(self, repo_url: str, token: Optional[str]) -> List[str]:
        """获取仓库默认分支，并创建一个包含默认分支和其他常用分支的列表"""
        default_branches = []
        try:
            url_info = self.normalize_url(repo_url)
            if url_info['platform'] == 'github':
                from utils.github_client import GitHubClient
                # 禁用SSL验证（因为可能使用FastGit等代理）
                github_client = GitHubClient(verify_ssl=False)
                if token:
                    github_client._init_github_client(token)

                repo_info = await github_client.get_repository_info(repo_url, token)
                if repo_info and 'default_branch' in repo_info:
                    default_branch = repo_info['default_branch']
                    logger.info(f"获取到仓库默认分支: {default_branch}")
                    default_branches.append(default_branch)
        except Exception as e:
            logger.warning(f"获取默认分支失败: {e}")

        default_branches.extend(["main", "master"])
        seen = set()
        result = []
        for branch in default_branches:
            if branch not in seen:
                seen.add(branch)
                result.append(branch)

        return result

    def get_default_branch(self, repo_path: str) -> Optional[str]:
        """
        从本地仓库获取默认分支名称
        
        Args:
            repo_path: 本地仓库路径
        
        Returns:
            默认分支名称，如果获取失败则返回None
        """
        try:
            repo = Repo(repo_path)
            # 尝试获取HEAD引用的分支
            if repo.head.is_detached:
                # 如果是分离HEAD状态，尝试获取符号引用
                try:
                    return str(repo.head.ref).split('/')[-1]
                except:
                    pass
            else:
                # 获取当前分支名称
                return repo.active_branch.name
        except Exception as e:
            logger.warning(f"获取本地仓库默认分支失败: {e}")
            return None

    async def _try_ssh_clone(self, ssh_url: str, branches: List[str], temp_dir: str, cancel_callback: Optional[callable] = None) -> bool:
        """
        SSH克隆：使用浅克隆优化的速度
        
        参数:
            cancel_callback: 可选的取消检查函数
        """
        if isinstance(branches, str):
            logger.error(f"branches 参数类型错误: {branches}，应为列表")
            branches = [branches]

        # 1. 动态查找有效的 SSH Key
        ssh_key_path = None
        ssh_dir = os.path.expanduser("~/.ssh")
        for key_name in ['id_rsa', 'id_ed25519', 'id_ecdsa']:
            path = os.path.join(ssh_dir, key_name)
            if os.path.exists(path):
                ssh_key_path = path
                break

        if not ssh_key_path:
            logger.warning("未找到任何 SSH 密钥 (id_rsa, id_ed25519, id_ecdsa），跳过 SSH 克隆")
            return False

        # 检查取消状态
        if cancel_callback and cancel_callback():
            logger.info(f"SSH克隆被取消")
            return False

        # 确保目标目录是空的
        self._ensure_empty_dir(temp_dir)

        # 2. 尝试指定分支克隆（使用浅克隆 --depth=1）
        for branch in branches:
            # 每次尝试分支前检查取消
            if cancel_callback and cancel_callback():
                logger.info(f"SSH克隆被取消（分支 {branch}）")
                return False
            env = os.environ.copy()
            # SSH配置优化
            env['GIT_SSH_COMMAND'] = f'ssh -i "{ssh_key_path}" -o StrictHostKeyChecking=no -o ConnectTimeout=10 -o ServerAliveInterval=30'

            loop = asyncio.get_event_loop()
            try:
                logger.info(f"尝试 SSH 克隆: 分支={branch}, Key={ssh_key_path}")
                # 清理代理设置（避免代理导致的超时）
                env_copy = env.copy()
                env_copy.pop('http_proxy', None)
                env_copy.pop('https_proxy', None)
                env_copy.pop('HTTP_PROXY', None)
                env_copy.pop('HTTPS_PROXY', None)

                # 使用浅克隆（--depth=1）大幅减少下载量
                # 使用 Popen 而不是 run，这样可以随时取消
                process = subprocess.Popen(
                    ['git', 'clone', '--depth', '1', '--branch', branch, '--single-branch', ssh_url, temp_dir],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env_copy
                )
                
                # 等待进程完成，定期检查取消标志
                while True:
                    # 检查取消标志
                    if cancel_callback and cancel_callback():
                        logger.info(f"SSH克隆被取消，终止进程 (分支 {branch})")
                        # 终止进程
                        try:
                            process.terminate()
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            # 如果5秒后还没终止，强制杀死
                            try:
                                process.kill()
                            except:
                                pass
                        return False
                    
                    # 检查进程是否完成
                    returncode = process.poll()
                    if returncode is not None:
                        # 进程已完成
                        if returncode == 0:
                            logger.info(f"SSH克隆成功！分支: {branch}")
                            return True
                        else:
                            error_msg = process.stderr.read().decode()
                            if "not found" in error_msg.lower() or "error: pathspec" in error_msg.lower():
                                logger.warning(f"远程分支 '{branch}' 不存在，尝试下一分支")
                                break  # 尝试下一个分支
                            elif "Connection timed out" in error_msg or "Could not resolve hostname" in error_msg:
                                logger.warning(f"SSH连接超时或无法解析主机: {error_msg}")
                                return False  # 网络问题，直接返回失败
                            else:
                                logger.warning(f"SSH克隆失败 (分支 {branch}): {error_msg.strip()}")
                                break
                    
                    # 进程还在运行，等待一小段时间再检查
                    await asyncio.sleep(0.5)
                    
            except Exception as e:
                logger.warning(f"SSH克隆异常: {e}")

        return False

    async def _try_https_clone(self, https_url: str, branches: List[str],
                               temp_dir: str, token: Optional[str], cancel_callback: Optional[callable] = None) -> bool:
        """
        HTTPS克隆：使用浅克隆和重试机制
        
        优化:
        1. 指数退避重试（1, 2, 4, 8秒）
        2. 浅克隆 --depth=1 --single-branch
        3. 自动清理代理设置避免冲突
        4. 支持取消检查
        
        参数:
            cancel_callback: 可选的取消检查函数
        """
        # 检查取消状态
        if cancel_callback and cancel_callback():
            logger.info(f"HTTPS克隆被取消")
            return False

        # 确保目标目录是空的
        self._ensure_empty_dir(temp_dir)

        # 尝试指定分支克隆
        for branch in branches:
            # 每次尝试分支前检查取消
            if cancel_callback and cancel_callback():
                logger.info(f"HTTPS克隆被取消（分支 {branch}）")
                return False
            
            for attempt in range(self.max_retries):
                # 每次重试前检查取消
                if cancel_callback and cancel_callback():
                    logger.info(f"HTTPS克隆被取消（分支 {branch}, 尝试 {attempt + 1}）")
                    return False
                clone_url = https_url
                if token:
                    clone_url = https_url.replace("https://", f"https://{token}@")
                try:
                    # 清理代理设置
                    env = os.environ.copy()
                    env.pop('http_proxy', None)
                    env.pop('https_proxy', None)
                    env.pop('HTTP_PROXY', None)
                    env.pop('HTTPS_PROXY', None)

                    # 使用 git clone 命令而不是 Repo.clone_from，这样可以随时取消
                    # 构建命令参数
                    cmd = ['git', 'clone', '--depth', '1', '--branch', branch, '--single-branch', clone_url, temp_dir]
                    
                    # 创建进程
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        env=env
                    )
                    
                    # 等待进程完成，定期检查取消标志
                    while True:
                        # 检查取消标志
                        if cancel_callback and cancel_callback():
                            logger.info(f"HTTPS克隆被取消，终止进程 (分支 {branch}, 尝试 {attempt + 1})")
                            # 终止进程
                            try:
                                process.terminate()
                                process.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                # 如果5秒后还没终止，强制杀死
                                try:
                                    process.kill()
                                except:
                                    pass
                            return False
                        
                        # 检查进程是否完成
                        returncode = process.poll()
                        if returncode is not None:
                            # 进程已完成
                            if returncode == 0:
                                logger.info(f"HTTPS克隆成功！分支: {branch}, 重试次数: {attempt}")
                                return True
                            else:
                                # 进程完成但失败
                                error_msg = process.stderr.read().decode()
                                msg = error_msg.lower()
                                if "branch" in msg and ("not found" in msg or "couldn't find remote ref" in msg):
                                    logger.warning(f"分支不存在: {branch}，尝试下一分支")
                                    break  # 分支不存在，跳到下一个分支
                                elif "authentication" in msg or "403" in msg or "401" in msg:
                                    logger.error(f"认证失败，请检查token: {msg}")
                                    return False
                                elif "connection was reset" in msg or "could not connect" in msg:
                                    logger.warning(f"网络连接问题 (分支 {branch}, 尝试 {attempt + 1}/{self.max_retries}): {error_msg}")
                                    if attempt < self.max_retries - 1:
                                        await asyncio.sleep(2 ** attempt)  # 指数退避
                                        continue  # 继续重试
                                    else:
                                        break  # 重试次数用完，跳出
                                else:
                                    logger.warning(f"HTTPS克隆失败 (分支 {branch}, 尝试 {attempt + 1}/{self.max_retries}): {error_msg}")
                                    if attempt < self.max_retries - 1:
                                        await asyncio.sleep(2 ** attempt)  # 指数退避
                                        continue  # 继续重试
                                    else:
                                        break  # 重试次数用完，跳出
                        
                        # 进程还在运行，等待一小段时间再检查
                        await asyncio.sleep(0.5)
                except GitCommandError as e:
                    msg = str(e).lower()
                    if "branch" in msg and ("not found" in msg or "couldn't find remote ref" in msg):
                        logger.warning(f"分支不存在: {branch}，尝试下一分支")
                        break  # 分支不存在，跳到下一个分支
                    elif "authentication" in msg or "403" in msg or "401" in msg:
                        logger.error(f"认证失败，请检查token: {msg}")
                        return False
                    elif "connection was reset" in msg or "could not connect" in msg:
                        logger.warning(f"网络连接问题 (分支 {branch}, 尝试 {attempt + 1}/{self.max_retries}): {e}")
                        if attempt < self.max_retries - 1:
                            await asyncio.sleep(2 ** attempt)  # 指数退避
                        continue
                    else:
                        logger.warning(f"HTTPS克隆失败 (分支 {branch}, 尝试 {attempt + 1}/{self.max_retries}): {e}")
                        if attempt < self.max_retries - 1:
                            await asyncio.sleep(2 ** attempt)  # 指数退避
                except Exception as e:
                    logger.warning(f"HTTPS克隆异常: {e}")
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(2 ** attempt)  # 指数退避

        # 尝试不指定分支克隆（使用默认分支）
        # 检查取消状态
        if cancel_callback and cancel_callback():
            logger.info(f"HTTPS克隆默认分支被取消")
            return False
            
        try:
            clone_url = https_url
            if token:
                clone_url = https_url.replace("https://", f"https://{token}@")

            logger.info("尝试克隆默认分支")
            env = os.environ.copy()
            env.pop('http_proxy', None)
            env.pop('https_proxy', None)
            env.pop('HTTP_PROXY', None)
            env.pop('HTTPS_PROXY', None)

            # 使用可中断的克隆方式
            cmd = ['git', 'clone', '--depth', '1', clone_url, temp_dir]
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env
            )
            
            # 等待进程完成，定期检查取消标志
            while True:
                # 检查取消标志
                if cancel_callback and cancel_callback():
                    logger.info(f"HTTPS默认分支克隆被取消")
                    try:
                        process.terminate()
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        try:
                            process.kill()
                        except:
                            pass
                    return False
                
                # 检查进程是否完成
                returncode = process.poll()
                if returncode is not None:
                    if returncode == 0:
                        logger.info(f"HTTPS克隆成功！使用默认分支")
                        return True
                    else:
                        error_msg = process.stderr.read().decode()
                        logger.warning(f"HTTPS克隆默认分支也失败了: {error_msg}")
                        break
                
                await asyncio.sleep(0.5)
                
        except Exception as e:
            logger.warning(f"HTTPS克隆默认分支异常: {e}")

        return False

    async def _download_from_proxies(self, url_info: Dict[str, str],
                                   branches: List[str], temp_dir: str,
                                   cancel_callback: Optional[callable] = None) -> Optional[str]:
        """
        从反向代理域名下载仓库ZIP文件，按优先级尝试不同代理和分支
        
        按用户要求的代理域名优先级：
        githubproxy.cc > ghproxylist.com > ghfast.top > gh-proxy.com
        
        参数:
            cancel_callback: 可选的取消检查函数
        """
        # 检查取消状态
        if cancel_callback and cancel_callback():
            logger.info(f"代理下载被取消")
            return None
        # 使用较短的超时时间，以便快速尝试下一个代理
        connector = aiohttp.TCPConnector(limit=10, limit_per_host=5,ssl=False)
        timeout = aiohttp.ClientTimeout(total=15, connect=5)  # 使用ClientTimeout的参数
        try:
            async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                # 按代理优先级尝试
                for proxy_domain in self.github_proxy_domains:
                    # 每次尝试代理前检查取消
                    if cancel_callback and cancel_callback():
                        logger.info(f"代理下载被取消（代理 {proxy_domain}）")
                        return None
                    
                    # 首先尝试默认分支
                    for branch in branches:
                        # 每次尝试分支前检查取消
                        if cancel_callback and cancel_callback():
                            logger.info(f"代理下载被取消（代理 {proxy_domain}, 分支 {branch}）")
                            return None
                            
                        zip_url = f"https://{proxy_domain}/{url_info['owner']}/{url_info['repo']}/archive/refs/heads/{branch}.zip"
                        try:
                            logger.info(f"尝试从代理下载: {zip_url}")
                            async with session.get(zip_url) as resp:
                                if resp.status == 200:
                                    zip_path = os.path.join(tempfile.gettempdir(),
                                                              f"{url_info['owner']}_{url_info['repo']}.zip")
                                    with open(zip_path, 'wb') as f:
                                        f.write(await resp.read())
                                    shutil.unpack_archive(zip_path, temp_dir)
                                    logger.info(f"代理下载ZIP成功: {zip_url}")

                                    # 找到实际解压的目录
                                    extracted_dir = self._find_extracted_dir(temp_dir)
                                    if extracted_dir:
                                        logger.info(f"使用解压目录: {extracted_dir}")
                                        return extracted_dir
                                elif resp.status == 404:
                                    logger.warning(f"代理中分支不存在: {branch} at {proxy_domain}")
                                    continue  # 尝试下一个分支
                                else:
                                    # 这里不应该执行到，因为上面所有分支都失败
                                    logger.warning(f"代理下载失败，状态码 {resp.status}: {zip_url}")
                        except asyncio.TimeoutError:
                            logger.warning(f"代理下载超时: {zip_url}")
                        except aiohttp.ClientConnectorError as e:
                            logger.warning(f"代理连接错误: {zip_url}, 错误: {e}")
                        except Exception as e:
                            logger.warning(f"代理下载失败 {zip_url}: {e}")
        except Exception as e:
            logger.warning(f"代理下载过程异常: {e}")
            return None

    async def _download_gitee_zip(self, url_info: Dict[str, str], branches: List[str], temp_dir: str) -> Optional[str]:
        base_url = f"https://gitee.com/{url_info['owner']}/{url_info['repo']}/repository/archive"
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
            for branch in branches:
                zip_url = f"{base_url}?ref={branch}&type=zip"
                try:
                    async with session.get(zip_url) as resp:
                        if resp.status == 200:
                            zip_path = os.path.join(tempfile.gettempdir(),
                                                      f"{url_info['owner']}_{url_info['repo']}.zip")
                            with open(zip_path, 'wb') as f:
                                f.write(await resp.read())
                            shutil.unpack_archive(zip_path, temp_dir)
                            logger.info(f"Gitee ZIP下载成功: {zip_url}")

                            # 找到实际解压的目录
                            extracted_dir = self._find_extracted_dir(temp_dir)
                            if extracted_dir:
                                logger.info(f"使用解压目录: {extracted_dir}")
                                return extracted_dir
                            else:
                                logger.warning("未找到解压目录，使用: {temp_dir}")
                                return temp_dir
                        elif resp.status == 404:
                            logger.warning(f"Gitee 分支不存在: {branch}")
                            continue
                except Exception as e:
                    logger.warning(f"Gitee ZIP下载失败 {zip_url}: {e}")
        return None

    def _find_extracted_dir(self, temp_dir: str) -> Optional[str]:
        """
        找到ZIP解压后的实际代码目录
        ZIP解压后通常会在temp_dir下创建一个子目录
        """
        try:
            items = os.listdir(temp_dir)
            if not items:
                logger.warning(f"解压后目录为空: {temp_dir}")
                return None

            # 如果只有一个子目录，假设那就是解压后的内容
            if len(items) == 1:
                item_path = os.path.join(temp_dir, items[0])
                if os.path.isdir(item_path):
                    logger.info(f"找到解压目录: {item_path}")
                    return item_path

            # 如果有多个，查找包含代码文件的目录
            for item in items:
                item_path = os.path.join(temp_dir, item)
                if os.path.isdir(item_path) and not item.startswith('.'):
                    # 检查这个目录是否包含代码文件
                    try:
                        sub_items = os.listdir(item_path)
                        has_code = any(
                            any(f.endswith(ext) for ext in
                                ['.py', '.js', '.ts', '.java', '.go', '.rs', '.cpp', '.c', '.php', '.rb'])
                            for f in sub_items[:20]  # 只检查前20个文件
                        )
                        if has_code:
                            logger.info(f"找到包含代码的目录: {item_path}")
                            return item_path
                    except:
                        continue

            # 如果找不到明确的代码目录，返回temp_dir本身
            logger.warning(f"未找到明确的代码目录，使用: {temp_dir}")
            return temp_dir

        except Exception as e:
            logger.error(f"查找解压目录失败: {e}")
            return temp_dir

    async def cleanup_repo(self, repo_path: str, cache_key: Optional[str] = None):
        """清理克隆的仓库，同步删除对应缓存（支持异步调用）"""
        try:
            if os.path.exists(repo_path):
                # 在Windows上，可能需要先解除文件占用才能删除
                GitUtils._force_remove_directory(repo_path)

                logger.info(f"清理仓库目录: {repo_path}")

            # 同步删除缓存（加锁保证并发安全）
            if cache_key and cache_key in GitUtils._repo_cache:
                async with GitUtils._cache_lock:
                    del GitUtils._repo_cache[cache_key]
                    logger.info(f"同步删除缓存: {cache_key}")
        except Exception as e:
            logger.error(f"清理仓库失败: {e}")

    @staticmethod
    def _force_remove_directory(path: str):
        """强制删除目录，处理Windows权限问题"""
        import stat
        def handle_remove_readonly(func, path, exc):
            """处理只读文件删除问题"""
            if os.path.exists(path):
                os.chmod(path, stat.S_IWRITE)
                func(path)

        if os.path.exists(path):
            # 对于Windows系统，先尝试正常删除
            try:
                shutil.rmtree(path)
            except PermissionError:
                # 如果遇到权限错误，递归处理所有文件
                for root, dirs, files in os.walk(path, topdown=False):
                    for name in files:
                        filename = os.path.join(root, name)
                        os.chmod(filename, stat.S_IWRITE)
                        os.remove(filename)
                    for name in dirs:
                        os.rmdir(os.path.join(root, name))
                os.rmdir(path)

    @staticmethod
    def analyze_repo_structure(repo_path: str) -> Dict[str, Any]:
        """分析仓库结构"""
        structure = {
            "total_files": 0,
            "total_dirs": 0,
            "main_language": "",
            "languages": {},
            "has_readme": False,
            "has_license": False,
            "has_contributing": False,
            "has_code_of_conduct": False,
            "has_issue_template": False,
            "has_pr_template": False,
            "has_github_actions": False,
            "has_tests": False,
            "has_ci_cd": False,
            "main_language_files": [],
            "file_types": {}
        }

        extension_to_language = {
            '.py': 'Python',
            '.js': 'JavaScript',
            '.jsx': 'JavaScript',
            '.ts': 'TypeScript',
            '.tsx': 'TypeScript',
            '.java': 'Java',
            '.cpp': 'C++',
            '.c': 'C',
            '.cs': 'C#',
            '.go': 'Go',
            '.rs': 'Rust',
            '.php': 'PHP',
            '.rb': 'Ruby',
            '.swift': 'Swift',
            '.kt': 'Kotlin',
            '.m': 'Objective-C',
            '.mm': 'Objective-C',
            '.scala': 'Scala',
            '.pl': 'Perl',
            '.pm': 'Perl',
            '.r': 'R',
            '.lua': 'Lua',
            '.groovy': 'Groovy',
            '.dart': 'Dart',
            '.elm': 'Elm',
            '.erl': 'Erlang',
            '.ex': 'Elixir',
            '.fs': 'F#',
            '.hs': 'Haskell',
            '.clj': 'Clojure',
            '.coffee': 'CoffeeScript'
        }

        try:
            for root, dirs, files in os.walk(repo_path):
                dirs[:] = [d for d in dirs if
                           not d.startswith('.') and d not in ['node_modules', '__pycache__', 'venv', 'env', '.git']]

                structure["total_dirs"] += len(dirs)

                for file in files:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, repo_path)

                    structure["total_files"] += 1

                    _, ext = os.path.splitext(file)
                    ext = ext.lower()

                    if ext in extension_to_language:
                        lang = extension_to_language[ext]
                        structure["languages"][lang] = structure["languages"].get(lang, 0) + 1
                        if lang not in structure["main_language_files"]:
                            structure["main_language_files"].append(rel_path)

                    structure["file_types"][ext] = structure["file_types"].get(ext, 0) + 1

                    file_lower = file.lower()
                    if 'readme' in file_lower:
                        structure["has_readme"] = True
                    elif 'license' in file_lower or 'copying' in file_lower:
                        structure["has_license"] = True
                    elif 'contributing' in file_lower:
                        structure["has_contributing"] = True
                    elif 'conduct' in file_lower:
                        structure["has_code_of_conduct"] = True

                    if 'test' in rel_path.lower() or 'spec' in rel_path.lower():
                        structure["has_tests"] = True

                    ci_cd_files = [
                        '.gitlab-ci.yml', '.travis.yml', 'circle.yml', 'circle.config.yml',
                        'Jenkinsfile', 'azure-pipelines.yml', '.drone.yml', 'bitbucket-pipelines.yml',
                        'cloudbuild.yaml', 'buildspec.yml', 'appveyor.yml'
                    ]
                    for ci_file in ci_cd_files:
                        if ci_file in file.lower():
                            structure["has_ci_cd"] = True
                            break

            github_workflows_path = os.path.join(repo_path, '.github', 'workflows')
            if os.path.exists(github_workflows_path):
                structure["has_github_actions"] = True

            issue_templates_path = os.path.join(repo_path, '.github', 'ISSUE_TEMPLATE')
            if os.path.exists(issue_templates_path):
                structure["has_issue_template"] = True

            pr_templates_path = os.path.join(repo_path, '.github', 'PULL_REQUEST_TEMPLATE')
            if os.path.exists(pr_templates_path):
                structure["has_pr_template"] = True
            else:
                for file in os.listdir(repo_path):
                    if 'pull_request' in file.lower() and (
                            'template' in file.lower() or file.endswith(('.md', '.txt'))):
                        structure["has_pr_template"] = True
                        break

            if structure["languages"]:
                structure["main_language"] = max(structure["languages"].items(), key=lambda x: x[1])[0]

        except Exception as e:
            logger.error(f"分析仓库结构时出错: {e}")

        return structure

    async def cleanup_temp_dir(self, temp_path: Optional[str], cache_key: Optional[str] = None):
        """清理临时目录，同步删除对应缓存"""
        try:
            if not temp_path:
                return
            temp_path = os.path.abspath(temp_path)
            base = os.path.abspath(self.base_temp_dir)
            if os.path.commonpath([base, temp_path]) == base and os.path.exists(temp_path):
                GitUtils._force_remove_directory(temp_path)
                logger.info(f"临时目录清理成功: {temp_path}")

            # 同步删除缓存（加锁保证并发安全）
            if cache_key and cache_key in GitUtils._repo_cache:
                async with GitUtils._cache_lock:
                    del GitUtils._repo_cache[cache_key]
                    logger.info(f"同步删除缓存: {cache_key}")
        except Exception as e:
            logger.error(f"清理临时目录失败: {temp_path}, 错误: {e}")

    def _ensure_empty_dir(self, temp_dir: str):
        """
        确保目标目录为空，如果存在则清理
        """
        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                logger.warning(f"清理目录失败，继续使用: {temp_dir}")
                pass
