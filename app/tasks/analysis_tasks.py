import asyncio
import logging
from app.core.celery_app import celery_app
from services.analysis_service import AnalysisService
from models.request_models import AnalysisRequest
from models.analysis_models import AnalysisResult
from typing import Dict, Any

logger = logging.getLogger(__name__)


def sync_to_async(coro):
    """在同步上下文中运行异步协程"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, name='analyze_repository_task')
def analyze_repository_task(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
   用于分析仓库的Celery任务
    """
    task_id = self.request.id
    logger.info(f"Starting analysis task {task_id} with data: {request_data}")

    # 更新任务状态为开始
    self.update_state(state='PROGRESS', meta={'progress': 0, 'message': '开始分析'})

    # 构建AnalysisRequest对象
    try:
        request = AnalysisRequest(**request_data)
    except Exception as e:
        logger.error(f"Invalid request data: {e}")
        return {
            'error': f'Invalid request data: {str(e)}',
            'task_id': task_id,
            'status': 'FAILED'
        }

    # 定义进度回调函数
    def progress_callback(progress: int, message: str):
        # 更新Celery任务状态
        self.update_state(
            state='PROGRESS',
            meta={'progress': progress, 'message': message}
        )
        logger.info(f"Task {task_id} progress: {progress}% - {message}")

    # 运行异步分析
    async def run_analysis():
        service = AnalysisService()
        result: AnalysisResult = await service.analyze_repository(
            request,
            progress_callback=progress_callback
        )
        return result.dict() if hasattr(result, 'dict') else result

    try:
        result_dict = sync_to_async(run_analysis())
        logger.info(f"分析任务 {task_id} 成功完成")
        return {
            'task_id': task_id,
            'status': 'SUCCESS',
            'result': result_dict
        }
    except asyncio.TimeoutError as e:
        logger.exception(f"分析任务 {task_id} 超时: {e}")
        return {
            'task_id': task_id,
            'status': 'FAILED',
            'error': f'分析超时: {str(e)}'
        }
    except Exception as e:
        logger.exception(f"分析任务 {task_id} 失败并带有回溯信息:")
        import traceback
        traceback_str = traceback.format_exc()
        logger.error(traceback_str)
        return {
            'task_id': task_id,
            'status': 'FAILED',
            'error': str(e),
            'traceback': traceback_str
        }

