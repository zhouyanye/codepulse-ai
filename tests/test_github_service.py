import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from services.github_service import GitHubService


class TestGitHubService:
    """测试GitHub服务"""
    
    def test_initialization(self):
        """测试GitHub服务初始化"""
        service = GitHubService()
        assert service.github_client is not None
        assert service.token_estimator is not None
    
    @pytest.mark.asyncio
    async def test_get_repo_info(self):
        """测试获取仓库信息"""
        service = GitHubService()
        
        # Mock GitHub客户端
        with patch.object(service.github_client, 'get_repo', new_callable=AsyncMock) as mock_get_repo:
            mock_repo = MagicMock()
            mock_repo.full_name = "test/repo"
            mock_repo.description = "A test repository"
            mock_repo.stargazers_count = 100
            mock_repo.forks_count = 20
            mock_repo.language = "Python"
            mock_repo.html_url = "https://github.com/test/repo"
            
            mock_get_repo.return_value = mock_repo
            
            repo_info = await service._get_repo_info("test/repo", "dummy_token")
            
            assert repo_info["full_name"] == "test/repo"
            assert repo_info["description"] == "A test repository"
            assert repo_info["stars"] == 100
            assert repo_info["forks"] == 20
            assert repo_info["language"] == "Python"
    
    @pytest.mark.asyncio
    async def test_get_repo_structure(self):
        """测试获取仓库结构"""
        service = GitHubService()
        
        # Mock仓库结构获取
        with patch.object(service, '_get_repo_files', new_callable=AsyncMock) as mock_get_files:
            mock_get_files.return_value = {
                "files": ["main.py", "README.md"],
                "directories": ["src", "tests"],
                "size": 1024
            }
            
            structure = await service._get_repo_structure("test/repo", "dummy_token")
            
            assert "files" in structure
            assert "directories" in structure
            assert "size" in structure
    
    @pytest.mark.asyncio
    async def test_get_contributors(self):
        """测试获取贡献者信息"""
        service = GitHubService()
        
        # Mock贡献者获取
        with patch.object(service.github_client, 'get_contributors', new_callable=AsyncMock) as mock_get_contributors:
            mock_contributors = [
                MagicMock(login="user1", contributions=50),
                MagicMock(login="user2", contributions=30)
            ]
            mock_get_contributors.return_value = mock_contributors
            
            contributors = await service._get_contributors("test/repo", "dummy_token")
            
            assert len(contributors) == 2
            assert contributors[0]["login"] == "user1"
            assert contributors[0]["contributions"] == 50
    
    @pytest.mark.asyncio
    async def test_get_recent_activity(self):
        """测试获取近期活动"""
        service = GitHubService()
        
        # Mock活动获取
        with patch.object(service.github_client, 'get_recent_activity', new_callable=AsyncMock) as mock_get_activity:
            mock_activity = [
                MagicMock(created_at="2023-01-01"),
                MagicMock(created_at="2023-01-02")
            ]
            mock_get_activity.return_value = mock_activity
            
            activity = await service._get_recent_activity("test/repo", "dummy_token")
            
            assert len(activity) == 2
    
    def test_estimate_tokens(self):
        """测试令牌估算"""
        service = GitHubService()
        
        code_content = "def hello():\n    print('Hello, World!')"
        tokens = service._estimate_tokens(code_content)
        
        # 令牌估算应该返回一个数字
        assert isinstance(tokens, int)
        assert tokens > 0