"""
测试配置和 Git 集成的脚本
"""
import sys
import os

# 将项目根目录添加到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_config_integration():
    print("测试配置文件集成...")

    try:
        from app.core.config import settings
        print(f"配置文件加载成功")
        print(f"  Git 超时时间: {settings.GIT_TIMEOUT}")
        print(f"  Git 最大重试次数: {settings.GIT_MAX_RETRIES}")
        print(f"  Git 镜像列表: {settings.GIT_MIRRORS}")

        # 测试 GitUtils 是否能使用配置
        from utils.git_utils import GitUtils, GIT_AVAILABLE
        print(f"GitUtils 加载成功，GIT_AVAILABLE: {GIT_AVAILABLE}")

        if GIT_AVAILABLE:
            git_utils = GitUtils()
            print("GitUtils 实例创建成功，能够使用配置文件中的设置")
        else:
            print("Git 不可用，但配置加载正常")

    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_config_integration()
    print("\n配置集成测试完成！")
