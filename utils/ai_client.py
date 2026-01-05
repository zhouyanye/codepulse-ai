"""
AI客户端
提供AI通信的核心功能和公共工具方法
"""

import aiohttp
import json
import logging
import os
import re
from app.core.config import settings
from utils.ai_provider_utils import get_available_provider, log_provider_info

logger = logging.getLogger(__name__)


class AIClient:
    """AI客户端 - 初始化时自动选择可用AI提供商"""

    def __init__(self, provider=None):
        # 使用降级机制获取可用提供商
        self.provider = get_available_provider(provider)
        self.api_key = self._get_api_key(self.provider)
        self.base_url = self._get_base_url(self.provider)
        logger.info(f"使用 {self.provider} AI服务")

    def _get_api_key(self, provider):
        """获取API密钥"""
        provider_key = f"{provider.upper()}_API_KEY"
        if provider == "costrict":
            return None
        return getattr(settings, provider_key, None)

    def _get_base_url(self, provider):
        """获取API基础URL"""
        from utils.ai_provider_utils import _get_base_url as get_url
        return get_url(provider)

    def _get_model_name(self, provider):
        """获取模型名称"""
        from utils.ai_provider_utils import _get_model_name
        return _get_model_name(provider)

    def _get_json_mode_config(self, provider, prompt):
        """
        根据provider和prompt获取JSON模式配置

        Args:
            provider: AI服务提供商
            prompt: 提示词内容

        Returns:
            JSON模式配置字典，如果不支持则返回None
        """
        # 检查提示词中是否包含JSON相关关键词
        contains_json = "json" in prompt.lower()

        # 不同provider的JSON模式配置
        json_configs = {
            "deepseek": {
                "response_format": {"type": "json_object"} if contains_json else None,
                "note": "DeepSeek使用response_format确保JSON输出，提示词需包含'json'关键词"
            },
            "kimi": {
                "response_format": {"type": "json_object"} if contains_json else None,
                "note": "Kimi使用response_format确保JSON输出，提示词需包含'json'关键词"
            },
            "openai": {
                "response_format": {"type": "json_object"} if contains_json else None,
                "note": "OpenAI使用response_format确保JSON输出，提示词需包含'json'关键词"
            },
            "costrict": {
                "response_format": {"type": "json_object"} if contains_json else None,
                "note": "CoStrict使用response_format确保JSON输出，提示词需包含'json'关键词"
            },
            "doubao": {
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "json_response",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "result": {
                                    "type": "object",
                                    "description": "分析结果"
                                }
                            },
                            "additionalProperties": True
                        }
                    }
                } if contains_json else None,
                "note": "Doubao使用json_schema模式确保JSON输出，提示词需包含'json'关键词"
            }
        }

        config = json_configs.get(provider, {})
        response_format = config.get("response_format")

        if response_format and contains_json:
            logger.debug(f"{provider}启用JSON模式: {response_format}")
            return {"response_format": response_format}
        else:
            logger.debug(f"{provider}未启用JSON模式 (prompt包含'json': {contains_json})")
            return None

    def _load_prompt(self, name):
        """读取 prompts 目录下的提示词文件"""
        prompt_path = os.path.join(os.path.dirname(__file__), "prompts", f"{name}.txt")
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            logger.error(f"读取提示词文件失败: {prompt_path} - {str(e)}")
            return ""

    async def _chat_completion(self, prompt):
        """调用AI聊天补全API - 支持自动降级"""
        return await self._chat_completion_with_fallback(prompt)

    async def _chat_completion_with_fallback(self, prompt, provider_chain=None):
        """
        带降级机制的聊天补全调用

        Args:
            prompt: 提示词
            provider_chain: 指定的提供商降级链，如果不指定则从当前provider开始

        Returns:
            AI响应内容
        """
        if provider_chain is None:
            # 从当前provider开始获取降级链
            from utils.ai_provider_utils import _get_fallback_chain
            provider_chain = _get_fallback_chain(self.provider)

        # 如果当前provider是costrict，直接返回默认响应，不尝试调用AI API
        if self.provider == "costrict":
            logger.info("CoStrict模式：跳过AI调用，返回默认响应")
            return "{\"result\": \"CoStrict模式：基于API数据的分析结果\"}"

        last_error = None
        for provider in provider_chain:
            try:
                log_provider_info(provider, "AI聊天补全")

                # costrict模式直接跳过
                if provider == "costrict":
                    logger.warning("到达costrict模式，停止降级")
                    raise ValueError("所有AI提供商都不可用，无法调用AI")

                api_key = self._get_api_key(provider)
                if not api_key:
                    logger.warning(f"{provider} 没有API Key，尝试下一个")
                    continue

                base_url = self._get_base_url(provider)
                model_name = self._get_model_name(provider)

                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                }

                data = {
                    "model": model_name,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.2,
                    "max_tokens": 8000
                }

                # 根据provider设置JSON模式
                if "json" in prompt.lower():
                    if provider == "doubao":
                        # 豆包API需要完整的json_schema格式
                        data["response_format"] = {
                            "type": "json_schema",
                            "json_schema": {
                                "name": "json_response",
                                "strict": True,
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "result": {
                                            "type": "object",
                                            "description": "分析结果"
                                        }
                                    },
                                    "additionalProperties": True
                                }
                            }
                        }
                        logger.info(f"为{provider}启用JSON模式: json_schema")
                    else:
                        # 其他provider使用OpenAI兼容格式
                        data["response_format"] = {"type": "json_object"}
                        logger.debug(f"为{provider}启用JSON模式: json_object")

                # 发送AI请求
                logger.debug(f"发送AI请求到 {provider}: {model_name}")

                # 使用会话并确保正确关闭
                timeout = aiohttp.ClientTimeout(total=300)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    try:
                        async with session.post(
                                f"{base_url}/chat/completions",
                                headers=headers,
                                json=data,
                                timeout=timeout
                        ) as response:

                            response_text = await response.text()
                            logger.debug(f"AI原始响应状态码: {response.status}")

                            if response.status == 200:
                                result = await response.json()
                                content = result["choices"][0]["message"]["content"]
                                logger.info(f"{provider} AI响应成功，内容长度: {len(content)}字符")
                                return content
                            else:
                                logger.error(f"{provider} API请求失败: {response.status} - {response_text[:200]}")
                                raise Exception(f"{provider} API failed: {response.status}")
                    except Exception as e:
                        # 确保会话被正确关闭
                        raise e

            except Exception as e:
                logger.error(f"AI API调用失败: {str(e)}")
                last_error = str(e)
                logger.warning(f"{provider} 调用失败，尝试下一个提供商: {last_error}")

                # 尝试简化提示词重试一次当前提供商
                if provider not in ["costrict"]:
                    try:
                        simplified_prompt = self._simplify_prompt(prompt)
                        # 重新初始化当前provider的配置
                        api_key = self._get_api_key(provider)
                        base_url = self._get_base_url(provider)
                        model_name = self._get_model_name(provider)
                        headers = {
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {api_key}"
                        }
                        data = {
                            "model": model_name,
                            "messages": [{"role": "user", "content": simplified_prompt}],
                            "temperature": 0.2,
                            "max_tokens": 8000
                        }
                        if "json" in simplified_prompt.lower():
                            data["response_format"] = {"type": "json_object"}

                        # 使用会话并确保正确关闭
                        retry_timeout = aiohttp.ClientTimeout(total=300)
                        async with aiohttp.ClientSession(timeout=retry_timeout) as retry_session:
                            try:
                                async with retry_session.post(
                                        f"{base_url}/chat/completions",
                                        headers=headers,
                                        json=data,
                                        timeout=retry_timeout
                                ) as retry_response:
                                    if retry_response.status == 200:
                                        result = await retry_response.json()
                                        content = result["choices"][0]["message"]["content"]
                                        logger.info(f"{provider} 重试成功，内容长度: {len(content)}字符")
                                        return content
                            except Exception as e:
                                # 确保会话被正确关闭
                                raise e
                    except Exception as retry_e:
                        logger.warning(f"{provider} 简化重试也失败: {str(retry_e)}")

        # 所有提供商都失败，抛出异常
        error_msg = f"所有AI提供商都失败: {last_error}" if last_error else "所有AI提供商都不可用"
        logger.error(error_msg)
        raise ValueError(error_msg)

    async def chat(self, prompt):
        """与AI进行对话，返回AI的响应文本"""
        try:
            text = await self._chat_completion(prompt)
            # 检查返回内容是否为空
            if not text or not text.strip():
                logger.warning("AI返回空响应")
                return ""
            # 处理转义字符，将\n转换为实际换行符
            text = text.replace('\\n', '\n')
            # 处理其他可能的转义字符
            text = text.replace('\\t', '\t')
            text = text.replace('\\r', '\r')
            return text
        except Exception as e:
            logger.error(f"AI聊天调用失败: {str(e)}")
            raise

    def _simplify_prompt(self, prompt):
        """简化提示词以减少token使用量"""
        lines = prompt.split('\n')
        simplified_lines = []

        # 保留关键部分
        for line in lines:
            # 保留重要的指令行
            if any(keyword in line.lower() for keyword in [
                '角色', '任务', '分析', '输出', '格式', '要求'
            ]):
                simplified_lines.append(line)
            # 保留代码示例
            elif line.strip().startswith('```') or line.strip().endswith('```'):
                simplified_lines.append(line)
            # 保留JSON结构示例
            elif '{' in line or '}' in line or ':' in line:
                simplified_lines.append(line)
            # 保留文档分析相关内容
            elif any(keyword in line.lower() for keyword in [
                '文档', '链接', 'readme', 'license', 'rst', 'txt'
            ]):
                simplified_lines.append(line)
            # 保留安全和质量问题相关内容
            elif any(keyword in line.lower() for keyword in [
                '安全', '漏洞', '风险', 'exec', 'eval', '密码', '密钥'
            ]):
                simplified_lines.append(line)

        simplified_prompt = '\n'.join(simplified_lines)

        # 如果简化后还是太长，则只保留开头和结尾的一部分
        if len(simplified_prompt) > 3000:
            # 保留前1000字符和后2000字符
            simplified_prompt = simplified_prompt[:1000] + "\n\n... (中间内容已省略) ...\n\n" + simplified_prompt[
                                                                                                -2000:]

        return simplified_prompt

    def _clean_ai_response(self, response):
        """清理AI响应内容"""
        # 移除代码块标记
        cleaned = re.sub(r'```json\s*|\s*```', '', response, flags=re.IGNORECASE)
        # 移除其他代码标记
        cleaned = re.sub(r'```.*?\n|```', '', cleaned, flags=re.DOTALL)
        # 移除Markdown加粗标记
        cleaned = re.sub(r'\*\*(.*?)\*\*', r'\1', cleaned)
        # 处理转义字符，将\n转换为实际换行符
        cleaned = cleaned.replace('\\n', '\n')
        # 移除前导/后缀空白
        cleaned = cleaned.strip()
        return cleaned

    def _extract_json_array(self, text):
        """从文本中提取JSON数组"""
        # 处理转义字符，将\n转换为实际换行符
        text = text.replace('\\\\n', '\\n')
        # 处理其他可能的转义字符
        text = text.replace('\\\\t', '\\t')
        text = text.replace('\\\\r', '\\r')
        
        # 方法1: 直接找最外层的方括号
        start_idx = text.find('[')
        end_idx = text.rfind(']')

        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            json_str = text[start_idx:end_idx + 1]
            # 验证提取的JSON是否有效
            try:
                json.loads(json_str)
                return json_str
            except json.JSONDecodeError:
                # 如果不是有效的JSON，继续尝试其他方法
                pass

        # 方法2: 找包含推荐字段的JSON结构
        patterns = [
            r'\[.*?\]',  # 最简化的数组匹配
            r'\[\s*\{.*?\}\s*\]',  # 包含对象的数组
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in reversed(matches):  # 从最后一个匹配开始尝试
                try:
                    json.loads(match)
                    return match
                except json.JSONDecodeError:
                    continue

        # 方法3: 尝试修复被截断的JSON
        if start_idx != -1:
            # 如果找到了开始的[但没有有效的结束]，尝试找到尽可能多的有效对象
            array_content = text[start_idx + 1:]
            valid_objects = []
            brace_count = 0
            in_string = False
            escape_next = False
            current_obj = ""

            for i, char in enumerate(array_content):
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
                            try:
                                json.loads(current_obj)
                                valid_objects.append(current_obj)
                                current_obj = ""
                            except json.JSONDecodeError:
                                # 对象无效，放弃
                                current_obj = ""
                    elif brace_count > 0:
                        current_obj += char
                    elif char == ']':
                        # 结束数组
                        break
                else:
                    if brace_count > 0:
                        current_obj += char

            # 构造尽可能完整的JSON数组
            if valid_objects:
                repaired_json = '[' + ','.join(valid_objects) + ']'
                return repaired_json

        return ""

    def _extract_json_object(self, text):
        """从文本中提取JSON对象"""
        # 处理转义字符，将\n转换为实际换行符
        text = text.replace('\\\\n', '\\n')
        # 处理其他可能的转义字符
        text = text.replace('\\\\t', '\\t')
        text = text.replace('\\\\r', '\\r')
        
        # 方法1: 直接找最外层的花括号
        start_idx = text.find('{')
        end_idx = text.rfind('}')

        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            return text[start_idx:end_idx + 1]

        # 方法2: 找包含score字段的JSON结构
        pattern = r'\{.*?"score".*?\}'
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(0)

        return ""

    def _repair_json_object(self, text):
        """修复可能损坏的JSON对象"""
        if not text:
            return ""
        
        # 首先清理控制字符
        cleaned_text = self._sanitize_json_string(text)
        
        # 处理转义字符
        cleaned_text = cleaned_text.replace('\\\\n', '\\n')
        cleaned_text = cleaned_text.replace('\\\\t', '\\t')
        cleaned_text = cleaned_text.replace('\\\\r', '\\r')
        
        # 尝试修复未闭合的JSON对象
        start_idx = cleaned_text.find('{')
        if start_idx != -1:
            # 计算括号匹配
            brace_count = 0
            in_string = False
            escape_next = False
            
            for i, char in enumerate(cleaned_text[start_idx:], start_idx):
                if escape_next:
                    escape_next = False
                    continue
                
                if char == '\\\\':
                    escape_next = True
                    continue
                
                if char == '"' and not escape_next:
                    in_string = not in_string
                    continue
                
                if not in_string:
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            # 找到匹配的闭合括号
                            repaired = cleaned_text[start_idx:i+1]
                            try:
                                json.loads(repaired)  # 验证是否为有效JSON
                                return repaired
                            except json.JSONDecodeError:
                                continue
        
        # 如果没有找到匹配的闭合括号，尝试从文本中提取所有可能的对象
        possible_objects = []
        brace_count = 0
        in_string = False
        escape_next = False
        current_obj_start = -1
        current_obj = ""
        
        for i, char in enumerate(cleaned_text):
            if escape_next:
                escape_next = False
                current_obj += char
                continue
            
            if char == '\\\\':
                escape_next = True
                current_obj += char
                continue
            
            if char == '"' and not escape_next:
                in_string = not in_string
            
            if not in_string:
                if char == '{':
                    if brace_count == 0:
                        current_obj_start = i
                        current_obj = char
                    else:
                        current_obj += char
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    current_obj += char
                    if brace_count == 0 and current_obj_start != -1:
                        try:
                            json.loads(current_obj)  # 验证是否为有效JSON
                            possible_objects.append((current_obj_start, current_obj))
                        except json.JSONDecodeError:
                            pass
                        current_obj = ""
                        current_obj_start = -1
                elif brace_count > 0:
                    current_obj += char
            else:
                if brace_count > 0:
                    current_obj += char
        
        # 返回最长的有效JSON对象
        if possible_objects:
            # 按长度排序，返回最长的有效对象
            possible_objects.sort(key=lambda x: len(x[1]), reverse=True)
            return possible_objects[0][1]
        
        return ""

    def _sanitize_json_string(self, text):
        """清理JSON字符串中的特殊字符，特别是控制字符"""
        if not text:
            return ""
        
        # 移除控制字符（ASCII 0-31，除了\\t, \\n, \\r）
        sanitized = ''.join(char if ord(char) >= 32 or char in '\\t\\n\\r' else ' ' for char in text)
        
        # 替换可能导致JSON解析错误的字符序列
        sanitized = sanitized.replace('\\x00', '')  # null字符
        sanitized = sanitized.replace('\\x01', '')  # SOH字符
        sanitized = sanitized.replace('\\x02', '')  # STX字符
        sanitized = sanitized.replace('\\x03', '')  # ETX字符
        sanitized = sanitized.replace('\\x04', '')  # EOT字符
        sanitized = sanitized.replace('\\x05', '')  # ENQ字符
        sanitized = sanitized.replace('\\x06', '')  # ACK字符
        sanitized = sanitized.replace('\\x07', '')  # BEL字符
        sanitized = sanitized.replace('\\x08', '')  # BS字符
        sanitized = sanitized.replace('\\x0b', '')  # VT字符
        sanitized = sanitized.replace('\\x0c', '')  # FF字符
        sanitized = sanitized.replace('\\x0e', '')  # SO字符
        sanitized = sanitized.replace('\\x0f', '')  # SI字符
        sanitized = sanitized.replace('\\x10', '')  # DLE字符
        sanitized = sanitized.replace('\\x11', '')  # DC1字符
        sanitized = sanitized.replace('\\x12', '')  # DC2字符
        sanitized = sanitized.replace('\\x13', '')  # DC3字符
        sanitized = sanitized.replace('\\x14', '')  # DC4字符
        sanitized = sanitized.replace('\\x15', '')  # NAK字符
        sanitized = sanitized.replace('\\x16', '')  # SYN字符
        sanitized = sanitized.replace('\\x17', '')  # ETB字符
        sanitized = sanitized.replace('\\x18', '')  # CAN字符
        sanitized = sanitized.replace('\\x19', '')  # EM字符
        sanitized = sanitized.replace('\\x1a', '')  # SUB字符
        sanitized = sanitized.replace('\\x1b', '')  # ESC字符
        sanitized = sanitized.replace('\\x1c', '')  # FS字符
        sanitized = sanitized.replace('\\x1d', '')  # GS字符
        sanitized = sanitized.replace('\\x1e', '')  # RS字符
        sanitized = sanitized.replace('\\x1f', '')  # US字符
        
        return sanitized
