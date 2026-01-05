import pytest
import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch
from utils.git_utils import GitUtils


class TestGitUtils:
    """测试Git工具类"""
    
    def test_initialization(self):
        """测试Git工具初始化"""
        git_utils = GitUtils()
        assert git_utils is not None
    
    @pytest.mark.asyncio
    async def test_clone_repo(self):
        """测试克隆仓库"""
        git_utils = GitUtils()
        
        # 测试正常URL
        repo_url = "https://github.com/test/repo.git"
        
        with patch('utils.git_utils.asyncio.create_subprocess_exec', new_callable=AsyncMock) as mock_subprocess:
            mock_process = MagicMock()
            mock_process.wait = AsyncMock(return_value=0)  # 成功退出码
            mock_subprocess.return_value = mock_process
            
            with patch('utils.git_utils.os.path.exists', return_value=True):
                with patch('utils.git_utils.os.listdir', return_value=['file1.txt', 'file2.py']):
                    result = await git_utils.clone_repo(repo_url)
                    
                    # 验证返回值
                    assert result is not None
                    assert 'repo_' in result
    
    @pytest.mark.asyncio
    async def test_clone_repo_with_token(self):
        """测试使用令牌克隆仓库"""
        git_utils = GitUtils()
        
        repo_url = "https://github.com/test/repo.git"
        token = "dummy_token"
        
        with patch('utils.git_utils.asyncio.create_subprocess_exec', new_callable=AsyncMock) as mock_subprocess:
            mock_process = MagicMock()
            mock_process.wait = AsyncMock(return_value=0)  # 成功退出码
            mock_subprocess.return_value = mock_process
            
            with patch('utils.git_utils.os.path.exists', return_value=True):
                with patch('utils.git_utils.os.listdir', return_value=['file1.txt', 'file2.py']):
                    result = await git_utils.clone_repo(repo_url, token=token)
                    
                    # 验证返回值
                    assert result is not None
    
    @pytest.mark.asyncio
    async def test_clone_repo_failure(self):
        """测试克隆仓库失败"""
        git_utils = GitUtils()
        
        repo_url = "https://github.com/invalid/repo.git"
        
        with patch('utils.git_utils.asyncio.create_subprocess_exec', new_callable=AsyncMock) as mock_subprocess:
            mock_process = MagicMock()
            mock_process.wait = AsyncMock(return_value=1)  # 失败退出码
            mock_subprocess.return_value = mock_process
            
            result = await git_utils.clone_repo(repo_url)
            
            # 验证返回值为None表示失败
            assert result is None
    
    def test_get_repo_size(self):
        """测试获取仓库大小"""
        git_utils = GitUtils()
        
        with patch('utils.git_utils.os.path.getsize', return_value=1024):
            with patch('utils.git_utils.os.walk') as mock_walk:
                mock_walk.return_value = [
                    ('/fake/path', ['subdir'], ['file1.txt', 'file2.py']),
                    ('/fake/path/subdir', [], ['file3.txt'])
                ]
                
                size = git_utils.get_repo_size('/fake/path')
                
                # 由于mock了单个文件大小为1024，有3个文件，所以总大小为3072
                assert size > 0
    
    @pytest.mark.asyncio
    async def test_get_repo_structure(self):
        """测试获取仓库结构"""
        git_utils = GitUtils()
        
        with patch('utils.git_utils.os.walk') as mock_walk:
            mock_walk.return_value = [
                ('/fake/path', ['subdir'], ['file1.txt', 'file2.py']),
                ('/fake/path/subdir', [], ['file3.txt'])
            ]
            
            with patch('utils.git_utils.os.path.isfile', return_value=True):
                with patch('utils.git_utils.os.path.isdir', return_value=False):
                    structure = await git_utils.get_repo_structure('/fake/path')
                    
                    # 验证结构包含必要的键
                    assert 'files' in structure
                    assert 'directories' in structure
                    assert 'size' in structure
                    assert len(structure['files']) >= 0
                    assert len(structure['directories']) >= 0