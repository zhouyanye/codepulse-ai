from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.database import Base, engine
from app.api.endpoints import analysis, health


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 初始化数据库表
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("数据库表初始化成功")
    except Exception as e:
        logger.error(f"数据库表初始化失败: {e}")

    logger.info("启动开源项目健康扫描器后端服务")
    yield
    logger.info("关闭开源项目健康扫描器后端服务")
    # 在关闭时清理所有分析任务
    try:
        from models.task_manager import task_manager
        import asyncio
        # 从数据库获取所有进行中的任务并取消
        # 由于task_manager使用数据库存储，这里主要是更新状态
        logger.info("已触发应用关闭，正在处理未完成的任务")
    except Exception as e:
        logger.error(f"清理分析任务时出错: {e}")


# 创建FastAPI应用
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="一个用于分析开源项目健康状况的AI驱动工具",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    authors=[{"name": "Yanleaf", "url": "https://github.com/zhouyanye/codepulse-ai"}],
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(health.router, prefix=settings.API_V1_STR)
app.include_router(analysis.router, prefix=settings.API_V1_STR)

if __name__ == "__main__":
    import uvicorn

    # 在开发环境中，如果使用热重载，建议将reload设置为False以避免任务状态丢失
    # 但在开发阶段保留热重载功能，以便快速开发
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        reload_dirs=["app", "services", "utils", "models"],
        log_level="info",
        log_config=None
    )