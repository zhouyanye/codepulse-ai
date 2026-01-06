"""
测试Celery任务。
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from unittest.mock import patch, MagicMock
from app.tasks.analysis_tasks import analyze_repository_task
from utils.celery_utils import get_task_status


def test_analyze_repository_task_mock():
    """测试分析仓库任务"""
    with patch('app.tasks.analysis_tasks.AnalysisService') as MockService, \
         patch('celery.Task.update_state') as mock_update_state:
        mock_service = MagicMock()
        # 设置 analyze_repository 为异步 mock
        async def mock_analyze(*args, **kwargs):
            return {
                "repo_info": {"full_name": "test/repo"},
                "overall_score": 80
            }
        mock_service.analyze_repository = mock_analyze
        MockService.return_value = mock_service

        # 调用任务（同步）
        # 注意：这里需要确保 Redis 连接不被触发，或者被 Mock
        # 由于 Celery 配置使用了 Redis，apply() 可能会尝试连接结果后端
        # 我们可以尝试配置 Celery 使用内存后端，或者 Mock 整个 celery_app
        
        # 临时修改 backend 为 memory (如果可行)
        from app.core.celery_app import celery_app
        original_backend = celery_app.conf.result_backend
        celery_app.conf.result_backend = 'cache+memory://'
        celery_app.conf.broker_url = 'memory://'
        
        try:
            result = analyze_repository_task.apply(args=[{
                "repo_url": "https://gitee.com/zhou-yanye/houseSpider",
                "ai_provider": "deepseek"
            }]).get()
        finally:
            celery_app.conf.result_backend = original_backend

        assert isinstance(result, dict)
        assert result["status"] == "SUCCESS"
        assert "repo_info" in result["result"]
        assert result["result"]["overall_score"] == 80
        print("Celery任务执行测试通过")


def test_task_status():
    """测试任务状态查询"""
    with patch('utils.celery_utils.AsyncResult') as MockAsyncResult:
        mock_result = MagicMock()
        mock_result.status = "SUCCESS"
        mock_result.ready.return_value = True
        mock_result.successful.return_value = True
        mock_result.result = {"test": "data"}
        MockAsyncResult.return_value = mock_result

        status = get_task_status("fake_task_id")
        assert status["status"] == "SUCCESS"
        assert status["result"] == {"test": "data"}
        print("任务状态查询测试通过")


def test_task_status_pending():
    """测试任务待处理状态"""
    with patch('utils.celery_utils.AsyncResult') as MockAsyncResult:
        mock_result = MagicMock()
        mock_result.status = "PENDING"
        mock_result.ready.return_value = False
        MockAsyncResult.return_value = mock_result

        status = get_task_status("pending_task_id")
        assert status["status"] == "PENDING"
        assert status["result"] is None
        print("任务待处理状态测试通过")


def test_task_status_failure():
    """测试任务失败状态"""
    with patch('utils.celery_utils.AsyncResult') as MockAsyncResult:
        mock_result = MagicMock()
        mock_result.status = "FAILURE"
        mock_result.ready.return_value = True
        mock_result.successful.return_value = False
        mock_result.traceback = "Fake traceback"
        MockAsyncResult.return_value = mock_result

        status = get_task_status("failed_task_id")
        assert status["status"] == "FAILURE"
        assert "error" in status
        print("任务失败状态测试通过")


if __name__ == "__main__":
    test_analyze_repository_task_mock()
    test_task_status()
    test_task_status_pending()
    test_task_status_failure()
    print("所有Celery任务测试通过")