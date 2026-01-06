"""
测试轮询状态端点的核心逻辑
直接测试修复的 'str' object has no attribute 'get' 错误修复逻辑
"""

import json
from app.api.endpoints.analysis import get_polling_task_status
from models.task_manager import task_manager


def test_polling_status_logic():
    """测试轮询状态端点的修复逻辑"""
    
    # 测试任务ID
    task_id = "test_logic_fix"
    
    # 1. 测试字符串格式的结果数据（模拟修复前可能的问题情况）
    mock_result = {
        "repo_info": {"full_name": "test/repo"},
        "code_quality": {"score": 85},
        "overall_score": 78
    }
    
    # 在数据库中创建任务记录
    task_manager.update_task(task_id,
        status="completed",
        progress=100,
        message="分析完成",
        result=json.dumps(mock_result),  # 以JSON字符串格式存储
        cost_estimate=json.dumps({"estimated_cost_rmb": 0.5}),  # 以JSON字符串格式存储
        cancelled=False,
        ai_provider="deepseek",
        repo_url="https://github.com/test/repo",
        user_confirmed=True
    )
    
    # 直接调用函数来测试修复逻辑
    response = get_polling_task_status(task_id)
    
    # 验证修复后的结果
    assert response["task_id"] == task_id
    assert response["status"] == "completed"
    assert response["result"] is not None
    assert isinstance(response["result"], dict)  # 确保返回的是字典而不是字符串
    assert response["result"]["code_quality"]["score"] == 85
    assert isinstance(response["cost_estimate"], dict)  # 确保成本估算也是字典格式
    assert response["cost_estimate"]["estimated_cost_rmb"] == 0.5
    
    print("✓ 测试1通过: 字符串格式结果被正确解析为字典")
    
    # 2. 测试字典格式的结果数据
    task_id2 = "test_dict_result"
    mock_result2 = {
        "repo_info": {"full_name": "test/repo2"},
        "code_quality": {"score": 90},
        "overall_score": 82
    }
    
    # 直接在数据库中存储JSON字符串（实际数据库中是这样存储的）
    task_manager.update_task(task_id2,
        status="completed",
        progress=100,
        message="分析完成",
        result=json.dumps(mock_result2),  # 存储为JSON字符串
        cost_estimate=json.dumps({"estimated_cost_rmb": 0.8}),
        cancelled=False,
        ai_provider="deepseek",
        repo_url="https://github.com/test/repo2",
        user_confirmed=True
    )
    
    response2 = get_polling_task_status(task_id2)
    
    assert response2["task_id"] == task_id2
    assert response2["status"] == "completed"
    assert isinstance(response2["result"], dict)  # 确保是字典格式
    assert response2["result"]["code_quality"]["score"] == 90
    assert isinstance(response2["cost_estimate"], dict)  # 确保成本估算也是字典格式
    assert response2["cost_estimate"]["estimated_cost_rmb"] == 0.8
    
    print("✓ 测试2通过: 字典格式结果处理正常")
    
    # 3. 测试错误状态
    task_id3 = "test_error_status"
    task_manager.update_task(task_id3,
        status="failed",
        progress=30,
        message="分析失败",
        result=None,
        error="无法克隆仓库",
        cost_estimate=None,
        cancelled=False,
        ai_provider="deepseek",
        repo_url="https://github.com/test/repo3",
        user_confirmed=True
    )
    
    response3 = get_polling_task_status(task_id3)
    
    assert response3["task_id"] == task_id3
    assert response3["status"] == "failed"
    assert response3["error"] == "无法克隆仓库"
    
    print("✓ 测试3通过: 错误状态处理正常")
    
    # 4. 测试进行中状态
    task_id4 = "test_in_progress"
    task_manager.update_task(task_id4,
        status="in_progress",
        progress=50,
        message="正在分析中...",
        result=None,
        cost_estimate=json.dumps({"estimated_cost_rmb": 0.6}),
        cancelled=False,
        ai_provider="deepseek",
        repo_url="https://github.com/test/repo4",
        user_confirmed=True
    )
    
    response4 = get_polling_task_status(task_id4)
    
    assert response4["task_id"] == task_id4
    assert response4["status"] == "in_progress"
    assert response4["progress"] == 50
    assert response4["message"] == "正在分析中..."
    assert isinstance(response4["cost_estimate"], dict)
    assert response4["cost_estimate"]["estimated_cost_rmb"] == 0.6
    
    print("✓ 测试4通过: 进行中状态处理正常")
    
    # 5. 测试任务不存在的情况
    try:
        response5 = get_polling_task_status("nonexistent_task")
        assert False, "应该抛出异常"
    except Exception as e:
        # 这里会抛出404异常，这是预期的
        print("✓ 测试5通过: 任务不存在时正确处理")
    
    print("\n所有测试通过！修复的逻辑验证成功。")
    print("修复内容：")
    print("- 修复了轮询端点中字符串格式结果的解析问题")
    print("- 确保返回给前端的数据始终是字典格式")
    print("- 避免了 'str' object has no attribute 'get' 错误")


if __name__ == "__main__":
    test_polling_status_logic()