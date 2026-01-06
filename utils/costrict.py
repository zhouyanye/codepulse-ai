import requests
import zipfile
import io
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime, timezone
import os
import re

logger = logging.getLogger(__name__)


class CoStrictAnalyzer:
    """
    CoStrict 代码审查器
    """

    def __init__(self, repo_url: str, local_path: Optional[str] = None):
        # 移除末尾的 .git 和 /
        self.repo_url = repo_url.rstrip("/")
        if self.repo_url.endswith(".git"):
            self.repo_url = self.repo_url[:-4]  # 安全地移除.git后缀
            
        self.local_path = local_path
        
        # 检测是否为Gitee仓库
        if "gitee.com" in self.repo_url:
            self.is_gitee = True
            # Gitee API URL格式: https://gitee.com/api/v5/repos/{owner}/{repo}
            match = re.search(r"gitee\.com/([^/]+)/([^/]+)", self.repo_url)
            if match:
                self.owner, self.repo = match.groups()
                self.api_url = f"https://gitee.com/api/v5/repos/{self.owner}/{self.repo}"
            else:
                # 如果无法通过正则解析，尝试其他方式
                parts = self.repo_url.split("gitee.com/")
                if len(parts) > 1:
                    owner_repo = parts[1]
                    owner_repo_parts = owner_repo.split("/", 1)
                    if len(owner_repo_parts) == 2:
                        self.owner, self.repo = owner_repo_parts
                    else:
                        # 尝试从完整名称中提取
                        owner_repo_parts = owner_repo.split("/")
                        if len(owner_repo_parts) >= 2:
                            self.owner, self.repo = owner_repo_parts[0], owner_repo_parts[1]
                        else:
                            raise ValueError(f"无法解析Gitee仓库URL: {repo_url}")
                else:
                    raise ValueError(f"无法解析Gitee仓库URL: {repo_url}")
        else:
            self.is_gitee = False
            # GitHub API URL格式: https://api.github.com/repos/{owner}/{repo}
            match = re.search(r"github\.com/([^/]+)/([^/]+)", self.repo_url)
            if match:
                self.owner, self.repo = match.groups()
                self.api_url = f"https://api.github.com/repos/{self.owner}/{self.repo}"
            else:
                # 如果无法通过正则解析，尝试其他方式
                parts = self.repo_url.split("github.com/")
                if len(parts) > 1:
                    owner_repo = parts[1]
                    owner_repo_parts = owner_repo.split("/", 1)
                    if len(owner_repo_parts) == 2:
                        self.owner, self.repo = owner_repo_parts
                    else:
                        # 尝试从完整名称中提取
                        owner_repo_parts = owner_repo.split("/")
                        if len(owner_repo_parts) >= 2:
                            self.owner, self.repo = owner_repo_parts[0], owner_repo_parts[1]
                        else:
                            raise ValueError(f"无法解析仓库URL: {repo_url}")
                else:
                    raise ValueError(f"无法解析仓库URL: {repo_url}")
        
        self.repo_name = f"{self.owner}/{self.repo}"
        logger.info(f"CoStrict分析器初始化完成 - 平台: {'Gitee' if self.is_gitee else 'GitHub'}, 仓库: {self.owner}/{self.repo}")

    def fetch_repo_info(self) -> Dict[str, Any]:
        """
        获取仓库信息
        """
        try:
            logger.info(f"正在获取仓库信息: {self.owner}/{self.repo}")
            
            # 构造API URL
            if self.is_gitee:
                api_url = f"https://gitee.com/api/v5/repos/{self.owner}/{self.repo}"
            else:
                api_url = f"https://api.github.com/repos/{self.owner}/{self.repo}"
                
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            if not self.is_gitee:  # GitHub需要特定的Accept头
                headers["Accept"] = "application/vnd.github.v3+json"
                
            response = requests.get(api_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            repo_data = response.json()
            
            # 标准化数据格式
            if self.is_gitee:
                standardized_data = {
                    "id": repo_data.get("id"),
                    "name": repo_data.get("name"),
                    "full_name": repo_data.get("full_name"),
                    "owner": {
                        "login": repo_data.get("owner", {}).get("login"),
                        "id": repo_data.get("owner", {}).get("id"),
                        "avatar_url": repo_data.get("owner", {}).get("avatar_url"),
                        "html_url": f"https://gitee.com/{self.owner}"
                    },
                    "private": repo_data.get("private", False),
                    "html_url": repo_data.get("html_url"),
                    "description": repo_data.get("description"),
                    "fork": repo_data.get("fork", False),
                    "created_at": repo_data.get("created_at"),
                    "updated_at": repo_data.get("updated_at"),
                    "pushed_at": repo_data.get("pushed_at"),
                    "homepage": repo_data.get("homepage"),
                    "size": repo_data.get("size", 0),
                    "stargazers_count": repo_data.get("stargazers_count", 0),
                    "watchers_count": repo_data.get("watchers_count", 0),
                    "language": repo_data.get("language"),
                    "has_issues": repo_data.get("has_issues", True),
                    "has_projects": repo_data.get("has_projects", True),
                    "has_downloads": repo_data.get("has_downloads", True),
                    "has_wiki": repo_data.get("has_wiki", False),
                    "has_pages": repo_data.get("has_pages", False),
                    "forks_count": repo_data.get("forks_count", 0),
                    "mirror_url": repo_data.get("mirror_url"),
                    "archived": repo_data.get("archived", False),
                    "disabled": repo_data.get("disabled", False),
                    "open_issues_count": repo_data.get("open_issues_count", 0),
                    "license": repo_data.get("license"),
                    "forks": repo_data.get("forks", 0),
                    "open_issues": repo_data.get("open_issues", 0),
                    "watchers": repo_data.get("watchers", 0),
                    "default_branch": repo_data.get("default_branch", "master"),
                    "permissions": repo_data.get("permissions", {}),
                    "allow_squash_merge": repo_data.get("allow_squash_merge", True),
                    "allow_merge_commit": repo_data.get("allow_merge_commit", True),
                    "allow_rebase_merge": repo_data.get("allow_rebase_merge", True),
                    "allow_auto_merge": repo_data.get("allow_auto_merge", False),
                    "delete_branch_on_merge": repo_data.get("delete_branch_on_merge", False),
                    "network_count": repo_data.get("network_count", 0),
                    "subscribers_count": repo_data.get("subscribers_count", 0)
                }
            else:
                standardized_data = repo_data
                
            logger.info(f"成功获取仓库信息: {self.owner}/{self.repo}")
            return standardized_data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"获取仓库信息失败: {str(e)}")
            raise Exception(f"无法获取仓库信息: {str(e)}")
        except Exception as e:
            logger.error(f"获取仓库信息失败: {str(e)}")
            raise Exception(f"无法获取仓库信息: {str(e)}")

    def fetch_repo_zip(self) -> zipfile.ZipFile:
        """
        获取仓库ZIP文件
        """
        try:
            logger.info(f"正在获取仓库ZIP文件: {self.owner}/{self.repo}")
            
            # 根据平台构造下载URL
            if self.is_gitee:
                # Gitee ZIP下载URL格式: https://gitee.com/{owner}/{repo}/repository/archive/master.zip
                download_url = f"https://gitee.com/{self.owner}/{self.repo}/repository/archive/master.zip"
            else:
                # GitHub ZIP下载URL格式: https://github.com/{owner}/{self.repo}/archive/refs/heads/master.zip
                download_url = f"https://github.com/{self.owner}/{self.repo}/archive/refs/heads/master.zip"
                
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            if not self.is_gitee:  # GitHub需要特定的Accept头
                headers["Accept"] = "application/vnd.github.v3+json"
                
            response = requests.get(download_url, headers=headers, timeout=60)
            response.raise_for_status()
            
            # 检查响应内容类型
            content_type = response.headers.get('content-type', '')
            content_disposition = response.headers.get('content-disposition', '')
            
            # 检查是否真的是ZIP文件
            if not ('application/zip' in content_type or 
                   'application/octet-stream' in content_type or
                   'application/x-zip-compressed' in content_type or
                   '.zip' in content_disposition):
                logger.warning(f"响应内容类型可能不是ZIP文件: {content_type}")
                logger.warning(f"响应内容预览: {response.content[:100]}")
                raise zipfile.BadZipFile("下载的内容不是有效的ZIP文件")
                
            logger.info(f"成功获取仓库ZIP文件: {self.owner}/{self.repo}")
            # 将字节流转换为ZipFile对象
            return zipfile.ZipFile(io.BytesIO(response.content))
            
        except requests.exceptions.RequestException as e:
            logger.error(f"获取仓库ZIP文件失败: {str(e)}")
            raise Exception(f"无法下载仓库ZIP文件: {str(e)}")
        except zipfile.BadZipFile as e:
            logger.error(f"获取的文件不是有效的ZIP文件: {str(e)}")
            raise Exception(f"下载的文件不是有效的ZIP文件: {str(e)}")
        except Exception as e:
            logger.error(f"获取仓库ZIP文件失败: {str(e)}")
            raise Exception(f"无法下载仓库ZIP文件: {str(e)}")

    def analyze_code_structure(self, zf: zipfile.ZipFile) -> Dict[str, Any]:
        """分析代码结构"""
        py_files = []
        js_files = []
        java_files = []
        go_files = []
        ts_files = []
        cpp_files = []
        total_lines = 0
        long_lines = 0
        empty_lines = 0
        test_files = []

        # 常见测试文件模式
        test_patterns = ['test_', '_test', 'spec_', 'tests/', 'test/']

        for file_path in zf.namelist():
            # 跳过目录和隐藏文件
            if file_path.endswith('/'):
                continue

            file_ext = Path(file_path).suffix.lower()

            # 统计文件类型
            if file_ext == '.py':
                py_files.append(file_path)
            elif file_ext == '.js':
                js_files.append(file_path)
            elif file_ext == '.java':
                java_files.append(file_path)
            elif file_ext == '.go':
                go_files.append(file_path)
            elif file_ext == '.ts':
                ts_files.append(file_path)
            elif file_ext == '.cpp' or file_ext == '.cc' or file_ext == '.cxx':
                cpp_files.append(file_path)

            # 检查测试文件
            if any(pattern in file_path.lower() for pattern in test_patterns):
                test_files.append(file_path)

            # 分析代码行数和长行
            try:
                with zf.open(file_path) as f:
                    content = f.read().decode('utf-8', errors='ignore').splitlines()
                    total_lines += len(content)

                    # 统计空行和长行
                    for line in content:
                        if not line.strip():
                            empty_lines += 1
                        elif len(line.strip()) > 120:
                            long_lines += 1
            except:
                continue

        return {
            "python_files": len(py_files),
            "javascript_files": len(js_files),
            "java_files": len(java_files),
            "go_files": len(go_files),
            "typescript_files": len(ts_files),
            "cpp_files": len(cpp_files),
            "total_lines": total_lines,
            "long_lines": long_lines,
            "empty_lines": empty_lines,
            "test_files": len(test_files),
            "test_coverage_ratio": len(test_files) / max(
                len(py_files) + len(js_files) + len(java_files) + len(ts_files) + len(cpp_files), 1)
        }

    def analyze_repository_structure(self, zf: zipfile.ZipFile, repo_info: Dict[str, Any]) -> Dict[str, Any]:
        """分析仓库结构"""
        structure = {
            "has_readme": False,
            "has_license": False,
            "has_contributing": False,
            "has_code_of_conduct": False,
            "has_issue_template": False,
            "has_pr_template": False,
            "has_github_actions": False,
            "has_ci_config": False,
            "has_dockerfile": False,
            "has_makefile": False,
            "has_documentation": False,
            "requirements_files": [],
            "config_files": []
        }

        # 检查配置文件
        ci_files = ['.github/workflows/', 'travis.yml', 'circle.yml', 'jenkinsfile', '.gitlab-ci.yml']
        req_files = ['requirements.txt', 'package.json', 'pom.xml', 'go.mod', 'Gemfile', 'composer.json']
        config_files = ['.env', '..env.example', 'config.yml', 'config.yaml', 'config.json']
        doc_folders = ['docs/', 'doc/', 'documentation/', 'wiki/']

        for file_path in zf.namelist():
            file_lower = file_path.lower()

            # README 文件
            if 'readme' in file_lower and ('.md' in file_lower or '.rst' in file_lower or '.txt' in file_lower):
                structure["has_readme"] = True

            # 许可证文件
            if 'license' in file_lower or 'licence' in file_lower:
                structure["has_license"] = True

            # 贡献指南
            if 'contributing' in file_lower:
                structure["has_contributing"] = True

            # 行为准则
            if 'code_of_conduct' in file_lower or 'coc' in file_lower:
                structure["has_code_of_conduct"] = True

            # Issue 模板
            if 'issue_template' in file_lower or file_lower.startswith('.github/issue'):
                structure["has_issue_template"] = True

            # PR 模板
            if 'pull_request_template' in file_lower or file_lower.startswith('.github/pull'):
                structure["has_pr_template"] = True

            # GitHub Actions
            if '.github/workflows/' in file_lower:
                structure["has_github_actions"] = True

            # CI 配置
            if any(ci_file in file_lower for ci_file in ci_files):
                structure["has_ci_config"] = True

            # Dockerfile
            if 'dockerfile' in file_lower:
                structure["has_dockerfile"] = True

            # Makefile
            if 'makefile' in file_lower or 'makefile' == Path(file_path).name.lower():
                structure["has_makefile"] = True

            # 文档目录
            if any(doc_folder in file_lower for doc_folder in doc_folders):
                structure["has_documentation"] = True

            # 依赖文件
            if any(req_file in file_lower for req_file in req_files):
                structure["requirements_files"].append(file_path)

            # 配置文件
            if any(config_file in file_lower for config_file in config_files):
                structure["config_files"].append(file_path)

        return structure

    def strict_review(self, repo_info: Dict[str, Any], code_stats: Dict[str, Any],
                      structure: Dict[str, Any]) -> Dict[str, Any]:
        """执行严格的代码审查"""
        # 确保repo_info是一个字典而不是字符串
        if not isinstance(repo_info, dict):
            return {
                "status": "error",
                "message": "仓库信息格式错误",
            }

        if "error" in repo_info:
            return {
                "status": "error",
                "message": repo_info["error"],
            }

        logs = []
        score = 100
        deductions = []

        # Rule 1: License 检查
        if not repo_info.get("license"):
            logs.append("缺少 License 文件")
            deductions.append({"type": "license", "points": 15, "reason": "开源项目必须包含许可证"})
        else:
            logs.append(f"有 License: {repo_info['license'].get('name', 'Unknown') if isinstance(repo_info['license'], dict) else repo_info['license']}")

        # Rule 2: 项目描述
        if not repo_info.get("description"):
            logs.append("仓库缺少描述")
            deductions.append({"type": "description", "points": 10, "reason": "项目描述对用户很重要"})
        else:
            description = repo_info["description"]
            if len(description) < 20:
                logs.append("描述过于简短")
                deductions.append({"type": "description", "points": 5, "reason": "描述需要更详细"})
            else:
                logs.append("描述质量良好")

        # Rule 3: 社区活跃度
        stars = repo_info.get("stargazers_count", 0)
        forks = repo_info.get("forks_count", 0)
        watchers = repo_info.get("subscribers_count", 0)

        if stars < 10:
            logs.append(f"Star 数量偏少: {stars}")
            deductions.append({"type": "community", "points": 10, "reason": "项目关注度较低"})
        else:
            logs.append(f"Star 数量: {stars}")

        # Rule 4: 仓库状态
        if repo_info.get("archived"):
            logs.append("仓库已归档，不再维护")
            deductions.append({"type": "status", "points": 30, "reason": "归档项目不再维护"})

        if repo_info.get("disabled"):
            logs.append("仓库已被禁用")
            deductions.append({"type": "status", "points": 50, "reason": "禁用项目无法使用"})

        # Rule 5: 代码量
        if code_stats["total_lines"] < 100:
            logs.append(f"代码量不足（{code_stats['total_lines']} 行）")
            deductions.append({"type": "code_volume", "points": 15, "reason": "代码量太少，项目不够成熟"})
        else:
            logs.append(f"代码量充足: {code_stats['total_lines']} 行")

        # Rule 6: 长行检查
        long_line_ratio = code_stats["long_lines"] / max(code_stats["total_lines"] - code_stats["empty_lines"], 1)
        if long_line_ratio > 0.1:
            logs.append(f"长行比例过高: {long_line_ratio:.1%}")
            deductions.append({"type": "code_style", "points": 10, "reason": "代码行过长，影响可读性"})
        else:
            logs.append("代码行长度合理")

        # Rule 7: 测试覆盖率
        if code_stats["test_files"] == 0:
            logs.append("缺少测试文件")
            deductions.append({"type": "testing", "points": 20, "reason": "没有测试，质量难以保证"})
        else:
            test_ratio = code_stats["test_coverage_ratio"]
            if test_ratio < 0.1:
                logs.append(f"测试覆盖率较低: {test_ratio:.1%}")
                deductions.append({"type": "testing", "points": 10, "reason": "建议增加测试用例"})
            else:
                logs.append(f"测试覆盖率良好: {test_ratio:.1%}")

        # Rule 8: 项目结构
        if not structure["has_readme"]:
            logs.append("缺少 README")
            deductions.append({"type": "structure", "points": 15, "reason": "README 是项目的门面"})

        if not structure["has_license"]:
            logs.append("缺少 License")
            deductions.append({"type": "structure", "points": 10, "reason": "License 是开源项目的必备文件"})

        if structure["has_github_actions"]:
            logs.append("有 CI/CD 配置")
        else:
            logs.append("缺少 CI/CD 配置")
            deductions.append({"type": "ci", "points": 10, "reason": "CI/CD 有助于保证代码质量"})

        # Rule 9: 文档完整性
        if structure["has_documentation"]:
            logs.append("有专门的文档目录")
        else:
            logs.append("缺少文档目录")
            deductions.append({"type": "documentation", "points": 5, "reason": "建议添加文档目录"})

        # Rule 10: 配置文件
        if structure["config_files"]:
            logs.append(f"有配置文件: {len(structure['config_files'])} 个")
        else:
            logs.append("未发现配置文件")

        # Rule 11: Docker 支持
        if structure["has_dockerfile"]:
            logs.append("支持 Docker 部署")
        else:
            logs.append("不支持 Docker 部署")
            deductions.append({"type": "deployment", "points": 5, "reason": "建议添加 Docker 支持"})

        # Rule 12: 更新频率
        updated_at = repo_info.get("updated_at", "")
        if updated_at:
            try:
                updated_date = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                days_since_update = (datetime.now(timezone.utc) - updated_date).days

                if days_since_update > 365:
                    logs.append(f"长期未更新（{days_since_update} 天）")
                    deductions.append({"type": "maintenance", "points": 20, "reason": "项目长期未更新"})
                elif days_since_update > 180:
                    logs.append(f"更新间隔较长（{days_since_update} 天）")
                    deductions.append({"type": "maintenance", "points": 10, "reason": "建议保持定期更新"})
                elif days_since_update > 90:
                    logs.append(f"更新频率一般（{days_since_update} 天）")
                    deductions.append({"type": "maintenance", "points": 5, "reason": "建议保持定期更新"})
                else:
                    logs.append(f"更新积极（{days_since_update} 天前）")
            except Exception as e:
                logger.warning(f"无法解析更新时间: {str(e)}")
                logs.append("无法解析更新时间")

        # Rule 13: 社区参与
        if forks > 0:
            logs.append(f"有 {forks} 个 Fork")
        else:
            logs.append("没有 Fork")

        # 计算总分
        total_deduction = sum(d["points"] for d in deductions)
        score = max(100 - total_deduction, 0)

        return {
            "status": "ok",
            "repo": self.repo_name,
            "score": score,
            "max_score": 100,
            "deduction_details": deductions,
            "logs": logs,
            "code_stats": code_stats,
            "structure": structure,
            "repo_info": {
                "stars": stars,
                "forks": forks,
                "watchers": watchers,
                "language": repo_info.get("language", "Unknown"),
                "created_at": repo_info.get("created_at", ""),
                "updated_at": repo_info.get("updated_at", "")
            }
        }

    def default_evaluation(self) -> Dict[str, Any]:
        """
        当AI分析受限时，提供默认评估
        """
        logs = [
            "由于AI分析受限，启用默认评估模式",
            "项目基础结构符合标准要求",
            "无法进行深度代码质量分析",
            "缺少详细的测试覆盖信息",
            "缺少安全漏洞扫描",
            "缺少性能基准测试"
        ]
        
        deductions = [
            {"type": "analysis_limitation", "points": 20, "reason": "AI分析受限，无法进行全面评估"},
            {"type": "security", "points": 15, "reason": "缺少安全漏洞检测"},
            {"type": "testing", "points": 10, "reason": "缺少测试覆盖信息"},
            {"type": "performance", "points": 10, "reason": "缺少性能基准测试"}
        ]
        
        score = max(100 - sum(d["points"] for d in deductions), 0)
        
        return {
            "status": "limited",
            "repo": self.repo_name,
            "score": score,
            "max_score": 100,
            "deduction_details": deductions,
            "logs": logs,
            "evaluation_type": "default",
            "recommendation": "建议提供更多访问权限或使用本地分析以获得更全面的评估结果"
        }

    def analyze_repository(self) -> Dict[str, Any]:
        """主分析流程 - 支持本地路径优先"""
        try:
            # 1. 获取仓库信息（必须）
            repo_info = self.fetch_repo_info()
            if "error" in repo_info:
                # 如果无法获取仓库信息，则返回默认评估
                logger.warning("无法获取仓库信息，返回默认评估")
                return self.default_evaluation()

            # 2. 优先使用本地路径！
            local_path_to_use = None
            if self.local_path and os.path.exists(self.local_path):
                local_path_to_use = self.local_path
            # 如果local_path是仓库URL，检查是否对应本地路径存在
            elif os.path.exists(self.repo_url):
                local_path_to_use = self.repo_url
                
            if local_path_to_use:
                logger.info(f"CoStrict 直接使用本地路径分析（超快！）: {local_path_to_use}")
                code_stats = self._analyze_code_structure_local(local_path_to_use)
                structure = self._analyze_repository_structure_local(local_path_to_use)
            else:
                # 降级：下载 ZIP（原来逻辑）
                logger.info("未检测到本地仓库路径，降级使用 ZIP 下载")
                try:
                    zip_file = self.fetch_repo_zip()
                    code_stats = self.analyze_code_structure(zip_file)
                    structure = self.analyze_repository_structure(zip_file, repo_info)
                    # 关闭zip文件
                    zip_file.close()
                except Exception as e:
                    logger.error(f"ZIP文件处理失败: {str(e)}")
                    # 返回默认评估而不是基本分析结果
                    return self.default_evaluation()

            # 3. 执行严格审查
            result = self.strict_review(repo_info, code_stats, structure)
            return result

        except Exception as e:
            logger.error(f"CoStrict 分析失败: {str(e)}")
            # 返回默认评估而不是错误消息
            return self.default_evaluation()

    def _analyze_code_structure_local(self, root_path: str) -> Dict[str, Any]:
        """直接遍历本地目录分析代码结构"""
        py_files = js_files = java_files = go_files = ts_files = cpp_files = 0
        total_lines = long_lines = empty_lines = test_files = 0
        test_patterns = ['test_', '_test', 'spec_', 'tests/', 'test/']

        for current_dir, dirs, files in os.walk(root_path):
            # 跳过 .git 等目录
            dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', 'node_modules', '.venv', 'venv']]

            for file in files:
                file_path = os.path.join(current_dir, file)
                rel_path = os.path.relpath(file_path, root_path)
                ext = Path(file).suffix.lower()

                if ext == '.py':
                    py_files += 1
                elif ext == '.js':
                    js_files += 1
                elif ext == '.java':
                    java_files += 1
                elif ext == '.go':
                    go_files += 1
                elif ext == '.ts':
                    ts_files += 1
                elif ext in ['.cpp', '.cc', '.cxx', '.h', '.hpp']:
                    cpp_files += 1

                # 测试文件判断
                if any(p in rel_path.lower() for p in test_patterns):
                    test_files += 1

                # 行数统计
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                        total_lines += len(lines)
                        for line in lines:
                            stripped = line.strip()
                            if not stripped:
                                empty_lines += 1
                            elif len(stripped) > 120:
                                long_lines += 1
                except:
                    continue

        total_coded_files = max(py_files + js_files + java_files + go_files + ts_files + cpp_files, 1)
        return {
            "python_files": py_files,
            "javascript_files": js_files,
            "java_files": java_files,
            "go_files": go_files,
            "typescript_files": ts_files,
            "cpp_files": cpp_files,
            "total_lines": total_lines,
            "long_lines": long_lines,
            "empty_lines": empty_lines,
            "test_files": test_files,
            "test_coverage_ratio": test_files / total_coded_files
        }

    def _analyze_repository_structure_local(self, root_path: str) -> Dict[str, Any]:
        """本地路径分析项目结构检查"""
        structure = {
            "has_readme": False,
            "has_license": False,
            "has_contributing": False,
            "has_code_of_conduct": False,
            "has_issue_template": False,
            "has_pr_template": False,
            "has_github_actions": False,
            "has_ci_config": False,
            "has_dockerfile": False,
            "has_makefile": False,
            "has_documentation": False,
            "requirements_files": [],
            "config_files": []
        }

        root_path_obj = Path(root_path)
        if not root_path_obj.exists():
            return structure

        for file_path in root_path_obj.rglob("*"):
            if file_path.is_dir():
                continue
            name = file_path.name.lower()
            path_str = str(file_path).lower()

            if name.startswith('readme') or name in ['readme.md', 'readme.txt', 'readme.rst']:
                structure["has_readme"] = True
            if 'license' in name or 'licence' in name:
                structure["has_license"] = True
            if 'contributing' in name:
                structure["has_contributing"] = True
            if 'code_of_conduct' in name or 'coc' in name:
                structure["has_code_of_conduct"] = True
            if 'pull_request_template' in name or file_path.parts[-2:] == ('.github', 'pull_request_template.md'):
                structure["has_pr_template"] = True
            if file_path.parts[-3:-1] == ('.github', 'workflows'):
                structure["has_github_actions"] = True
            if name == 'dockerfile' or name.startswith('dockerfile.'):
                structure["has_dockerfile"] = True
            if name == 'makefile':
                structure["has_makefile"] = True

            # 文档目录
            if file_path.parts[0] in ['docs', 'doc', 'documentation']:
                structure["has_documentation"] = True

        # CI 文件检查（简化）
        ci_indicators = ['.github/workflows/', 'travis.yml', '.gitlab-ci.yml', 'jenkinsfile']
        if any(root_path_obj.joinpath(p).exists() for p in ci_indicators if '/' not in p):
            structure["has_ci_config"] = True
        if any(any(root_path_obj.joinpath(d).exists() for d in ['.github/workflows']) for _ in [0]):
            structure["has_github_actions"] = True

        return structure


def analyze_with_costrict(repo_url: str, local_path: Optional[str] = None) -> Dict[str, Any]:
    """
    使用 CoStrict 模式分析仓库（支持本地路径加速！）
    
    Args:
        repo_url: 仓库URL，支持GitHub和Gitee
        local_path: 本地仓库路径（可选）
    """
    try:
        # 修复URL解析问题
        if not repo_url.startswith(("http://", "https://")):
            # 如果不是完整URL，尝试构造完整URL
            if "gitee.com" in repo_url:
                repo_url = f"https://gitee.com/{repo_url}"
            elif "github.com" in repo_url:
                repo_url = f"https://github.com/{repo_url}"
            else:
                # 默认认为是Gitee仓库
                repo_url = f"https://gitee.com/{repo_url}"
        
        analyzer = CoStrictAnalyzer(repo_url, local_path=local_path)
        return analyzer.analyze_repository()
    except Exception as e:
        logger.error(f"CoStrict 建议生成失败: {str(e)}")
        # 即使在这个级别也返回默认评估
        return {
            "status": "limited", 
            "message": "分析受限，启用默认评估",
            "recommendation": "请参考问题描述和修复建议"
        }