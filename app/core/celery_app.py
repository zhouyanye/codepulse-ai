from celery import Celery
from app.core.config import settings

# 创建Celery应用实例
celery_app = Celery(
    'codepulse_ai',
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=['app.tasks.analysis_tasks'],
    broker_connection_retry_on_startup = True,
)

# 从配置类加载配置
celery_app.conf.update(
    task_serializer=settings.CELERY_TASK_SERIALIZER,
    result_serializer=settings.CELERY_RESULT_SERIALIZER,
    accept_content=settings.CELERY_ACCEPT_CONTENT,
    timezone=settings.CELERY_TIMEZONE,
    enable_utc=settings.CELERY_ENABLE_UTC,
    task_track_started=settings.CELERY_TASK_TRACK_STARTED,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    result_expires=settings.CELERY_RESULT_EXPIRES,
)

# 自动发现任务
celery_app.autodiscover_tasks(['app.tasks'])

# 定义任务路由
celery_app.conf.task_routes = {
    'app.tasks.analysis_tasks.analyze_repository_task': {'queue': 'analysis'},
}