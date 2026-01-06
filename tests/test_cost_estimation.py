import os
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.cost_estimation_service import CostEstimationService


def test_extract_repo_name_from_url():
    """测试从URL提取仓库名称的各种情况"""
    service = CostEstimationService()
    
    test_cases = [
        # 标准GitHub URL
        ("https://github.com/owner/repo", "owner/repo"),
        ("https://www.github.com/owner/repo", "owner/repo"),
        ("http://github.com/owner/repo", "owner/repo"),
        ("git@github.com:owner/repo.git", "owner/repo"),
        
        # 标准Gitee URL
        ("https://gitee.com/owner/repo", "owner/repo"),
        ("https://www.gitee.com/owner/repo", "owner/repo"),
        ("http://gitee.com/owner/repo", "owner/repo"),
        ("git@gitee.com:owner/repo.git", "owner/repo"),
        
        # 带.git后缀
        ("https://github.com/owner/repo.git", "owner/repo"),
        ("https://gitee.com/owner/repo.git", "owner/repo"),
        
        # 带末尾斜杠
        ("https://github.com/owner/repo/", "owner/repo"),
        ("https://gitee.com/owner/repo/", "owner/repo"),
        
        # 带查询参数或片段标识符 - 这些现在应该能正确处理
        ("https://github.com/owner/repo?tab=readme-ov-file", "owner/repo"),
        ("https://github.com/owner/repo#readme", "owner/repo"),
        ("https://gitee.com/owner/repo?tab=readme", "owner/repo"),
        
        # 你提到的复杂情况 - 仓库名应该是前两个部分
        ("github.com/owen/repo/owen/repo", "owen/repo"),  # 实际上应该是 owen/repo
        ("https://github.com/owen/repo/extra/path", "owen/repo"),  # 仓库是 owen/repo，extra/path是仓库内路径
        ("https://github.com/owner/repo/subdir/file", "owner/repo"),  # 仓库是 owner/repo，subdir/file是仓库内路径
        
        # 简单的owner/repo格式
        ("owner/repo", "owner/repo"),
        
        # 边界情况
        ("https://github.com/owner", "owner"),  # 只有一个部分
        ("single", "single"),  # 单个部分
    ]
    
    print("开始测试 _extract_repo_name_from_url 方法...")
    print("=" * 80)
    
    for url, expected in test_cases:
        result = service._extract_repo_name_from_url(url)
        status = "✓" if result == expected else "✗"
        print(f"{status} URL: {url}")
        print(f"    Expected: {expected}")
        print(f"    Got:      {result}")
        print()
        
        if result != expected:
            print(f"  失败: URL: {url}, Expected: {expected}, Got: {result}")
            print()


if __name__ == "__main__":
    test_extract_repo_name_from_url()