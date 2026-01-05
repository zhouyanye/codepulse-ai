import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os
import sys
from unittest.mock import AsyncMock, patch

# Add project root to path
sys.path.append(os.getcwd())

from app.main import app
from app.core.database import Base, get_db
from models.analysis_models import (
    AnalysisResult, 
    CodeQualityMetrics, 
    CommunityHealthMetrics, 
    DocumentationMetrics, 
    MaintenanceMetrics,
    RiskAssessment
)

# Setup test DB
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_history_integration.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="module")
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    # Cleanup
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_history_integration.db"):
        try:
            os.remove("./test_history_integration.db")
        except Exception:
            pass

@pytest.fixture
def db_session(setup_db):
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    del app.dependency_overrides[get_db]

def test_history_flow(client):
    # Mock the analysis service
    mock_result = AnalysisResult(
        repo_info={
            "full_name": "test/repo", 
            "html_url": "https://github.com/test/repo",
            "description": "Test Repo",
            "stars": 100,
            "forks": 20,
            "open_issues": 5,
            "language": "Python",
            "license": "MIT"
        },
        overall_score=85.5,
        code_quality=CodeQualityMetrics(
            score=80.0, 
            complexity=10.0,
            documentation_score=80.0,
            security_score=90.0,
            test_coverage=0.0
        ),
        community_health=CommunityHealthMetrics(
            score=85.0, 
            contributors_count=100
        ),
        documentation=DocumentationMetrics(score=90.0),
        maintenance=MaintenanceMetrics(score=88.0),
        risk_assessment=RiskAssessment(
            overall_risk_level="low",
            security_risks=[],
            legal_risks=[],
            maintenance_risks=[]
        ),
        recommendations=[{"title": "Keep it up", "description": "Good job", "priority": "low", "id": 1}]
    )
    
    with patch('services.analysis_service.AnalysisService.analyze_repository', new_callable=AsyncMock) as mock_analyze:
        mock_analyze.return_value = mock_result
        
        # 1. Analyze a repo (mocked analysis)
        response = client.post(
            "/api/v1/analyze?async_mode=false",
            json={"repo_url": "https://github.com/test/repo", "github_token": "dummy"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["overall_score"] == 85.5
        
        # 2. Check history
        response = client.get("/api/v1/analyze/history")
        assert response.status_code == 200
        history = response.json()
        
        assert len(history) > 0
        latest = history[0]
        assert "test/repo" in latest["repo_url"] or latest["owner"] == "test" and latest["repo_name"] == "repo"
        assert latest["platform"] == "GitHub"
        assert latest["overall_score"] == 85.5

def test_gitee_history(client, db_session):
    # Mock the analysis service
    mock_result = AnalysisResult(
        repo_info={
            "full_name": "test/repo", 
            "html_url": "https://gitee.com/test/repo",
            "description": "Test Repo",
            "stars": 100,
            "forks": 20,
            "open_issues": 5,
            "language": "Python",
            "license": "MIT"
        },
        overall_score=85.5,
        code_quality=CodeQualityMetrics(
            score=80.0, 
            complexity=10.0,
            documentation_score=80.0,
            security_score=90.0,
            test_coverage=0.0
        ),
        community_health=CommunityHealthMetrics(
            score=85.0, 
            contributors_count=100
        ),
        documentation=DocumentationMetrics(score=90.0),
        maintenance=MaintenanceMetrics(score=88.0),
        risk_assessment=RiskAssessment(
            overall_risk_level="low",
            security_risks=[],
            legal_risks=[],
            maintenance_risks=[]
        ),
        recommendations=[{"title": "Keep it up", "description": "Good job", "priority": "low", "id": 1}]
    )
    
    with patch('services.analysis_service.AnalysisService.analyze_repository', new_callable=AsyncMock) as mock_analyze:
        mock_analyze.return_value = mock_result
        
        # Test Gitee platform detection
        response = client.post(
            "/api/v1/analyze?async_mode=false",
            json={"repo_url": "https://gitee.com/test/repo", "gitee_token": "dummy"}
        )
        assert response.status_code == 200
        
        response = client.get("/api/v1/analyze/history")
        history = response.json()
        latest = history[0]
        assert "gitee.com/test/repo" in latest["repo_url"] or latest["owner"] == "test" and latest["repo_name"] == "repo"
        assert latest["platform"] == "Gitee"

def test_get_history_detail(client):
    # Mock the analysis service
    mock_result = AnalysisResult(
        repo_info={
            "full_name": "test/repo-detail", 
            "html_url": "https://github.com/test/repo-detail",
            "description": "Test Repo Detail",
            "stars": 100,
            "forks": 20,
            "open_issues": 5,
            "language": "Python",
            "license": "MIT"
        },
        overall_score=85.5,
        code_quality=CodeQualityMetrics(
            score=80.0, 
            complexity=10.0,
            documentation_score=80.0,
            security_score=90.0,
            test_coverage=0.0
        ),
        community_health=CommunityHealthMetrics(
            score=85.0, 
            contributors_count=100
        ),
        documentation=DocumentationMetrics(score=90.0),
        maintenance=MaintenanceMetrics(score=88.0),
        risk_assessment=RiskAssessment(
            overall_risk_level="low",
            security_risks=[],
            legal_risks=[],
            maintenance_risks=[]
        ),
        recommendations=[{"title": "Keep it up", "description": "Good job", "priority": "low", "id": 1}]
    )
    
    with patch('services.analysis_service.AnalysisService.analyze_repository', new_callable=AsyncMock) as mock_analyze:
        mock_analyze.return_value = mock_result
        
        # 1. Analyze a repo to generate history
        response = client.post(
            "/api/v1/analyze?async_mode=false",
            json={"repo_url": "https://github.com/test/repo-detail", "github_token": "dummy"}
        )
        assert response.status_code == 200
        
        # 2. Get history list to find ID
        response = client.get("/api/v1/analyze/history")
        assert response.status_code == 200
        history = response.json()
        assert len(history) > 0
        target_id = history[0]["id"]
        
        # 3. Get detail by ID
        response = client.get(f"/api/v1/analyze/history/{target_id}")
        assert response.status_code == 200
        detail = response.json()
        
        # 4. Verify detail content
        assert detail["overall_score"] == 85.5
        assert "test/repo-detail" in detail["repo_info"]["full_name"] or "repo-detail" in detail["repo_info"]["full_name"]
        assert "code_quality" in detail
        assert "community_health" in detail

def test_get_history_detail_not_found(client):
    response = client.get("/api/v1/analyze/history/99999")
    assert response.status_code == 404