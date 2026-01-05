"""
测试主应用配置
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

import pytest
from fastapi.testclient import TestClient
from app.main import app
from fastapi.middleware.cors import CORSMiddleware

def test_app_creation():
    """测试应用创建"""
    assert app is not None

def test_cors_configuration():
    """测试CORS配置"""
    # 检查是否有CORS中间件
    cors_middleware_found = False
    for middleware in app.user_middleware:
        if middleware.cls == CORSMiddleware:
            cors_middleware_found = True
            break
    
    assert cors_middleware_found, "CORS中间件未正确配置"

def test_router_registration():
    """测试路由注册"""
    routes = [route.path for route in app.routes]
    assert "/api/v1/health" in routes
    assert "/api/v1/analyze" in routes
    print("✅ 路由注册测试通过")


def test_docs_available():
    """测试文档端点可用"""
    client = TestClient(app)
    response = client.get("/docs")
    assert response.status_code == 200
    print("✅ 文档端点测试通过")


def test_redoc_available():
    """测试ReDoc端点可用"""
    client = TestClient(app)
    response = client.get("/redoc")
    assert response.status_code == 200
    print("✅ ReDoc端点测试通过")


def test_root_endpoint():
    """测试根端点"""
    client = TestClient(app)
    response = client.get("/")
    # FastAPI默认返回404，但我们可以测试应用是否正常运行
    assert response.status_code in [404, 200]
    print("✅ 根端点测试通过")


if __name__ == "__main__":
    test_app_initialization()
    test_cors_configuration()
    test_router_registration()
    test_docs_available()
    test_redoc_available()
    test_root_endpoint()
    print("\n所有主应用测试通过")