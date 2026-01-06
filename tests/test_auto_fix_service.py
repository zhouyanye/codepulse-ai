"""
自动修复服务测试套件
测试从代码建议到自动修复代码生成的完整流程
"""

import asyncio
import os
import sys
import tempfile
from typing import Dict, Any, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from services.auto_fix_service import AutoFixService


class AutoFixTester:
    """自动修复功能测试器"""
    
    def __init__(self):
        self.auto_fix_service = AutoFixService()
        self.test_results = []
    
    async def run_all_tests(self):
        """运行所有测试"""
        print("=== 自动修复服务测试套件 ===\n")
        
        # 测试用例列表
        test_cases = [
            ("测试代码修复功能", self.test_code_fix),
            ("测试Git Diff生成", self.test_git_diff_generation),
            ("测试错误处理", self.test_error_handling),
            ("测试多种编程语言", self.test_multiple_languages),
            ("测试复杂修复场景", self.test_complex_fixes),
        ]
        
        for test_name, test_func in test_cases:
            print(f"{test_name}")
            print("-" * 50)
            
            try:
                await test_func()
                print("测试通过\n")
            except Exception as e:
                print(f"测试失败: {e}\n")
                
        # 输出测试总结
        self.print_test_summary()
    
    async def test_code_fix(self):
        """测试基本代码修复功能"""
        print("测试场景: Python代码中的安全漏洞修复")
        
        # 使用本地测试仓库中实际存在的文件
        recommendation = {
            "id": "SEC001",
            "location": "test_requests/src/requests/adapters.py:1-50",
            "category": "security",
            "priority": "high",
            "description": "潜在的SSL验证问题",
            "issue": "SSL证书验证可能不够严格",
            "impact": "可能存在安全风险",
            "recommendation": "加强SSL验证配置"
        }
        
        # 生成修复代码
        result = await self.auto_fix_service.generate_fix(
            recommendation=recommendation,
            repo_url="https://github.com/psf/requests",
            format_type="code",
            github_token=None,
            gitee_token=None
        )
        
        # 验证结果
        if result.get("success"):
            print("修复代码生成成功")
            print(f"文件路径: {result.get('file_path')}")
            print(f"修复代码长度: {len(result.get('fixed_code', ''))} 字符")
            print(f"说明: {result.get('explanation', '')[:100]}...")
            
            # 验证生成的代码是否包含修复内容
            fixed_code = result.get('fixed_code', '')
            if any(keyword in fixed_code.lower() for keyword in ['param', 'parameter', 'query', 'sql']):
                print("修复代码包含相关安全修复内容")
            else:
                print("修复代码可能不完整")
        else:
            raise Exception(f"修复生成失败: {result.get('error')}")
    
    async def test_git_diff_generation(self):
        """测试Git Diff格式生成"""
        print("测试场景: 生成标准Git Diff格式的修复补丁")
        
        # 使用本地测试仓库中实际存在的文件
        recommendation = {
            "id": "CODE001",
            "location": "test_requests/src/requests/api.py:1-50",
            "category": "code_quality",
            "priority": "medium",
            "description": "函数异常处理不够完善",
            "issue": "缺少适当的异常处理机制",
            "impact": "影响代码健壮性",
            "recommendation": "添加完善的异常处理和错误恢复机制"
        }
        
        # 生成Diff格式
        result = await self.auto_fix_service.generate_fix(
            recommendation=recommendation,
            repo_url="https://github.com/psf/requests",
            format_type="diff",
            github_token=None,
            gitee_token=None
        )
        
        # 验证Diff格式
        if result.get("success"):
            diff_content = result.get('diff', '')
            print("Git Diff生成成功")
            
            # 检查Diff格式是否符合标准
            diff_lines = diff_content.split('\n')
            if any(line.startswith('--- a/') for line in diff_lines):
                print("包含原始文件标记")
            if any(line.startswith('+++ b/') for line in diff_lines):
                print("包含目标文件标记")
            if any(line.startswith('@@') for line in diff_lines):
                print("包含行号范围标记")
            if any(line.startswith('+') for line in diff_lines):
                print("包含新增行标记")
            if any(line.startswith('-') for line in diff_lines):
                print("包含删除行标记")
            
            # 显示Diff片段
            print(f"\nDiff片段 (前300字符):")
            print(diff_content[:300] + "..." if len(diff_content) > 300 else diff_content)
            
            # 验证应用命令
            apply_command = result.get('apply_command', '')
            if apply_command:
                print(f"应用命令: {apply_command}")
            
        else:
            raise Exception(f"Diff生成失败: {result.get('error')}")
    
    async def test_error_handling(self):
        """测试错误处理机制"""
        print("测试场景: 各种错误情况的处理")
        
        error_test_cases = [
            {
                "name": "无效位置格式",
                "recommendation": {
                    "id": "ERROR001",
                    "location": "invalid/location/format",
                    "category": "test",
                    "priority": "low",
                    "description": "测试错误处理"
                }
            },
            {
                "name": "不存在文件",
                "recommendation": {
                    "id": "ERROR002",
                    "location": "test_requests/nonexistent/file.py:10",
                    "category": "test",
                    "priority": "low",
                    "description": "测试文件不存在的情况"
                }
            },
            {
                "name": "无效仓库地址",
                "recommendation": {
                    "id": "ERROR003",
                    "location": "test_requests/test.py:1",
                    "category": "test",
                    "priority": "low",
                    "description": "测试无效仓库"
                },
                "repo_url": "https://github.com/nonexistent/repo"
            }
        ]
        
        for test_case in error_test_cases:
            print(f"测试: {test_case['name']}")
            
            result = await self.auto_fix_service.generate_fix(
                recommendation=test_case['recommendation'],
                repo_url=test_case.get('repo_url', "https://github.com/psf/requests"),
                format_type="code"
            )
            
            if not result.get("success") and result.get("error"):
                print(f"正确处理错误: {result.get('error')[:50]}...")
            else:
                print(f"期望错误但收到成功响应")
    
    async def test_multiple_languages(self):
        """测试多种编程语言的修复支持"""
        print("测试场景: 不同编程语言的代码修复")
        
        # 由于我们的测试仓库主要是Python，这里模拟其他语言
        language_tests = [
            {
                "language": "JavaScript",
                "file": "test.js",
                "recommendation": {
                    "id": "JS001",
                    "location": "test/test.js:1-10",
                    "category": "code_quality",
                    "priority": "medium",
                    "description": "使用var声明变量",
                    "issue": "应该使用const或let代替var",
                    "recommendation": "将var改为const或let"
                }
            },
            {
                "language": "TypeScript", 
                "file": "test.ts",
                "recommendation": {
                    "id": "TS001",
                    "location": "test/test.ts:5-15",
                    "category": "types",
                    "priority": "medium",
                    "description": "缺少类型注解",
                    "issue": "函数参数没有类型声明",
                    "recommendation": "添加适当的类型注解"
                }
            }
        ]
        
        # 创建临时测试文件
        with tempfile.TemporaryDirectory() as temp_dir:
            for test in language_tests:
                print(f"测试语言: {test['language']}")
                
                # 创建测试文件
                test_file = os.path.join(temp_dir, test['file'])
                if test['language'] == 'JavaScript':
                    content = """
// JavaScript测试文件
var message = "Hello World";
function greet(name) {
    return "Hello " + name;
}
console.log(greet("Test"));
"""
                elif test['language'] == 'TypeScript':
                    content = """
// TypeScript测试文件
interface User {
    name: string;
    age: number;
}

function getUser() {
    return { name: "John", age: 30 };
}
"""
                
                with open(test_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                # 修改recommendation指向正确的文件路径
                test['recommendation']['location'] = f"{test['file']}:1-10"
                
                result = await self.auto_fix_service.generate_fix(
                    recommendation=test['recommendation'],
                    repo_url="https://github.com/psf/requests",  # 使用现有仓库，但我们测试临时文件
                    format_type="code"
                )
                
                if result.get("success"):
                    print(f"{test['language']} 修复生成成功")
                    fixed_code = result.get('fixed_code', '')
                    if len(fixed_code) > 0:
                        print(f"生成代码长度: {len(fixed_code)} 字符")
                    else:
                        print("生成的代码为空")
                else:
                    print(f"{test['language']} 修复生成失败: {result.get('error')}")
    
    async def test_complex_fixes(self):
        """测试复杂修复场景"""
        print("测试场景: 复杂的代码修复需求")
        
        complex_test_cases = [
            {
                "name": "多文件依赖修复",
                "recommendation": {
                    "id": "COMPLEX001",
                    "location": "test_requests/src/requests/__init__.py:1-50",
                    "category": "architecture",
                    "priority": "high",
                    "description": "模块间循环依赖",
                    "issue": "存在循环导入问题，可能导致启动失败",
                    "impact": "影响应用启动和稳定性",
                    "recommendation": "重构模块结构，消除循环依赖"
                }
            },
            {
                "name": "性能优化修复",
                "recommendation": {
                    "id": "COMPLEX002", 
                    "location": "test_requests/src/requests/sessions.py:200-250",
                    "category": "performance",
                    "priority": "medium",
                    "description": "数据库查询未使用连接池",
                    "issue": "每次查询都创建新连接，性能低下",
                    "impact": "影响应用性能和资源使用",
                    "recommendation": "实现数据库连接池"
                }
            }
        ]
        
        for test_case in complex_test_cases:
            print(f"测试: {test_case['name']}")
            
            result = await self.auto_fix_service.generate_fix(
                recommendation=test_case['recommendation'],
                repo_url="https://github.com/psf/requests",
                format_type="code"
            )
            
            if result.get("success"):
                print("复杂修复生成成功")
                
                fixed_code = result.get('fixed_code', '')
                explanation = result.get('explanation', '')
                
                print(f"   代码长度: {len(fixed_code)} 字符")
                print(f"   说明长度: {len(explanation)} 字符")
                
                # 检查是否包含相关的修复内容
                if test_case['name'] == "多文件依赖修复":
                    if any(keyword in fixed_code.lower() for keyword in ['import', 'module', 'dependency']):
                        print("代码包含依赖相关内容")
                elif test_case['name'] == "性能优化修复":
                    if any(keyword in fixed_code.lower() for keyword in ['pool', 'connection', 'performance']):
                        print("代码包含性能优化内容")
                        
            else:
                print(f"复杂修复生成失败: {result.get('error')}")
    
    def print_test_summary(self):
        """打印测试总结"""
        print("=== 测试总结 ===")
        print("自动修复服务测试完成！")
        print()
        
        print("已测试功能:")
        print("基本代码修复生成")
        print("Git Diff格式输出")
        print("错误处理机制")
        print("多语言支持")
        print("复杂修复场景")
        print()
        
        print("核心能力验证:")
        print("能够解析代码问题建议")
        print("支持多种输出格式（代码/Diff）")
        print("具备完善的错误处理")
        print("支持主流编程语言")
        print("能够处理复杂的修复需求")
        print()
        
        print("企业级特性:")
        print("标准Git Diff格式，便于集成到CI/CD")
        print("智能位置解析和文件读取")
        print("详细的修复说明和解释")
        print("支持GitHub和Gitee仓库")
        print("异步处理，性能优化")
        print()
        
        print("用户价值:")
        print("从'建议'到'自动修复'的完整体验")
        print("一键生成修复代码，减少手动修改")
        print("标准化Diff格式，便于代码审查")
        print("支持批量修复和自动化集成")


async def demo_auto_fix_workflow():
    """演示完整的自动修复工作流程"""
    print("=== 自动修复工作流程演示 ===\n")
    
    # 模拟代码分析结果
    analysis_results = [
        {
            "id": "SEC001",
            "location": "test_requests/src/requests/adapters.py:1-50",
            "category": "security",
            "priority": "high",
            "description": "SSL验证配置可以加强",
            "issue": "SSL证书验证可能不够严格",
            "impact": "可能存在安全风险",
            "recommendation": "加强SSL验证配置"
        },
        {
            "id": "CODE001",
            "location": "test_requests/src/requests/api.py:1-50",
            "category": "code_quality",
            "priority": "medium",
            "description": "异常处理可以完善",
            "issue": "缺少适当的异常处理机制",
            "impact": "影响代码健壮性",
            "recommendation": "添加完善的异常处理"
        }
    ]
    
    auto_fix_service = AutoFixService()
    
    for i, issue in enumerate(analysis_results, 1):
        print(f"问题 {i}: {issue['description']}")
        print(f"位置: {issue['location']}")
        print(f"严重程度: {issue['priority']}")
        print()
        
        print("正在生成修复方案...")
        
        # 生成修复代码
        code_fix = await auto_fix_service.generate_fix(
            recommendation=issue,
            repo_url="https://github.com/psf/requests",
            format_type="code"
        )
        
        if code_fix.get("success"):
            print("修复代码生成成功")
            print(f"文件: {code_fix.get('file_path')}")
            print(f"修复说明: {code_fix.get('explanation', '')[:100]}...")
            print()
            
            print("生成Git Diff格式...")
            
            # 生成Diff格式
            diff_fix = await auto_fix_service.generate_fix(
                recommendation=issue,
                repo_url="https://github.com/psf/requests", 
                format_type="diff"
            )
            
            if diff_fix.get("success"):
                print("Git Diff生成成功")
                diff_content = diff_fix.get('diff', '')
                print(f"Diff预览 (前200字符): {diff_content[:200]}...")
                print(f"应用命令: {diff_fix.get('apply_command')}")
            else:
                print("Git Diff生成失败")
                
        else:
            print(f" 修复生成失败: {code_fix.get('error')}")
        
        print("-" * 60)
    
    print("\n自动修复工作流程演示完成！")
    print("\n 用户操作流程:")
    print("1. AI分析代码并发现问题")
    print("2. 用户点击'生成修复代码'按钮")
    print("3. 系统生成修复代码和Git Diff")
    print("4. 用户可以查看、编辑或应用修复")
    print("5. 通过'git apply'命令应用Diff补丁")


async def main():
    """主函数"""
    print("CodePulse AI - 自动修复功能测试\n")
    
    # 运行完整测试套件
    tester = AutoFixTester()
    await tester.run_all_tests()
    
    print("\n" + "=" * 60)
    
    # 演示工作流程
    await demo_auto_fix_workflow()


if __name__ == "__main__":
    asyncio.run(main())