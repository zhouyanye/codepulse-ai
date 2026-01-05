"""
测试仓库缓存机制
"""
import asyncio
import os
from utils.git_utils import GitUtils
import pytest

@pytest.mark.asyncio
async def test_repo_cache():
    """测试仓库缓存功能"""
    print("=" * 60)
    print("测试仓库缓存机制")
    print("=" * 60)

    # 测试仓库URL
    repo_url = "https://gitee.com/zhou-yanye/houseSpider"

    # 第一次克隆 - 应该会克隆
    print("\n[测试1] 第一次克隆仓库...")
    git_utils1 = GitUtils()
    repo_path1 = await git_utils1.clone_repo(repo_url)
    print(f"第一次克隆路径: {repo_path1}")
    print(f"缓存大小: {len(GitUtils._repo_cache)}")
    print(f"缓存内容: {GitUtils._repo_cache}")

    if not repo_path1:
        print("❌ 第一次克隆失败")
        return

    # 检查文件是否存在
    if os.path.exists(repo_path1):
        print(f"✅ 仓库路径有效: {repo_path1}")
    else:
        print(f"❌ 仓库路径无效: {repo_path1}")
        return

    # 第二次克隆 - 应该使用缓存
    print("\n[测试2] 第二次克隆仓库（应该使用缓存）...")
    git_utils2 = GitUtils()
    repo_path2 = await git_utils2.clone_repo(repo_url)
    print(f"第二次克隆路径: {repo_path2}")
    print(f"缓存大小: {len(GitUtils._repo_cache)}")

    # 验证两次克隆的路径是否相同
    if repo_path1 == repo_path2:
        print("✅ 两次克隆路径相同，缓存机制工作正常！")
    else:
        print(f"❌ 两次克隆路径不同：")
        print(f"   第一次: {repo_path1}")
        print(f"   第二次: {repo_path2}")

    # 测试不同仓库
    print("\n[测试3] 克隆不同的仓库...")
    repo_url2 = "https://github.com/zhouyanye/houseSpider"
    repo_path3 = await git_utils2.clone_repo(repo_url2)
    print(f"不同仓库路径: {repo_path3}")
    print(f"缓存大小: {len(GitUtils._repo_cache)}")
    print(f"缓存内容: {GitUtils._repo_cache}")

    if repo_path3 != repo_path2:
        print("✅ 不同仓库路径不同，符合预期")
    else:
        print("❌ 不同仓库路径相同，有问题")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_repo_cache())
