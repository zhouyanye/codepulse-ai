"""
测试缓存API端点。
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_list_cache_keys():
    """测试列出缓存键"""
    with patch('app.api.endpoints.analysis.list_cache_keys') as mock_list:
        mock_list.return_value = ["key1", "key2"]
        response = client.get("/api/v1/analyze/cache?pattern=*")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert "key1" in data["keys"]
        print("列出缓存键测试通过")


def test_delete_cache_key():
    """测试删除缓存键"""
    with patch('app.api.endpoints.analysis.delete_cache_key') as mock_delete:
        mock_delete.return_value = True
        response = client.delete("/api/v1/analyze/cache/test_key")
        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True
        print("删除缓存键测试通过（存在）")

    with patch('app.api.endpoints.analysis.delete_cache_key') as mock_delete:
        mock_delete.return_value = False
        response = client.delete("/api/v1/analyze/cache/nonexistent")
        assert response.status_code == 404
        print("删除缓存键测试通过（不存在）")


def test_get_cached_result():
    """测试获取缓存结果"""
    with patch('app.api.endpoints.analysis.get_cached_analysis_result') as mock_get:
        mock_get.return_value = {"score": 90}
        response = client.get("/api/v1/analyze/cache/abc123")
        assert response.status_code == 200
        data = response.json()
        assert data["score"] == 90
        print("获取缓存结果测试通过（存在）")

    with patch('app.api.endpoints.analysis.get_cached_analysis_result') as mock_get:
        mock_get.return_value = None
        response = client.get("/api/v1/analyze/cache/abc123")
        assert response.status_code == 404
        print("获取缓存结果测试通过（不存在）")


def test_cache_endpoints_headers():
    """测试缓存端点的响应头"""
    with patch('app.api.endpoints.analysis.list_cache_keys') as mock_list:
        mock_list.return_value = []
        response = client.get("/api/v1/analyze/cache?pattern=*")
        assert response.status_code == 200
        assert "content-type" in response.headers
        assert "application/json" in response.headers["content-type"]
        print("缓存端点头部测试通过")


if __name__ == "__main__":
    # 注意：需要启动FastAPI应用，这里仅作为示例
    print("运行缓存端点测试需要启动FastAPI，请使用pytest运行")
    print("示例命令: pytest tests/test_cache_endpoints.py -v")