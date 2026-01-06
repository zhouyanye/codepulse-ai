"""
用于 Celery 任务管理与 Redis 缓存的工具函数。
"""
import json
import logging
import hashlib
from typing import Optional, Dict, Any
from celery.result import AsyncResult
from app.core.celery_app import celery_app
from datetime import datetime

import redis
from app.core.config import settings

logger = logging.getLogger(__name__)


class DateTimeEncoder(json.JSONEncoder):
    """
    自定义JSON编码器，用于处理datetime对象的序列化
    """

    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def get_task_status(task_id: str) -> Dict[str, Any]:
    """
    获取 Celery 任务状态与结果。
    """
    task_result = AsyncResult(task_id, app=celery_app)
    response = {
        "task_id": task_id,
        "status": task_result.status,
        "result": None,
        "error": None,
    }

    if task_result.ready():
        if task_result.successful():
            response["result"] = task_result.result
        else:
            response["error"] = str(task_result.result)
    elif task_result.state == "PROGRESS":
        # Celery 自定义进度信息
        response["progress"] = task_result.info.get("progress", 0)
        response["message"] = task_result.info.get("message", "")

    return response


def cache_analysis_result(cache_key: str, result: Dict[str, Any], ttl: int = settings.REDIS_CACHE_TTL) -> bool:
    """
    将分析结果缓存到 Redis，TTL 默认为 1 天。
    返回 True 表示缓存成功。
    """
    try:
        # 使用 Redis 客户端直接操作缓存
        client = get_redis_client()
        client.setex(cache_key, ttl, json.dumps(result, cls=DateTimeEncoder))
        logger.debug(f"已缓存 key: {cache_key}")
        return True
    except Exception as e:
        import redis
        if isinstance(e, redis.ConnectionError):
            logger.debug(f"Redis 连接失败，跳过缓存: {e}")
        else:
            logger.warning(f"缓存结果失败: {e}")
        return False


def get_cached_analysis_result(cache_key: str) -> Optional[Dict[str, Any]]:
    """
    从 Redis 获取缓存的分析结果。
    """
    try:
        client = get_redis_client()
        data = client.get(cache_key)
        if data:
            if isinstance(data, bytes):
                data = data.decode('utf-8')
            return json.loads(data)
        return None
    except Exception as e:
        import redis
        if isinstance(e, redis.ConnectionError):
            logger.debug(f"Redis 连接失败，跳过缓存: {e}")
        else:
            logger.warning(f"获取缓存失败: {e}")
        return None


def generate_cache_key(repo_url: str, params: Dict[str, Any]) -> str:
    """
    根据仓库 URL 和分析参数生成唯一缓存 key。
    """
    key_string = f"{repo_url}:{json.dumps(params, sort_keys=True)}"
    return hashlib.md5(key_string.encode()).hexdigest()


# Redis Client

def get_redis_client():
    """
    获取 Redis 客户端，优先使用 REDIS_URL。
    """

    if settings.REDIS_URL.startswith("redis://"):
        return redis.Redis.from_url(settings.REDIS_URL)

    return redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        password=settings.REDIS_PASSWORD,
    )


# Redis Key 操作

def list_cache_keys(pattern: str = "*") -> list:
    """
    使用 SCAN 遍历匹配指定模式的 Redis key。
    """
    try:
        client = get_redis_client()
        keys = []
        cursor = 0

        while True:
            cursor, batch = client.scan(cursor=cursor, match=pattern, count=1000)
            keys.extend(batch)
            if cursor == 0:
                break

        return [k.decode("utf-8") if isinstance(k, bytes) else k for k in keys]
    except Exception as e:
        import redis
        if isinstance(e, redis.ConnectionError):
            logger.debug(f"Redis 连接失败，无法列出缓存键: {e}")
        else:
            logger.warning(f"列出缓存键失败: {e}")
        return []


def delete_cache_key(cache_key: str) -> bool:
    """
    删除指定 Redis key。
    返回 True 表示删除成功。
    """
    try:
        client = get_redis_client()
        deleted = client.delete(cache_key)
        return deleted > 0
    except Exception as e:
        import redis
        if isinstance(e, redis.ConnectionError):
            logger.debug(f"Redis 连接失败，无法删除缓存键: {e}")
        else:
            logger.warning(f"删除缓存键失败: {e}")
        return False


# Celery 可用性检测

def is_celery_available(timeout: float = 2.0) -> bool:
    """
    检测 Celery 及其 Broker 是否可用。
    
    尝试连接指定的 Celery broker，如果超时或连接失败则返回 False。
    该函数用于自动选择执行模式时判断是否可以使用 Celery 异步任务。
    
    Args:
        timeout: 连接超时时间（秒），默认 2 秒
        
    Returns:
        bool: Celery 是否可用
    """
    global RedisConnectionError, TimeoutError
    try:
        # 检查 Celery 应用配置
        if not celery_app.conf.broker_url:
            logger.debug("Celery broker URL 未配置")
            return False

        # 尝试连接 Broker（默认使用 Redis）
        import redis
        from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError
        from app.core.config import settings

        # 获取 Redis URL
        redis_url = settings.REDIS_URL if hasattr(settings, 'REDIS_URL') else None
        if not redis_url:
            logger.debug("Redis URL 未配置")
            return False

        # 创建 Redis 连接并测试
        client = redis.Redis.from_url(
            redis_url,
            socket_timeout=timeout,
            socket_connect_timeout=timeout
        )

        # 执行 PING 命令测试连接
        client.ping()
        client.close()

        logger.debug("Celery broker 连接测试成功")
        return True

    except (RedisConnectionError, TimeoutError) as e:
        logger.debug(f"Celery broker 连接失败: {e}")
        return False
    except Exception as e:
        logger.warning(f"检测 Celery 可用性时发生意外错误: {e}")
        return False
