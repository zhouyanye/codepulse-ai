import pytest
from fastapi.testclient import TestClient
from app.main import app
from unittest.mock import MagicMock, patch

client = TestClient(app)

def test_estimate_cost_endpoint():
    # Mock TokenEstimator and CostEstimationService
    with patch("services.cost_estimation_service.CostEstimationService.estimate_repository_cost") as mock_estimate:
        mock_estimate.return_value = {
            "total_estimated_tokens": 1000000,
            "estimated_cost": {
                "cost_usd": 0.1,
                "cost_rmb": 0.72,
                "details": "DeepSeek V3 Pricing"
            },
            "repository_size_mb": 10,
            "file_statistics": {"py": 10}
        }
        
        response = client.post(
            "/api/v1/estimate-cost",
            json={
                "repo_url": "https://gitee.com/zhou-yanye/houseSpider",
                "ai_provider": "deepseek",
                "include_static_scan": True
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_estimated_tokens"] == 1000000
        assert data["estimated_cost"]["cost_rmb"] == 0.72

def test_estimate_cost_real_logic_mocked_network():
    # Test the logic without mocking the service method entirely, but mocking network calls
    with patch("services.cost_estimation_service.GitHubService.get_repository_info") as mock_repo_info, \
         patch("services.cost_estimation_service.CostEstimationService._clone_repository") as mock_clone, \
         patch("services.cost_estimation_service.CostEstimationService._analyze_repository_structure") as mock_structure, \
         patch("services.cost_estimation_service.CostEstimationService._calculate_repository_size") as mock_size, \
         patch("services.cost_estimation_service.CostEstimationService._apply_blacklist_filter") as mock_filter, \
         patch("shutil.rmtree"): # Prevent deletion of non-existent paths
        
        mock_repo_info.return_value = {"full_name": "test/repo", "size": 1000}
        mock_clone.return_value = "/tmp/test_repo"
        mock_structure.return_value = {"python": 10}
        mock_size.return_value = 5.0
        mock_filter.return_value = {"python": 10}
        
        # We need to verify the pricing calculation in TokenEstimator
        from utils.token_estimator import TokenEstimator
        estimator = TokenEstimator()
        
        # Test DeepSeek Pricing
        # 1M tokens input (cache miss) = 2.0 RMB
        # 1M tokens output = 3.0 RMB
        # Ratio 7:3
        # 1M tokens total -> 0.7M input, 0.3M output
        # Input cost: 0.7 * 2.0 = 1.4
        # Output cost: 0.3 * 3.0 = 0.9
        # Total: 2.3 RMB
        
        cost_deepseek = estimator._estimate_cost(1000000, "deepseek")
        assert abs(cost_deepseek["cost_rmb"] - 2.3) < 0.01
        
        # Test Kimi Pricing
        # 1M tokens total
        # Input (0.7M) * 8.0 = 5.6
        # Output (0.3M) * 58.0 = 17.4
        # Total: 23.0 RMB
        
        cost_kimi = estimator._estimate_cost(1000000, "kimi")
        assert abs(cost_kimi["cost_rmb"] - 23.0) < 0.01

