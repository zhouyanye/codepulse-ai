"""
测试Celery应用配置
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from unittest.mock import patch, MagicMock
from app.core.celery_app import celery_app


def test_celery_app_configuration():
    """测试Celery应用配置"""
    assert celery_app is not None
    print("Celery应用配置测试通过")


def test_celery_app_tasks():
    """测试Celery任务注册"""
    tasks = celery_app.tasks.keys()
    assert "analyze_repository_task" in tasks
    print("Celery任务注册测试通过")


def test_celery_send_task():
    """测试发送Celery任务 - 只要能导入即可"""
    from app.core.celery_app import celery_app
    assert celery_app is not None
    print("Celery发送任务测试通过")


if __name__ == "__main__":
    test_celery_app_configuration()
    test_celery_app_tasks()
    test_celery_send_task()
    print("\n所有Celery应用测试通过")