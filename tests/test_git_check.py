#!/usr/bin/env python
"""
测试 Git 检测功能的脚本
"""
import subprocess
import sys
import os

# 将项目根目录添加到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_git_check():
    print("测试 Git 检测功能...")

    # 尝试导入 Git 相关模块，但不实际使用 Git 命令
    try:
        from utils.git_utils import GIT_AVAILABLE
        print(f"GitUtils 中的 GIT_AVAILABLE 状态: {GIT_AVAILABLE}")

        if GIT_AVAILABLE:
            print("GitPython 库可用")
        else:
            print("GitPython 库不可用或 Git 未安装")

        # 尝试创建 GitUtils 实例（这会检查 Git 是否可用）
        try:
            from utils.git_utils import GitUtils
            print("尝试创建 GitUtils 实例...")
            git_utils = GitUtils()  # 这会触发 Git 可用性检查
            print("GitUtils 实例创建成功")
        except RuntimeError as e:
            print(f"GitUtils 实例创建失败: {e}")

    except ImportError as e:
        print(f"导入 GitUtils 失败: {e}")

    # 测试 run.py 中的 Git 检查功能
    print("\n测试 run.py 中的 Git 检查功能...")
    try:
        from run import check_git_availability
        result = check_git_availability()
        if result:
            print("run.py 中的 Git 检查功能正常")
        else:
            print("run.py 中的 Git 检查功能显示 Git 不可用")
    except Exception as e:
        print(f"测试 run.py 中的 Git 检查功能失败: {e}")


def test_services_with_git():
    print("\n测试服务模块在 Git 可用时的行为...")
    try:
        from services.github_service import GitHubService
        from services.gitee_service import GiteeService
        from services.analysis_service import AnalysisService

        print("尝试创建 GitHubService 实例...")
        github_service = GitHubService()
        print("GitHubService 实例创建成功")

        print("尝试创建 GiteeService 实例...")
        gitee_service = GiteeService()
        print("GiteeService 实例创建成功")

        print("尝试创建 AnalysisService 实例...")
        analysis_service = AnalysisService()
        print("AnalysisService 实例创建成功")

    except RuntimeError as e:
        print(f"服务实例创建失败（预期在 Git 不可用时）: {e}")
    except Exception as e:
        print(f"服务实例创建时发生其他错误: {e}")


def test_api_endpoints_with_git():
    print("\n测试 API 端点模块...")
    try:
        from app.api.endpoints.analysis import analyze_repository
        print("API 端点模块导入成功")
    except Exception as e:
        print(f"API 端点模块导入失败: {e}")


if __name__ == "__main__":
    test_git_check()
    test_services_with_git()
    test_api_endpoints_with_git()
    print("\n所有测试完成！")
