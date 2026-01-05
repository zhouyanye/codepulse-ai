import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from models.analysis_models import AnalysisResult
from services.ai_analyzer import AIAnalyzer


class TestAIAnalyzer:
    """测试AI分析器"""
    
    def test_initialization(self):
        """测试AI分析器初始化"""
        analyzer = AIAnalyzer(provider="deepseek")
        assert analyzer.provider == "deepseek"
        
        analyzer = AIAnalyzer(provider="costrict")
        assert analyzer.provider == "costrict"
    
    @pytest.mark.asyncio
    async def test_analyze_repository_with_costrict(self):
        """测试使用costrict分析仓库"""
        analyzer = AIAnalyzer(provider="costrict")
        
        repo_data = {
            "repo_info": {
                "full_name": "test/repo",
                "description": "A test repository",
                "stars": 100,
                "forks": 20,
                "language": "Python"
            },
            "repo_structure": {
                "files": ["main.py", "README.md"],
                "directories": [".git", "src"],
                "size": 1024
            }
        }
        
        result = await analyzer.analyze_repository(repo_data)
        
        # 验证返回结果类型
        assert isinstance(result, AnalysisResult)
        assert result.overall_score >= 0
        assert result.overall_score <= 100
    
    @pytest.mark.asyncio
    async def test_analyze_repository_with_ai_provider(self):
        """测试使用AI提供商分析仓库"""
        analyzer = AIAnalyzer(provider="deepseek")
        
        repo_data = {
            "repo_info": {
                "full_name": "test/repo",
                "description": "A test repository",
                "stars": 100,
                "forks": 20,
                "language": "Python"
            },
            "repo_structure": {
                "files": ["main.py", "README.md"],
                "directories": [".git", "src"],
                "size": 1024
            }
        }
        
        # Mock AI客户端的chat方法
        with patch.object(analyzer, '_call_ai', new_callable=AsyncMock) as mock_call_ai:
            mock_call_ai.return_value = """
            {
                "code_quality": {"score": 80},
                "community_health": {"score": 75},
                "documentation": {"score": 90},
                "maintenance": {"score": 85},
                "risk_assessment": {"overall_risk_level": "low"},
                "recommendations": []
            }
            """
            
            result = await analyzer.analyze_repository(repo_data)
            
            # 验证返回结果类型
            assert isinstance(result, AnalysisResult)
            assert result.overall_score >= 0
            assert result.overall_score <= 100
    
    @pytest.mark.asyncio
    async def test_format_repo_data(self):
        """测试格式化仓库数据"""
        analyzer = AIAnalyzer(provider="deepseek")
        
        repo_data = {
            "repo_info": {
                "full_name": "test/repo",
                "description": "A test repository",
                "stars": 100,
                "forks": 20,
                "language": "Python",
                "license": "MIT"
            },
            "repo_structure": {
                "files": ["main.py", "README.md"],
                "directories": [".git", "src"],
                "size": 1024,
                "languages": {"Python": 95, "Shell": 5}
            }
        }
        
        formatted_data = analyzer._format_repo_data(repo_data)
        
        # 验证格式化后的数据包含必要字段
        assert "仓库名称" in formatted_data
        assert "仓库描述" in formatted_data
        assert "编程语言" in formatted_data
        assert "仓库大小" in formatted_data