#!/usr/bin/env python3
"""
测试克隆取消中断功能
验证取消时能真正终止正在运行的git进程
"""
import asyncio
import time
import sys
import os

# 确保能从项目根目录导入模块
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from utils.git_utils import GitUtils
    from models.task_manager import task_manager
except ImportError:
    try:
        from app.utils.git_utils import GitUtils
        from models.task_manager import task_manager
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        print("请确保在项目根目录运行，或使用 python -m tests.test_cancel_clone_interrupt")
        sys.exit(1)


class CancelCounter:
    """取消计数器，用于测试"""
    def __init__(self):
        self.cancel_triggered = False
    
    def trigger_cancel(self):
        """触发取消"""
        print("🚫 取消标志已设置！")
        self.cancel_triggered = True
    
    def check_cancel(self):
        """检查是否取消"""
        return self.cancel_triggered


async def test_immediate_cancel():
    """测试立即取消（克隆前）"""
    print("\n" + "="*60)
    print("测试1: 立即取消（克隆前）")
    print("="*60)
    
    cancel_counter = CancelCounter()
    
    # 立即触发取消
    cancel_counter.trigger_cancel()
    
    git_utils = GitUtils()
    repo_url = "https://github.com/psf/requests"
    
    start_time = time.time()
    result = await git_utils.clone_repo(
        repo_url, 
        cancel_callback=cancel_counter.check_cancel
    )
    elapsed = time.time() - start_time
    
    print(f"✓ 克隆结果: {result}")
    print(f"✓ 耗时: {elapsed:.2f}秒")
    
    if elapsed < 2:
        print("✓ 立即取消成功（应在2秒内返回）")
        return True
    else:
        print(f"❌ 立即取消失败（耗时{elapsed:.2f}秒）")
        return False


async def test_cancel_during_clone():
    """测试克隆过程中取消"""
    print("\n" + "="*60)
    print("测试2: 克隆过程中取消")
    print("="*60)
    
    cancel_counter = CancelCounter()
    
    # 使用一个需要时间克隆的仓库
    repo_url = "https://github.com/python/cpython"
    
    # 3秒后取消
    async def delayed_cancel():
        await asyncio.sleep(3)
        cancel_counter.trigger_cancel()
        print("🚫 3秒后触发取消...")
    
    git_utils = GitUtils()
    
    # 启动异步任务
    clone_task = asyncio.create_task(
        git_utils.clone_repo(
            repo_url,
            cancel_callback=cancel_counter.check_cancel
        )
    )
    
    # 启动延迟取消
    cancel_task = asyncio.create_task(delayed_cancel())
    
    start_time = time.time()
    try:
        result = await clone_task
    except Exception as e:
        print(f"克隆异常: {e}")
        result = None
    elapsed = time.time() - start_time
    
    # 取消延迟取消任务
    cancel_task.cancel()
    try:
        await cancel_task
    except:
        pass
    
    print(f"✓ 克隆结果: {result}")
    print(f"✓ 耗时: {elapsed:.2f}秒")
    
    # 应该在5秒左右完成（3秒等待 + 一点开销）
    if 3 < elapsed < 8:
        print("✓ 克隆过程中取消成功（耗时符合预期）")
        return True
    else:
        print(f"❌ 克隆过程中取消失败（耗时{elapsed:.2f}秒不符合预期）")
        return False


async def test_full_polling_cancel():
    """测试完整的轮询+取消流程"""
    print("\n" + "="*60)
    print("测试3: 完整轮询+取消流程")
    print("="*60)
    
    import requests
    
    # 启动分析任务
    payload = {
        "repo_url": "https://github.com/psf/requests",
        "ai_provider": "deepseek",
        "include_static_scan": False  # 跳过静态扫描加快速度
    }
    
    print("1. 启动分析任务...")
    try:
        resp = requests.post("http://localhost:8000/api/v1/analyze/sync-polling", 
                           json=payload, timeout=10)
    except requests.exceptions.ConnectionError:
        print("⚠ 后端未运行，跳过完整轮询测试")
        print("   提示: 使用 'python run.py' 启动后再测试")
        return None  # 返回None表示跳过
    
    if resp.status_code != 200:
        print(f"❌ 启动任务失败: {resp.status_code}")
        return False
    
    task_id = resp.json().get("task_id")
    print(f"✓ 任务ID: {task_id}")
    
    # 等待3秒让克隆开始
    print("2. 等待3秒让克隆开始...")
    time.sleep(3)
    
    # 取消任务
    print("3. 取消任务...")
    cancel_resp = requests.post(f"http://localhost:8000/api/v1/analyze/cancel/{task_id}",
                              timeout=10)
    
    if cancel_resp.status_code == 200:
        print(f"✓ 取消API调用成功")
    else:
        print(f"⚠ 取消API调用失败: {cancel_resp.status_code}")
    
    # 等待任务停止
    print("4. 等待任务停止...")
    attempts = 0
    max_attempts = 20  # 最多等20秒
    
    while attempts < max_attempts:
        time.sleep(1)
        try:
            status_resp = requests.get(f"http://localhost:8000/api/v1/analyze/polling-status/{task_id}",
                                      timeout=10)
            
            if status_resp.status_code == 200:
                status_data = status_resp.json()
                status = status_data.get("status")
                cancelled = status_data.get("cancelled", False)
                
                print(f"   状态检查 {attempts + 1}: status={status}, cancelled={cancelled}")
                
                if status == "cancelled" or cancelled:
                    print("✓ 任务已成功取消")
                    return True
        except requests.exceptions.RequestException as e:
            print(f"   状态检查失败: {e}")
        
        attempts += 1
    
    print(f"❌ 任务在{max_attempts}秒内未正确停止")
    return False


async def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("CodePulse-AI 克隆取消中断测试")
    print("="*60)
    
    # 检查后端是否运行
    try:
        import requests
        health_resp = requests.get("http://localhost:8000/api/v1/health", timeout=5)
        if health_resp.status_code != 200:
            print(f"❌ 后端健康检查失败，请确保后端正在运行")
            return 1
        print(f"✓ 后端运行正常\n")
    except requests.exceptions.ConnectionError:
        print(f"⚠ 后端未运行，跳过需要后端的测试")
        print(f"   提示: 使用 'python run.py' 启动后再测试完整功能")
        print(f"   当前将运行基础克隆取消测试...\n")
    
    results = []
    
    # 运行测试
    try:
        results.append(("立即取消", await test_immediate_cancel()))
    except Exception as e:
        print(f"❌ 测试1执行异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("立即取消", False))
    
    try:
        results.append(("克隆过程中取消", await test_cancel_during_clone()))
    except Exception as e:
        print(f"❌ 测试2执行异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("克隆过程中取消", False))
    
    try:
        test3_result = await test_full_polling_cancel()
        if test3_result is not None:
            results.append(("完整轮询取消", test3_result))
    except Exception as e:
        print(f"❌ 测试3执行异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("完整轮询取消", False))
    
    # 输出测试结果
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    
    for test_name, result in results:
        status = "✓ 通过" if result else "❌ 失败" if result is False else "⚭ 跳过"
        print(f"{test_name}: {status}")
    
    all_passed = all(result for _, result in results if result is not None)
    
    print("\n" + "="*60)
    if all_passed:
        print("✓ 所有测试通过")
        print("="*60)
        return 0
    else:
        print("❌ 部分测试失败或跳过")
        print("="*60)
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))