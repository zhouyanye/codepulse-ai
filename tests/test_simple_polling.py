"""
简单测试轮询端点是否可用
"""

from app.main import app
from fastapi.testclient import TestClient
import json


def test_health_endpoint():
    """测试健康检查端点是否可用"""
    client = TestClient(app)
    response = client.get('/api/v1/health')
    print(f"Health endpoint status: {response.status_code}")
    if response.status_code == 200:
        print(f"Health response: {response.json()}")
    else:
        print("Health endpoint not available")


def test_analysis_polling_endpoint_exists():
    """测试分析轮询端点是否存在"""
    client = TestClient(app)
    # 先测试一个不存在的任务ID，应该返回404而不是404 Not Found（路由不存在）
    response = client.get('/api/v1/analyze/polling-status/nonexistent_task')
    print(f"Polling endpoint status for nonexistent task: {response.status_code}")
    # 如果返回404，检查是否是"任务不存在"（路由存在）还是其他404（路由不存在）
    if response.status_code == 404:
        response_text = response.json()
        if "任务不存在" in str(response_text):
            print("Polling endpoint exists (returned '任务不存在' for nonexistent task)")
        else:
            print(f"Polling endpoint may not exist (returned: {response_text})")
    else:
        print(f"Polling endpoint returned: {response.status_code}, {response.json()}")


if __name__ == "__main__":
    print("Testing endpoints...")
    test_health_endpoint()
    test_analysis_polling_endpoint_exists()
