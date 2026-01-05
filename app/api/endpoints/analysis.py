import os
import json
import asyncio
import logging
import threading
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Depends, Request
from sqlalchemy.orm import Session
from ratelimit import limits, sleep_and_retry

from models.request_models import (
    AnalysisRequest, BatchAnalysisRequest, GenerateFixRequest, AnalysisHistoryItem
)
from models.analysis_models import AnalysisResult

# 服务导入
from services.analysis_service import AnalysisService
from services.history_service import HistoryService
from services.cost_estimation_service import CostEstimationService
from services.auto_fix_service import AutoFixService

from app.core.database import get_db
from app.core.config import settings
from app.tasks.analysis_tasks import analyze_repository_task
from models.task_manager import task_manager
from utils.celery_utils import (
    get_task_status,
    cache_analysis_result,
    get_cached_analysis_result,
    generate_cache_key,
    list_cache_keys,
    delete_cache_key
)
from utils.git_utils import GitUtils

router = APIRouter(tags=["Analysis"])
logger = logging.getLogger(__name__)

AI_PROVIDER_FALLBACK = ["deepseek", "kimi", "doubao", "openai", "costrict"]


def get_client_ip(request: Request) -> str:
    """获取客户端IP地址，优先处理反向代理情况。"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


def get_available_ai_provider(request_ai_provider: Optional[str] = None) -> str:
    """
    获取可用的 AI 提供商，支持降级逻辑。
    优先级: 用户指定的 -> deepseek -> kimi -> doubao -> openai -> costrict
    CoStrict模式不依赖API Key，仅进行基础评分。
    """
    # 如果用户明确指定costrict，直接返回
    if request_ai_provider == "costrict":
        return "costrict"

    # 检查用户指定的其他提供商
    if request_ai_provider and hasattr(settings, f"{request_ai_provider.upper()}_API_KEY"):
        api_key = getattr(settings, f"{request_ai_provider.upper()}_API_KEY")
        if api_key:
            return request_ai_provider

    # 按照预设的优先级列表查找第一个可用的提供商
    for provider in AI_PROVIDER_FALLBACK:
        if provider == "costrict":
            return "costrict"
        if hasattr(settings, f"{provider.upper()}_API_KEY") and getattr(settings, f"{provider.upper()}_API_KEY"):
            return provider

    # 如果所有API提供商都不可用，则回退到costrict
    return "costrict"


async def _cleanup_cloned_repo(repo_url: str):
    """清理因分析而克隆的临时仓库文件。"""
    try:
        git_utils = GitUtils()
        url_info = git_utils.normalize_url(repo_url)
        if url_info['owner'] and url_info['repo']:
            cache_key = f"{url_info['platform']}_{url_info['owner']}_{url_info['repo']}"
            if hasattr(git_utils, '_repo_cache') and cache_key in git_utils._repo_cache:
                repo_path, _ = git_utils._repo_cache[cache_key]
                await git_utils.cleanup_repo(repo_path, cache_key)
                logger.info(f"已清理临时仓库: {repo_path}")
    except Exception as e:
        logger.error(f"清理克隆仓库失败: {str(e)}", exc_info=True)


async def _wait_for_user_confirmation(task_id: str, timeout: int = 300) -> bool:
    """
    等待用户确认成本，超时则取消任务。
    
    返回:
        True: 用户已确认，继续分析
        False: 用户已取消或超时，终止分析
    """
    import time
    start_time = time.time()

    logger.info(f"等待用户确认分析成本（最长等待{timeout}秒）: {task_id}")

    while time.time() - start_time < timeout:
        task_data = task_manager.get_task(task_id)
        if not task_data:
            logger.warning(f"任务不存在: {task_id}")
            return False

        # 检查用户取消
        if task_data.get("cancelled"):
            logger.info(f"检测到用户取消: {task_id}")
            return False

        # 检查用户确认
        if task_data.get("user_confirmed"):
            logger.info(f"用户已确认: {task_id}")
            return True

        await asyncio.sleep(1)

    # 超时处理
    logger.info(f"用户确认超时，任务已取消: {task_id}")
    task_manager.update_task(task_id, status="cancelled", cancelled=True, message="用户确认超时，分析已取消")
    return False


async def _run_sync_analysis_with_progress(task_id: str, request: dict):
    """
    同步模式执行分析任务（带进度更新）。
    优化流程:
    1. 先进行成本估算
    2. 用户确认后才克隆仓库。
    3. 克隆和处理过程中定期检查取消状态。
    """
    
    # 首先检查Git是否可用
    try:
        git_utils = GitUtils()
    except RuntimeError as e:
        logger.error(f"Git不可用，无法执行分析: {e}")
        task_manager.update_task(task_id, status="failed", error=str(e),
                                 message="Git不可用，无法执行分析。请安装Git并确保其在系统PATH中。")
        return

    async def update_progress(progress: int, message: str):
        task_manager.update_task(task_id, progress=progress, message=message)

    def check_cancelled() -> bool:
        """检查任务是否被取消（同步函数）"""
        task_data = task_manager.get_task(task_id)
        return task_data and task_data.get("cancelled", False)

    try:
        task_data = task_manager.get_task(task_id)
        if not task_data:
            logger.error(f"任务不存在: {task_id}")
            return

        repo_url = task_data["repo_url"]
        ai_provider = task_data["ai_provider"]
        include_static_scan = task_data["include_static_scan"]
        github_token = task_data["github_token"]
        gitee_token = task_data["gitee_token"]

        await update_progress(5, "正在初始化分析环境...")

        if check_cancelled(): return

        # 克隆仓库
        await update_progress(10, "正在克隆仓库...")
        git_utils = GitUtils()
        if check_cancelled(): return

        # 传递取消检查函数到克隆操作
        repo_path = await git_utils.clone_repo(
            repo_url,
            token=github_token if "github.com" in repo_url else gitee_token,
            cancel_callback=check_cancelled
        )

        if check_cancelled():
            await _cleanup_cloned_repo(repo_url)
            return

        if not repo_path or not os.path.exists(repo_path):
            error_msg = "无法克隆仓库，请检查仓库地址或网络连接"
            logger.error(f"{error_msg}: {repo_url}")
            task_manager.update_task(task_id, status="failed", error=error_msg, message=error_msg)
            return

        # 基于克隆的仓库评估成本
        if ai_provider != "costrict":
            await update_progress(30, "正在评估分析成本...")
            cost_service = CostEstimationService()
            try:
                # 基于已克隆的路径评估成本
                import shutil
                cost_estimate = await cost_service.estimate_repository_cost_from_path(
                    repo_path=repo_path,
                    repo_url=repo_url,
                    include_static_scan=include_static_scan,
                    ai_provider=ai_provider
                )
                task_manager.update_task(task_id, cost_estimate=cost_estimate)
                await update_progress(40, "成本估算完成，等待用户确认...")

                # 等待用户确认，并检查返回值
                user_confirmed = await _wait_for_user_confirmation(task_id)
                if not user_confirmed:
                    logger.info(f"用户取消或超时，终止分析: {task_id}")
                    await _cleanup_cloned_repo(repo_url)
                    return

            except Exception as e:
                logger.error(f"成本估算失败: {e}", exc_info=True)
                task_manager.update_task(task_id, status="failed", error=str(e),
                                         message=f"分析失败: 成本估算失败 - {str(e)}")
                await _cleanup_cloned_repo(repo_url)
                return

        # 执行分析（用户确认后或CoStrict模式直接执行）

        # 执行分析
        await update_progress(60, f"正在使用 {ai_provider} 进行分析...")
        service = AnalysisService()
        analysis_request = AnalysisRequest(
            repo_url=repo_url, ai_provider=ai_provider, include_static_scan=include_static_scan,
            github_token=github_token, gitee_token=gitee_token
        )
        result = await service.analyze_repository(analysis_request, progress_callback=update_progress)

        if check_cancelled():
            await _cleanup_cloned_repo(repo_url)
            return

        # 保存结果并完成任务
        await update_progress(90, "正在保存分析结果...")
        result_dict = result.dict() if hasattr(result, "dict") else result

        task_manager.update_task(task_id, status="completed", result=result_dict, progress=100, message="分析完成")

        try:
            db = next(get_db())
            history_service = HistoryService(db)
            history_service.save_analysis(repo_url, result)
            logger.info(f"分析记录已保存到数据库: {repo_url}")
        except Exception as e:
            logger.error(f"保存分析记录失败: {str(e)}")

        await _cleanup_cloned_repo(repo_url)
        logger.info(f"分析任务完成: {task_id}")

    except Exception as e:
        logger.error(f"分析任务失败: {str(e)}", exc_info=True)
        error_message = f"分析失败: {str(e)}"
        if "git" in str(e).lower() or "clone" in str(e).lower():
            error_message = "仓库克隆失败，请检查仓库地址或网络连接"
        task_manager.update_task(task_id, status="failed", error=str(e), message=error_message)
        await _cleanup_cloned_repo(repo_url)


@router.post("/analyze", response_model=AnalysisResult)
async def analyze_repository(
        request: AnalysisRequest,
        async_mode: bool = Query(False, description="是否异步执行（返回任务ID）"),
        db: Session = Depends(get_db)
):
    """分析单个GitHub/Gitee仓库的健康状况。"""
    cache_key = generate_cache_key(request.repo_url, request.model_dump())
    cached = get_cached_analysis_result(cache_key)
    if cached:
        logger.info(f"缓存命中: {cache_key}")
        return AnalysisResult(**cached)

    if async_mode:
        task = analyze_repository_task.delay(request.model_dump())
        logger.info(f"已提交异步分析任务，任务ID: {task.id}")
        raise HTTPException(
            status_code=202,
            detail="分析任务已提交，请使用任务ID查询状态",
            headers={"X-Task-Id": task.id}
        )

    try:
        logger.info(f"收到同步分析请求: {request.repo_url}")
        
        # 检查Git是否可用
        try:
            git_utils = GitUtils()
        except RuntimeError as e:
            logger.error(f"Git不可用，无法执行分析: {e}")
            raise RuntimeError("Git不可用，无法执行分析。请安装Git并确保其在系统PATH中。")
        
        service = AnalysisService()
        result = await asyncio.wait_for(service.analyze_repository(request), timeout=1500.0)

        cache_analysis_result(cache_key, result.dict())
        logger.info(f"结果已缓存，缓存键: {cache_key}")

        history_service = HistoryService(db)
        history_service.save_analysis(request.repo_url, result)
        logger.info(f"分析记录已保存到数据库: {request.repo_url}")

        return result

    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="分析超时，请稍后重试")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"分析失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@router.post("/analyze/async")
async def analyze_repository_async(request: AnalysisRequest):
    """提交异步分析任务，立即返回任务ID。"""
    cache_key = generate_cache_key(request.repo_url, request.model_dump())
    cached = get_cached_analysis_result(cache_key)
    if cached:
        return {"cached": True, "result": cached, "message": "结果来自缓存"}

    task = analyze_repository_task.delay(request.model_dump())
    logger.info(f"已提交异步分析任务，任务ID: {task.id}")
    return {
        "task_id": task.id,
        "status": "PENDING",
        "message": "分析任务已提交，请使用任务ID查询状态",
        "cache_key": cache_key
    }


@limits(calls=5, period=60)
@sleep_and_retry
@router.post("/analyze/batch", response_model=List[AnalysisResult])
async def analyze_multiple_repositories(request: BatchAnalysisRequest):
    """批量分析多个GitHub/Gitee仓库。"""
    try:
        logger.info(f"收到批量分析请求，仓库数量: {len(request.repo_urls)}")
        service = AnalysisService()
        results = await asyncio.wait_for(
            service.analyze_multiple_repositories(request.repo_urls, request.ai_provider),
            timeout=3600.0
        )
        return results
    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="批量分析超时，请减少仓库数量或稍后重试")
    except Exception as e:
        logger.error(f"批量分析失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"批量分析失败: {str(e)}")


@limits(calls=10, period=60)
@sleep_and_retry
@router.post("/analyze/sync-polling")
async def analyze_repository_sync_polling(request: dict):
    """
    启动一个支持轮询进度的同步分析任务。
    流程: 成本评估 -> 用户确认 -> 克隆 -> AI分析。
    """
    try:
        repo_url = request.get("repo_url")
        if not repo_url:
            raise HTTPException(status_code=400, detail="仓库地址不能为空")

        actual_ai_provider = get_available_ai_provider(request.get("ai_provider"))
        
        # 检查Git是否可用
        try:
            git_utils = GitUtils()
        except RuntimeError as e:
            logger.error(f"Git不可用，无法启动分析任务: {e}")
            raise HTTPException(status_code=500, detail="Git不可用，无法执行分析。请安装Git并确保其在系统PATH中。")

        task_data = {
            "status": "initializing", "progress": 0, "message": "任务初始化中", "cost_estimate": None,
            "result": None, "error": None, "cancelled": False, "ai_provider": actual_ai_provider,
            "repo_url": repo_url, "include_static_scan": request.get("include_static_scan", True),
            "github_token": request.get("github_token"), "gitee_token": request.get("gitee_token"),
            "user_confirmed": False
        }
        task_id = task_manager.create_task(task_data)
        logger.info(f"启动同步分析任务: {task_id}, AI提供商: {actual_ai_provider}")

        def run_analysis_task():
            try:
                asyncio.run(_run_sync_analysis_with_progress(task_id, request))
            except Exception as e:
                logger.error(f"分析任务执行失败: {str(e)}", exc_info=True)
                error_message = f"分析任务执行失败: {str(e)}"
                if isinstance(e, asyncio.TimeoutError):
                    error_message = "分析任务超时，可能仓库过大或网络连接缓慢"
                elif "git" in str(e).lower() or "clone" in str(e).lower():
                    error_message = "仓库克隆失败，请检查仓库地址或网络连接"
                elif "api" in str(e).lower() or "token" in str(e).lower():
                    error_message = "API访问失败，请检查API密钥或访问权限"
                task_manager.update_task(task_id, status="failed", error=str(e), message=error_message)

        thread = threading.Thread(target=run_analysis_task, daemon=True)
        thread.start()

        return {"task_id": task_id, "status": "initializing", "message": "分析任务已启动"}
    except Exception as e:
        logger.error(f"启动分析任务失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"启动分析任务失败: {str(e)}")


@router.get("/analyze/polling-status/{task_id}")
async def get_polling_task_status(task_id: str):
    """获取同步轮询分析任务的状态、进度和结果。"""
    task_data = task_manager.get_task(task_id)
    if not task_data:
        raise HTTPException(status_code=404, detail="任务不存在")

    return {
        "task_id": task_id, "status": task_data.get("status", "unknown"),
        "progress": task_data.get("progress", 0), "message": task_data.get("message", ""),
        "cost_estimate": task_data.get("cost_estimate"), "result": task_data.get("result"),
        "error": task_data.get("error"), "cancelled": task_data.get("cancelled", False),
        "ai_provider": task_data.get("ai_provider"), "repo_url": task_data.get("repo_url"),
        "user_confirmed": task_data.get("user_confirmed", False)
    }


@router.post("/analyze/confirm-cost/{task_id}")
async def confirm_cost(task_id: str):
    """用户确认成本估算，并允许分析任务继续执行。"""
    task_data = task_manager.get_task(task_id)
    if not task_data:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task_manager.update_task(task_id, user_confirmed=True):
        return {"message": "成本确认成功，分析将继续"}
    raise HTTPException(status_code=500, detail="更新任务状态失败")


@router.post("/analyze/cancel/{task_id}")
async def cancel_analysis(task_id: str):
    """取消一个正在进行的分析任务。"""
    task_data = task_manager.get_task(task_id)
    if not task_data:
        raise HTTPException(status_code=404, detail="任务不存在")

    try:
        # 更新取消状态
        success = task_manager.update_task(task_id, cancelled=True, status="cancelled", message="用户取消分析")

        # 清理克隆的仓库
        repo_url = task_data.get("repo_url")
        if repo_url:
            await _cleanup_cloned_repo(repo_url)

        if success:
            logger.info(f"任务取消成功: {task_id}")
            return {"message": "分析任务已取消", "success": True}
        else:
            logger.warning(f"任务更新失败，但清理完成: {task_id}")
            return {"message": "任务已取消（状态更新失败）", "success": True}

    except Exception as e:
        logger.error(f"取消任务异常: {e}", exc_info=True)
        # 即使更新失败，也尝试返回成功（避免前端报错）
        return {"message": "任务已取消", "success": True}


@router.get("/analyze/status/{task_id}")
async def get_analysis_status(task_id: str):
    """获取Celery异步任务的状态。"""
    return get_task_status(task_id)


@router.get("/analyze/result/{task_id}")
async def get_analysis_result(task_id: str):
    """获取Celery异步任务的最终结果。"""
    status = get_task_status(task_id)
    if status['status'] == 'SUCCESS':
        return status['result']
    elif status['status'] == 'FAILED':
        raise HTTPException(status_code=500, detail=f"任务失败: {status.get('error', '未知错误')}")
    else:
        raise HTTPException(status_code=202, detail="任务尚未完成", headers={"X-Task-Status": status['status']})


@router.get("/analyze/history", response_model=List[AnalysisHistoryItem])
async def get_analysis_history(limit: int = 10, db: Session = Depends(get_db)):
    """获取最近的分析历史记录。"""
    service = HistoryService(db)
    return service.get_recent_history(limit)


@router.get("/analyze/history/{analysis_id}", response_model=AnalysisResult)
async def get_analysis_by_id(analysis_id: int, db: Session = Depends(get_db)):
    """根据ID获取特定的分析历史记录详情。"""
    service = HistoryService(db)
    record = service.get_analysis_by_id(analysis_id)
    if not record:
        raise HTTPException(status_code=404, detail="分析记录不存在")

    try:
        result_data = record.result_json
        if isinstance(result_data, str):
            result_data = json.loads(result_data)
        return AnalysisResult(**result_data)
    except Exception as e:
        logger.error(f"重建分析结果失败: {str(e)}")
        raise HTTPException(status_code=500, detail="分析记录格式错误或已损坏")


@router.post("/estimate-cost")
async def estimate_cost(request: dict):
    """独立的接口，用于估算分析一个仓库的成本。"""
    try:
        repo_url = request.get("repo_url")
        if not repo_url:
            raise HTTPException(status_code=400, detail="仓库地址不能为空")

        actual_ai_provider = get_available_ai_provider(request.get("ai_provider", "deepseek"))
        include_static_scan = request.get("include_static_scan", True)

        logger.info(f"收到成本估算请求: {repo_url}, AI提供商: {actual_ai_provider}")
        
        # 检查Git是否可用（成本估算可能需要访问仓库）
        try:
            git_utils = GitUtils()
        except RuntimeError as e:
            if include_static_scan:  # 如果需要静态扫描，则必须有Git
                logger.error(f"Git不可用，无法执行需要静态扫描的成本估算: {e}")
                raise HTTPException(status_code=500, detail="Git不可用，无法执行需要静态扫描的成本估算。请安装Git并确保其在系统PATH中。")
            else:
                logger.warning(f"Git不可用，但仍可进行基础成本估算: {e}")

        cost_service = CostEstimationService()
        result = await cost_service.estimate_repository_cost(
            repo_url=repo_url, include_static_scan=include_static_scan, ai_provider=actual_ai_provider,
            github_token=request.get("github_token"), gitee_token=request.get("gitee_token")
        )

        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=result.get("error", "成本估算失败"))

        logger.info(
            f"成本估算完成: tokens={result.get('estimated_tokens', 0)}, cost={result.get('estimated_cost_rmb', 0):.4f} RMB")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"成本估算异常: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"成本估算失败: {str(e)}")


@limits(calls=20, period=60)
@sleep_and_retry
@router.post("/generate-fix")
async def generate_auto_fix(request: GenerateFixRequest):
    """根据分析建议，生成代码修复或Git Diff补丁。"""
    try:
        logger.info(f"收到{'Diff' if request.format == 'diff' else '修复代码'}生成请求")
        fix_service = AutoFixService(ai_provider=request.ai_provider)
        result = await fix_service.generate_fix(
            recommendation=request.recommendation, repo_url=request.repo_url, format_type=request.format,
            github_token=request.github_token, gitee_token=request.gitee_token
        )
        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=result.get("error", "生成修复失败"))
        logger.info(f"{'Diff' if request.format == 'diff' else '修复代码'}生成完成")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成修复失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"生成修复失败: {str(e)}")


@router.get("/analyze/cache")
async def list_cached_results(pattern: str = Query("*", description="Redis键匹配模式，默认为*")):
    """列出所有缓存的分析结果的键。"""
    try:
        keys = list_cache_keys(pattern)
        return {"pattern": pattern, "count": len(keys), "keys": keys}
    except Exception as e:
        logger.error(f"列出缓存键失败: {e}")
        raise HTTPException(status_code=500, detail=f"列出缓存键失败: {str(e)}")


@router.delete("/analyze/cache/{cache_key}")
async def clear_cached_result(cache_key: str):
    """清除指定的缓存分析结果。"""
    try:
        if delete_cache_key(cache_key):
            return {"message": f"缓存键 {cache_key} 已删除", "deleted": True}
        raise HTTPException(status_code=404, detail="缓存键不存在")
    except Exception as e:
        logger.error(f"删除缓存失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除缓存失败: {str(e)}")
