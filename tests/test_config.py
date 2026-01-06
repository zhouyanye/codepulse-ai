"""
测试配置加载。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from app.core.config import Settings


def test_settings_load():
    """测试配置加载"""
    settings = Settings()
    if settings.GITHUB_TOKEN is not None:
        assert isinstance(settings.GITHUB_TOKEN, str)
    if settings.GITEE_TOKEN is not None:
        assert isinstance(settings.GITEE_TOKEN, str)
    
    assert settings.REDIS_URL is not None
    assert settings.REDIS_URL.startswith("redis://")
    assert settings.CELERY_BROKER_URL == settings.REDIS_URL
    assert settings.CELERY_RESULT_BACKEND == settings.REDIS_URL
    print("配置加载测试通过")


def test_settings_defaults():
    """测试配置默认值"""
    settings = Settings()
    assert settings.PROJECT_NAME == "Codepulse Ai 开源项目健康扫描器"
    assert settings.PROJECT_VERSION == "1.0.0"
    assert settings.API_V1_STR == "/api/v1"
    assert settings.BACKEND_CORS_ORIGINS == ["*"]
    assert settings.CELERY_TASK_SERIALIZER == "json"
    assert settings.CELERY_TIMEZONE == "Asia/Shanghai"
    print("配置默认值测试通过")


def test_settings_types():
    """测试配置类型"""
    settings = Settings()
    assert isinstance(settings.GITHUB_TOKEN, (str, type(None)))
    assert isinstance(settings.GITEE_TOKEN, (str, type(None)))
    assert isinstance(settings.REDIS_PORT, int)
    assert isinstance(settings.REDIS_DB, int)
    assert isinstance(settings.CELERY_TASK_TIME_LIMIT, int)
    print("配置类型测试通过")


if __name__ == "__main__":
    test_settings_load()
    test_settings_defaults()
    test_settings_types()
    print("所有配置测试通过")
