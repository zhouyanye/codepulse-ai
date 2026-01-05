from sqlalchemy.orm import Session
from models.db_models import AnalysisRecord
from models.analysis_models import AnalysisResult
import json
from datetime import datetime


class HistoryService:
    def __init__(self, db: Session):
        self.db = db

    def save_analysis(self, repo_url: str, result: AnalysisResult) -> AnalysisRecord:
        repo_info = result.repo_info

        # Determine platform
        platform = "GitHub"
        if "gitee.com" in repo_url.lower():
            platform = "Gitee"

        # Parse owner and repo name
        owner = ""
        repo_name = ""
        if repo_info.get("full_name"):
            parts = repo_info["full_name"].split("/")
            if len(parts) == 2:
                owner, repo_name = parts

        # Create record
        record = AnalysisRecord(
            repo_url=repo_url,
            platform=platform,
            owner=owner,
            repo_name=repo_name,
            overall_score=result.overall_score,
            code_quality_score=result.code_quality.score,
            community_score=result.community_health.score,
            documentation_score=result.documentation.score,
            maintenance_score=result.maintenance.score,
            security_score=result.code_quality.security_score,
            created_at=datetime.now(),
            result_json=result.model_dump(mode='json') if hasattr(result, 'model_dump') else result.dict()
        )

        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_recent_history(self, limit: int = 10):
        return self.db.query(AnalysisRecord).order_by(AnalysisRecord.created_at.desc()).limit(limit).all()

    def get_analysis_by_id(self, analysis_id: int):
        return self.db.query(AnalysisRecord).filter(AnalysisRecord.id == analysis_id).first()
