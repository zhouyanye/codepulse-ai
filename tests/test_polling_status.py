"""
测试轮询状态端点功能
验证修复的 'str' object has no attribute 'get' 错误
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app  # 修正导入路径
from app.api.endpoints.analysis import task_manager
import asyncio
import json
from models.analysis_models import AnalysisResult, CodeQualityMetrics, CommunityHealthMetrics, DocumentationMetrics, MaintenanceMetrics, RiskAssessment


def test_polling_status_with_dict_result():
    """测试轮询端点返回字典格式结果的情况"""
    client = TestClient(app)
    
    # 创建一个模拟的任务ID和任务数据
    task_id = "test_task_dict_result"
    mock_result = {
        "repo_info": {"full_name": "test/repo"},
        "code_quality": {"score": 85},
        "community_health": {"score": 80},
        "documentation": {"score": 75},
        "maintenance": {"score": 70},
        "risk_assessment": {"security": []},
        "recommendations": [],
        "overall_score": 78
    }
    
    # 在任务管理器中添加测试任务 - 使用关键字参数
    task_manager.update_task(task_id, 
        status="completed",
        progress=100,
        message="分析完成",
        result=json.dumps(mock_result),  # 存储为JSON字符串
        cost_estimate=json.dumps({"estimated_cost_rmb": 0.5}),
        cancelled=False,
        ai_provider="deepseek",
        repo_url="https://github.com/zhouyanye/houseSpider",
        user_confirmed=True
    )
    
    # 请求轮询状态
    response = client.get(f"/api/v1/analyze/polling-status/{task_id}")
    assert response.status_code == 200
    
    data = response.json()
    assert data["task_id"] == task_id
    assert data["status"] == "completed"
    assert data["result"] is not None
    assert isinstance(data["result"], dict)  # 确保返回的是字典
    assert data["result"]["code_quality"]["score"] == 85


def test_polling_status_with_string_result():
    """测试轮询端点处理字符串格式结果的情况（修复前可能出错的情况）"""
    client = TestClient(app)
    
    # 创建一个模拟的任务ID和任务数据
    task_id = "test_task_string_result"
    mock_result = {
        "repo_info": {"full_name": "test/repo"},
        "code_quality": {"score": 90},
        "community_health": {"score": 85},
        "documentation": {"score": 80},
        "maintenance": {"score": 75},
        "risk_assessment": {"security": []},
        "recommendations": [],
        "overall_score": 83
    }
    
    # 在任务管理器中添加测试任务，结果为字符串格式（模拟旧版本可能的情况）
    task_manager.update_task(task_id,
        status="completed",
        progress=100,
        message="分析完成",
        result=json.dumps(mock_result),  # 字符串格式
        cost_estimate=json.dumps({"estimated_cost_rmb": 0.8}),  # 字符串格式
        cancelled=False,
        ai_provider="deepseek",
        repo_url="https://github.com/test/repo",
        user_confirmed=True
    )
    
    # 请求轮询状态
    response = client.get(f"/api/v1/analyze/polling-status/{task_id}")
    assert response.status_code == 200
    
    data = response.json()
    assert data["task_id"] == task_id
    assert data["status"] == "completed"
    assert data["result"] is not None
    assert isinstance(data["result"], dict)  # 确保返回的是字典（已解析）
    assert data["result"]["code_quality"]["score"] == 90
    assert isinstance(data["cost_estimate"], dict)  # 确保成本估算也是字典格式
    assert data["cost_estimate"]["estimated_cost_rmb"] == 0.8


def test_polling_status_with_string_cost_estimate_only():
    """测试只有成本估算为字符串格式的情况"""
    client = TestClient(app)
    
    # 创建一个模拟的任务ID和任务数据
    task_id = "test_task_cost_string_only"
    mock_result = {
        "repo_info": {"full_name": "test/repo"},
        "code_quality": {"score": 75},
        "community_health": {"score": 70},
        "documentation": {"score": 65},
        "maintenance": {"score": 60},
        "risk_assessment": {"security": []},
        "recommendations": [],
        "overall_score": 68
    }
    
    # 在任务管理器中添加测试任务，只有成本估算为字符串格式
    task_manager.update_task(task_id,
        status="completed",
        progress=100,
        message="分析完成",
        result=json.dumps(mock_result),  # 字符串格式
        cost_estimate=json.dumps({"estimated_cost_rmb": 1.2}),  # 字符串格式
        cancelled=False,
        ai_provider="deepseek",
        repo_url="https://github.com/test/repo",
        user_confirmed=True
    )
    
    # 请求轮询状态
    response = client.get(f"/api/v1/analyze/polling-status/{task_id}")
    assert response.status_code == 200
    
    data = response.json()
    assert data["task_id"] == task_id
    assert data["status"] == "completed"
    assert data["result"] is not None
    assert isinstance(data["result"], dict)  # 确保返回的是字典
    assert data["result"]["code_quality"]["score"] == 75
    assert isinstance(data["cost_estimate"], dict)  # 确保成本估算被正确解析
    assert data["cost_estimate"]["estimated_cost_rmb"] == 1.2


def test_polling_status_in_progress():
    """测试轮询端点返回进行中状态的情况"""
    client = TestClient(app)
    
    # 创建一个模拟的任务ID和任务数据
    task_id = "test_task_in_progress"
    
    # 在任务管理器中添加测试任务，状态为进行中
    task_manager.update_task(task_id,
        status="in_progress",
        progress=50,
        message="正在分析中...",
        result=None,
        cost_estimate=json.dumps({"estimated_cost_rmb": 0.6}),
        cancelled=False,
        ai_provider="deepseek",
        repo_url="https://github.com/test/repo",
        user_confirmed=True
    )
    
    # 请求轮询状态
    response = client.get(f"/api/v1/analyze/polling-status/{task_id}")
    assert response.status_code == 200
    
    data = response.json()
    assert data["task_id"] == task_id
    assert data["status"] == "in_progress"
    assert data["progress"] == 50
    assert data["message"] == "正在分析中..."
    assert data["cost_estimate"] is not None
    assert isinstance(data["cost_estimate"], dict)
    assert data["cost_estimate"]["estimated_cost_rmb"] == 0.6


def test_polling_status_task_not_found():
    """测试轮询端点处理任务不存在的情况"""
    client = TestClient(app)
    
    # 请求一个不存在的任务ID
    response = client.get("/api/v1/analyze/polling-status/nonexistent_task")
    assert response.status_code == 404
    
    data = response.json()
    assert "任务不存在" in data["detail"]


def test_polling_status_with_error_result():
    """测试轮询端点返回错误状态的情况"""
    client = TestClient(app)
    
    # 创建一个模拟的任务ID和错误数据
    task_id = "test_task_error"
    
    # 在任务管理器中添加测试任务，状态为失败
    task_manager.update_task(task_id,
        status="failed",
        progress=30,
        message="分析失败",
        result=None,
        error="无法克隆仓库",
        cost_estimate=None,
        cancelled=False,
        ai_provider="deepseek",
        repo_url="https://github.com/test/repo",
        user_confirmed=True
    )
    
    # 请求轮询状态
    response = client.get(f"/api/v1/analyze/polling-status/{task_id}")
    assert response.status_code == 200
    
    data = response.json()
    assert data["task_id"] == task_id
    assert data["status"] == "failed"
    assert data["error"] == "无法克隆仓库"


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])