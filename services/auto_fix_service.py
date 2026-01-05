import logging
import os
import re
from typing import Dict, Any, Optional, List
from datetime import datetime

from utils.ai_client import AIClient
from utils.ai_provider_utils import get_available_provider
from utils.git_utils import GitUtils

logger = logging.getLogger(__name__)


def _load_auto_fix_prompt() -> str:
    """读取自动修复提示词文件"""
    prompt_path = os.path.join(os.path.dirname(__file__), '..', 'utils', 'prompts', 'auto_fix.txt')
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        logger.warning(f"无法读取auto_fix.txt提示词文件: {e}，使用默认提示词")
        return ""


class AutoFixService:
    """自动修复服务 - 支持AI提供商自动降级"""

    def __init__(self, ai_provider: Optional[str] = None):
        # 使用降级机制获取可用提供商
        self.ai_provider = get_available_provider(ai_provider)
        self.ai_client = AIClient(self.ai_provider)
        # 使用全局 GitUtils 实例
        self.git_utils = GitUtils()
        # 初始化仓库缓存
        self._repo_cache = {}
        logger.info(f"AutoFixService初始化完成，使用AI提供商: {self.ai_provider}")

    async def generate_fix(self,
                           recommendation: Dict[str, Any],
                           repo_url: str,
                           format_type: str = "code",
                           github_token: Optional[str] = None,
                           gitee_token: Optional[str] = None) -> Dict[str, Any]:
        """
        生成自动修复代码或Git Diff补丁

        Args:
            recommendation: 建议信息
            repo_url: 仓库URL
            format_type: 输出格式 ("code" 或 "diff")
            github_token: GitHub访问令牌
            gitee_token: Gitee访问令牌

        Returns:
            包含修复代码或Diff的字典
        """
        try:
            logger.info(f"开始生成{format_type}格式的自动修复")

            # 解析建议位置信息
            location = recommendation.get("location", "")
            file_path, line_range = self._parse_location(location)

            if not file_path:
                return self._create_error_result("无法解析文件位置信息")

            # 克隆仓库获取文件内容
            repo_path = await self._clone_repository(repo_url, github_token, gitee_token)
            if not repo_path:
                return self._create_error_result("无法克隆仓库")

            # 验证并获取目标文件路径
            file_exists, target_file_path = await self._validate_file_exists(repo_path, file_path)
            if not file_exists:
                return self._create_error_result(f"文件不存在: {file_path} (在仓库 {repo_path} 中)")

            original_code = self._read_file_content(target_file_path)

            # 生成修复代码
            fix_result = await self._generate_fix_with_ai(
                original_code=original_code,
                recommendation=recommendation,
                file_path=file_path,
                line_range=line_range,
                format_type=format_type
            )

            if format_type == "diff":
                # 生成Git Diff格式
                diff_content = self._create_git_diff(
                    original_code=original_code,
                    fixed_code=fix_result.get("fixed_code", ""),
                    file_path=file_path
                )

                return {
                    "success": True,
                    "diff": diff_content,
                    "explanation": fix_result.get("explanation", ""),
                    "files_affected": [
                        {
                            "path": file_path,
                            "changes": len(fix_result.get("fixed_code", "").splitlines()),
                            "action": "modified"
                        }
                    ],
                    "apply_command": f"git apply patch_{recommendation.get('id', 'unknown')}.diff",
                    "recommendation_id": recommendation.get("id"),
                    "generated_at": datetime.now().isoformat()
                }
            else:
                # 返回修复代码
                return {
                    "success": True,
                    "fixed_code": fix_result.get("fixed_code", ""),
                    "explanation": fix_result.get("explanation", ""),
                    "file_path": file_path,
                    "line_range": line_range,
                    "recommendation_id": recommendation.get("id"),
                    "file_extension": os.path.splitext(file_path)[1].lstrip('.') or "txt",
                    "generated_at": datetime.now().isoformat()
                }

        except Exception as e:
            logger.error(f"生成自动修复失败: {str(e)}")
            return self._create_error_result(f"生成修复失败: {str(e)}")

    def _parse_location(self, location: str) -> tuple:
        """解析位置信息，返回(文件路径, 行号范围)"""
        try:
            if not location:
                return "", ""

            location = location.strip()
            if not location:
                return "", ""

            # 匹配格式: "src/file.py:120-145" 或 "src/file.py:120" 或仅文件路径
            if ':' in location:
                # 分割路径和行号部分
                parts = location.rsplit(':', 1)  # 从右边分割，避免路径中有冒号的情况
                file_path = parts[0].strip()
                line_part = parts[1].strip()

                # 验证行号部分是否为数字格式（包括范围）
                if re.match(r'^\d+(-\d+)?$', line_part):
                    return file_path, line_part
                else:
                    # 如果行号部分不是有效格式，则将其视为文件路径的一部分
                    # 这种情况可能发生在文件名中包含冒号的情况
                    return location, ""
            else:
                # 没有冒号，只返回文件路径
                return location, ""
        except Exception as e:
            logger.error(f"解析位置信息失败: {e}")
            return "", ""

    async def _clone_repository(self, repo_url: str, github_token: Optional[str], gitee_token: Optional[str]) -> str:
        """克隆仓库"""
        try:
            # 检查缓存
            if repo_url in self._repo_cache:
                cached_path = self._repo_cache[repo_url]
                if os.path.exists(cached_path):
                    logger.info(f"使用缓存的仓库路径: {cached_path}")
                    return cached_path
                else:
                    # 缓存路径不存在，清除缓存
                    logger.warning(f"缓存的仓库路径不存在: {cached_path}")
                    del self._repo_cache[repo_url]

            # 克隆仓库
            token = gitee_token if "gitee.com" in repo_url.lower() else github_token
            repo_path = await self.git_utils.clone_repo(repo_url, token=token)

            if repo_path:
                # 缓存仓库路径
                self._repo_cache[repo_url] = repo_path
                logger.info(f"克隆仓库成功，已缓存: {repo_path}")

            return repo_path
        except Exception as e:
            logger.error(f"克隆仓库失败: {e}")
            return ""

    def _read_file_content(self, file_path: str) -> str:
        """读取文件内容"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            logger.error(f"读取文件失败 {file_path}: {e}")
            return ""

    async def _validate_file_exists(self, repo_path: str, file_path: str) -> tuple[bool, str]:
        """
        验证文件是否在仓库中存在，如果不存在尝试在整个仓库中搜索

        Args:
            repo_path: 仓库根目录路径
            file_path: 文件路径（可能是完整路径，也可能只是文件名）

        Returns:
            (是否存在, 完整的文件绝对路径)
        """
        # 首先尝试直接拼接路径
        target_file_path = os.path.join(repo_path, file_path)
        if os.path.exists(target_file_path):
            return True, target_file_path

        # 获取文件名（用于搜索）
        file_name = os.path.basename(file_path)
        target_file_name = file_name.lower()

        # 在整个仓库中递归搜索同名文件
        repo_path_abs = os.path.abspath(repo_path)
        found_files = []

        for root, dirs, files in os.walk(repo_path_abs):
            for file in files:
                file_lower = file.lower()

                # 精确匹配文件名（不区分大小写）
                if file_lower == target_file_name:
                    found_path = os.path.join(root, file)
                    found_files.append(found_path)

                # 部分匹配：如果输入的file_path包含目录结构，尝试匹配
                elif '/' in file_path or '\\' in file_path:
                    # 移除扩展名和特殊字符进行比较
                    input_name_clean = file_path.replace('/', '').replace('\\', '').replace('.', '').replace('-',
                                                                                                             '').replace(
                        '_', '').lower()
                    file_name_clean = file_lower.replace('.', '').replace('-', '').replace('_', '')

                    if file_name_clean in input_name_clean or input_name_clean in file_name_clean:
                        found_path = os.path.join(root, file)
                        found_files.append(found_path)

        # 如果找到了文件
        if found_files:
            # 优先选择较短的路径（通常根目录或常见目录的结构更直接）
            found_files.sort(key=lambda x: (x.count(os.sep), len(x)))
            best_match = found_files[0]
            relative_path = os.path.relpath(best_match, repo_path_abs)
            logger.info(f"在仓库中找到文件: {file_path} -> {relative_path}")
            return True, best_match

        # 记录所有文件以便调试（只记录前50个）
        all_files = []
        for root, dirs, files in os.walk(repo_path_abs):
            for file in files:
                all_files.append(os.path.relpath(os.path.join(root, file), repo_path_abs))
            if len(all_files) > 50:
                break

        logger.warning(f"文件未找到: {file_path}. 仓库中的文件示例: {', '.join(all_files[:10])}")

        # 返回错误
        return False, target_file_path

    async def _generate_fix_with_ai(self,
                                    original_code: str,
                                    recommendation: Dict[str, Any],
                                    file_path: str,
                                    line_range: str,
                                    format_type: str) -> Dict[str, Any]:
        """使用AI生成修复代码"""
        try:
            prompt = self._build_fix_prompt(
                original_code=original_code,
                recommendation=recommendation,
                file_path=file_path,
                line_range=line_range
            )

            response = await self.ai_client.chat(prompt)

            if not response:
                logger.warning("AI返回空响应")
                return {"fixed_code": "", "explanation": "AI无法生成修复代码"}

            # 记录原始响应
            logger.info(f"AI响应前50字符: {response[:50]}")
            logger.info(f"AI响应完整长度: {len(response)}")

            # 解析AI响应
            if format_type == "diff":
                # 对于diff格式，提取修复后的代码
                fixed_code = self._extract_fixed_code(response)
                explanation = self._extract_explanation(response)
            else:
                # 对于代码格式，直接返回修复代码
                fixed_code = self._extract_fixed_code(response)
                explanation = self._extract_explanation(response)

            logger.info(f"提取的修复代码长度: {len(fixed_code)}")

            if not fixed_code:
                logger.warning(f"提取的修复代码为空，原始响应: {response}")

            return {
                "fixed_code": fixed_code,
                "explanation": explanation
            }

        except Exception as e:
            logger.error(f"AI生成修复代码失败: {e}")
            return {"fixed_code": "", "explanation": f"AI生成失败: {str(e)}"}

    def _build_fix_prompt(self, original_code: str, recommendation: Dict[str, Any], file_path: str,
                          line_range: str) -> str:
        """构建修复提示词"""

        # 根据文件扩展名确定语言
        file_extension = os.path.splitext(file_path)[1].lower()
        language_map = {
            '.py': 'Python',
            '.js': 'JavaScript',
            '.ts': 'TypeScript',
            '.java': 'Java',
            '.go': 'Go',
            '.rs': 'Rust',
            '.cpp': 'C++',
            '.c': 'C',
            '.php': 'PHP',
            '.rb': 'Ruby'
        }
        language = language_map.get(file_extension, 'Unknown')

        # 从文件读取提示词模板
        template = _load_auto_fix_prompt()
        if not template:
            # 如果文件读取失败，使用默认提示词
            template = """你是一位资深的代码修复专家，擅长{LANGUAGE}代码的bug修复和优化。

## 原始代码
文件路径: {FILE_PATH}
{LINE_RANGE}

```{LANGUAGE}
{ORIGINAL_CODE}
```

## 需要修复的问题
- 问题类别: {CATEGORY}
- 优先级: {PRIORITY}
- 问题描述: {DESCRIPTION}
- 问题描述: {ISSUE}
- 影响说明: {IMPACT}
- 修复建议: {RECOMMENDATION}

## 修复要求
1. 只修复指出的问题，不要修改无关的代码
2. 保持代码的原有逻辑和功能不变
3. 遵循{LANGUAGE}的最佳实践和编码规范
4. 确保修复后的代码语法正确且可以运行
5. 只输出需要修改的代码片段，包含足够的上下文行以便于定位

## 重要提示
请只输出需要修改的代码片段（修改行及其上下文），不要输出整个文件的完整代码。
对于需要修改的具体行数范围，你可以在修复说明中标注。
特别注意：不要返回完整文件内容，只返回与修复相关的代码行及必要的上下文。

## 输出格式
请按照以下格式输出：

### 修复说明
[简要说明修复的内容和原因，标注修改的行号范围]

### 修改后的代码片段
```{LANGUAGE}
[只输出需要修改的代码片段，包含修改的行及其上下文]
```
"""

        # 替换占位符
        line_range_str = f'需要修改的行号范围: {line_range}' if line_range else '注意：请只输出需要修改的代码片段'
        prompt = template.replace("{LANGUAGE}", language)
        prompt = prompt.replace("{FILE_PATH}", file_path)
        prompt = prompt.replace("{LINE_RANGE}", line_range_str)
        prompt = prompt.replace("{ORIGINAL_CODE}", original_code)
        prompt = prompt.replace("{CATEGORY}", recommendation.get('category', '未知'))
        prompt = prompt.replace("{PRIORITY}", recommendation.get('priority', '中'))
        prompt = prompt.replace("{DESCRIPTION}", recommendation.get('description', ''))
        prompt = prompt.replace("{ISSUE}", recommendation.get('issue', ''))
        prompt = prompt.replace("{IMPACT}", recommendation.get('impact', ''))
        prompt = prompt.replace("{RECOMMENDATION}", recommendation.get('recommendation', ''))

        return prompt

    def _extract_fixed_code(self, response: str) -> str:
        """从响应中提取修复后的代码"""
        try:
            logger.debug(f"开始提取修复代码，响应长度: {len(response)}")

            # 首先检查是否是JSON格式的响应
            if response.strip().startswith('{') and response.strip().endswith('}'):
                import json
                try:
                    # 尝试解析JSON响应
                    json_response = json.loads(response)
                    
                    # 检查是否包含code字段
                    if 'code' in json_response:
                        code = json_response['code']
                        logger.info(f"从JSON响应中提取到代码，长度: {len(code)}")
                        return code
                    
                    # 检查是否包含fixed_code字段
                    if 'fixed_code' in json_response:
                        fixed_code = json_response['fixed_code']
                        logger.info(f"从JSON响应中提取到fixed_code，长度: {len(fixed_code)}")
                        return fixed_code
                        
                    # 检查是否包含修改后的代码片段
                    if '修改后的代码片段' in json_response:
                        code = json_response['修改后的代码片段']
                        logger.info(f"从JSON响应中提取到修改后的代码片段，长度: {len(code)}")
                        return code
                    
                except json.JSONDecodeError:
                    logger.warning("响应看起来像JSON但解析失败，继续使用正则匹配")

            # 查找代码块 - 支持多种格式
            patterns = [
                r'```(?:\w+)?\n*(.*?)\n*```',  # 标准 markdown 代码块
                r'```([\s\S]*?)```',  # 换行符友好版本
                r'(?:### 修改后的代码片段|修改后的代码片段|### 修复后的代码|修复后的代码)[:：\s]*```([\s\S]*?)```',
                # 带标题的代码块
            ]

            for pattern in patterns:
                matches = re.findall(pattern, response, re.DOTALL)
                if matches:
                    # 返回最后一个代码块（修复后的代码）
                    fixed_code = matches[-1].strip()
                    # 处理转义字符，将\n转换为实际换行符
                    fixed_code = fixed_code.replace('\\n', '\n')
                    # 处理其他可能的转义字符
                    fixed_code = fixed_code.replace('\\t', '\t')
                    fixed_code = fixed_code.replace('\\r', '\r')
                    logger.info(f"使用正则提取到代码块，长度: {len(fixed_code)}")
                    return fixed_code

            # 如果没有代码块，尝试查找"修改后的代码片段"或"修复后的代码"之后的内容
            after_fix_pattern = r'(?:### 修改后的代码片段|修改后的代码片段|### 修复后的代码|修复后的代码)[:：\s]*([\s\S]*?)(?:\n\n|\Z)'
            match = re.search(after_fix_pattern, response, re.IGNORECASE)
            if match:
                fixed_code = match.group(1).strip()
                # 移除可能残留的代码块标记
                fixed_code = re.sub(r'^```[\w]*\n?', '', fixed_code)
                fixed_code = re.sub(r'\n```$', '', fixed_code)
                # 处理转义字符，将\n转换为实际换行符
                fixed_code = fixed_code.replace('\\n', '\n')
                # 处理其他可能的转义字符
                fixed_code = fixed_code.replace('\\t', '\t')
                fixed_code = fixed_code.replace('\\r', '\r')
                logger.info(f"从标题后提取代码，长度: {len(fixed_code)}")
                return fixed_code

            # 如果还是没有，尝试提取整个响应（移除代码块标记）
            logger.warning("未找到代码块，尝试提取整个响应")
            full_response = response.strip()
            # 移除开头的标题和说明
            full_response = re.sub(r'^(.*?)(?:### 修改后的代码片段|修改后的代码片段|### 修复后的代码|修复后的代码)', '',
                                   full_response, flags=re.DOTALL)
            # 移除代码块标记
            full_response = re.sub(r'```[\w]*\n?', '', full_response)
            full_response = re.sub(r'```$', '', full_response)
            # 处理转义字符，将\n转换为实际换行符
            full_response = full_response.replace('\\n', '\n')
            # 处理其他可能的转义字符
            full_response = full_response.replace('\\t', '\t')
            full_response = full_response.replace('\\r', '\r')

            if full_response and len(full_response) > 10:  # 至少要有一些内容
                logger.info(f"提取完整响应作为代码，长度: {len(full_response)}")
                return full_response.strip()

            logger.error("无法从响应中提取有效的修复代码")
            return ""

        except Exception as e:
            logger.error(f"提取修复代码失败: {e}")
            return ""

    def _extract_explanation(self, response: str) -> str:
        """从响应中提取修复说明"""
        try:
            # 查找修复说明部分
            explanation_pattern = r'(?:修复说明|### 修复说明)[:：\s]*([^\n]*(?:\n[^#][^\n]*)*)'
            match = re.search(explanation_pattern, response, re.IGNORECASE)

            if match:
                explanation = match.group(1).strip()
                # 清理可能的代码块标记
                explanation = re.sub(r'```\w*\n?', '', explanation)
                explanation = explanation[:500]  # 限制长度
                return explanation
            else:
                # 如果没有找到说明，返回默认说明
                return "基于AI分析生成的代码修复"
        except Exception as e:
            logger.error(f"提取修复说明失败: {e}")
            return "AI生成的代码修复"

    def _create_git_diff(self, original_code: str, fixed_code: str, file_path: str) -> str:
        """创建Git Diff格式"""
        try:
            import difflib

            original_lines = original_code.splitlines(keepends=True)
            fixed_lines = fixed_code.splitlines(keepends=True)

            # 生成统一diff格式
            diff_lines = list(difflib.unified_diff(
                original_lines,
                fixed_lines,
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
                lineterm=''
            ))

            return '\n'.join(diff_lines) if diff_lines else ""

        except Exception as e:
            logger.error(f"创建Git Diff失败: {e}")
            return f"--- a/{file_path}\n+++ b/{file_path}\n@@ -1,1 +0,0 @@\n-Diff generation failed"

    def _create_error_result(self, error_message: str) -> Dict[str, Any]:
        """创建错误结果"""
        return {
            "success": False,
            "error": error_message,
            "explanation": "",
            "fixed_code" if "diff" not in error_message.lower() else "diff": "",
            "generated_at": datetime.now().isoformat()
        }
