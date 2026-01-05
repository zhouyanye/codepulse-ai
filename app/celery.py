# 从核心模块导入Celery应用
from app.core.celery_app import celery_app

# 为Celery命令行提供别名
celery = celery_app

if __name__ == '__main__':
    celery_app.start()
