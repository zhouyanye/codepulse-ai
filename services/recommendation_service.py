"""
优化建议生成服务
负责生成优化建议、代码改进建议等功能
"""

import json
import logging
import os
import re
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class RecommendationService:
    """优化建议生成服务"""

    def __init__(self, ai_client):
        """
        初始化优化建议服务

        Args:
            ai_client: AIClient实例，可以为None
        """
        self.ai_client = ai_client
        if ai_client is not None:
            self.provider = ai_client.provider
        else:
            self.provider = "costrict"  # 当ai_client为None时，假定为costrict模式

    async def generate_recommendations(self, analysis_data: Dict[str, Any]) -> List[Dict]:
        """
        生成优化建议

        Args:
            analysis_data: 分析数据

        Returns:
            优化建议列表
        """
        if self.provider == "costrict":
            return await self._generate_costrict_recommendations(analysis_data)

        prompt = self._build_recommendation_prompt(analysis_data)
        if not prompt:
            logger.warning("建议提示词为空，返回空建议列表")
            return []

        try:
            response = await self.ai_client._chat_completion(prompt)
            logger.info(f"AI建议生成响应长度: {len(response)}字符")
            return self._parse_recommendations_response_improved(response)
        except Exception as e:
            logger.error(f"AI建议生成失败: {str(e)}")
            logger.error(f"失败的提示词: {prompt[:200]}...")
            return []

    def _load_prompt(self, name: str) -> str:
        """读取 prompts 目录下的提示词文件"""
        prompt_path = os.path.join(os.path.dirname(__file__), "..", "utils", "prompts", f"{name}.txt")
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            logger.error(f"读取提示词文件失败: {prompt_path} - {str(e)}")
            return ""

    def _build_recommendation_prompt(self, analysis_data: Dict[str, Any]) -> str:
        """构建优化建议提示词"""
        template = self._load_prompt("recommendations")
        if not template:
            logger.error("优化建议提示词模板为空")
            return ""

        try:
            # 将分析数据格式化为JSON字符串
            analysis_json = json.dumps(analysis_data, ensure_ascii=False, indent=2)
            prompt = template.replace("{{ANALYSIS_DATA}}", analysis_json)
            # 添加明确的指令，要求返回完整JSON
            prompt += "\n\n请确保返回完整的JSON格式数据，不要截断输出。"
            return prompt
        except Exception as e:
            logger.error(f"构建建议提示词失败: {str(e)}")
            prompt = template.replace("{{ANALYSIS_DATA}}", "{}")
            # 添加明确的指令，要求返回完整JSON
            prompt += "\n\n请确保返回完整的JSON格式数据，不要截断输出。"
            return prompt

    def _parse_recommendations_response_improved(self, response: str) -> List[Dict]:
        """推荐建议解析"""
        try:
            logger.debug(f"开始解析AI建议响应，长度: {len(response)}字符")

            # 1. 清理响应内容 - 移除可能的代码标记
            if self.ai_client is not None:
                cleaned_response = self.ai_client._clean_ai_response(response)
            else:
                # 在costrict模式下，直接使用基础清理
                cleaned_response = response.strip()
            logger.debug(f"清理后的响应: {cleaned_response[:200]}...")

            # 2. 寻找JSON数组
            if self.ai_client is not None:
                json_array = self.ai_client._extract_json_array(cleaned_response)
            else:
                # 在costrict模式下，直接尝试解析JSON
                json_array = cleaned_response
            if not json_array:
                logger.warning("未找到JSON数组，尝试降级处理")
                logger.warning(f"清理后的响应内容: {cleaned_response[:500]}...")
                # 检查是否是纯文本建议
                if self._is_plain_text_recommendations(cleaned_response):
                    logger.info("检测到纯文本建议，直接返回")
                    return [{"id": 1, "description": cleaned_response}]
                return self._fallback_recommendations(cleaned_response)

            logger.info(f"成功提取JSON数组，长度: {len(json_array)}字符")
            logger.debug(f"提取的JSON数组前100字符: {json_array[:100]}...")

            # 3. 解析JSON
            try:
                data = json.loads(json_array)
                logger.info(
                    f"JSON解析成功，数据类型: {type(data)}, 长度: {len(data) if isinstance(data, list) else 'N/A'}")
                if isinstance(data, list):
                    normalized = self._normalize_recommendations(data)
                    logger.info(f"标准化后建议数量: {len(normalized)}")
                    return normalized
                else:
                    logger.warning("解析结果不是数组，降级处理")
                    return self._fallback_recommendations(cleaned_response)

            except json.JSONDecodeError as e:
                logger.error(f"JSON解析失败: {str(e)}")
                logger.error(f"失败的JSON内容: {json_array[:100]}...")
                # 尝试修复JSON
                repaired_json = self._repair_json_array(json_array)
                if repaired_json:
                    try:
                        data = json.loads(repaired_json)
                        if isinstance(data, list):
                            logger.info("成功修复JSON并解析")
                            normalized = self._normalize_recommendations(data)
                            logger.info(f"修复后标准化建议数量: {len(normalized)}")
                            return normalized
                    except json.JSONDecodeError:
                        pass
                return self._fallback_recommendations(cleaned_response)

        except Exception as e:
            logger.error(f"建议解析严重错误: {str(e)}")
            return self._fallback_recommendations(response)

    def _repair_json_array(self, json_str: str) -> str:
        """
        尝试修复不完整的JSON数组字符串
        """
        if not json_str.startswith('[') or not json_str.endswith(']'):
            return ""

        # 移除首尾的方括号
        content = json_str[1:-1].strip()
        if not content:
            return "[]"

        # 分割对象
        objects = []
        brace_count = 0
        in_string = False
        escape_next = False
        current_obj = ""

        for i, char in enumerate(content):
            if escape_next:
                escape_next = False
                current_obj += char
                continue

            if char == '\\':
                escape_next = True
                current_obj += char
                continue

            if char == '"' and not escape_next:
                in_string = not in_string

            if not in_string:
                if char == '{':
                    if brace_count == 0:
                        # 开始一个新的对象
                        current_obj = char
                    else:
                        current_obj += char
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    current_obj += char
                    if brace_count == 0:
                        # 完成了一个对象
                        objects.append(current_obj)
                        current_obj = ""
                elif brace_count > 0:
                    current_obj += char
                elif char in [',', ' ', '\n', '\t', '\r']:
                    # 忽略分隔符和空白字符
                    if brace_count > 0:
                        current_obj += char
            else:
                if brace_count > 0:
                    current_obj += char

        # 验证每个对象是否是有效的JSON
        valid_objects = []
        for obj_str in objects:
            try:
                json.loads(obj_str)
                valid_objects.append(obj_str)
            except json.JSONDecodeError:
                continue

        # 构造修复后的JSON数组
        repaired_json = '[' + ','.join(valid_objects) + ']'
        return repaired_json

    def _is_plain_text_recommendations(self, text: str) -> bool:
        """
        判断是否是纯文本建议
        """
        # 检查是否包含典型的Markdown标题
        if re.search(r'^#{2,4}\s+.*', text.strip(), re.MULTILINE):
            return True

        # 检查是否包含安全漏洞、优化建议等关键词
        keywords = ['安全漏洞', '优化建议', '风险', '建议', '问题', '修复']
        count = sum(1 for keyword in keywords if keyword in text)

        return count >= 2

    def _normalize_recommendations(self, data: List) -> List[Dict]:
        """标准化推荐建议格式"""
        normalized = []

        for i, item in enumerate(data):
            if isinstance(item, dict):
                # 清理location字段，去除占位符
                location = item.get("location", "全局配置")
                placeholders = ["行号范围", "未知", "unknown", "N/A", "n/a", "全局", "多个文件", "全局配置"]
                for placeholder in placeholders:
                    if placeholder in location:
                        if location.strip() == placeholder:
                            location = "未知位置"
                        elif ":" in location:
                            parts = location.split(":")
                            if len(parts) >= 2:
                                file_path = parts[0].strip()
                                if file_path and file_path not in placeholders:
                                    location = file_path
                location = location.replace("：", ":")

                # 验证location是否为合理的文件路径
                is_valid_location = True
                
                # 检查是否为虚构的文件路径（没有常见扩展名）
                if location != "未知位置" and \
                   not any(ext in location.lower() for ext in ['.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs', '.cpp', '.c', '.php', '.rb', '.kt', '.swift', '.html', '.css', '.vue', '.dart', '.sql', '.graphql', '.json', '.yaml', '.yml', '.xml', '.md', '.txt', '.dockerfile', '.dockerignore', '.makefile', '.cmake', '.ini', '.cfg', '.conf', '.toml', '.properties', '.lua', '.perl', '.pl', '.r', '.dart', '.groovy', '.vbs', '.vba', '.asm', '.s', '.svg', '.plist', '.xsd', '.xsl', '.xhtml', '.shtml', '.tmpl', '.tpl', '.erb', '.haml', '.slim', '.jade', '.pug', '.styl', '.sass', '.scss', '.less', '.coffee', '.litcoffee', '.vue', '.svelte', '.elm', '.erl', '.hrl', '.ex', '.exs', '.clj', '.cljs', '.cljc', '.edn', '.fs', '.fsi', '.fsx', '.fsscript', '.hs', '.lhs', '.ml', '.mli', '.mll', '.mly', '.hx', '.hxml', '.d', '.di', '.pde', '.wxs', '.wxl', '.xib', '.storyboard', '.pbxproj', '.lock', '.ipynb']):
                    # 如果文件路径没有常见扩展名，跳过该建议
                    is_valid_location = False
                
                if not is_valid_location:
                    logger.debug(f"跳过包含虚构文件路径的建议: {location}")
                    continue

                # 确保所有必需字段都存在
                normalized_item = {
                    "id": item.get("id", i + 1),
                    "category": item.get("category", "代码优化"),
                    "priority": item.get("priority", "中"),
                    "title": item.get("title", f"建议 {i + 1}"),
                    "location": location,
                    "description": item.get("description", ""),
                    "issue": item.get("issue", ""),
                    "fix": item.get("fix", ""),
                    "reason": item.get("reason", ""),
                    "impact": item.get("impact", ""),
                    "recommendation": item.get("recommendation", "")
                }
                normalized.append(normalized_item)
            else:
                # 如果不是字典，创建默认结构
                title = str(item)[:100] if item else f"建议 {i + 1}"
                normalized.append({
                    "id": i + 1,
                    "category": "代码优化",
                    "priority": "中",
                    "title": title,
                    "location": "全局配置",
                    "description": str(item) if item else "",
                    "issue": "",
                    "fix": "",
                    "reason": "AI分析结果",
                    "impact": "待评估",
                    "recommendation": str(item) if item else ""
                })

        # 如果analysis_data包含静态扫描结果，从中提取建议
        if hasattr(self, '_analysis_data') and self._analysis_data:
            static_scan_results = self._analysis_data.get("code_quality", {}).get("static_scan_results", {})
            if static_scan_results and isinstance(static_scan_results, dict):
                scans = static_scan_results.get("scans", {})
                ai_static_scan = scans.get("ai_static_scan", {})
                detailed_issues = ai_static_scan.get("detailed_issues", [])
                
                for issue in detailed_issues:
                    if isinstance(issue, dict):
                        # 从静态扫描结果中提取优化建议
                        issue_type = str(issue.get("type", "")).lower()
                        issue_title = str(issue.get("title", issue.get("issue", "代码问题")))
                        issue_analysis = str(issue.get("analysis", "需要进一步分析"))
                        file_path = str(issue.get("file", "未知文件"))
                        line_number = issue.get("line", 0)
                        
                        # 检查文件路径是否合理
                        if file_path != "未知文件" and \
                           any(ext in file_path.lower() for ext in ['.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs', '.cpp', '.c', '.php', '.rb', '.kt', '.swift', '.html', '.css', '.vue', '.dart', '.sql', '.graphql', '.json', '.yaml', '.yml', '.xml', '.md', '.txt', '.dockerfile', '.dockerignore', '.makefile', '.cmake', '.ini', '.cfg', '.conf', '.toml', '.properties', '.lua', '.perl', '.pl', '.r', '.dart', '.groovy', '.vbs', '.vba', '.asm', '.s', '.svg', '.plist', '.xsd', '.xsl', '.xhtml', '.shtml', '.tmpl', '.tpl', '.erb', '.haml', '.slim', '.jade', '.pug', '.styl', '.sass', '.scss', '.less', '.coffee', '.litcoffee', '.vue', '.svelte', '.elm', '.erl', '.hrl', '.ex', '.exs', '.clj', '.cljs', '.cljc', '.edn', '.fs', '.fsi', '.fsx', '.fsscript', '.hs', '.lhs', '.ml', '.mli', '.mll', '.mly', '.hx', '.hxml', '.d', '.di', '.pde', '.wxs', '.wxl', '.xib', '.storyboard', '.pbxproj', '.lock', '.ipynb']):
                            
                            # 构建位置信息
                            location = f"{file_path}:{line_number}" if line_number != 0 else file_path
                            
                            # 检查是否已存在相同建议
                            is_duplicate = False
                            for existing_rec in normalized:
                                if (existing_rec.get("title") == issue_title and
                                    existing_rec.get("location") == location):
                                    is_duplicate = True
                                    break
                            
                            if not is_duplicate:
                                recommendation_item = {
                                    "id": len(normalized) + 1,
                                    "category": str(issue.get("type", "代码优化")),
                                    "priority": str(issue.get("severity", "中")).capitalize(),
                                    "title": issue_title,
                                    "location": location,
                                    "description": issue_analysis,
                                    "issue": issue_analysis,
                                    "fix": str(issue.get("recommendation", "请参考问题描述和修复建议")),
                                    "reason": f"基于静态扫描发现的问题: {issue_analysis}",
                                    "impact": str(issue.get("impact", "潜在风险")),
                                    "recommendation": str(issue.get("recommendation", "请参考问题描述和修复建议"))
                                }
                                normalized.append(recommendation_item)

        return normalized

    def _fallback_recommendations(self, response: str) -> List[Dict]:
        """降级处理 - 生成默认推荐建议"""
        logger.warning("使用降级推荐建议生成")

        # 从响应文本中提取关键信息
        lines = [line.strip() for line in response.split('\n') if line.strip()]

        fallback = []
        for i, line in enumerate(lines[:10]):  # 最多10条建议
            # 检查是否包含虚构文件路径模式
            if len(line) > 10 and any(keyword in line for keyword in ["建议", "推荐", "优化", "修复", "改进", "注意"]):
                fallback.append({
                    "id": i + 1,
                    "category": "代码优化",
                    "priority": "中",
                    "title": line[:100],
                    "location": "多个文件",
                    "description": line,
                    "issue": "需要进一步优化",
                    "fix": "请参考建议进行改进",
                    "reason": "AI分析识别到改进点",
                    "impact": "提升代码质量",
                    "recommendation": line
                })

        # 如果没有提取到任何建议，返回默认建议
        if not fallback:
            fallback = [{
                "id": 1,
                "category": "系统提示",
                "priority": "低",
                "title": "AI建议解析异常",
                "location": "全局配置",
                "description": "AI响应解析失败，已启用降级处理",
                "issue": "解析错误",
                "fix": "请重试或切换AI模型",
                "reason": "容错机制",
                "impact": "不影响核心功能",
                "recommendation": "建议检查AI模型响应格式或切换其他模型"
            }]

        return fallback

    async def _generate_costrict_recommendations(self, analysis_data: Dict[str, Any]) -> List[Dict]:
        """使用 CoStrict 模式生成建议"""
        return []
