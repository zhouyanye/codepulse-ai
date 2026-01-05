#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试修复后的Git克隆功能
"""
import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.git_utils import GitUtils


async def test_clone_fix():
    """测试修复后的克隆功能"""
    git_utils = GitUtils()
    
    # 多次尝试克隆同一个仓库，以测试目录清理逻辑
    for i in range(2):
        print(f"\n第 {i+1} 次尝试克隆: https://github.com/zhouyanye/house")
        try:
            result = await git_utils.clone_repo('https://github.com/zhouyanye/house')
            if result:
                print(f"✓ 克隆成功! 仓库位置: {result}")
                
                # 分析仓库结构
                structure = git_utils.analyze_repo_structure(result)
                print(f"  - 文件总数: {structure['total_files']}")
                print(f"  - 目录总数: {structure['total_dirs']}")
                print(f"  - 主要语言: {structure['main_language']}")
                print(f"  - 包含README: {structure['has_readme']}")
            else:
                print(f"✗ 克隆失败")
        except Exception as e:
            print(f"✗ 克隆异常: {e}")
    
    print("\n测试完成!")


if __name__ == "__main__":
    asyncio.run(test_clone_fix())