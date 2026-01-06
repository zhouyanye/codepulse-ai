from pydantic import BaseModel, Field
from pydantic_settings import SettingsConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime


class HealthCheckResponse(BaseModel):
    status: str = Field(..., description="服务状态")
    timestamp: str = Field(..., description="时间戳")
    version: str = Field(..., description="API版本")

    model_config = SettingsConfigDict(extra="allow")


class AnalysisRequest(BaseModel):
    repo_url: str = Field(..., description="仓库URL (GitHub或Gitee)")
    ai_provider: str = Field("deepseek", description="AI服务提供商 (deepseek, kimi, openai, costrict)")
    include_code_analysis: bool = Field(True, description="是否包含代码分析")
    include_community_analysis: bool = Field(True, description="是否包含社区分析")
    include_static_scan: bool = Field(False, description="是否包含静态代码扫描")
    github_token: Optional[str] = Field(None, description="GitHub访问令牌")
    gitee_token: Optional[str] = Field(None, description="Gitee访问令牌")

    model_config = SettingsConfigDict(
        json_schema_extra={
            "example": {
                "repo_url": "https://github.com/owner/repo",
                "ai_provider": "deepseek",
                "include_code_analysis": True,
                "include_community_analysis": True,
                "include_static_scan": False
            },
            "examples": [
                {
                    "repo_url": "https://github.com/psf/requests",
                    "ai_provider": "costrict",
                    "include_code_analysis": True,
                    "include_community_analysis": True,
                    "include_static_scan": True
                },
                {
                    "repo_url": "https://gitee.com/owner/repo",
                    "ai_provider": "deepseek",
                    "include_code_analysis": True,
                    "include_community_analysis": True,
                    "include_static_scan": False,
                    "gitee_token": "your_gitee_token_here"
                }
            ]
        }
    )

    def __init__(self, **data):
        super().__init__(**data)

    @property
    def platform(self) -> str:
        """检测仓库平台"""
        url = self.repo_url.lower()
        if "gitee.com" in url:
            return "gitee"
        return "github"

    @property
    def token(self) -> Optional[str]:
        """获取对应平台的访问令牌"""
        return self.gitee_token if self.platform == "gitee" else self.github_token


class BatchAnalysisRequest(BaseModel):
    repo_urls: List[str] = Field(..., description="仓库URL列表 (GitHub或Gitee)")
    ai_provider: str = Field("deepseek", description="AI服务提供商 (deepseek, kimi, openai, costrict,doubao)")

    model_config = SettingsConfigDict(extra="allow")


class GenerateFixRequest(BaseModel):
    recommendation: dict = Field(..., description="修复建议信息")
    repo_url: str = Field(..., description="仓库URL")
    ai_provider: str = Field("deepseek", description="AI服务提供商")
    format: str = Field("code", description="输出格式: 'code' 或 'diff'")
    github_token: Optional[str] = Field(None, description="GitHub访问令牌")
    gitee_token: Optional[str] = Field(None, description="Gitee访问令牌")

    model_config = SettingsConfigDict(
        json_schema_extra={
            "example": {
                "recommendation": {
                    "id": "1",
                    "title": "建议标题",
                    "category": "security",
                    "priority": "high",
                    "description": "问题描述",
                    "issue": "具体问题",
                    "impact": "影响说明",
                    "recommendation": "修复建议",
                    "location": "src/settings.py:120-145"
                },
                "repo_url": "https://gitee.com/owner/repo",
                "ai_provider": "deepseek",
                "format": "code"
            }
        }
    )


class AnalysisHistoryItem(BaseModel):
    id: int
    repo_url: str
    platform: str
    owner: str
    repo_name: str
    overall_score: float
    code_quality_score: float
    community_score: float
    documentation_score: float
    maintenance_score: float
    security_score: float
    created_at: datetime

    model_config = SettingsConfigDict(extra="allow", from_attributes=True)
