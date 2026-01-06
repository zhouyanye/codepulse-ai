from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON
from datetime import datetime
from app.core.database import Base


class AnalysisRecord(Base):
    __tablename__ = "analysis_records"

    id = Column(Integer, primary_key=True, index=True)
    repo_url = Column(String, index=True)
    platform = Column(String)  # GitHub or Gitee
    owner = Column(String)
    repo_name = Column(String)
    overall_score = Column(Float)
    code_quality_score = Column(Float)
    community_score = Column(Float)
    documentation_score = Column(Float)
    maintenance_score = Column(Float)
    security_score = Column(Float)
    created_at = Column(DateTime, default=datetime.now)
    result_json = Column(JSON)  # Store the complete analysis result
