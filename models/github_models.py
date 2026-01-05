from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class GitHubRepoInfo(BaseModel):
    owner: str = Field(..., alias="owner", description="仓库拥有者")
    name: str = Field(..., alias="name", description="仓库名称")
    full_name: str = Field(..., alias="full_name", description="仓库全名")
    description: Optional[str] = Field(None, alias="description", description="仓库描述")
    language: Optional[str] = Field(None, alias="language", description="仓库使用的编程语言")
    stars: int = Field(0, alias="stargazers_count", description="仓库的Star数量")
    forks: int = Field(0, alias="forks_count", description="仓库的Fork数量")
    open_issues: int = Field(0, alias="open_issues_count", description="仓库的Open Issue数量")
    created_at: str = Field(..., alias="created_at", description="仓库的创建时间")
    updated_at: str = Field(..., alias="updated_at", description="仓库的更新时间")
    pushed_at: str = Field(..., alias="pushed_at", description="仓库的推送时间")
    license: Optional[Dict[str, Any]] = Field(None, alias="license", description="仓库的许可证")
    topics: List[str] = Field(default_factory=list, description="仓库的标签")
    size: int = Field(0, alias="size", description="仓库的代码大小")
    default_branch: str = Field(..., alias="default_branch", default="main", description="仓库的默认分支")
    archived: bool = Field(False, alias="archived", description="仓库是否被归档")

    class Config:
        allow_population_by_field_name = True


class ContributorStats(BaseModel):
    login: str
    contributions: int
    avatar_url: Optional[str] = None


class CommitActivity(BaseModel):
    date: str
    commits: int


class IssueInfo(BaseModel):
    total_count: int = 0
    open_count: int = 0
    closed_count: int = 0
    avg_response_time: Optional[float] = None


class PullRequestInfo(BaseModel):
    total_count: int = 0
    open_count: int = 0
    merged_count: int = 0
    avg_merge_time: Optional[float] = None


class ReleaseInfo(BaseModel):
    latest_release: Optional[str] = None
    release_count: int = 0
    last_release_date: Optional[str] = None
