"""
测试边界情况和潜在的类型比较错误
专门测试可能导致 '<' not supported between instances of 'str' and 'int' 的情况
"""
import pytest
from services.ai_analyzer import AIAnalyzer
from services.code_quality_service import CodeQualityService
from models.analysis_models import AnalysisResult, CodeQualityMetrics, CommunityHealthMetrics, DocumentationMetrics, MaintenanceMetrics, RiskAssessment
from app.core.config import settings
import logging


class TestComparisonSafety:
    """测试比较操作的安全性"""

    @pytest.mark.asyncio
    async def test_calculate_overall_score_with_invalid_values(self):
        """测试当分数为无效值时的总体评分计算"""
        ai_analyzer = AIAnalyzer()
        
        # 测试各种无效输入
        test_cases = [
            ("invalid", 75, 80, 85, 90),      # 第一个参数为字符串
            (85, "invalid", 80, 85, 90),      # 第二个参数为字符串
            (85, 75, "invalid", 85, 90),      # 第三个参数为字符串
            (85, 75, 80, "invalid", 90),      # 第四个参数为字符串
            (85, 75, 80, 85, "invalid"),      # 第五个参数为字符串
            (None, 75, 80, 85, 90),           # 第一个参数为None
            (85, None, 80, 85, 90),           # 第二个参数为None
            ("", 75, 80, 85, 90),             # 第一个参数为空字符串
            ([], 75, 80, 85, 90),             # 第一个参数为列表
            ({}, 75, 80, 85, 90),             # 第一个参数为字典
        ]
        
        for case in test_cases:
            overall_score = ai_analyzer._calculate_overall_score(*case)
            assert isinstance(overall_score, float)
            assert 0 <= overall_score <= 100

    def test_analysis_result_with_invalid_scores(self):
        """测试AnalysisResult中使用无效分数时的类型安全"""
        # 测试各种无效分数值
        invalid_scores = ["invalid", None, "", [], {}]
        
        for invalid_score in invalid_scores:
            try:
                result = AnalysisResult(
                    repo_info={"name": "test"},
                    code_quality=CodeQualityMetrics(
                        score=invalid_score if invalid_score != None else 0,
                        complexity=5.0,
                        documentation_score=80,
                        security_score=90
                    ),
                    community_health=CommunityHealthMetrics(
                        score=invalid_score if invalid_score != None else 75
                    ),
                    documentation=DocumentationMetrics(
                        score=invalid_score if invalid_score != None else 88
                    ),
                    maintenance=MaintenanceMetrics(
                        score=invalid_score if invalid_score != None else 82
                    ),
                    risk_assessment=RiskAssessment()
                )
                
                # 计算总体评分，不应该抛出类型错误
                overall_score = result.calculate_overall_score()
                assert isinstance(overall_score, float)
                assert 0 <= overall_score <= 100
            except Exception as e:
                # 如果有异常，确保是合理的异常而不是类型比较错误
                assert "not supported between instances of" not in str(e)

    @pytest.mark.asyncio
    async def test_ai_analyzer_methods_with_invalid_input(self):
        """测试AIAnalyzer中各种方法处理无效输入的类型安全"""
        ai_analyzer = AIAnalyzer()
        
        # 测试_normalize_code_quality方法
        invalid_data_cases = [
            {"score": "invalid", "complexity": 5, "documentation_score": 80, "security_score": 90},
            {"score": None, "complexity": 5, "documentation_score": 80, "security_score": 90},
            {"score": "", "complexity": 5, "documentation_score": 80, "security_score": 90},
            {"score": [], "complexity": 5, "documentation_score": 80, "security_score": 90},
            {"score": {}, "complexity": 5, "documentation_score": 80, "security_score": 90},
        ]
        
        for data in invalid_data_cases:
            data.update({
                "security_issues": [],
                "code_standards": ["标准"],
                "dependencies_health": {"score": 80, "comment": "健康"},
                "detailed_analysis": {"security": "安全"}
            })
            try:
                normalized = ai_analyzer._normalize_code_quality(data)
                # 确保关键字段是数值类型
                assert isinstance(normalized["score"], float)
                assert isinstance(normalized["complexity"], float)
                assert isinstance(normalized["documentation_score"], float)
                assert isinstance(normalized["security_score"], float)
            except Exception as e:
                assert "not supported between instances of" not in str(e)

    def test_code_quality_service_with_invalid_values(self):
        """测试CodeQualityService处理无效值的类型安全"""
        # 创建一个模拟的ai_client
        class MockAIClient:
            def __init__(self):
                self.provider = "test"
                
        mock_client = MockAIClient()
        service = CodeQualityService(mock_client)
        
        # 测试_normalize_code_quality方法
        invalid_data_cases = [
            {"score": "invalid", "complexity": "5", "documentation_score": "80", "security_score": "90"},
            {"score": None, "complexity": "5", "documentation_score": "80", "security_score": "90"},
            {"score": "", "complexity": "5", "documentation_score": "80", "security_score": "90"},
            {"score": [], "complexity": "5", "documentation_score": "80", "security_score": "90"},
            {"score": {}, "complexity": "5", "documentation_score": "80", "security_score": "90"},
        ]
        
        for data in invalid_data_cases:
            data.update({
                "security_issues": [],
                "code_standards": ["标准"],
                "dependencies_health": {"score": 80, "comment": "健康"}
            })
            try:
                normalized = service._normalize_code_quality(data)
                # 确保关键字段是数值类型
                assert isinstance(normalized["score"], float)
                assert isinstance(normalized["complexity"], float)
                assert isinstance(normalized["documentation_score"], float)
                assert isinstance(normalized["security_score"], float)
            except Exception as e:
                assert "not supported between instances of" not in str(e)

    def test_calculate_complexity_with_invalid_input(self):
        """测试计算复杂度时处理无效输入的类型安全"""
        # 创建一个模拟的ai_client
        class MockAIClient:
            def __init__(self):
                self.provider = "costrict"
                
        mock_client = MockAIClient()
        service = CodeQualityService(mock_client)
        
        invalid_result_cases = [
            {"score": "invalid"},
            {"score": None},
            {"score": ""},
            {"score": []},
            {"score": {}},
            {},  # 空字典
        ]
        
        for result in invalid_result_cases:
            try:
                complexity = service._calculate_complexity(result)
                assert isinstance(complexity, (float, int))
            except Exception as e:
                assert "not supported between instances of" not in str(e)

    def test_calculate_documentation_score_with_invalid_input(self):
        """测试计算文档分数时处理无效输入的类型安全"""
        # 创建一个模拟的ai_client
        class MockAIClient:
            def __init__(self):
                self.provider = "costrict"
                
        mock_client = MockAIClient()
        service = CodeQualityService(mock_client)
        
        invalid_result_cases = [
            {"structure": {"has_readme": True, "test_files": "invalid"}},
            {"structure": {"has_readme": True, "test_files": None}},
            {"structure": {"has_readme": True, "test_files": ""}},
            {"structure": {"has_readme": True, "test_files": []}},
            {"structure": {"has_readme": True, "test_files": {}}},
            {"structure": {}},  # 空结构
            {},  # 空结果
        ]
        
        for result in invalid_result_cases:
            try:
                doc_score = service._calculate_documentation_score(result)
                assert isinstance(doc_score, (float, int))
            except Exception as e:
                assert "not supported between instances of" not in str(e)

    def test_settings_weight_calculations(self):
        """测试使用配置权重进行计算时的类型安全"""
        # 确保权重计算不会导致类型错误
        scores = [85.5, 75.0, 90.0, 82.0, 88.0]
        
        total = (settings.SCORE_WEIGHT_CODE * scores[0] +
                 settings.SCORE_WEIGHT_COMMUNITY * scores[1] +
                 settings.SCORE_WEIGHT_DOC * scores[2] +
                 settings.SCORE_WEIGHT_MAINTENANCE * scores[3] +
                 settings.SCORE_WEIGHT_SECURITY * scores[4])
        
        assert isinstance(total, float)
        assert 0 <= total <= 100

    @pytest.mark.asyncio
    async def test_recommendation_normalization_with_invalid_ids(self):
        """测试推荐建议标准化时处理无效ID的类型安全"""
        ai_analyzer = AIAnalyzer()
        
        invalid_recs_cases = [
            [{"id": "invalid", "category": "代码质量", "priority": "高", "title": "标题", 
              "location": "file.py:10", "description": "描述", "issue": "问题", 
              "fix": "修复", "reason": "原因", "impact": "影响", "recommendation": "建议"}],
            [{"id": None, "category": "代码质量", "priority": "高", "title": "标题", 
              "location": "file.py:10", "description": "描述", "issue": "问题", 
              "fix": "修复", "reason": "原因", "impact": "影响", "recommendation": "建议"}],
            [{"id": "", "category": "代码质量", "priority": "高", "title": "标题", 
              "location": "file.py:10", "description": "描述", "issue": "问题", 
              "fix": "修复", "reason": "原因", "impact": "影响", "recommendation": "建议"}],
            [{"id": [], "category": "代码质量", "priority": "高", "title": "标题", 
              "location": "file.py:10", "description": "描述", "issue": "问题", 
              "fix": "修复", "reason": "原因", "impact": "影响", "recommendation": "建议"}],
            [{"id": {}, "category": "代码质量", "priority": "高", "title": "标题", 
              "location": "file.py:10", "description": "描述", "issue": "问题", 
              "fix": "修复", "reason": "原因", "impact": "影响", "recommendation": "建议"}],
        ]
        
        for recs in invalid_recs_cases:
            try:
                normalized = ai_analyzer._normalize_recommendations(recs)
                # 如果ID无效，应该使用默认ID或跳过
            except ValueError:
                # ValueError是可以接受的，比如int('invalid')的情况
                pass
            except Exception as e:
                assert "not supported between instances of" not in str(e)

    def test_comparison_operations_in_metrics(self):
        """测试各种可能的比较操作安全性"""
        # 测试在各种计算和比较中不会出现类型错误
        metrics = CodeQualityMetrics(
            score=85.5,
            complexity=4.2,
            documentation_score=78.9,
            security_score=92.1
        )
        
        # 测试各种可能的比较操作
        comparisons = [
            metrics.score > 80,
            metrics.complexity < 5,
            metrics.documentation_score >= 70,
            metrics.security_score <= 95,
            80 < metrics.score < 90,
            metrics.score == 85.5
        ]
        
        # 所有比较都应该成功执行
        assert all(isinstance(comp, bool) for comp in comparisons)