import unittest
import tempfile
import os
from pathlib import Path
import shutil
from unittest.mock import Mock


class TestCostEstimationWithRealRepo(unittest.TestCase):
    """测试对真实仓库进行成本估算的功能"""

    def _is_blacklisted_file_cost_estimation(self, root: str, file: str) -> bool:
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

    def _is_blacklisted_file_preprocessing(self, root: str, file: str) -> bool:
        """
        复制 PreprocessingService 中 _is_blacklisted_file 方法的逻辑
        """
        # 预处理服务的黑名单模式
        blacklist_patterns = [
            # 版本控制
            '.git', '.gitignore', '.gitmodules', '.gitattributes', '.svn', '.hg', '.bzr',
            # CI/CD配置
            '.circleci', '.travis', '.drone', '.github', '.gitlab', '.gitee',
            # 常见的依赖目录
            'node_modules', 'venv', 'virtualenv', '.venv', 'env', 'envs', '__pycache__',
            '.pytest_cache', '.tox', 'coverage', '.coverage', 'jspm_packages', '.yarn', 'yarn-cache',
            # 构建产物
            'dist', 'build', 'target', 'out', 'release', 'obj', 'site',
            # 虚拟环境
            '.env',
            # IDE配置
            '.idea', '.vscode', '.vs', '.project', '.settings', '.metadata',
            # 临时文件
            'tmp', 'logs', 'cache', '.cache', 'temp',
            # 静态资源
            'images', 'static', 'public', 'assets', 'media', 'img', 'fonts', 'icon', 'icons',
            # 移动端相关
            '.dart_tool', '.fvm', 'Pods', 'Carthage', '.build',
            # 前端框架
            '.angular', '.nuxt', '.next', '.svelte', 'nosetests.xml',
            # IDE和编辑器文件
            '*.swp', '*.swo', '*~', '.DS_Store', 'Thumbs.db',
            # 锁文件
            'package-lock.json', 'yarn.lock', 'Gemfile.lock', 'Pipfile.lock', 'poetry.lock', 'Cargo.lock',
            # macOS和Windows系统文件
            'desktop.ini',
            # 日志和临时文件
            '*.log', '*.tmp', '*.bak',
            # 环境配置文件
            '.env.local', '.env.development.local', '.env.test.local', '.env.production.local', '.env.*.local',
            # 缓存目录
            '.npm', '.m2', '.gradle', '.cabal', 'vendor',
            # 测试覆盖率目录
            '.nyc_output',
            # 其他
            '.output',
        ]

        full_path = os.path.join(root, file).lower()
        file_lower = file.lower()
        # 将路径按分隔符分割，检查目录名是否匹配，而不是路径子串
        root_parts = [part.lower() for part in root.replace('\\', '/').split('/') if part]

        for pattern in blacklist_patterns:
            # 处理通配符模式
            if '*' in pattern:
                import fnmatch
                if fnmatch.fnmatch(file_lower, pattern.lower()) or fnmatch.fnmatch(full_path, pattern.lower()):
                    return True
            # 检查文件名是否完全匹配
            elif file_lower == pattern.lower():
                return True
            # 检查路径中是否包含目录模式（精确匹配目录名，而不是子串）
            elif pattern.lower() in root_parts:
                return True

        return False

    def test_cost_estimation_blacklist_logic(self):
        """测试成本估算服务的黑名单逻辑"""
        # 测试用户提到的具体文件路径（使用非temp路径以避免temp目录模式的干扰）
        test_cases = [
            # (root, file, should_be_blacklisted, description)
            ("C:/projects/repo_analysis_github/houseSpider", "items.py", False, "houseSpider目录下的items.py不应该被跳过"),
            ("C:/projects/repo_analysis_github", "clear_redis_keys.py", False, "根目录下的clear_redis_keys.py不应该被跳过"),
            ("C:/projects/repo_analysis_github/.git", "config", True, ".git目录下的文件应该被跳过"),
            ("C:/projects/repo_analysis_github/venv/lib", "some_file.py", True, "venv目录下的文件应该被跳过"),
            ("C:/projects/repo_analysis_github/environment", "config.py", False, "environment目录下的文件不应该被跳过"),
            ("C:/projects/repo_analysis_github/github_project", "main.py", False, "包含github的路径不应该导致误判"),
            ("C:/projects/repo_analysis_github/repo_analysis_github", "crawl_fang_city_code_mapping.py", False, "repo_analysis_github目录下的py文件不应该被跳过"),
            ("C:/projects/repo_analysis_github/houseSpider/spiders", "house.py", False, "houseSpider/spiders目录下的house.py不应该被跳过"),
        ]
        
        for root, file, should_be_blacklisted, description in test_cases:
            with self.subTest(service="cost_estimation", root=root, file=file):
                result = self._is_blacklisted_file_cost_estimation(root, file)
                self.assertEqual(result, should_be_blacklisted, 
                               f"[成本估算服务] {description} - 路径: {root}, 文件: {file}, 期望: {should_be_blacklisted}, 实际: {result}")

    def test_preprocessing_blacklist_logic(self):
        """测试预处理服务的黑名单逻辑"""
        # 测试用户提到的具体文件路径（使用非temp路径以避免temp目录模式的干扰）
        test_cases = [
            # (root, file, should_be_blacklisted, description)
            ("C:/projects/repo_analysis_github/houseSpider", "items.py", False, "非temp路径下的houseSpider/items.py不应该被跳过"),
            ("C:/projects/repo_analysis_github", "clear_redis_keys.py", False, "非temp路径下的clear_redis_keys.py不应该被跳过"),
            ("C:/projects/repo_analysis_github/.git", "config", True, ".git目录下的文件应该被跳过"),
            ("C:/projects/repo_analysis_github/venv/lib", "some_file.py", True, "venv目录下的文件应该被跳过"),
            ("C:/projects/repo_analysis_github/environment", "config.py", False, "非temp路径下的environment/config.py不应该被跳过"),
            ("C:/projects/repo_analysis_github/github_project", "main.py", False, "非temp路径下的github_project/main.py不应该被跳过"),
            ("C:/projects/repo_analysis_github/repo_analysis_github", "crawl_fang_city_code_mapping.py", False, "非temp路径下的py文件不应该被跳过"),
            ("C:/projects/repo_analysis_github/houseSpider/spiders", "house.py", False, "非temp路径下的house.py不应该被跳过"),
        ]
        
        for root, file, should_be_blacklisted, description in test_cases:
            with self.subTest(service="preprocessing", root=root, file=file):
                result = self._is_blacklisted_file_preprocessing(root, file)
                self.assertEqual(result, should_be_blacklisted, 
                               f"[预处理服务] {description} - 路径: {root}, 文件: {file}, 期望: {should_be_blacklisted}, 实际: {result}")

    def test_both_services_consistency_with_non_temp_paths(self):
        """测试两个服务在非temp路径下的逻辑一致性"""
        test_cases = [
            ("C:/projects/repo_analysis_github/houseSpider", "items.py"),
            ("C:/projects/repo_analysis_github", "clear_redis_keys.py"),
            ("C:/projects/repo_analysis_github/.git", "config"),
            ("C:/projects/repo_analysis_github/venv/lib", "some_file.py"),
            ("C:/projects/repo_analysis_github/environment", "config.py"),
        ]
        
        for root, file in test_cases:
            with self.subTest(root=root, file=file):
                result_cost = self._is_blacklisted_file_cost_estimation(root, file)
                result_preprocessing = self._is_blacklisted_file_preprocessing(root, file)
                # 两个服务应该对同一个文件有一致的判断（在非temp路径下）
                self.assertEqual(result_cost, result_preprocessing,
                               f"两个服务对路径 {root}/{file} 的判断不一致: 成本估算={result_cost}, 预处理={result_preprocessing}")


if __name__ == '__main__':
    unittest.main()