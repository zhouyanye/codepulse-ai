#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简单测试改进后的Git克隆功能
"""
import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.git_utils import GitUtils


async def test():
    git_utils = GitUtils()
    result = await git_utils.clone_repo('https://github.com/zhouyanye/house')
    print('Success!' if result else 'Failed')
    if result:
        print(f"Repository cloned to: {result}")


if __name__ == "__main__":
    asyncio.run(test())