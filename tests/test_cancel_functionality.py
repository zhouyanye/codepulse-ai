#!/usr/bin/env python3
"""
测试取消功能的完整性
验证前端取消按钮能够正确终止分析流程
"""
import time
import requests
import sys


def test_cancel_during_cost_estimation():
    """测试在成本估算阶段取消分析"""
    print("=" * 60)
    print("测试1: 在成本估算阶段取消分析")
    print("=" * 60)
    
    # 启动分析任务
    payload = {
        "repo_url": "https://github.com/psf/requests",
        "ai_provider": "deepseek",
        "include_static_scan": True
    }
    
    print(f"\n1. 启动分析任务: {payload['repo_url']}")
    resp = requests.post("http://localhost:8000/api/v1/analyze/sync-polling", json=payload, timeout=10)
    
    if resp.status_code != 200:
        print(f"❌ 启动任务失败: {resp.status_code} - {resp.text}")
        return False
    
    task_id = resp.json().get("task_id")
    print(f"✓ 任务已启动，ID: {task_id}")
    
    # 等待成本估算完成
    print(f"\n2. 等待成本估算...")
    max_wait = 60  # 最多等待60秒
    start_time = time.time()
    cost_estimate_shown = False
    
    while time.time() - start_time < max_wait:
        status_resp = requests.get(f"http://localhost:8000/api/v1/analyze/polling-status/{task_id}", timeout=10)
        if status_resp.status_code == 200:
            status_data = status_resp.json()
            status = status_data.get("status")
            message = status_data.get("message", "")
            cost_estimate = status_data.get("cost_estimate")
            
            print(f"   状态: {status}, 进度: {status_data.get('progress', 0)}%, 消息: {message}")
            
            if cost_estimate:
                print(f"✓ 成本估算已生成，准备取消...")
                cost_estimate_shown = True
                break
        
        time.sleep(2)
    
    if not cost_estimate_shown:
        print(f"❌ 等待成本估算超时")
        # 即使超时也尝试取消
        status_data = status_resp.json()
        task_id = status_data.get("task_id", task_id)
    
    if not cost_estimate_shown and not status_data.get("cancelled", False):
        print(f"   尝试继续取消测试...")
    
    # 取消任务
    print(f"\n3. 取消任务: {task_id}")
    cancel_resp = requests.post(f"http://localhost:8000/api/v1/analyze/cancel/{task_id}", timeout=10)
    
    if cancel_resp.status_code == 200:
        print(f"✓ 取消请求成功: {cancel_resp.json()}")
    else:
        print(f"⚠ 取消请求失败: {cancel_resp.status_code} - {cancel_resp.text}")
    
    # 验证任务状态变为cancelled
    print(f"\n4. 验证任务状态...")
    time.sleep(2)  # 等待状态更新
    
    status_resp = requests.get(f"http://localhost:8000/api/v1/analyze/polling-status/{task_id}", timeout=10)
    if status_resp.status_code == 200:
        status_data = status_resp.json()
        status = status_data.get("status")
        cancelled = status_data.get("cancelled", False)
        
        print(f"   最终状态: {status}, cancelled: {cancelled}")
        
        if status == "cancelled" or cancelled:
            print(f"✓ 任务已成功取消")
            return True
        else:
            print(f"⚠ 任务未正确取消，状态仍为: {status}")
            return False
    else:
        print(f"❌ 获取状态失败: {status_resp.status_code}")
        return False


def test_cancel_during_cloning():
    """测试在克隆阶段取消分析"""
    print("\n" + "=" * 60)
    print("测试2: 在克隆阶段立即取消分析")
    print("=" * 60)
    
    # 启动分析任务
    payload = {
        "repo_url": "https://github.com/psf/requests",  # 较大的仓库，克隆需要时间
        "ai_provider": "deepseek",
        "include_static_scan": True
    }
    
    print(f"\n1. 启动分析任务: {payload['repo_url']}")
    resp = requests.post("http://localhost:8000/api/v1/analyze/sync-polling", json=payload, timeout=10)
    
    if resp.status_code != 200:
        print(f"❌ 启动任务失败: {resp.status_code} - {resp.text}")
        return False
    
    task_id = resp.json().get("task_id")
    print(f"✓ 任务已启动，ID: {task_id}")
    
    # 立即取消（在克隆过程中）
    print(f"\n2. 立即取消任务（克隆中）...")
    time.sleep(1)  # 等待1秒让克隆开始
    
    cancel_resp = requests.post(f"http://localhost:8000/api/v1/analyze/cancel/{task_id}", timeout=10)
    if cancel_resp.status_code == 200:
        print(f"✓ 取消请求成功: {cancel_resp.json()}")
    else:
        print(f"⚠ 取消请求失败: {cancel_resp.status_code} - {cancel_resp.text}")
    
    # 验证任务状态
    print(f"\n3. 验证任务状态...")
    time.sleep(3)  # 等待取消生效
    
    status_resp = requests.get(f"http://localhost:8000/api/v1/analyze/polling-status/{task_id}", timeout=10)
    if status_resp.status_code == 200:
        status_data = status_resp.json()
        status = status_data.get("status")
        cancelled = status_data.get("cancelled", False)
        message = status_data.get("message", "")
        
        print(f"   最终状态: {status}, cancelled: {cancelled}, 消息: {message}")
        
        if status == "cancelled" or cancelled:
            print(f"✓ 任务已成功取消")
            return True
        else:
            print(f"⚠ 任务未正确取消，状态仍为: {status}")
            return False
    else:
        print(f"❌ 获取状态失败: {status_resp.status_code}")
        return False


def test_cancel_after_confirmation_timeout():
    """测试用户确认超时后的自动取消"""
    print("\n" + "=" * 60)
    print("测试3: 用户确认超时自动取消")
    print("=" * 60)
    
    # 启动分析任务
    payload = {
        "repo_url": "https://github.com/psf/requests",
        "ai_provider": "deepseek",
        "include_static_scan": True
    }
    
    print(f"\n1. 启动分析任务: {payload['repo_url']}")
    resp = requests.post("http://localhost:8000/api/v1/analyze/sync-polling", json=payload, timeout=10)
    
    if resp.status_code != 200:
        print(f"❌ 启动任务失败: {resp.status_code} - {resp.text}")
        return False
    
    task_id = resp.json().get("task_id")
    print(f"✓ 任务已启动，ID: {task_id}")
    
    # 等待成本估算和超时（不确认，也不取消）
    print(f"\n2. 等待成本估算...")
    max_wait = 120  # 最多等待2分钟
    start_time = time.time()
    cost_estimate_shown = False
    
    while time.time() - start_time < max_wait:
        status_resp = requests.get(f"http://localhost:8000/api/v1/analyze/polling-status/{task_id}", timeout=10)
        if status_resp.status_code == 200:
            status_data = status_resp.json()
            status = status_data.get("status")
            message = status_data.get("message", "")
            cost_estimate = status_data.get("cost_estimate")
            
            if cost_estimate and not cost_estimate_shown:
                print(f"✓ 成本估算已生成，等待确认超时...")
                cost_estimate_shown = True
            
            if status == "cancelled":
                print(f"✓ 任务已因确认超时自动取消")
                print(f"   消息: {message}")
                return True
            
            if status == "failed":
                print(f"⚠ 任务失败: {message}")
                return False
            
            if status == "completed":
                print(f"❌ 任务意外完成，应该被超时取消")
                return False
        
        time.sleep(2)
    
    print(f"⚠ 等待超时，检查任务状态...")
    status_resp = requests.get(f"http://localhost:8000/api/v1/analyze/polling-status/{task_id}", timeout=10)
    if status_resp.status_code == 200:
        status_data = status_resp.json()
        status = status_data.get("status")
        print(f"   最终状态: {status}")
        return status == "cancelled"
    
    return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("CodePulse-AI 取消功能测试套件")
    print("=" * 60)
    
    # 检查后端是否运行
    try:
        health_resp = requests.get("http://localhost:8000/api/v1/health", timeout=5)
        if health_resp.status_code != 200:
            print(f"❌ 后端健康检查失败，请确保后端正在运行")
            return False
        print(f"✓ 后端运行正常")
    except requests.exceptions.ConnectionError:
        print(f"❌ 无法连接到后端，请确保后端正在运行 (http://localhost:8000)")
        return False
    
    results = []
    
    # 运行测试
    try:
        results.append(("成本估算阶段取消", test_cancel_during_cost_estimation()))
    except Exception as e:
        print(f"❌ 测试1执行异常: {e}")
        results.append(("成本估算阶段取消", False))
    
    try:
        results.append(("克隆阶段取消", test_cancel_during_cloning()))
    except Exception as e:
        print(f"❌ 测试2执行异常: {e}")
        results.append(("克隆阶段取消", False))
    
    # 跳过超时测试（需要等待较长时间）
    # try:
    #     results.append(("确认超时自动取消", test_cancel_after_confirmation_timeout()))
    # except Exception as e:
    #     print(f"❌ 测试3执行异常: {e}")
    #     results.append(("确认超时自动取消", False))
    
    # 输出测试结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    for test_name, result in results:
        status = "✓ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
    
    all_passed = all(result for _, result in results)
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ 所有测试通过")
        print("=" * 60)
        return 0
    else:
        print("❌ 部分测试失败")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())