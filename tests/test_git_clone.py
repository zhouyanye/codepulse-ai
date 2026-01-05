#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试改进后的Git克隆功能
"""
import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.git_utils import GitUtils


async def test_clone_strategies():
    """测试不同的克隆策略"""
    git_utils = GitUtils()
    
    # 测试仓库URL
    test_repos = [
        "https://github.com/zhouyanye/house",  
        "zhouyanye/house",  # 简写形式
    ]
    
    for repo_url in test_repos:
        print(f"\n开始测试克隆: {repo_url}")
        try:
            result = await git_utils.clone_repo(repo_url)
            if result:
                print(f"✓ 克隆成功! 仓库位置: {result}")
                
                # 分析仓库结构
                structure = git_utils.analyze_repo_structure(result)
                print(f"  - 文件总数: {structure['total_files']}")
                print(f"  - 目录总数: {structure['total_dirs']}")
                print(f"  - 主要语言: {structure['main_language']}")
                print(f"  - 包含README: {structure['has_readme']}")
            else:
                print(f"克隆失败: {repo_url}")
        except Exception as e:
            print(f"克隆异常: {repo_url}, 错误: {e}")
    
    print("\n测试完成!")
    
    # 等待一段时间以确保所有异步任务完成
    await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(test_clone_strategies())