"""
CodePulse AI CLI 工具
====================

功能:
- 单仓库分析: python cli.py analyze https://github.com/user/repo
- 批量分析: python cli.py batch repos.txt
- 生成报告: python cli.py report https://github.com/user/repo [--format json|md]
- Token预估: python cli.py estimate https://github.com/user/repo
- 私有仓库分析: python cli.py analyze https://github.com/user/repo --github_token xxx

使用示例:
- 分析单个仓库: cli.py analyze https://github.com/user/repo --provider deepseek
- 批量分析: cli.py batch repos.txt --format md --output ./reports/
- 生成JSON报告: cli.py report https://github.com/user/repo --format json
- 预估Token消耗: cli.py estimate https://github.com/user/repo --provider deepseek

选项:
--provider: deepseek (默认), kimi,doubao, openai
--format: json, md
--output: 输出目录
"""

import argparse
import asyncio
import sys
import os
import logging
from pathlib import Path
import traceback
import json
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings
from services.analysis_service import AnalysisService
from services.cost_estimation_service import CostEstimationService
from models.request_models import AnalysisRequest
from utils.ai_provider_utils import get_available_provider

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


async def analyze_single_repo(url: str, provider: str = "deepseek",
                              github_token: str = None, gitee_token: str = None,
                              output_format: str = None, output_path: str = None,
                              skip_cost_estimate: bool = False):
    """分析单个仓库"""
    try:
        # 成本估算
        if not skip_cost_estimate:
            print(f"\n正在估算分析成本...")
            cost_service = CostEstimationService()
            estimate_result = await cost_service.estimate_repository_cost(
                repo_url=url,
                include_static_scan=True,
                ai_provider=provider,
                github_token=github_token if github_token else None,
                gitee_token=gitee_token if gitee_token else None
            )
            
            if estimate_result.get("success"):
                print(f"\n成本估算完成:")
                print(f"  预估Token: {estimate_result.get('estimated_tokens', 0):,}")
                print(f"  预估成本: ¥{estimate_result.get('estimated_cost_rmb', 0):.4f}")
                print(f"  预估时间: {estimate_result.get('estimated_analysis_time', '未知')}")
                print(f"  仓库大小: {estimate_result.get('repository_size_mb', 0):.2f} MB")
            else:
                print(f"\n成本估算失败: {estimate_result.get('error', '未知错误')}")
        
        service = AnalysisService()
        request = AnalysisRequest(
            repo_url=url,
            github_token=github_token if github_token is not None else settings.GITHUB_TOKEN,
            gitee_token=gitee_token if gitee_token is not None else settings.GITEE_TOKEN,
            ai_provider=provider,
            include_static_scan=True,
            include_code_analysis=True,
            include_community_analysis=True
        )

        logger.info(f"开始分析仓库: {url}")
        result = await service.analyze_repository(request)

        # 显示简要结果
        print(f"\n仓库分析完成: {url}")
        print(f"总体评分: {result.overall_score}/100")
        print(f"代码质量: {result.code_quality.score}/100")
        print(f"社区健康: {result.community_health.score}/100")
        print(f"文档完整: {result.documentation.score}/100")
        print(f"维护状况: {result.maintenance.score}/100")
        print(f"安全评分: {result.code_quality.security_score}/100")

        # 如果指定了输出格式，生成报告
        if output_format:
            # 将AnalysisResult转换为字典
            result_dict = result.model_dump(mode='json')

            # 确定输出路径
            if not output_path:
                # 生成默认文件名
                safe_url = url.replace('https://', '').replace('/', '_').replace('.', '_')
                output_path = f"./{safe_url}.{output_format}"

            # 确保输出目录存在
            from pathlib import Path
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            if output_format.lower() == 'json':
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(result_dict, f, ensure_ascii=False, indent=2, cls=DateTimeEncoder)
                logger.info(f"JSON报告已保存至: {output_path}")
            elif output_format.lower() == 'md':
                generate_markdown_report(result_dict, output_path)
                logger.info(f"Markdown报告已保存至: {output_path}")
            else:
                logger.warning(f"不支持的输出格式: {output_format}")

        return result
    except Exception as e:
        logger.error(f"分析仓库时出错: {e}")
        logger.debug(traceback.format_exc())
        return None


async def batch_analyze(repos_file: str, provider: str = "deepseek",
                        output_format: str = "json", output_dir: str = "./reports/",
                        github_token: str = None, gitee_token: str = None):
    """批量分析仓库"""
    try:
        # 读取仓库列表
        with open(repos_file, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]

        logger.info(f"准备批量分析 {len(urls)} 个仓库")

        # 创建输出目录
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # 逐个分析
        results = []
        for i, url in enumerate(urls, 1):
            logger.info(f"正在分析第 {i}/{len(urls)} 个仓库: {url}")
            result = await analyze_single_repo(url, provider, github_token, gitee_token)
            if result:
                results.append((url, result))

                # 生成报告
                filename = url.replace('https://', '').replace('/', '_').replace('.', '_')
                # 将AnalysisResult转换为字典
                result_dict = result.model_dump(mode='json')
                if output_format.lower() == 'json':
                    report_path = os.path.join(output_dir, f"{filename}.json")
                    with open(report_path, 'w', encoding='utf-8') as f:
                        json.dump(result_dict, f, ensure_ascii=False, indent=2, cls=DateTimeEncoder)
                else:  # md
                    report_path = os.path.join(output_dir, f"{filename}.md")
                    generate_markdown_report(result_dict, report_path)

                logger.info(f"报告已保存至: {report_path}")

        logger.info(f"批量分析完成，共处理 {len(results)} 个仓库")
        return results
    except FileNotFoundError:
        logger.error(f"仓库列表文件未找到: {repos_file}")
        return []
    except Exception as e:
        logger.error(f"批量分析时出错: {e}")
        logger.debug(traceback.format_exc())
        return []


def generate_markdown_report(result: dict, output_path: str):
    """生成Markdown格式报告"""
    try:
        # 确保输出目录存在
        from pathlib import Path
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"# 仓库分析报告\n\n")
            f.write(f"**分析时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**仓库地址**: {result.get('repo_info', {}).get('html_url', 'N/A')}\n\n")

            f.write(f"## 总体评分: {result['overall_score']}/100\n\n")

            f.write(f"### 各项评分\n\n")
            f.write(f"- 代码质量: {result['code_quality']['score']}/100\n")
            f.write(f"- 社区健康: {result['community_health']['score']}/100\n")
            f.write(f"- 文档完整: {result['documentation']['score']}/100\n")
            f.write(f"- 维护状况: {result['maintenance']['score']}/100\n")
            f.write(f"- 安全风险: {result['code_quality']['security_score']}/100\n\n")

            f.write(f"### 主要建议\n\n")
            for rec in result.get('recommendations', []):
                f.write(f"- **{rec.get('title', '无标题')}**\n")
                f.write(f"  严重程度: {rec.get('severity', '未知')}\n")
                f.write(f"  描述: {rec.get('description', '无描述')}\n\n")

        logger.info(f"Markdown报告已生成: {output_path}")
    except Exception as e:
        logger.error(f"生成Markdown报告时出错: {e}")
        logger.debug(traceback.format_exc())


async def generate_report(url: str, provider: str = "deepseek",
                          output_format: str = "json", output_path: str = None,
                          github_token: str = None, gitee_token: str = None):
    """生成仓库分析报告"""
    try:
        # 分析仓库
        result = await analyze_single_repo(url, provider, github_token, gitee_token)
        if not result:
            return False

        # 生成报告
        if not output_path:
            filename = url.replace('https://', '').replace('/', '_').replace('.', '_')
            if output_format.lower() == 'json':
                output_path = f"{filename}.json"
            else:
                output_path = f"{filename}.md"

        # 确保输出目录存在
        from pathlib import Path
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # 将AnalysisResult转换为字典（使用JSON兼容模式）
        result_dict = result.model_dump(mode='json')

        if output_format.lower() == 'json':
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result_dict, f, ensure_ascii=False, indent=2, cls=DateTimeEncoder)
        else:  # md
            generate_markdown_report(result_dict, output_path)

        logger.info(f"报告已生成: {output_path}")
        return True
    except Exception as e:
        logger.error(f"生成报告时出错: {e}")
        logger.debug(traceback.format_exc())
        return False


async def estimate_tokens_async(url: str, provider: str = "deepseek", github_token: str = None, gitee_token: str = None):
    """异步预估分析仓库所需的Token数量和成本"""
    cost_service = None
    try:
        print(f"正在预估分析仓库 {url} 的成本...")

        # 获取实际可用的AI提供商
        actual_provider = get_available_provider(provider)
        if actual_provider != provider:
            print(f"注意: AI提供商 {provider} 不可用，自动切换为 {actual_provider}")
        print(f"AI提供商: {actual_provider}")

        print("\n" + "=" * 60)
        print("成本预估详情")
        print("=" * 60)

        # 调用成本估算服务
        cost_service = CostEstimationService()
        estimate_result = await cost_service.estimate_repository_cost(
            repo_url=url,
            include_static_scan=True,
            ai_provider=actual_provider,
            github_token=github_token if github_token else None,
            gitee_token=gitee_token if gitee_token else None
        )

        if not estimate_result.get("success"):
            print(f"\n错误: {estimate_result.get('error', '成本估算失败')}")
            return

        # 显示估算结果
        print(f"\n仓库信息:")
        print(f"  名称: {estimate_result.get('repository_name', 'N/A')}")
        print(f"  地址: {url}")
        print(f"  大小: {estimate_result.get('repository_size_mb', 0):.2f} MB")
        print(f"  AI提供商: {actual_provider}")

        # 文件统计
        file_stats = estimate_result.get("file_statistics", {})
        print(f"\n文件统计:")
        print(f"  总文件数: {file_stats.get('total_files', 0)}")
        print(f"  代码行数: {estimate_result.get('total_lines', 0):,}")
        print(f"  跳过文件: {estimate_result.get('skipped_files_count', 0)}")

        if estimate_result.get('filtered_files_details'):
            filtered = estimate_result['filtered_files_details']
            print(f"    - 大文件 (>10MB): {len(filtered.get('large_files', []))}")
            print(f"    - 二进制文件: {len(filtered.get('binary_files', []))}")

        # Token和成本估算
        token_data = estimate_result.get("token_estimate", {})
        estimated_tokens = token_data.get("total_estimated_tokens", 0)
        cost_data = token_data.get("estimated_cost", {})
        estimated_time = estimate_result.get("estimated_analysis_time", "未知")

        print(f"\n成本预估:")
        print(f"  预估Token: {estimated_tokens:,}")
        print(f"  预估成本: ¥{cost_data.get('cost_rmb', 0):.4f} (${cost_data.get('cost_usd', 0):.4f})")
        print(f"  预估时间: {estimated_time}")

        # 成本警告
        estimated_cost_rmb = cost_data.get('cost_rmb', 0)
        if estimated_cost_rmb > 1.0:
            print(f"  警告: 预估成本较高 (¥{estimated_cost_rmb:.2f})")
        elif estimated_cost_rmb > 0.1:
            print(f"  提示: 预估成本适中 (¥{estimated_cost_rmb:.2f})")
        else:
            print(f"  提示: 预估成本较低 (¥{estimated_cost_rmb:.2f})")

        # 友好提示
        print(f"\n" + "=" * 60)
        print("提示:")
        print("- 预计时间根据项目大小估算，实际可能因网络速度、AI服务响应而有所不同")
        print("- 实际消耗可能因仓库内容复杂度而有所不同")
        print("- CoStrict模式不使用AI API，成本为0，仅做基础评分")
        print("- 建议在.env文件中配置各AI服务商的API密钥以启用实际分析")
        print("=" * 60)

    except Exception as e:
        logger.error(f"成本预估时出错: {e}")
        logger.debug(traceback.format_exc())
    finally:
        # 确保异步资源被正确关闭
        if cost_service:
            try:
                await cost_service.close()
            except Exception as e:
                logger.debug(f"关闭成本估算服务时出错: {e}")


def estimate_tokens(url: str, provider: str = "deepseek", github_token: str = None, gitee_token: str = None):
    """预估分析仓库所需的Token数量和成本"""
    try:
        # 使用新的异步实现，确保事件循环正确管理
        asyncio.run(estimate_tokens_async(url, provider, github_token, gitee_token))
    except Exception as e:
        logger.error(f"成本预估时出错: {e}")
        logger.debug(traceback.format_exc())


def main():
    parser = argparse.ArgumentParser(
        description="CodePulse AI - 开源项目健康扫描器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    # analyze 命令
    analyze_parser = subparsers.add_parser('analyze', help='分析单个仓库')
    analyze_parser.add_argument('url', help='仓库URL', type=str)
    analyze_parser.add_argument('--provider', choices=['deepseek', 'kimi','Doubao', 'openai'],
                                default='deepseek', help='AI提供商 (默认: deepseek)')
    analyze_parser.add_argument('--github-token', help='GitHub Token（可选，覆盖环境变量）')
    analyze_parser.add_argument('--gitee-token', help='Gitee Token（可选，覆盖环境变量）')
    analyze_parser.add_argument('--format', choices=['json', 'md'],
                                help='报告格式（可选，指定则生成对应格式报告）')
    analyze_parser.add_argument('--output', help='输出文件路径（可选，配合--format使用）')

    # batch 命令
    batch_parser = subparsers.add_parser('batch', help='批量分析仓库')
    batch_parser.add_argument('file', help='包含仓库URL列表的文件')
    batch_parser.add_argument('--provider', choices=['deepseek', 'kimi', 'openai'],
                              default='deepseek', help='AI提供商 (默认: deepseek)')
    batch_parser.add_argument('--format', choices=['json', 'md'],
                              default='json', help='报告格式 (默认: json)')
    batch_parser.add_argument('--output', default='./reports/',
                              help='输出目录 (默认: ./reports/)')
    batch_parser.add_argument('--github-token', help='GitHub Token（可选，覆盖环境变量）')
    batch_parser.add_argument('--gitee-token', help='Gitee Token（可选，覆盖环境变量）')

    # report 命令
    report_parser = subparsers.add_parser('report', help='生成仓库分析报告')
    report_parser.add_argument('url', help='仓库URL')
    report_parser.add_argument('--provider', choices=['deepseek', 'kimi','Doubao', 'openai'],
                               default='deepseek', help='AI提供商 (默认: deepseek)')
    report_parser.add_argument('--format', choices=['json', 'md'],
                               default='json', help='报告格式 (默认: json)')
    report_parser.add_argument('--output', help='输出文件路径')
    report_parser.add_argument('--github-token', help='GitHub Token（可选，覆盖环境变量）')
    report_parser.add_argument('--gitee-token', help='Gitee Token（可选，覆盖环境变量）')

    # estimate 命令
    estimate_parser = subparsers.add_parser('estimate', help='预估分析仓库的成本和时间')
    estimate_parser.add_argument('url',
                                 help='仓库URL,例如https://github.com/zhouyanye/codepulse-ai/')
    estimate_parser.add_argument('--provider', choices=['deepseek', 'kimi', 'Doubao', 'openai', 'costrict'],
                                 default='deepseek', help='AI提供商 (默认: deepseek)')
    estimate_parser.add_argument('--github-token', help='GitHub Token（可选，覆盖环境变量）')
    estimate_parser.add_argument('--gitee-token', help='Gitee Token（可选，覆盖环境变量）')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        if args.command == 'analyze':
            asyncio.run(analyze_single_repo(args.url, args.provider,
                                            github_token=args.github_token,
                                            gitee_token=args.gitee_token,
                                            output_format=args.format,
                                            output_path=args.output,
                                            skip_cost_estimate=False))
        elif args.command == 'batch':
            asyncio.run(batch_analyze(args.file, args.provider, args.format, args.output,
                                      github_token=args.github_token,
                                      gitee_token=args.gitee_token))
        elif args.command == 'report':
            asyncio.run(generate_report(args.url, args.provider, args.format, args.output,
                                        github_token=args.github_token,
                                        gitee_token=args.gitee_token))
        elif args.command == 'estimate':
            asyncio.run(estimate_tokens_async(args.url, args.provider,
                                              github_token=args.github_token,
                                              gitee_token=args.gitee_token))
    except KeyboardInterrupt:
        logger.info("操作已被用户取消")
    except Exception as e:
        logger.error(f"执行命令时发生错误: {e}")
        logger.debug(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("程序被用户中断。")
        sys.exit(0)
