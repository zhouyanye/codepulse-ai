#!/usr/bin/env python
"""
模拟 Git 不可用情况的测试脚本
"""
import sys
import os

# 将项目根目录添加到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_git_unavailable_simulation():
    print("模拟 Git 不可用情况的测试...")
    
    # 模拟 Git 不可用的情况 - 通过临时修改环境
    import utils.git_utils
    original_git_available = utils.git_utils.GIT_AVAILABLE
    
    try:
        # 临时设置 GIT_AVAILABLE 为 False 来模拟 Git 不可用
        utils.git_utils.GIT_AVAILABLE = False
        print(f"已将 GIT_AVAILABLE 设置为: {utils.git_utils.GIT_AVAILABLE}")
        
        # 尝试创建 GitUtils 实例，这应该抛出 RuntimeError
        try:
            git_utils_instance = utils.git_utils.GitUtils()
            print("意外：GitUtils 实例创建成功，应该抛出异常")
        except RuntimeError as e:
            print(f"预期：GitUtils 实例创建失败，抛出异常: {e}")
        
        # 测试 GitHubService 初始化
        try:
            from services.github_service import GitHubService
            github_service = GitHubService()
            print("意外：GitHubService 实例创建成功，应该抛出异常")
        except RuntimeError as e:
            print(f"预期：GitHubService 实例创建失败，抛出异常: {e}")
        
        # 测试 GiteeService 初始化
        try:
            from services.gitee_service import GiteeService
            gitee_service = GiteeService()
            print("意外：GiteeService 实例创建成功，应该抛出异常")
        except RuntimeError as e:
            print(f"预期：GiteeService 实例创建失败，抛出异常: {e}")
        
        # 测试 AnalysisService 初始化
        try:
            from services.analysis_service import AnalysisService
            analysis_service = AnalysisService()
            print("意外：AnalysisService 实例创建成功，应该抛出异常")
        except RuntimeError as e:
            print(f"预期：AnalysisService 实例创建失败，抛出异常: {e}")
            
    finally:
        # 恢复原始值
        utils.git_utils.GIT_AVAILABLE = original_git_available
        print(f"已恢复 GIT_AVAILABLE 为原始值: {original_git_available}")

if __name__ == "__main__":
    test_git_unavailable_simulation()
    print("\nGit 不可用模拟测试完成！")