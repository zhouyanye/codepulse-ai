import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

import pytest
import json
from unittest.mock import MagicMock, patch, AsyncMock
from utils.ai_client import AIClient

@pytest.fixture
def mock_settings():
    with patch("utils.ai_client.settings") as mock_settings:
        mock_settings.DEEPSEEK_API_KEY = "test_deepseek_key"
        mock_settings.KIMI_API_KEY = "test_kimi_key"
        mock_settings.OPENAI_API_KEY = "test_openai_key"
        yield mock_settings

def test_ai_client_initialization(mock_settings):
    """测试AI客户端初始化"""
    # 在测试环境中，模拟API密钥可用
    with patch("utils.ai_provider_utils.has_api_key", return_value=True):
        client = AIClient(provider="deepseek")
        assert client.provider == "deepseek"
        assert client.api_key == "test_deepseek_key"
        
        client = AIClient(provider="kimi")
        assert client.provider == "kimi"
        assert client.api_key == "test_kimi_key"

@pytest.mark.asyncio
async def test_ai_client_chat_method(mock_settings):
    """测试AI客户端的chat方法"""
    with patch("utils.ai_provider_utils.has_api_key", return_value=True):
        client = AIClient(provider="deepseek")
        
        with patch.object(client, '_chat_completion', new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = "测试响应内容"
            
            result = await client.chat("测试提示词")
            
            assert isinstance(result, str)
            assert result == "测试响应内容"
            mock_chat.assert_called_once()

@pytest.mark.asyncio
async def test_ai_client_json_mode_detection(mock_settings):
    """测试JSON模式检测"""
    with patch("utils.ai_provider_utils.has_api_key", return_value=True):
        client = AIClient(provider="deepseek")
        
        # 测试包含json关键词的提示词
        config = client._get_json_mode_config("deepseek", "请以json格式返回")
        assert config is not None
        assert "response_format" in config
        
        # 测试不包含json关键词的提示词
        config = client._get_json_mode_config("deepseek", "请简单回答")
        assert config is None

def test_ai_client_providers(mock_settings):
    """测试不同AI提供商"""
    with patch("utils.ai_provider_utils.has_api_key", return_value=True):
        providers = ["deepseek", "kimi", "openai","doubao"]
        for provider in providers:
            client = AIClient(provider=provider)
            assert client.provider == provider
            assert client.api_key is not None

def test_ai_client_base_urls(mock_settings):
    """测试不同AI提供商的基础URL"""
    with patch("utils.ai_provider_utils.has_api_key", return_value=True):
        client_deepseek = AIClient(provider="deepseek")
        assert "deepseek" in client_deepseek.base_url

        client_kimi = AIClient(provider="kimi")
        assert "moonshot" in client_kimi.base_url

        client_openai = AIClient(provider="openai")
        assert "openai" in client_openai.base_url