import pytest
from unittest.mock import MagicMock
from sqlalchemy.orm import Session
from models.analysis_models import (
    AnalysisResult, 
    CodeQualityMetrics, 
    CommunityHealthMetrics, 
    DocumentationMetrics, 
    MaintenanceMetrics,
    RiskAssessment
)
from services.history_service import HistoryService


class TestHistoryService:
    """测试历史服务"""
    
    def test_initialization(self):
        """测试历史服务初始化"""
        mock_db = MagicMock(spec=Session)
        history_service = HistoryService(mock_db)
        
        assert history_service.db == mock_db
    
    def test_save_analysis(self):
        """测试保存分析结果"""
        mock_db = MagicMock(spec=Session)
        history_service = HistoryService(mock_db)
        
        # 创建模拟分析结果
        result = AnalysisResult(
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
        
        # Mock数据库操作
        mock_record = MagicMock()
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None
        
        with patch('services.history_service.AnalysisRecord') as mock_analysis_record:
            mock_analysis_record.return_value = mock_record
            mock_record.id = 1
            
            saved_record = history_service.save_analysis("https://github.com/test/repo", result)
            
            # 验证数据库操作被调用
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
            mock_db.refresh.assert_called_once()
            
            assert saved_record == mock_record
    
    def test_get_recent_history(self):
        """测试获取最近历史"""
        mock_db = MagicMock(spec=Session)
        history_service = HistoryService(mock_db)
        
        # Mock查询结果
        mock_query = MagicMock()
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        
        mock_db.query.return_value = mock_query
        
        history = history_service.get_recent_history(10)
        
        # 验证查询操作
        mock_db.query.assert_called_once()
        mock_query.order_by.assert_called_once()
        mock_query.limit.assert_called_once_with(10)
        mock_query.all.assert_called_once()
        
        assert history == []
    
    def test_get_analysis_by_id(self):
        """测试根据ID获取分析"""
        mock_db = MagicMock(spec=Session)
        history_service = HistoryService(mock_db)
        
        # Mock查询结果
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None  # 模拟未找到记录
        
        mock_db.query.return_value = mock_query
        
        record = history_service.get_analysis_by_id(1)
        
        # 验证查询操作
        mock_db.query.assert_called_once()
        mock_query.filter.assert_called_once()
        mock_query.first.assert_called_once()
        
        assert record is None