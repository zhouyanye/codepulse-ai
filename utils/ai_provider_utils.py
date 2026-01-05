"""AI提供商管理工具，支持自动降级机制"""
import logging
from typing import Optional, List, Dict, Any, Callable
from app.core.config import settings

logger = logging.getLogger(__name__)

# AI提供商降级链顺序：deepseek → kimi → doubao → openai → costrict
AI_PROVIDER_FALLBACK_CHAIN = ["deepseek", "kimi", "doubao", "openai", "costrict"]


def has_api_key(provider):
    """检查指定的AI提供商是否有有效的API Key"""
    if not provider:
        return False
    
    # costrict不需要API Key
    if provider == "costrict":
        return True
    
    provider_key = f"{provider.upper()}_API_KEY"
    return bool(hasattr(settings, provider_key) and getattr(settings, provider_key))


def get_available_provider(request_provider=None):
    """
    获取可用的AI提供商，支持降级逻辑

    Args:
        request_provider: 用户请求的AI提供商

    Returns:
        可用的AI提供商名称
    """
    # 如果用户明确指定costrict，直接返回costrict，不检查API Key
    if request_provider == "costrict":
        return "costrict"
    
    # 直接获取过滤后的第一个可用提供商
    fallback_chain = _get_fallback_chain(request_provider)
    available_provider = fallback_chain[0]

    # 仅在发生降级时输出警告日志
    if request_provider and available_provider != request_provider:
        logger.warning(f"AI提供商降级: {request_provider} -> {available_provider}")

    return available_provider


def execute_with_fallback(
        operation,
        request_provider=None,
        task_description="AI操作"
):
    """
    执行AI操作，失败时自动降级到下一个提供商
    """
    fallback_chain = _get_fallback_chain(request_provider)
    if not fallback_chain:
        logger.error(f"无可用的AI提供商，{task_description} 无法执行")
        return False, None, "costrict"

    last_error = None
    for provider in fallback_chain:
        try:
            logger.info(f"尝试使用 {provider} 执行 {task_description}")
            if provider == "costrict":
                logger.warning(f"注意：{provider} 仅支持评分功能，执行生成类任务可能无效")
            result = operation(provider)
            actual_provider = provider
            logger.info(f"{task_description} 成功，使用提供商: {actual_provider}")
            return True, result, actual_provider
        except Exception as e:
            last_error = str(e)
            if provider == "costrict":
                logger.error(f"costrict执行 {task_description} 失败: {last_error}")
            else:
                logger.warning(f"使用 {provider} 执行 {task_description} 失败，准备降级: {last_error}")

    # 所有提供商失败，无需额外判断
    logger.error(f"所有可用AI提供商都失败，{task_description} 最终失败")
    return False, None, fallback_chain[-1]


def _get_fallback_chain(request_provider=None):
    """
    获取降级链

    Args:
        request_provider: 用户请求的AI提供商

    Returns:
        过滤后的可用降级链列表
    """
    if not request_provider:
        # 过滤可用提供商
        unique_original_chain = list(dict.fromkeys(AI_PROVIDER_FALLBACK_CHAIN))
        available_chain = [p for p in unique_original_chain if has_api_key(p)]
        if "costrict" not in available_chain:
            available_chain.append("costrict")
        return available_chain

    if request_provider == "costrict":
        return ["costrict"]

    full_chain = [request_provider] + [p for p in AI_PROVIDER_FALLBACK_CHAIN if p != request_provider]
    unique_full_chain = list(dict.fromkeys(full_chain))
    # 过滤可用提供商
    available_chain = [p for p in unique_full_chain if has_api_key(p)]
    if "costrict" not in available_chain:
        available_chain.append("costrict")
    # 若过滤后为空,返回costrict
    return available_chain if available_chain else ["costrict"]


def get_provider_config(provider):
    """
    获取AI提供商的配置信息
    
    Args:
        provider: 提供商名称
        
    Returns:
        配置信息字典，包含 api_key, base_url, model_name 等
    """
    provider_key = f"{provider.upper()}_API_KEY"
    
    config = {
        "provider": provider,
        "api_key": getattr(settings, provider_key, None) if provider != "costrict" else None,
        "base_url": _get_base_url(provider),
        "model_name": _get_model_name(provider),
        "has_api_key": has_api_key(provider)
    }
    
    return config


def _get_base_url(provider):
    """获取API基础URL"""
    url_mapping = {
        "deepseek": "https://api.deepseek.com/v1",
        "kimi": "https://api.moonshot.cn/v1",
        "openai": "https://api.openai.com/v1",
        "costrict": "",
        "doubao": "https://ark.cn-beijing.volces.com/api/v3"
    }
    return url_mapping.get(provider, "https://api.deepseek.com/v1")


def _get_model_name(provider):
    """获取模型名称"""
    model_mapping = {
        "deepseek": "deepseek-chat",
        "kimi": "kimi-k2-0905-preview",
        "openai": "gpt-3.5-turbo",
        "costrict": "",
        "doubao": "doubao-seed-1-6-251015"
    }
    return model_mapping.get(provider, "deepseek-chat")


def log_provider_info(provider, context=""):
    """记录提供商信息，便于调试"""
    config = get_provider_config(provider)
    has_api = config["has_api_key"]
    model = config["model_name"] or "N/A (costrict)"

    logger.info(f"[Provider] {context}: {provider} | API配置: {'已配置' if has_api else '未配置'} | 模型: {model}")