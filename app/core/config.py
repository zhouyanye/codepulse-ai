import logging
from typing import List, Optional, Any
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    PROJECT_NAME: str = "Codepulse Ai 开源项目健康扫描器"
    PROJECT_VERSION: str = "1.0.0"

    # 调试模式
    DEBUG: bool = False

    # API配置
    API_V1_STR: str = "/api/v1"

    # 数据库配置
    DATABASE_URL: str = "sqlite:///./data/codepulse.db"

    # CORS配置
    BACKEND_CORS_ORIGINS: List[str] = ["*"]

    # GitHub配置
    GITHUB_TOKEN: Optional[str] = None

    # Gitee配置
    GITEE_TOKEN: Optional[str] = None

    # AI配置
    DEEPSEEK_API_KEY: Optional[str] = None
    KIMI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    COSTRICT_API_KEY: Optional[str] = None
    DOUBAO_API_KEY: Optional[str] = None

    # 静态扫描配置
    MAX_FILE_SIZE: int = 30 * 1024
    MAX_AI_RETRIES: int = 3
    MAX_TOTAL_FILES: int = 50
    MAX_PROMPT_LEN: int = 20000
    BATCH_DELAY: int = 2
    MAX_BATCH_CHARS: int = 50000

    # Redis配置
    REDIS_URL: str = "redis://127.0.0.1:6379/0"
    REDIS_PASSWORD: Optional[str] = None
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_CACHE_TTL: int = 86400

    # Celery配置
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None
    ANALYSIS_TIMEOUT: int = 1200  # 20分钟，支持大项目分析
    CELERY_TASK_SERIALIZER: str = "json"
    CELERY_RESULT_SERIALIZER: str = "json"
    CELERY_ACCEPT_CONTENT: List[str] = ["json"]
    CELERY_TIMEZONE: str = "Asia/Shanghai"
    CELERY_ENABLE_UTC: bool = True
    CELERY_TASK_TRACK_STARTED: bool = True
    CELERY_TASK_TIME_LIMIT: int = 30 * 60  # 30分钟
    CELERY_RESULT_EXPIRES: int = 24 * 60 * 60  # 24小时

    # 评分权重
    SCORE_WEIGHT_CODE: float = 0.3
    SCORE_WEIGHT_COMMUNITY: float = 0.2
    SCORE_WEIGHT_DOC: float = 0.15
    SCORE_WEIGHT_MAINTENANCE: float = 0.15
    SCORE_WEIGHT_SECURITY: float = 0.2

    # 执行模式配置
    ENABLE_CELERY_TASKS: bool = True  # 是否启用Celery异步任务端点
    ENABLE_SYNC_POLLING: bool = True  # 是否启用同步轮询端点（生产环境默认禁用）
    AUTO_SELECT_EXECUTION_MODE: bool = True  # 统一接口是否自动选择执行模式

    # Git克隆配置
    GIT_MIRRORS: List[str] = [
        "kkgithub.com",            # 最快，国内推荐
        "github.akams.cn",        # 支持raw文件加速
        "bgithub.xyz",            # 直接访问支持
        "gitclone.com",           # 克隆加速服务
        "hub.fastgit.org",        # FastGit镜像，国内访问速度快
        "ghproxy.com",            # GitHub代理
        "githubproxy.cc",         # 备选代理
        "ghproxy.net"             # 备选代理
    ]
    GIT_TIMEOUT: int = 60  # Git操作超时时间（秒）
    GIT_MAX_RETRIES: int = 2  # Git操作最大重试次数

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    def model_post_init(self, __context: Any) -> None:
        """初始化后验证及设置默认值"""
        if not self.CELERY_BROKER_URL:
            self.CELERY_BROKER_URL = self.REDIS_URL
        if not self.CELERY_RESULT_BACKEND:
            self.CELERY_RESULT_BACKEND = self.REDIS_URL

        self._validate_config()

    def _validate_config(self):
        """验证必要配置项"""
        if not self.GITHUB_TOKEN and not self.GITEE_TOKEN:
            logger.warning("未配置GitHub或Gitee令牌，可能影响仓库访问功能")

        if not any([self.DEEPSEEK_API_KEY, self.KIMI_API_KEY, self.OPENAI_API_KEY, self.COSTRICT_API_KEY,
                    self.DOUBAO_API_KEY]):
            logger.warning("未配置任何AI API密钥，AI分析功能将无法使用")

        if not self.REDIS_URL or self.REDIS_URL == "redis://127.0.0.1:6379/0":
            logger.info("使用默认Redis配置，如果是首次运行请确保Redis服务已启动")


settings = Settings()
