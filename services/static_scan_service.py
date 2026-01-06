import os
import logging
import json
import asyncio
from typing import Dict, Any, List, Optional
import re

from app.core.config import settings
from utils.ai_client import AIClient
from utils.ai_provider_utils import get_available_provider
from utils.git_utils import GitUtils
from services.code_quality_service import CodeQualityService

logger = logging.getLogger(__name__)


def _load_static_scan_prompt() -> str:
    """读取静态扫描提示词文件"""
    prompt_path = os.path.join(os.path.dirname(__file__), '..', 'utils', 'prompts', 'static_scan.txt')
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        logger.warning(f"无法读取static_scan.txt提示词文件: {e}，使用默认提示词")
        return ""


class StaticScanner:
    """AI 驱动多语言静态扫描 - 支持AI提供商自动降级"""

    MAX_FILE_SIZE = settings.MAX_FILE_SIZE  # 单文件最大读取 30KB
    MAX_AI_RETRIES = settings.MAX_AI_RETRIES  # 重试次数
    EXCLUDE_DIRS = {".git", ".gitlab", ".bitbucket",  
                    ".circleci", ".travis", ".drone", 
                    "site", "dist", "build", "target", "out",  
                    "__pycache__", ".pyc",  
                    "venv", "env", ".venv",  
                    "node_modules", "vendor", "bower_components", 
                    ".idea", ".vscode", ".vs", ".project", ".settings", ".metadata", 
                    "tmp", "logs", "cache", ".cache", 
                    "images", "static", "public", "assets", "media", "img", "fonts"}  
    MAX_TOTAL_FILES = settings.MAX_TOTAL_FILES  # 最大文件数
    MAX_PROMPT_LEN = settings.MAX_PROMPT_LEN  # 提示词长度限制
    BATCH_DELAY = settings.BATCH_DELAY  # 批处理之间的延迟(秒)
    MAX_BATCH_CHARS = settings.MAX_BATCH_CHARS  # 每批最大字符数限制

    def __init__(self, ai_provider: Optional[str] = None):
        # 使用降级机制获取可用提供商
        self.repo_path: Optional[str] = None
        self.ai_provider = get_available_provider(ai_provider)
        # 在costrict模式下不创建AI客户端，因为不需要AI分析
        if self.ai_provider != "costrict":
            self.ai_client = AIClient(self.ai_provider)
            # 初始化代码质量服务（备用方案）
            self.code_quality_service = CodeQualityService(self.ai_client)
        else:
            self.ai_client = None
            self.code_quality_service = None
        logger.info(f"StaticScanner初始化完成，使用AI提供商: {self.ai_provider}")

    # 收集文件信息
    def _validate_repo_has_code(self, repo_path: str) -> bool:
        """
        验证仓库路径是否包含源代码
        """
        try:
            if not os.path.exists(repo_path) or not os.path.isdir(repo_path):
                return False

            # 使用配置中的最大文件数，确保验证和实际扫描一致
            validation_check_limit = min(100, self.MAX_TOTAL_FILES * 2)  # 检查更多文件以提高准确性
            has_code_file = False
            checked_count = 0

            # 扩展代码扩展名列表，支持更多语言
            code_extensions = {
                '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.go', '.rs',
                '.cpp', '.c', '.php', '.h', '.hpp', '.rb', '.kt', '.swift',
                '.html', '.css', '.vue', '.dart', '.sql', '.graphql'
            }
            for root, dirs, files in os.walk(repo_path):
                # 跳过排除的目录
                dirs[:] = [d for d in dirs if d not in self.EXCLUDE_DIRS]

                for file in files:
                    if checked_count >= validation_check_limit:
                        logger.debug(f"已检查 {checked_count} 个文件，验证完成")
                        return has_code_file

                    ext = os.path.splitext(file)[1].lower()
                    if ext in code_extensions:
                        has_code_file = True
                        # logger.debug(f"找到源代码文件: {os.path.join(root, file)}")
                    checked_count += 1

            if not has_code_file:
                logger.warning(f"仓库路径缺少源代码文件（已检查 {checked_count} 个文件）: {repo_path}")
            else:
                logger.debug(f"仓库包含源代码文件: {repo_path}")

            return has_code_file
        except Exception as e:
            logger.error(f"检查仓库代码失败: {e}")
            return False

    def _collect_repo_files(self, repo_path: str, primary_languages: Optional[List[str]] = None) -> List[
        Dict[str, Any]]:
        file_info_list = []
        # 扩展语言支持，包括全栈技术栈
        primary_extensions = {
            # 后端语言
            "Python": [".py"],
            "Java": [".java"],
            "Kotlin": [".kt", ".kts"],
            "Go": [".go"],
            "Rust": [".rs"],
            "C/C++": [".c", ".h", ".cpp", ".hpp", ".cc"],
            "PHP": [".php"],
            "Ruby": [".rb"],
            "C#": [".cs"],
            "Swift": [".swift"],
            "Objective-C": [".m", ".mm"],
            "JSP": [".jsp", ".jspx", ".jspf"],

            # 前端语言和框架
            "JavaScript": [".js", ".jsx"],
            "TypeScript": [".ts", ".tsx"],
            "HTML": [".html", ".htm"],
            "CSS": [".css", ".scss", ".sass", ".less"],
            "Vue": [".vue"],
            "Svelte": [".svelte"],
            "Angular": [".component.ts", ".component.html", ".component.css"],

            # 移动端
            "ReactNative": [".tsx", ".ts", ".jsx", ".js"],
            "Flutter": [".dart"],

            # 数据相关
            "SQL": [".sql"],
            "GraphQL": [".graphql", ".gql"],

            # 配置和构建
            "Configuration": [".json", ".yaml", ".yml", ".ini", ".env", ".toml", ".cfg", ".conf", ".xml"],
            "Build": ["dockerfile", ".dockerignore", "makefile", "cmakelists.txt", "package.json", "gradle", "pom.xml"],
            "Documentation": [".md", ".rst", ".txt"],

            # 其他
            "Other": [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".zip", ".rar", ".7z", ".ipynb"]
        }

        logger.debug(f"开始收集文件，仓库路径: {repo_path}")
        logger.debug(f"排除目录: {self.EXCLUDE_DIRS}")

        # 首先检查repo_path是否存在
        if not os.path.exists(repo_path):
            logger.error(f"仓库路径不存在: {repo_path}")
            return []

        # 检查repo_path是否是目录
        if not os.path.isdir(repo_path):
            logger.error(f"仓库路径不是目录: {repo_path}")
            return []

        # 验证仓库路径是否确实包含源代码
        if not self._validate_repo_has_code(repo_path):
            logger.error(f"仓库路径不包含源代码（可能只有.git目录）: {repo_path}")
            return []

        # 列出repo_path下的内容用于调试
        try:
            root_items = os.listdir(repo_path)
            logger.debug(f"仓库根目录内容: {root_items[:20]}")  # 只显示前20项
        except Exception as e:
            logger.error(f"无法列出仓库根目录: {e}")
            return []

        for root, dirs, files in os.walk(repo_path):
            # 排除不必要目录
            original_dirs = dirs.copy()
            dirs[:] = [d for d in dirs if d not in self.EXCLUDE_DIRS]

            # 记录被排除的目录
            excluded = set(original_dirs) - set(dirs)
            if excluded and root == repo_path:
                logger.debug(f"根目录中已排除: {excluded}")

            for f in files:
                file_path = os.path.join(root, f)
                try:
                    rel_path = os.path.relpath(file_path, repo_path).replace("\\", "/")

                    # 检查是否在排除目录中
                    if any(exclude_dir in rel_path.split('/') for exclude_dir in self.EXCLUDE_DIRS):
                        continue

                    ext = os.path.splitext(f)[1].lower()
                    size = os.path.getsize(file_path)

                    # 如果指定了主语言，智能收集相关文件
                    if primary_languages:
                        # 检查是否是已知主语言的扩展名
                        known_languages = []
                        unknown_languages = []

                        for lang in primary_languages:
                            if lang in primary_extensions:
                                known_languages.append(lang)
                            else:
                                unknown_languages.append(lang)

                        # 如果有未知语言，收集所有文件（让AI处理）
                        if unknown_languages:
                            logger.info(
                                f"检测到未完全支持的语言: {unknown_languages}，收集所有文件以支持全栈分析")
                        else:
                            allowed = any(ext in primary_extensions.get(lang, []) for lang in primary_languages)
                            if not allowed:
                                continue

                    # 读取文件内容（最多 MAX_FILE_SIZE）
                    snippet = ""
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as fp:
                        if size <= self.MAX_FILE_SIZE:
                            snippet = fp.read()
                        else:
                            snippet = fp.read(self.MAX_FILE_SIZE)

                    file_info_list.append({
                        "path": rel_path,
                        "size": size,
                        "content": snippet,
                        "lines": snippet.count("\n") + 1 if snippet else 0
                    })
                except Exception as e:
                    logger.warning(f"收集文件 {file_path} 时出错: {e}")

        # 限制最大扫描文件数量（避免大仓库超时）
        if len(file_info_list) > self.MAX_TOTAL_FILES:
            logger.warning(f"仓库文件过多（{len(file_info_list)} 个），仅分析前 {self.MAX_TOTAL_FILES} 个文件")
            file_info_list = file_info_list[:self.MAX_TOTAL_FILES]

        logger.debug(f"共收集 {len(file_info_list)} 个文件用于 AI 分析")
        if len(file_info_list) == 0:
            logger.warning(f"未能收集到任何文件！检查路径: {repo_path}")
        return file_info_list

    # 检测仓库语言
    def _detect_languages(self, file_info_list: List[Dict[str, Any]]) -> List[str]:
        """
        语言检测：基于扩展名映射 + 文件数量与大小加权评分
        更准确识别项目主要语言
        """
        ext_lang_map = {
            ".py": "Python",
            ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
            ".ts": "TypeScript", ".tsx": "TypeScript",
            ".java": "Java",
            ".kt": "Kotlin",
            ".go": "Go",
            ".rs": "Rust",
            ".c": "C/C++", ".h": "C/C++", ".cpp": "C/C++", ".hpp": "C/C++", ".cc": "C/C++",
            ".php": "PHP",
            ".rb": "Ruby",
            ".swift": "Swift",
            ".m": "Objective-C", ".mm": "Objective-C",
            ".cs": "C#",
            ".md": "Documentation", ".rst": "Documentation", ".txt": "Documentation",
            ".json": "Configuration", ".yaml": "Configuration", ".yml": "Configuration",
            ".ini": "Configuration", ".env": "Configuration", ".toml": "Configuration", ".cfg": "Configuration",
        }

        # 为不同语言设定优先级权重（越高越重要）
        language_weight = {
            "Python": 1.5,
            "JavaScript": 1.4,
            "TypeScript": 1.4,
            "Java": 1.3,
            "Go": 1.2,
            "C#": 1.2,
            "C/C++": 1.2,
            "Rust": 1.1,
            "Kotlin": 1.1,
            "PHP": 1.0,
            "Ruby": 1.0,
            "Swift": 1.0,
            "Objective-C": 1.0,
        }

        scores = {}

        for f in file_info_list:
            path = f["path"]
            basename = os.path.basename(path).lower()
            ext = os.path.splitext(path)[1].lower()

            # 判断是否为核心构建文件
            if basename in ["dockerfile", "makefile", "cmakelists.txt"]:
                lang = "Build"
            else:
                # 从扩展名映射语言
                lang = ext_lang_map.get(ext)
                if not lang:
                    continue  # 忽略无法识别的语言

            if lang not in scores:
                scores[lang] = {"count": 0, "size": 0, "score": 0.0}

            count_score = 1
            size_score = f.get("size", 0) / 1024  # KB 单位
            weight = language_weight.get(lang, 1.0)

            scores[lang]["count"] += count_score
            scores[lang]["size"] += size_score
            scores[lang]["score"] += (count_score * 10 + size_score) * weight  # 加权综合得分

        # 按综合得分排序
        sorted_languages = sorted(scores.items(), key=lambda x: x[1]["score"], reverse=True)

        # 取前5个作为主要语言
        primary_languages = [lang for lang, _ in sorted_languages[:5]]
        logger.debug(f"各语言评分详情: {scores}")
        logger.debug(f"主要语言（按得分排序）: {primary_languages}")

        return primary_languages

    # 构建 AI 提示词

    def _build_ai_prompt(self, repo_structure: Dict[str, Any],
                         languages_found: List[str],
                         file_info_batch: List[Dict[str, Any]],
                         max_lines_per_file: int = 10,
                         max_chars_per_file: int = 500) -> str:

        truncated_files = []
        for f in file_info_batch:
            snippet = f.get("content_snippet", "")
            lines = snippet.splitlines()
            if len(lines) > max_lines_per_file:
                lines = lines[:max_lines_per_file]
            snippet_truncated = "\n".join(lines)
            if len(snippet_truncated) > max_chars_per_file:
                snippet_truncated = snippet_truncated[:max_chars_per_file]
            truncated_files.append({
                "file_path": f["file_path"],
                "size": f.get("size", 0),
                "content_snippet": snippet_truncated,
                "lines": len(lines)
            })

        # 紧凑JSON序列化，减少空格
        repo_structure_str = json.dumps(repo_structure, ensure_ascii=False, separators=(',', ':'))
        languages_found_str = json.dumps(languages_found, ensure_ascii=False, separators=(',', ':'))
        truncated_files_str = json.dumps(truncated_files, ensure_ascii=False, separators=(',', ':'))

        # 从文件读取提示词模板
        template = _load_static_scan_prompt()
        if not template:
            # 如果文件读取失败，使用默认提示词
            template = """你是一个专业的代码质量分析专家。请分析以下代码仓库，找出代码中的问题。
输入数据：
- 仓库结构: {REPO_STRUCTURE}
- 检测到的语言: {LANGUAGES}
- 文件内容片段: {FILE_CONTENTS}
请以JSON格式输出分析结果。"""

        # 替换占位符
        prompt = template.replace("{REPO_STRUCTURE}", repo_structure_str)
        prompt = prompt.replace("{LANGUAGES}", languages_found_str)
        prompt = prompt.replace("{FILE_CONTENTS}", truncated_files_str)

        logger.debug(f"构建 AI 提示词长度: {len(prompt)} 字符")

        # 限制 prompt 最大长度（DeepSeek最佳 < 12000 字符）
        if len(prompt) > self.MAX_PROMPT_LEN:
            logger.warning(f"Prompt 长度 {len(prompt)} 超限，自动截断为 {self.MAX_PROMPT_LEN}")
            prompt = prompt[:self.MAX_PROMPT_LEN]

        return prompt

    # 清理 AI 响应，去掉 ```json 包裹符

    def _clean_ai_json_response(self, ai_response: str) -> str:
        s = ai_response.strip()
        s = re.sub(r"^```json\s*|\s*```$", "", s, flags=re.MULTILINE)
        s = re.sub(r"^```", "", s)
        s = re.sub(r"```$", "", s)
        return s.strip()

    # 解析AI响应，处理各种格式

    def _parse_ai_response(self, ai_response: str) -> Dict[str, Any]:
        """
        正确解析AI的静态分析结果
        """
        if not ai_response or not ai_response.strip():
            logger.warning("收到空的AI响应")
            return self._create_empty_scan_result()

        try:
            # 清理响应
            cleaned = self._clean_ai_json_response(ai_response)
            if not cleaned:
                logger.warning("清理后AI响应为空")
                return self._create_empty_scan_result()

            parsed = json.loads(cleaned)

            if isinstance(parsed, dict):
                # 确保包含所有必要的字段
                return self._normalize_scan_result(parsed)
            else:
                logger.warning(f"AI返回的不是字典格式, 实际类型: {type(parsed)}")
                return self._create_empty_scan_result()

        except json.JSONDecodeError as e:
            logger.error(f"解析AI响应JSON失败: {str(e)}\n原始响应预览: {ai_response[:500]}...", exc_info=True)
            return self._create_empty_scan_result()
        except Exception as e:
            logger.error(f"解析AI响应时发生未预期错误: {str(e)}", exc_info=True)
            return self._create_empty_scan_result()

    def _create_empty_scan_result(self) -> Dict[str, Any]:
        """创建空的扫描结果结构"""
        return {
            "summary": {
                "total_files": 0,
                "languages": [],
                "overall_quality_score": 0,
                "critical_issues": 0,
                "high_risk_issues": 0,
                "medium_risk_issues": 0,
                "low_risk_issues": 0,
                "info_issues": 0
            },
            "issues_by_language": {},
            "detailed_issues": [],
            "language_specific_insights": {},
            "recommendations": [],
            "scan_status": "failed"
        }

    def _normalize_scan_result(self, raw_result: Dict[str, Any]) -> Dict[str, Any]:
        """标准化扫描结果结构"""
        normalized = self._create_empty_scan_result()
        normalized["scan_status"] = "success"

        # 合并summary
        if "summary" in raw_result and isinstance(raw_result["summary"], dict):
            normalized["summary"].update(raw_result["summary"])

        # 处理详细问题
        if "detailed_issues" in raw_result and isinstance(raw_result["detailed_issues"], list):
            normalized["detailed_issues"] = raw_result["detailed_issues"]

        # 处理语言特定问题
        if "issues_by_language" in raw_result and isinstance(raw_result["issues_by_language"], dict):
            normalized["issues_by_language"] = raw_result["issues_by_language"]

        # 处理建议
        if "recommendations" in raw_result and isinstance(raw_result["recommendations"], list):
            normalized["recommendations"] = raw_result["recommendations"]
        elif "recommendation" in raw_result:  # 兼容单数形式
            normalized["recommendations"] = [raw_result["recommendation"]]

        # 处理语言洞察
        if "language_specific_insights" in raw_result:
            normalized["language_specific_insights"] = raw_result["language_specific_insights"]

        return normalized

    # 分批调用 AI

    async def _run_ai_in_batches(self, repo_structure: Dict[str, Any],
                                 languages_found: List[str],
                                 file_info_list: List[Dict[str, Any]], progress_callback=None):

        logger.info(f"开始修复版AI分析，文件总数: {len(file_info_list)}")

        # 初始化完整结果结构
        all_results = {
            "scans": {
                "ai_static_scan": self._create_empty_scan_result()
            }
        }

        if not file_info_list:
            logger.warning("没有文件需要分析")
            return all_results

        # 动态分批处理
        current_batch = []
        current_batch_chars = 0
        batch_num = 1
        total_issues_found = 0
        total_files = len(file_info_list)

        for i, file_info in enumerate(file_info_list):
            file_content = file_info.get("content", "")
            file_content_length = len(file_content)

            # 检查是否开始新批次
            if current_batch and (current_batch_chars + file_content_length > self.MAX_BATCH_CHARS):
                logger.info(f"处理批次 {batch_num}, 文件数: {len(current_batch)}, 字符数: {current_batch_chars}")

                # 更新进度
                if progress_callback:
                    progress = 75 + int(20 * (i / total_files))  # 静态扫描占20%进度，从75%开始
                    await progress_callback(progress, f"正在处理第 {batch_num} 批次代码文件...")

                # 处理当前批次
                batch_result = await self._process_single_batch(
                    repo_structure, languages_found, current_batch, batch_num
                )

                # 合并结果
                self._merge_batch_results(all_results["scans"]["ai_static_scan"], batch_result)
                # 累加当前批次发现的问题数
                current_batch_issues = len(batch_result.get("detailed_issues", []))
                logger.info(f"[批次 {batch_num}] 发现问题: {current_batch_issues} 个")
                total_issues_found += current_batch_issues

                # 批次间延迟，避免API压力
                await asyncio.sleep(self.BATCH_DELAY)

                # 重置批次
                current_batch = [file_info]
                current_batch_chars = file_content_length
                batch_num += 1
            else:
                current_batch.append(file_info)
                current_batch_chars += file_content_length

        # 处理最后一个批次
        if current_batch:
            logger.info(f"处理最后批次 {batch_num}, 文件数: {len(current_batch)}, 字符数: {current_batch_chars}")
            if progress_callback:
                progress = 75 + int(20 * (len(file_info_list) / total_files))  # 静态扫描占20%进度
                await progress_callback(progress, f"正在处理最后批次代码文件...")
            batch_result = await self._process_single_batch(
                repo_structure, languages_found, current_batch, batch_num
            )
            self._merge_batch_results(all_results["scans"]["ai_static_scan"], batch_result)
            # 累加最后批次发现的问题数
            current_batch_issues = len(batch_result.get("detailed_issues", []))
            logger.info(f"[批次 {batch_num}] 发现问题: {current_batch_issues} 个")
            total_issues_found += current_batch_issues

        logger.info(f"AI静态分析完成，总共发现 {total_issues_found} 个问题")
        return all_results

    async def _process_single_batch(self, repo_structure: Dict[str, Any],
                                    languages_found: List[str],
                                    file_batch: List[Dict[str, Any]],
                                    batch_num: int) -> Dict[str, Any]:
        """处理单个批次的分析"""
        try:
            # 转换文件格式
            transformed_batch = []
            for f in file_batch:
                transformed_batch.append({
                    "file_path": f.get("path", ""),
                    "size": f.get("size", 0),
                    "content_snippet": f.get("content", ""),
                    "lines": f.get("lines", 0)
                })

            # 构建AI输入
            batch_repo_data = {
                "repo_info": {"languages_detected": languages_found},
                "repo_structure": repo_structure,
                "files": transformed_batch,
                "platform": self.ai_provider
            }

            # 如果是costrict模式，直接返回空结果，不进行AI分析
            if self.ai_provider == "costrict":
                logger.info(f"[批次 {batch_num}] CoStrict模式：跳过AI静态扫描，返回空结果")
                return self._create_empty_scan_result()

            # 调用AI分析
            for attempt in range(self.MAX_AI_RETRIES):
                try:
                    logger.info(f"[批次 {batch_num}] 第 {attempt + 1} 次尝试调用AI...")

                    # 方案1：使用静态分析专用提示词进行真实静态扫描
                    prompt = self._build_ai_prompt(repo_structure, languages_found, transformed_batch)
                    ai_response_text = await self.ai_client.chat(prompt)
                    parsed_result = self._parse_ai_response(ai_response_text)

                    if parsed_result and parsed_result.get("scan_status") == "success":
                        logger.info(
                            f"[批次 {batch_num}] 静态分析成功，发现问题: {len(parsed_result.get('detailed_issues', []))} 个")
                        return parsed_result
                    else:
                        logger.warning(f"[批次 {batch_num}] 静态分析返回空结果，尝试备用方案")

                    # 备用方案，使用代码质量分析（安全漏洞和代码规范）
                    if self.code_quality_service:
                        ai_response_dict = await self.code_quality_service.analyze_code_quality(batch_repo_data)
                        if ai_response_dict and isinstance(ai_response_dict, dict):
                            parsed_result = self._extract_static_scan_from_ai_response(ai_response_dict)
                            logger.info(
                                f"[批次 {batch_num}] 备用方案提取问题: {len(parsed_result.get('detailed_issues', []))} 个")
                            return parsed_result
                        else:
                            logger.warning(f"[批次 {batch_num}] 备用方案也返回空响应")
                    else:
                        logger.warning(f"[批次 {batch_num}] 代码质量服务不可用（costrict模式）")

                except Exception as e:
                    logger.error(f"[批次 {batch_num}] AI调用异常 (第 {attempt + 1} 次尝试): {str(e)}", exc_info=True)
                    if attempt == self.MAX_AI_RETRIES - 1:
                        logger.error(f"[批次 {batch_num}] 所有重试失败", exc_info=True)

            return self._create_empty_scan_result()

        except Exception as e:
            logger.error(f"[批次 {batch_num}] 处理批次时发生未预期错误: {str(e)}", exc_info=True)
            return self._create_empty_scan_result()

    def _extract_static_scan_from_ai_response(self, ai_response_dict: Dict[str, Any]) -> Dict[str, Any]:
        """从AI返回的字典中提取静态扫描结果"""
        static_scan_result = self._create_empty_scan_result()

        # 记录响应字典的键
        # logger.info(f"[提取静态扫描] ai_response_dict 键: {list(ai_response_dict.keys())}")

        # 兼容不同AI响应结构：从根级别或code_quality字段获取安全问题
        security_issues = []
        if "security_issues" in ai_response_dict:
            security_issues = ai_response_dict.get("security_issues", [])
        elif "code_quality" in ai_response_dict:
            # 有些AI响应将security_issues放在code_quality字段内
            code_quality = ai_response_dict.get("code_quality", {})
            security_issues = code_quality.get("security_issues", [])

        # 转换为静态扫描的格式
        detailed_issues = []
        if not isinstance(security_issues, list):
            security_issues = []

        for idx, sec_issue in enumerate(security_issues):
            if isinstance(sec_issue, dict):
                # 提取文件名和行号
                location = sec_issue.get("location", "") if isinstance(sec_issue, dict) else ""
                file_path = location.split(":")[0] if ":" in location else "unknown"
                line_number = 0
            if ":" in location:
                line_part = location.split(":")[1]
                # 使用正则表达式提取第一个数字作为行号
                numbers = re.findall(r'\d+', line_part)
                if numbers:
                    line_number = int(numbers[0])
                else:
                    line_number = 0
            # 如果没有冒号，尝试从整个location中提取数字
            else:
                numbers = re.findall(r'\d+', location)
                if numbers:
                    line_number = int(numbers[0])

            # 转换严重性（中文->英文）
            if isinstance(sec_issue, dict):
                chinese_severity = sec_issue.get("severity", "低")
            else:
                chinese_severity = "低"
            severity_map = {"高": "high", "中": "medium", "低": "low"}
            severity = severity_map.get(chinese_severity, "low")

            # 构建问题描述
            if isinstance(sec_issue, dict):
                title = sec_issue.get('title', '')
                analysis = sec_issue.get('analysis', '')
                issue_type = sec_issue.get('type', '')
                issue_code = sec_issue.get('issue_code', '')  # 问题代码片段
                fix_code = sec_issue.get('fix_code', '')  # 修复代码片段

                is_valid_issue = True

                # 进一步验证：检查是否为虚构的文件路径
                if file_path and file_path != "unknown" and \
                        not any(ext in file_path.lower() for ext in
                                ['.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs', '.cpp', '.c', '.php',
                                 '.rb', '.kt', '.swift', '.html', '.css', '.vue', '.dart', '.sql', '.graphql', '.json',
                                 '.yaml', '.yml', '.xml', '.md', '.txt', '.dockerfile', '.dockerignore', '.makefile',
                                 '.cmake', '.ini', '.cfg', '.conf', '.toml', '.properties', '.lua', '.perl', '.pl',
                                 '.r', '.dart', '.groovy', '.vbs', '.vba', '.asm', '.s', '.svg', '.plist', '.xsd',
                                 '.xsl', '.xhtml', '.shtml', '.tmpl', '.tpl', '.erb', '.haml', '.slim', '.jade', '.pug',
                                 '.styl', '.sass', '.scss', '.less', '.coffee', '.litcoffee', '.vue', '.svelte', '.elm',
                                 '.erl', '.hrl', '.ex', '.exs', '.clj', '.cljs', '.cljc', '.edn', '.fs', '.fsi', '.fsx',
                                 '.fsscript', '.hs', '.lhs', '.ml', '.mli', '.mll', '.mly', '.hx', '.hxml', '.d', '.di',
                                 '.pde', '.wxs', '.wxl', '.xib', '.storyboard', '.pbxproj', '.lock', '.ipynb']):
                    # 如果文件路径没有常见扩展名，可能为虚构
                    logger.debug(f"安全问题文件路径可能为虚构: {file_path}")
                    is_valid_issue = False

                if title or analysis:
                    issue_text = f"{title} - {analysis}".strip(" -")
                elif issue_type:
                    issue_text = issue_type
                else:
                    issue_text = "安全问题"
                recommendation = sec_issue.get("recommendation", "")
            else:
                issue_text = "安全问题"
                recommendation = ""
                issue_type = ""
                is_valid_issue = False

            # 只有验证为有效的问题才添加到结果中
            if is_valid_issue:
                # 额外验证：检查是否为不合理的项目配置问题
                is_reasonable_issue = True

                # 检查是否为对空文件的不合理配置问题报告
                if ("__init__.py" in file_path and
                        issue_type == "项目配置" and
                        ("CI/CD" in issue_text or "测试配置" in issue_text or "配置文件" in issue_text)):
                    logger.debug(f"跳过对空__init__.py文件的不合理配置问题: {issue_text}")
                    is_reasonable_issue = False

                if ("项目配置" == issue_type and
                        any(keyword in issue_text for keyword in ["缺少", "没有", "未发现"]) and
                        any(keyword in file_path for keyword in [".py", ".js", ".java"])):
                    logger.debug(f"跳过位置与问题类型不符的问题: {issue_text} in {file_path}")
                    is_reasonable_issue = False
                if is_reasonable_issue:
                    static_issue = {
                        "file": file_path,
                        "line": line_number,
                        "issue": issue_text,
                        "severity": severity,
                        "recommendation": recommendation,
                        "type": issue_type,  # 保留原始类型信息，用于安全判断
                        "title": title if isinstance(sec_issue, dict) else "",
                        "analysis": analysis if isinstance(sec_issue, dict) else "",
                        "issue_code": issue_code,  # 保留原始代码片段
                        "fix_code": fix_code  # 保留修复代码片段
                    }
                    detailed_issues.append(static_issue)
                else:
                    logger.debug(f"跳过不合理的问题: {issue_text}")
            else:
                logger.debug(f"跳过可能虚构的问题: {title if isinstance(sec_issue, dict) else 'Unknown'}")

        # 记录提取结果
        if detailed_issues:
            logger.info(f"提取到 {len(detailed_issues)} 个安全问题，第一个问题内容: {detailed_issues[0]}")
        else:
            logger.info("未提取到任何安全问题，security_issues 可能为空或格式不符")

        # 尝试从code_standards中提取问题，过滤泛化描述，保留具体问题
        code_standards = []
        if "code_standards" in ai_response_dict:
            code_standards = ai_response_dict.get("code_standards", [])
        elif "code_quality" in ai_response_dict:
            code_quality = ai_response_dict.get("code_quality", {})
            code_standards = code_quality.get("code_standards", [])

        if isinstance(code_standards, list) and code_standards:
            # 过滤掉空字符串和过于泛化的描述
            valid_standards = []
            generic_patterns = [
                "代码风格统一", "代码风格一致", "模块划分合理",
                "模块化设计良好", "部分函数缺少文档字符串",
                "部分函数缺少类型注解", "代码风格符合PEP 8",
                "模块化设计良好", "异常处理机制完善", "测试覆盖率高",
                "API设计清晰", "代码风格符合PEP 8规范"
            ]
            for standard in code_standards:
                if isinstance(standard, str) and standard.strip():
                    # 如果标准过于泛化，则跳过
                    if any(pattern in standard for pattern in generic_patterns):
                        continue
                    valid_standards.append(standard.strip())

            if valid_standards:
                # 去重
                unique_standards = list(dict.fromkeys(valid_standards))
                # 合并为一个字符串，限制长度
                combined = "；".join(unique_standards[:10])
                if len(combined) > 200:
                    combined = combined[:197] + "..."
                detailed_issues.append({
                    "file": "全局",
                    "line": 0,
                    "issue": f"代码规范问题: {combined}",
                    "severity": "low",
                    "recommendation": "请根据具体问题改进代码"
                })
            else:
                pass

        static_scan_result["detailed_issues"] = detailed_issues
        static_scan_result["scan_status"] = "success"

        # 更新summary统计
        summary = static_scan_result["summary"]
        summary["total_files"] = len(detailed_issues) if detailed_issues else 1

        # 获取质量分数
        score = 70
        if "score" in ai_response_dict:
            score = ai_response_dict.get("score", 70)
        elif "code_quality" in ai_response_dict:
            code_quality = ai_response_dict.get("code_quality", {})
            score = code_quality.get("score", 70)
        summary["overall_quality_score"] = score

        # 统计问题数量
        severity_count = {"critical_issues": 0, "high_risk_issues": 0, "medium_risk_issues": 0, "low_risk_issues": 0}
        for issue in detailed_issues:
            severity = issue.get("severity", "low")
            if severity == "high":
                severity_count["high_risk_issues"] += 1
            elif severity == "medium":
                severity_count["medium_risk_issues"] += 1
            elif severity == "low":
                severity_count["low_risk_issues"] += 1

        summary.update(severity_count)

        return static_scan_result

    def _merge_batch_results(self, main_result: Dict[str, Any], batch_result: Dict[str, Any]):
        """正确合并批次扫描结果，并去重"""
        if not batch_result or batch_result.get("scan_status") != "success":
            return

        # 合并详细问题（带去重和验证）
        batch_issues = batch_result.get("detailed_issues", [])
        main_issues = main_result.get("detailed_issues", [])

        # 使用字典去重，key为 file+issue+line
        seen_issues = {}

        # 先添加已有的主批次问题（已验证过的）
        for issue in main_issues:
            key = f"{issue.get('file', '')}:{issue.get('line', 0)}:{issue.get('issue', '')}"
            seen_issues[key] = issue

        # 添加新批次问题（如果不存在且通过验证）
        for issue in batch_issues:
            # 验证问题是否真实有效
            file_path = issue.get('file', '')
            line_number = issue.get('line', 0)

            # 检查文件路径是否合理
            is_valid_issue = True
            if file_path and file_path != "unknown" and file_path != "全局":
                # 检查文件路径是否包含有效扩展名
                has_valid_extension = any(ext in file_path.lower() for ext in
                                          ['.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs', '.cpp', '.c',
                                           '.php', '.rb', '.kt', '.swift', '.html', '.css', '.vue', '.dart', '.sql',
                                           '.graphql', '.json', '.yaml', '.yml', '.xml', '.md', '.txt', '.dockerfile',
                                           '.dockerignore', '.makefile', '.cmake', '.ini', '.cfg', '.conf', '.toml',
                                           '.properties', '.lua', '.perl', '.pl', '.r', '.dart', '.groovy', '.vbs',
                                           '.vba', '.asm', '.s', '.svg', '.plist', '.xsd', '.xsl', '.xhtml', '.shtml',
                                           '.tmpl', '.tpl', '.erb', '.haml', '.slim', '.jade', '.pug', '.styl', '.sass',
                                           '.scss', '.less', '.coffee', '.litcoffee', '.vue', '.svelte', '.elm', '.erl',
                                           '.hrl', '.ex', '.exs', '.clj', '.cljs', '.cljc', '.edn', '.fs', '.fsi',
                                           '.fsx', '.fsscript', '.hs', '.lhs', '.ml', '.mli', '.mll', '.mly', '.hx',
                                           '.hxml', '.d', '.di', '.pde', '.wxs', '.wxl', '.xib', '.storyboard',
                                           '.pbxproj', '.lock', '.ipynb'])

                if not has_valid_extension:
                    # 如果没有有效扩展名，检查是否是合理的文件名
                    filename = file_path.split('/')[-1].split('\\')[-1]  # 获取文件名部分
                    if not any(ext in filename.lower() for ext in
                               ['.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs', '.cpp', '.c', '.php', '.rb',
                                '.kt', '.swift', '.html', '.css', '.vue', '.dart', '.sql', '.graphql', '.json', '.yaml',
                                '.yml', '.xml', '.md', '.txt', '.dockerfile', '.dockerignore', '.makefile', '.cmake',
                                '.ini', '.cfg', '.conf', '.toml', '.properties', '.lua', '.perl', '.pl', '.r', '.dart',
                                '.groovy', '.vbs', '.vba', '.asm', '.s', '.svg', '.plist', '.xsd', '.xsl', '.xhtml',
                                '.shtml', '.tmpl', '.tpl', '.erb', '.haml', '.slim', '.jade', '.pug', '.styl', '.sass',
                                '.scss', '.less', '.coffee', '.litcoffee', '.vue', '.svelte', '.elm', '.erl', '.hrl',
                                '.ex', '.exs', '.clj', '.cljs', '.cljc', '.edn', '.fs', '.fsi', '.fsx', '.fsscript',
                                '.hs', '.lhs', '.ml', '.mli', '.mll', '.mly', '.hx', '.hxml', '.d', '.di', '.pde',
                                '.wxs', '.wxl', '.xib', '.storyboard', '.pbxproj', '.lock', '.ipynb']):
                        is_valid_issue = False



            # 检查行号是否有效（非负整数，除非是全局问题）
            if line_number is not None and line_number != 0 and (not isinstance(line_number, int) or line_number < 0):
                is_valid_issue = False

            if not is_valid_issue:
                continue

            key = f"{issue.get('file', '')}:{issue.get('line', 0)}:{issue.get('issue', '')}"
            if key not in seen_issues:
                seen_issues[key] = issue

        # 转换回列表
        main_result["detailed_issues"] = list(seen_issues.values())

        # 合并建议（带去重）
        batch_recommendations = batch_result.get("recommendations", [])
        main_recommendations = main_result.get("recommendations", [])

        seen_recs = set()
        for rec in main_recommendations:
            if isinstance(rec, str):
                seen_recs.add(rec[:100])  # 使用前100个字符作为去重key

        for rec in batch_recommendations:
            if isinstance(rec, str):
                rec_key = rec[:100]

                if rec_key not in seen_recs:
                    main_recommendations.append(rec)
                    seen_recs.add(rec_key)
                    logger.debug(f"添加新建议: {rec_key}")
                else:
                    logger.debug(f"跳过重复建议: {rec_key}")

        main_result["recommendations"] = main_recommendations

        # 更新统计信息
        main_summary = main_result.get("summary", {})
        batch_summary = batch_result.get("summary", {})

        # 重新计算问题数量（基于去重后的详细问题列表）
        main_issues = main_result.get("detailed_issues", [])
        severity_count = {
            "critical_issues": 0,
            "high_risk_issues": 0,
            "medium_risk_issues": 0,
            "low_risk_issues": 0,
            "info_issues": 0
        }

        for issue in main_issues:
            severity = issue.get("severity", "info")
            if severity in severity_count:
                severity_count[severity] += 1

        # 使用去重后的计数
        for severity in severity_count:
            main_summary[severity] = severity_count[severity]

        # 统计问题总数
        main_summary["total_issues"] = len(main_issues)

        # 标记扫描成功
        main_result["scan_status"] = "success"

    def _calculate_project_protection_level(self, repo_info: Dict[str, Any] = None) -> tuple:
        """
        计算项目的保护等级和评分保护因子
        """
        if not repo_info:
            return 0, 30, 50 

        stars = repo_info.get("stars", 0)
        forks = repo_info.get("forks", 0)

        if stars > 10000 or (stars > 5000 and forks > 2000):
            return 3, 75, 20  # 顶级保护：最低75分，最多扣20分

        # 知名项目：stars > 5000 或 (stars > 1000 且 forks > 500)
        if stars > 5000 or (stars > 1000 and forks > 500):
            return 2, 60, 30  # 知名保护：最低60分，最多扣30分

        # 良好项目：stars > 500 或 forks > 50
        if stars > 500 or forks > 50:
            return 1, 50, 40  # 基础保护：最低50分，最多扣40分

        # 普通项目：无特殊保护
        return 0, 30, 50  # 无保护：最低30分，最多扣50分

    def calculate_security_score(self, scan_results: Dict[str, Any], repo_info: Dict[str, Any] = None) -> int:
        """计算安全评分，基于静态扫描结果和可选的仓库信息

        Args:
            scan_results: 静态扫描结果
            repo_info: 可选的仓库信息，用于动态评分调整

        Returns:
            安全评分 (0-100分)
        """
        scans = scan_results.get("scans", {})
        ai_scan = scans.get("ai_static_scan", {})
        issues = ai_scan.get("detailed_issues", [])
        score = ai_scan.get("summary", {}).get("overall_quality_score", 50)

        protection_level, min_security_score, max_deduction = self._calculate_project_protection_level(repo_info)

        if protection_level >= 2:  
            score = max(score, 70)  

        total_deduction = 0

        if isinstance(issues, list):
            for i in issues:
                file_path = i.get("file", "")
                line_number = i.get("line", 0)
                issue_title = i.get("title", "")
                issue_analysis = i.get("analysis", "")

                # 检查文件路径是否合理
                is_valid_file = True
                if file_path and file_path != "unknown" and file_path != "全局":
                    # 检查文件路径是否包含有效扩展名
                    has_valid_extension = any(ext in file_path.lower() for ext in
                                              ['.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs', '.cpp', '.c',
                                               '.php',
                                               '.rb', '.kt', '.swift', '.html', '.css', '.vue', '.dart', '.sql',
                                               '.graphql', '.json',
                                               '.yaml', '.yml', '.xml', '.md', '.txt', '.dockerfile', '.dockerignore',
                                               '.makefile',
                                               '.cmake', '.ini', '.cfg', '.conf', '.toml', '.properties', '.lua',
                                               '.perl', '.pl',
                                               '.r', '.dart', '.groovy', '.vbs', '.vba', '.asm', '.s', '.svg', '.plist',
                                               '.xsd',
                                               '.xsl', '.xhtml', '.shtml', '.tmpl', '.tpl', '.erb', '.haml', '.slim',
                                               '.jade', '.pug',
                                               '.styl', '.sass', '.scss', '.less', '.coffee', '.litcoffee', '.vue',
                                               '.svelte', '.elm',
                                               '.erl', '.hrl', '.ex', '.exs', '.clj', '.cljs', '.cljc', '.edn', '.fs',
                                               '.fsi', '.fsx',
                                               '.fsscript', '.hs', '.lhs', '.ml', '.mli', '.mll', '.mly', '.hx',
                                               '.hxml', '.d', '.di',
                                               '.pde', '.wxs', '.wxl', '.xib', '.storyboard', '.pbxproj', '.lock',
                                               '.ipynb'])

                    if not has_valid_extension:
                        # 如果没有有效扩展名，检查是否是合理的文件名
                        filename = file_path.split('/')[-1].split('\\')[-1]  # 获取文件名部分
                        if not any(ext in filename.lower() for ext in
                                   ['.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs', '.cpp', '.c', '.php',
                                    '.rb', '.kt', '.swift', '.html', '.css', '.vue', '.dart', '.sql', '.graphql',
                                    '.json', '.yaml', '.yml', '.xml', '.md', '.txt', '.dockerfile', '.dockerignore',
                                    '.makefile', '.cmake', '.ini', '.cfg', '.conf', '.toml', '.properties', '.lua',
                                    '.perl', '.pl', '.r', '.dart', '.groovy', '.vbs', '.vba', '.asm', '.s', '.svg',
                                    '.plist', '.xsd', '.xsl', '.xhtml', '.shtml', '.tmpl', '.tpl', '.erb', '.haml',
                                    '.slim', '.jade', '.pug', '.styl', '.sass', '.scss', '.less', '.coffee',
                                    '.litcoffee', '.vue', '.svelte', '.elm', '.erl', '.hrl', '.ex', '.exs', '.clj',
                                    '.cljs', '.cljc', '.edn', '.fs', '.fsi', '.fsx', '.fsscript', '.hs', '.lhs', '.ml',
                                    '.mli', '.mll', '.mly', '.hx', '.hxml', '.d', '.di', '.pde', '.wxs', '.wxl', '.xib',
                                    '.storyboard', '.pbxproj', '.lock', '.ipynb']):
                            is_valid_file = False



                # 检查行号是否有效（非负整数，除非是全局问题）
                if line_number is not None and line_number != 0 and (
                        not isinstance(line_number, int) or line_number < 0):
                    is_valid_file = False

                if not is_valid_file:
                    continue  # 跳过无效问题

                sev = i.get("severity", "").lower()
                if total_deduction >= max_deduction:
                    break  # 达到最大扣分限制，停止扣分

                if sev == "high":
                    if total_deduction + 10 <= max_deduction:
                        total_deduction += 10
                    else:
                        # 如果加上本次扣分会超过限制，则只扣到上限
                        total_deduction = max_deduction
                elif sev == "medium":
                    if total_deduction + 5 <= max_deduction:
                        total_deduction += 5
                    else:
                        total_deduction = max_deduction
                elif sev == "low":
                    if total_deduction + 2 <= max_deduction:
                        total_deduction += 2
                    else:
                        total_deduction = max_deduction

        score = score - total_deduction

        # 应用项目保护机制
        final_score = max(min_security_score, score)  # 确保不低于保护最小分

        if protection_level >= 2 and final_score < 85:
            final_score = min(90, final_score + 10)
            logger.info(f" 应用知名项目保护，提升安全评分为: {final_score}")

        return max(min_security_score, final_score)

    # 运行完整扫描
    async def run_full_scan_with_path(self,
                                      repo_path: Optional[str] = None,
                                      repo_url: Optional[str] = None,
                                      primary_languages: Optional[List[str]] = None,
                                      progress_callback=None) -> Dict[str, Any]:
        try:
            if repo_url and not repo_path:
                temp_dir = os.path.join(os.getenv("TEMP", "/tmp"), f"repo_analysis_temp")
                # GitUtils.clone_repo 是 async 时需要 await
                repo_path = await GitUtils().clone_repo(repo_url, temp_dir)
                logger.debug(f"克隆 repo_url 到临时目录: {repo_path}")


            if not repo_path or not os.path.exists(repo_path):
                error_msg = f"仓库路径不存在，无法扫描: {repo_path}"
                logger.error(error_msg)
                return {"status": "error", "error": error_msg}

            logger.info(f"开始完整扫描: {repo_path}")

            file_info_list = self._collect_repo_files(repo_path, primary_languages=primary_languages)
            actual_scanned_files = len(file_info_list)
            logger.info(f"[统计] 实际扫描文件数: {actual_scanned_files}")

            languages_found = self._detect_languages(file_info_list)
            repo_structure = GitUtils.analyze_repo_structure(repo_path)
            # logger.debug(f"仓库结构: {json.dumps(repo_structure, ensure_ascii=False)}")

            scan_result = await self._run_ai_in_batches(repo_structure, languages_found, file_info_list,
                                                        progress_callback)

            if "scans" in scan_result and "ai_static_scan" in scan_result["scans"]:
                # 更新实际扫描的文件数，而不是问题涉及的文件数
                scan_result["scans"]["ai_static_scan"]["summary"]["total_files"] = actual_scanned_files
                scan_result["scans"]["ai_static_scan"]["summary"]["scanned_files"] = actual_scanned_files
                logger.info(f"[统计] 更新扫描结果中的实际扫描文件数: {actual_scanned_files}")

            analysis_data = {
                "repo_path": repo_path,
                "languages_detected": languages_found,
                "static_scan_results": scan_result
            }
            logger.info("完整扫描完成")
            # shutil.rmtree(temp_dir, ignore_errors=True)
            return analysis_data
        except Exception as e:
            logger.error(f"AI静态扫描执行失败: {str(e)}", exc_info=True)
            return {"status": "error", "error": str(e)}
