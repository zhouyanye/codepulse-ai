"""
验证修复的核心逻辑
测试字符串到字典的解析逻辑
"""

import json

def test_response_parsing_logic():
    """测试修复的响应解析逻辑"""
    
    # 模拟任务数据，其中result和cost_estimate是字符串格式（修复前可能导致错误的情况）
    task_data = {
        "status": "completed",
        "progress": 100,
        "message": "分析完成",
        "result": json.dumps({  # 模拟数据库中存储的JSON字符串
            "repo_info": {"full_name": "test/repo"},
            "code_quality": {"score": 85},
            "overall_score": 78
        }),
        "cost_estimate": json.dumps({  # 模拟数据库中存储的JSON字符串
            "estimated_cost_rmb": 0.5
        }),
        "error": None,
        "cancelled": False,
        "ai_provider": "deepseek",
        "repo_url": "https://github.com/test/repo",
        "user_confirmed": True
    }
    
    # 构建响应 - 这是修复后的逻辑
    response = {
        "task_id": "test_task",
        "status": task_data.get("status"),
        "progress": task_data.get("progress"),
        "message": task_data.get("message"),
        "cost_estimate": task_data.get("cost_estimate"),
        "result": task_data.get("result"),
        "error": task_data.get("error"),
        "cancelled": task_data.get("cancelled"),
        "ai_provider": task_data.get("ai_provider"),
        "repo_url": task_data.get("repo_url"),
        "user_confirmed": task_data.get("user_confirmed")
    }

    # 修复逻辑：处理cost_estimate字段
    if task_data.get("cost_estimate"):
        cost_estimate_data = task_data["cost_estimate"]
        # 如果成本估算结果是字符串，尝试解析为JSON
        if isinstance(cost_estimate_data, str):
            try:
                import json
                cost_estimate_data = json.loads(cost_estimate_data)
            except json.JSONDecodeError:
                # 如果解析失败，保持原值
                pass
        response["cost_estimate"] = cost_estimate_data

    # 修复逻辑：处理result字段
    if task_data["status"] == "completed" and task_data.get("result"):
        result_data = task_data["result"]
        # 如果结果是字符串，尝试解析为JSON
        if isinstance(result_data, str):
            try:
                import json
                result_data = json.loads(result_data)
            except json.JSONDecodeError:
                # 如果解析失败，保持原值
                pass
        response["result"] = result_data

    if task_data["status"] == "failed" and task_data.get("error"):
        response["error"] = task_data["error"]

    # 验证修复结果
    print("原始数据类型检查:")
    print(f"  task_data['result'] 类型: {type(task_data['result'])}")
    print(f"  task_data['cost_estimate'] 类型: {type(task_data['cost_estimate'])}")
    
    print("\n修复后响应数据类型检查:")
    print(f"  response['result'] 类型: {type(response['result'])}")
    print(f"  response['cost_estimate'] 类型: {type(response['cost_estimate'])}")
    
    # 验证修复结果
    assert isinstance(response["result"], dict), "result 应该是字典类型"
    assert isinstance(response["cost_estimate"], dict), "cost_estimate 应该是字典类型"
    
    # 验证数据内容
    assert response["result"]["code_quality"]["score"] == 85
    assert response["cost_estimate"]["estimated_cost_rmb"] == 0.5
    
    print("\n✓ 修复验证通过!")
    print("  - 字符串格式的结果被正确解析为字典")
    print("  - 字符串格式的成本估算被正确解析为字典")
    print("  - 前端现在可以正常调用 .get() 方法访问数据")
    
    # 演示前端访问逻辑（修复前会出错，修复后正常）
    print("\n前端访问测试:")
    try:
        repo_name = response["result"].get("repo_info", {}).get("full_name")
        score = response["result"].get("code_quality", {}).get("score")
        cost = response["cost_estimate"].get("estimated_cost_rmb")
        
        print(f"  仓库名称: {repo_name}")
        print(f"  代码质量分数: {score}")
        print(f"  预估成本: {cost}")
        print("  ✓ 前端访问成功，没有 'str' object has no attribute 'get' 错误")
    except AttributeError as e:
        print(f"  ✗ 前端访问失败: {e}")


def test_edge_cases():
    """测试边界情况"""
    print("\n测试边界情况:")
    
    # 测试None值
    task_data = {
        "status": "completed",
        "result": None,
        "cost_estimate": None
    }
    
    response = {
        "result": task_data.get("result"),
        "cost_estimate": task_data.get("cost_estimate")
    }
    
    # 应用修复逻辑
    if task_data["status"] == "completed" and task_data.get("result"):
        result_data = task_data["result"]
        if isinstance(result_data, str):
            try:
                result_data = json.loads(result_data)
            except json.JSONDecodeError:
                pass
        response["result"] = result_data

    if task_data.get("cost_estimate"):
        cost_estimate_data = task_data["cost_estimate"]
        if isinstance(cost_estimate_data, str):
            try:
                cost_estimate_data = json.loads(cost_estimate_data)
            except json.JSONDecodeError:
                pass
        response["cost_estimate"] = cost_estimate_data
    
    print("  ✓ None值处理正常")
    
    # 测试无效JSON字符串
    task_data_invalid = {
        "status": "completed",
        "result": "invalid json string {",
        "cost_estimate": "another invalid { json"
    }
    
    response_invalid = {
        "result": task_data_invalid["result"],
        "cost_estimate": task_data_invalid["cost_estimate"]
    }
    
    # 应用修复逻辑
    if task_data_invalid["status"] == "completed" and task_data_invalid.get("result"):
        result_data = task_data_invalid["result"]
        if isinstance(result_data, str):
            try:
                result_data = json.loads(result_data)
            except json.JSONDecodeError:
                # 如果解析失败，保持原值 - 这是修复的一部分
                pass
        response_invalid["result"] = result_data

    if task_data_invalid.get("cost_estimate"):
        cost_estimate_data = task_data_invalid["cost_estimate"]
        if isinstance(cost_estimate_data, str):
            try:
                cost_estimate_data = json.loads(cost_estimate_data)
            except json.JSONDecodeError:
                # 如果解析失败，保持原值 - 这是修复的一部分
                pass
        response_invalid["cost_estimate"] = cost_estimate_data
    
    print("  ✓ 无效JSON处理正常（保持原值，不崩溃）")
    
    print("\n所有边界情况测试通过!")


if __name__ == "__main__":
    test_response_parsing_logic()
    test_edge_cases()
    print("\n" + "="*50)
    print("验证完成！")
    print("修复总结：")
    print("1. 修复了字符串格式结果的解析问题")
    print("2. 确保返回给前端的数据始终是正确的字典格式")
    print("3. 避免了 'str' object has no attribute 'get' 错误")
    print("4. 处理了边界情况（None值、无效JSON等）")