from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

from pydantic_settings import SettingsConfigDict


class SecurityIssue(BaseModel):
    """安全漏洞详情模型"""
    severity: str = Field(description="严重性等级：高、中、低")
    title: str = Field(description="漏洞标题")
    type: str = Field(description="漏洞类型")
    location: str = Field(description="代码位置，如：filename.py:line-line")
    analysis: str = Field(description="详细分析")
    impact: str = Field(description="潜在影响")
    issue_code: str = Field(description="问题代码片段")
    fix_code: str = Field(description="修复代码示例")
    recommendation: str = Field(description="修复建议")
    description: Optional[str] = Field(None, description="问题描述")


class CodeQualityMetrics(BaseModel):
    score: float = Field(0, ge=0, le=100, description="代码质量得分")
    complexity: float = Field(0, ge=0, le=100, description="代码复杂度得分")
    test_coverage: Optional[float] = Field(None, ge=0, le=100, description="代码测试覆盖率得分")
    documentation_score: float = Field(0, ge=0, le=100, description="代码文档得分")
    security_issues: List[Dict[str, Any]] = Field(default_factory=list, description="安全漏洞列表")
    code_standards: List[str] = Field(default_factory=list, description="代码质量标准得分")
    dependencies_health: Dict[str, Any] = Field(default_factory=dict, description="依赖健康得分")
    # 静态扫描结果
    static_scan_results: Optional[Dict[str, Any]] = Field(default_factory=dict, description="静态扫描结果")
    security_score: float = Field(0, ge=0, le=100, description="安全得分")


class CommunityHealthMetrics(BaseModel):
    score: float = Field(0, ge=0, le=100, description="社区健康得分")
    contributors_count: int = 0
    recent_activity: Dict[str, int] = Field(default_factory=dict)
    issue_health: Dict[str, Any] = Field(default_factory=dict)
    pr_health: Dict[str, Any] = Field(default_factory=dict)
    community_growth: Dict[str, int] = Field(default_factory=dict)
    model_config = SettingsConfigDict(extra="allow")


class DocumentationMetrics(BaseModel):
    score: float = Field(0, ge=0, le=100)
    readme_quality: float = Field(0, ge=0, le=100)
    has_contributing: bool = Field(False, description="是否包含贡献指南")
    has_license: bool = Field(False, description="是否包含许可证")
    has_code_of_conduct: bool = False
    has_issue_template: bool = False
    has_pr_template: bool = False
    wiki_enabled: bool = False
    model_config = SettingsConfigDict(extra="allow")


class MaintenanceMetrics(BaseModel):
    score: float = Field(0, ge=0, le=100)
    update_frequency: float = 0
    dependency_updates: Dict[str, Any] = Field(default_factory=dict)
    release_frequency: float = 0
    response_time: Optional[float] = Field(0, ge=0)
    model_config = SettingsConfigDict(extra="allow")


class RiskAssessment(BaseModel):
    security_risks: List[Dict[str, Any]] = Field(default_factory=list, description="安全风险列表")
    maintenance_risks: List[str] = Field(default_factory=list)
    community_risks: List[str] = Field(default_factory=list)
    license_risks: List[str] = Field(default_factory=list)
    overall_risk_level: str = "low"  # low, medium, high
    # 静态扫描风险评估
    static_scan_risks: Optional[Dict[str, Any]] = Field(default_factory=dict)
    model_config = SettingsConfigDict(extra="allow")


class AnalysisResult(BaseModel):
    repo_info: Dict[str, Any]
    code_quality: CodeQualityMetrics
    community_health: CommunityHealthMetrics
    documentation: DocumentationMetrics
    maintenance: MaintenanceMetrics
    risk_assessment: RiskAssessment
    recommendations: List[Dict[str, Any]] = Field(default_factory=list, description="优化建议列表")
    overall_score: float = Field(0, ge=0, le=100)
    analysis_date: datetime = Field(default_factory=datetime.now)

    model_config = SettingsConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat()
        },
        extra="allow"
    )

    def calculate_overall_score(self) -> float:
        """
        计算项目的总体得分

        使用加权平均算法计算总分：
        - 代码质量: 30% (settings.SCORE_WEIGHT_CODE)
        - 社区健康: 20% (settings.SCORE_WEIGHT_COMMUNITY)
        - 安全漏洞: 20% (settings.SCORE_WEIGHT_SECURITY)
        - 文档完整: 15% (settings.SCORE_WEIGHT_DOC)
        - 维护活跃: 15% (settings.SCORE_WEIGHT_MAINTENANCE)

        Returns:
            float: 总体得分 (0-100)，保留两位小数
        """
        code_quality_score = float(self.code_quality.score) if isinstance(self.code_quality.score, (int, float, str)) else 0.0
        community_score = float(self.community_health.score) if isinstance(self.community_health.score, (int, float, str)) else 0.0
        doc_score = float(self.documentation.score) if isinstance(self.documentation.score, (int, float, str)) else 0.0
        maintenance_score = float(self.maintenance.score) if isinstance(self.maintenance.score, (int, float, str)) else 0.0
        security_score = float(self.code_quality.security_score) if isinstance(self.code_quality.security_score, (int, float, str)) else 0.0

        from app.core.config import settings
        total = (settings.SCORE_WEIGHT_CODE * code_quality_score +
                 settings.SCORE_WEIGHT_COMMUNITY * community_score +
                 settings.SCORE_WEIGHT_SECURITY * security_score +
                 settings.SCORE_WEIGHT_DOC * doc_score +
                 settings.SCORE_WEIGHT_MAINTENANCE * maintenance_score)
        
        stars = self.repo_info.get("stars", 0) if self.repo_info else 0
        forks = self.repo_info.get("forks", 0) if self.repo_info else 0
        popular_project = stars > 5000 or (stars > 1000 and forks > 500)
        if popular_project:
            total = max(80, total)

        # 保留两位小数
        return round(min(100.0, max(0.0, total)), 2)


class StaticScanResult(BaseModel):
    """静态扫描结果模型"""
    timestamp: str = Field(default_factory=datetime.now, description="扫描时间戳")
    repository_url: str = Field(description="仓库URL")
    scans: Dict[str, Any] = Field(description="扫描结果")
    security_score: float = Field(0, ge=0, le=100, description="安全得分")
    recommendations: List[str] = Field(default_factory=list, description="优化建议列表")
    scan_duration: Optional[float] = None
    tools_status: Dict[str, str] = Field(default_factory=dict, description="工具状态")
    model_config = SettingsConfigDict(extra="allow")