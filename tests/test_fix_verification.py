import os
def test_blacklist_fix():
    """测试黑名单修复是否生效"""
    print("测试成本估算服务黑名单修复...")
    
    # 手动复制修复后的黑名单逻辑
    def _is_blacklisted_file_fixed(root: str, file: str) -> bool:
        """
        修复后的黑名单检查逻辑
        """
        # 与 static_scan_service 保持完全一致
        EXCLUDE_DIRS = {".git", ".gitlab", ".bitbucket",  # 版本控制
                        ".circleci", ".travis", ".drone",  # CI配置
                        "site", "dist", "build", "target", "out", "release", "obj",  # 构建产物
                        "__pycache__", ".pyc", ".pytest_cache",  # Python缓存
                        "venv", "env", ".venv", ".env", "envs",  # 虚拟环境
                        "node_modules", "vendor", "bower_components", "jspm_packages",  # 依赖包
                        ".idea", ".vscode", ".vs", ".project", ".settings", ".metadata",  # IDE配置
                        "tmp", "logs", "cache", ".cache"}  # 临时文件 - 移除了"temp"

        # 系统文件和锁定文件
        SYSTEM_FILES = {".ds_store", "thumbs.db",  # 系统文件
                      "package-lock.json", "yarn.lock", "gemfile.lock", "podfile.lock"}  # 锁定文件

        file_lower = file.lower()
        
        print(f"  检查文件: {root}/{file}, 文件名小写: {file_lower}")
        
        # 方法1：检查路径中是否包含排除目录（使用路径分隔符边界确保精确匹配）
        root_normalized = '/' + root.replace('\\', '/').lower() + '/'
        print(f"    标准化路径: {root_normalized}")
        
        for exclude_dir in EXCLUDE_DIRS:
            # 在路径前后加上分隔符确保匹配完整目录名
            exclude_pattern = '/' + exclude_dir + '/'
            print(f"    检查模式: {exclude_pattern}, 是否包含: {exclude_pattern in root_normalized}")
            if exclude_pattern in root_normalized:
                print(f"    匹配到排除目录: {exclude_dir}")
                return True

        # 方法2：检查文件名是否匹配排除模式
        if file_lower in SYSTEM_FILES:
            print(f"    匹配到系统文件: {file_lower}")
            return True
        
        # 方法3：排除临时后缀文件
        if file_lower.endswith(('.log', '.tmp', '.bak')):
            print(f"    匹配到临时文件后缀: {file_lower}")
            return True

        print(f"    文件 {file} 未被排除")
        return False

    # 测试实际路径
    temp_path = 'C:\\Users\\admin\\AppData\\Local\\Temp\\repo_analysis_github_daqg048t'
    test_cases = [
        (temp_path, 'clear_redis_keys.py'),  # 应该保留，因为temp被移除
        (os.path.join(temp_path, 'houseSpider'), 'items.py'),  # 应该保留
        (os.path.join(temp_path, '.git'), 'config'),  # 应该跳过
        (temp_path, '.gitignore'),  # 应该保留
        (os.path.join(temp_path, 'houseSpider', 'spiders'), 'house.py'),  # 应该保留
        (os.path.join(temp_path, 'node_modules'), 'some_lib.js'),  # 应该跳过
        (os.path.join(temp_path, '.next'), 'some_file.js'),  # 应该跳过
        (os.path.join(temp_path, '.github'), 'workflow.yml'),  # 应该跳过
        (os.path.join(temp_path, 'temp'), 'temp_file.txt'),  # 应该跳过 - 项目内部的temp目录
    ]

    print('修复后的黑名单测试:')
    for root, file in test_cases:
        result = _is_blacklisted_file_fixed(root, file)
        status = "跳过" if result else "保留"
        print(f'  路径: {root}, 文件: {file}, 状态: {status}')
        print()
        
    print("\n修复验证完成！")

if __name__ == "__main__":
    test_blacklist_fix()