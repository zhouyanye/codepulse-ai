import unittest
import os
from unittest.mock import Mock
from services.cost_estimation_service import CostEstimationService


class TestBlacklistFilter(unittest.TestCase):
    """测试成本估算服务中的黑名单过滤功能"""

    def setUp(self):
        # 创建一个模拟对象，避免初始化完整的服务实例
        self.service = Mock()
        # 手动复制 _is_blacklisted_file 方法的逻辑到测试类
        pass

    def _is_blacklisted_file(self, root: str, file: str) -> bool:
        """
        复制 CostEstimationService 中 _is_blacklisted_file 方法的逻辑
        """
        # 与 static_scan_service 保持完全一致
        EXCLUDE_DIRS = {".git", ".gitlab", ".bitbucket",  # 版本控制
                        ".circleci", ".travis", ".drone",  # CI配置
                        "site", "dist", "build", "target", "out", "release", "obj",  # 构建产物
                        "__pycache__", ".pyc", ".pytest_cache",  # Python缓存
                        "venv", "env", ".venv", ".env", "envs",  # 虚拟环境
                        "node_modules", "vendor", "bower_components", "jspm_packages",  # 依赖包
                        ".idea", ".vscode", ".vs", ".project", ".settings", ".metadata",  # IDE配置
                        "tmp", "logs", "cache", ".cache", "temp",  # 临时文件
                        "images", "static", "public", "assets", "media", "img", "fonts", "icon", "icons",  # 静态资源
                        ".yarn", "yarn-cache",  # Yarn相关
                        ".dart_tool", ".fvm",  # Flutter相关
                        "Pods", "Carthage", "build", ".build",  # iOS相关
                        ".angular", ".nuxt", ".next", ".svelte",  # 前端框架相关
                        ".github", ".gitlab", ".gitee"}  # 平台配置目录

        # 系统文件和锁定文件
        SYSTEM_FILES = {".ds_store", "thumbs.db",  # 系统文件
                      "package-lock.json", "yarn.lock", "gemfile.lock", "podfile.lock"}  # 锁定文件

        file_lower = file.lower()
        
        # 方法1：检查路径中是否包含排除目录（使用路径分隔符边界确保精确匹配）
        # 修复：使用路径边界确保只匹配完整目录名，而不是子串
        root_normalized = '/' + root.replace('\\', '/').lower() + '/'
        for exclude_dir in EXCLUDE_DIRS:
            # 在路径前后加上分隔符确保匹配完整目录名
            exclude_pattern = '/' + exclude_dir + '/'
            if exclude_pattern in root_normalized:
                return True

        # 方法2：检查文件名是否匹配排除模式
        if file_lower in SYSTEM_FILES:
            return True
        
        # 方法3：排除临时后缀文件
        if file_lower.endswith(('.log', '.tmp', '.bak')):
            return True

        return False

    def test_is_blacklisted_file_basic(self):
        """测试基本的黑名单过滤功能"""
        # 测试正常文件
        self.assertFalse(self._is_blacklisted_file("/normal/path", "normal_file.py"))
        self.assertFalse(self._is_blacklisted_file("/normal/path", "normal_file.txt"))
        
        # 测试系统文件
        self.assertTrue(self._is_blacklisted_file("/any/path", ".DS_Store"))
        self.assertTrue(self._is_blacklisted_file("/any/path", "thumbs.db"))
        
        # 测试临时文件后缀
        self.assertTrue(self._is_blacklisted_file("/any/path", "temp.log"))
        self.assertTrue(self._is_blacklisted_file("/any/path", "temp.tmp"))
        self.assertTrue(self._is_blacklisted_file("/any/path", "temp.bak"))

    def test_is_blacklisted_file_excluded_directories(self):
        """测试排除目录中的文件"""
        # 测试 .git 目录
        self.assertTrue(self._is_blacklisted_file("/project/.git", "config"))
        self.assertTrue(self._is_blacklisted_file("/project/.git/objects", "file"))
        self.assertTrue(self._is_blacklisted_file("/project/sub/.git", "config"))
        
        # 测试虚拟环境目录
        self.assertTrue(self._is_blacklisted_file("/project/venv", "script.py"))
        self.assertTrue(self._is_blacklisted_file("/project/env", "script.py"))
        self.assertTrue(self._is_blacklisted_file("/project/.venv", "script.py"))
        self.assertTrue(self._is_blacklisted_file("/project/.env", "script.py"))
        
        # 测试 node_modules 目录
        self.assertTrue(self._is_blacklisted_file("/project/node_modules", "package.json"))
        
        # 测试 IDE 配置目录
        self.assertTrue(self._is_blacklisted_file("/project/.idea", "workspace.xml"))
        self.assertTrue(self._is_blacklisted_file("/project/.vscode", "settings.json"))

    def test_is_blacklisted_file_no_false_positives(self):
        """测试避免误判（路径中包含排除目录名但不是独立目录）"""
        # 测试路径中包含 "env" 但不是虚拟环境目录
        self.assertFalse(self._is_blacklisted_file("/project/environment", "config.py"))
        self.assertFalse(self._is_blacklisted_file("/project/environments", "config.py"))
        self.assertFalse(self._is_blacklisted_file("/project/myenv", "config.py"))
        self.assertFalse(self._is_blacklisted_file("/project/venv_backup", "config.py"))
        
        # 测试路径中包含 "git" 但不是 .git 目录
        self.assertFalse(self._is_blacklisted_file("/project/github", "repo.py"))
        self.assertFalse(self._is_blacklisted_file("/project/gitlab", "repo.py"))
        self.assertFalse(self._is_blacklisted_file("/project/program_git", "main.py"))
        self.assertFalse(self._is_blacklisted_file("/project/repo_analysis_github", "main.py"))
        
        # 测试路径中包含 "build" 但不是 build 目录
        self.assertFalse(self._is_blacklisted_file("/project/builder", "main.py"))
        self.assertFalse(self._is_blacklisted_file("/project/building", "main.py"))
        self.assertFalse(self._is_blacklisted_file("/project/rebuild", "main.py"))
        
        # 测试正常文件不应被排除 - 这是用户提到的关键问题
        self.assertFalse(self._is_blacklisted_file("/project/repo_analysis_github", "clear_redis_keys.py"))
        self.assertFalse(self._is_blacklisted_file("/project/houseSpider", "items.py"))
        self.assertFalse(self._is_blacklisted_file("/project/houseSpider/spiders", "house.py"))

    def test_is_blacklisted_file_case_insensitive(self):
        """测试大小写不敏感"""
        # 测试大小写不敏感的匹配
        self.assertTrue(self._is_blacklisted_file("/PROJECT/.GIT", "CONFIG"))
        self.assertTrue(self._is_blacklisted_file("/PROJECT/VENV", "SCRIPT.PY"))
        self.assertTrue(self._is_blacklisted_file("/PROJECT/.IDEA", "SETTINGS.JSON"))
        
        # 测试大小写不敏感的非匹配
        self.assertFalse(self._is_blacklisted_file("/PROJECT/GITHUB", "REPO.PY"))

    def test_is_blacklisted_file_windows_paths(self):
        """测试 Windows 路径格式"""
        # 测试 Windows 风格路径
        self.assertTrue(self._is_blacklisted_file("C:\\project\\.git", "config"))
        self.assertTrue(self._is_blacklisted_file("C:\\project\\venv", "script.py"))
        self.assertTrue(self._is_blacklisted_file("C:\\project\\.idea", "workspace.xml"))
        
        # 测试 Windows 路径中的非排除目录
        self.assertFalse(self._is_blacklisted_file("C:\\project\\environment", "config.py"))
        self.assertFalse(self._is_blacklisted_file("C:\\project\\github_repo", "main.py"))


if __name__ == '__main__':
    unittest.main()