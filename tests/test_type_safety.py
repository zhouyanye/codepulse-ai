"""
测试类型安全相关功能，确保不会出现字符串和数字比较的错误
如 '<' not supported between instances of 'str' and 'int'
"""
import pytest
from services.ai_analyzer import AIAnalyzer
from services.code_quality_service import CodeQualityService
from models.analysis_models import AnalysisResult, CodeQualityMetrics, CommunityHealthMetrics, DocumentationMetrics, MaintenanceMetrics, RiskAssessment
from app.core.config import settings


class TestTypeSafety:
    """测试类型安全"""

    @pytest.mark.asyncio
    async def test_calculate_overall_score_with_string_values(self):
        """测试当分数为字符串时的总体评分计算"""
        ai_analyzer = AIAnalyzer()
        
        # 测试字符串类型的分数输入
        overall_score = ai_analyzer._calculate_overall_score(
            code_score="85.5",  # 字符串
            community_score="75",  # 字符串
            doc_score="90.0",  # 字符串
            maintenance_score="80",  # 字符串
            security_score="88.2"  # 字符串
        )
        assert isinstance(overall_score, float)
        assert 0 <= overall_score <= 100

    @pytest.mark.asyncio
    async def test_calculate_overall_score_with_mixed_types(self):
        """测试混合类型输入的总体评分计算"""
        ai_analyzer = AIAnalyzer()
        
        # 测试混合类型输入
        overall_score = ai_analyzer._calculate_overall_score(
            code_score=85.5,      # float
            community_score="75", # string
            doc_score=90,         # int
            maintenance_score="80.0", # string
            security_score=88.2   # float
        )
        assert isinstance(overall_score, float)
        assert 0 <= overall_score <= 100

    def test_analysis_result_calculate_overall_score_with_string_values(self):
        """测试AnalysisResult中计算总体评分时的类型安全"""
        # 创建包含字符串分数的模型实例
        result = AnalysisResult(
            repo_info={"name": "test"},
            code_quality=CodeQualityMetrics(
                score="85.5",  # 字符串
                complexity="5.0",  # 字符串
                documentation_score="80",  # 字符串
                security_score="90.5"  # 字符串
            ),
            community_health=CommunityHealthMetrics(
                score="75"  # 字符串
            ),
            documentation=DocumentationMetrics(
                score="88"  # 字符串
            ),
            maintenance=MaintenanceMetrics(
                score="82"  # 字符串
            ),
            risk_assessment=RiskAssessment()
        )
        
        # 计算总体评分，不应该抛出类型错误
        overall_score = result.calculate_overall_score()
        assert isinstance(overall_score, float)
        assert 0 <= overall_score <= 100

    def test_code_quality_service_normalization_with_string_values(self):
        """测试CodeQualityService中代码质量标准化时的类型安全"""
        # 创建一个模拟的ai_client
        class MockAIClient:
            def __init__(self):
                self.provider = "test"
                
        mock_client = MockAIClient()
        service = CodeQualityService(mock_client)
        
        # 测试包含字符串值的数据
        data = {
            "score": "85",  # 字符串
            "complexity": "4.5",  # 字符串
            "documentation_score": "78",  # 字符串
            "security_score": "92.3",  # 字符串
            "security_issues": [],
            "code_standards": ["标准1", "标准2"],
            "dependencies_health": {"score": 85, "comment": "健康"},
            "detailed_analysis": {"security": "安全"}
        }
        
        normalized = service._normalize_code_quality(data)
        assert isinstance(normalized["score"], float)
        assert isinstance(normalized["complexity"], float)
        assert isinstance(normalized["documentation_score"], float)
        assert isinstance(normalized["security_score"], float)

    @pytest.mark.asyncio
    async def test_code_quality_service_with_string_values(self):
        """测试CodeQualityService处理字符串值时的类型安全"""
        # 创建一个模拟的ai_client
        class MockAIClient:
            def __init__(self):
                self.provider = "test"
                
        mock_client = MockAIClient()
        service = CodeQualityService(mock_client)
        
        # 测试标准化方法处理字符串值
        data = {
            "score": "85",  # 字符串
            "complexity": "4.5",  # 字符串
            "documentation_score": "78",  # 字符串
            "security_score": "92.3",  # 字符串
            "security_issues": [],
            "code_standards": ["标准1", "标准2"],
            "dependencies_health": {"score": 85, "comment": "健康"}
        }
        
        normalized = service._normalize_code_quality(data)
        assert isinstance(normalized["score"], float)
        assert isinstance(normalized["complexity"], float)
        assert isinstance(normalized["documentation_score"], float)
        assert isinstance(normalized["security_score"], float)

    def test_calculate_complexity_with_string_input(self):
        """测试计算复杂度时处理字符串输入的类型安全"""
        # 创建一个模拟的ai_client
        class MockAIClient:
            def __init__(self):
                self.provider = "costrict"
                
        mock_client = MockAIClient()
        service = CodeQualityService(mock_client)
        
        result = {"score": "85.5"}  # 字符串分数
        complexity = service._calculate_complexity(result)
        assert isinstance(complexity, float)

    def test_calculate_documentation_score_with_string_input(self):
        """测试计算文档分数时处理字符串输入的类型安全"""
        # 创建一个模拟的ai_client
        class MockAIClient:
            def __init__(self):
                self.provider = "costrict"
                
        mock_client = MockAIClient()
        service = CodeQualityService(mock_client)
        
        result = {"structure": {"has_readme": True, "test_files": "5"}}  # test_files是字符串
        doc_score = service._calculate_documentation_score(result)
        assert isinstance(doc_score, (float, int))  # 可能返回int或float

    @pytest.mark.asyncio
    async def test_recommendation_normalization_with_string_id(self):
        """测试推荐建议标准化时处理字符串ID的类型安全"""
        ai_analyzer = AIAnalyzer()
        
        # 测试包含字符串ID的建议
        recs = [{
            "id": "1",  # 字符串ID
            "category": "代码质量",
            "priority": "高",
            "title": "建议标题",
            "location": "file.py:10",
            "description": "描述",
            "issue": "问题",
            "fix": "修复方案",
            "reason": "原因",
            "impact": "影响",
            "recommendation": "建议"
        }]
        
        normalized = ai_analyzer._normalize_recommendations(recs)
        # 验证不会抛出类型错误
        assert len(normalized) == 1

    def test_settings_weights_type_safety(self):
        """测试配置权重的类型安全"""
        # 确保权重是浮点数类型
        assert isinstance(settings.SCORE_WEIGHT_CODE, float)
        assert isinstance(settings.SCORE_WEIGHT_COMMUNITY, float)
        assert isinstance(settings.SCORE_WEIGHT_DOC, float)
        assert isinstance(settings.SCORE_WEIGHT_MAINTENANCE, float)
        assert isinstance(settings.SCORE_WEIGHT_SECURITY, float)

        # 验证权重总和为1.0
        total_weight = (settings.SCORE_WEIGHT_CODE + settings.SCORE_WEIGHT_COMMUNITY + 
                       settings.SCORE_WEIGHT_DOC + settings.SCORE_WEIGHT_MAINTENANCE + 
                       settings.SCORE_WEIGHT_SECURITY)
        assert abs(total_weight - 1.0) < 0.001  # 允许微小的浮点数误差