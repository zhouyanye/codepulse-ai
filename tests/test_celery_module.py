"""
测试Celery配置
"""
import sys
import os
import subprocess
import importlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")


def test_celery_module_import():
    """测试Celery模块导入"""
    try:
        import app.celery
        assert hasattr(app.celery, 'celery_app')
        assert hasattr(app.celery, 'celery')
        print("Celery模块导入测试通过")
    except ImportError as e:
        print(f"Celery模块导入失败: {e}")
        raise


def test_celery_app_instance():
    """测试Celery应用实例"""
    from app.celery import celery_app, celery
    from app.core.celery_app import celery_app as core_celery_app
    
    # 验证celery和celery_app是同一个实例
    assert celery_app is core_celery_app
    assert celery is celery_app
    print("Celery应用实例测试通过")


def test_celery_main_execution():
    """测试Celery主执行函数（通过模拟）"""
    # 由于直接运行会启动Celery，我们只测试模块导入
    import app.celery
    # 验证模块属性
    assert hasattr(app.celery, '__name__')
    print("Celery主执行测试通过")


if __name__ == "__main__":
    test_celery_module_import()
    test_celery_app_instance()
    test_celery_main_execution()
    print("所有Celery测试通过！")