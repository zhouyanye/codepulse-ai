"""
本地仓库Token估算测试
使用克隆到本地的requests仓库进行准确的token消耗测试
"""

import os
import sys
from utils.token_estimator import TokenEstimator

def test_local_repo():
    """测试本地仓库的实际token消耗"""
    repo_path = 'test_requests'
    
    if not os.path.exists(repo_path):
        print(f"❌ 错误: 找不到测试仓库目录 '{repo_path}'")
        print("请先运行: git clone --depth 1 https://github.com/psf/requests test_requests")
        return
    
    estimator = TokenEstimator()
    
    total_tokens = 0
    file_count = 0
    total_size_bytes = 0
    file_details = {}
    skipped_files = 0
    
    # 支持的文本文件扩展名
    text_extensions = {
        '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.h', '.hpp',
        '.go', '.rs', '.php', '.rb', '.swift', '.kt', '.scala', '.sh', '.bash',
        '.md', '.rst', '.txt', '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg',
        '.xml', '.html', '.htm', '.css', '.scss', '.sass', '.less', '.sql',
        '.dockerfile', '.gitignore', '.gitattributes', '.editorconfig', '.mk',
        '.pyi', '.pyx', '.pxd'  # Python相关
    }
    
    # 跳过的目录
    skip_dirs = {
        '.git', '__pycache__', '.pytest_cache', '.venv', 'venv', 'env', 
        'node_modules', '.vscode', '.idea', '.DS_Store', 'dist', 'build'
    }
    
    print('=== 本地Token估算测试 ===')
    print(f'扫描仓库: {repo_path}')
    print('支持文件类型:', ', '.join(sorted(list(text_extensions))[:10]), '...')
    print()
    
    # 扫描所有文件
    for root, dirs, files in os.walk(repo_path):
        # 跳过特定目录
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        
        for file in files:
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, repo_path)
            
            # 检查文件扩展名
            ext = os.path.splitext(file)[1].lower()
            if ext not in text_extensions:
                skipped_files += 1
                continue
            
            try:
                # 读取文件内容
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # 跳过过大的文件（避免内存问题）
                if len(content) > 1024 * 1024:  # 1MB限制
                    print(f'⚠️  跳过大文件: {relative_path} ({len(content):,} bytes)')
                    skipped_files += 1
                    continue
                
                # 计算单个文件的token
                file_tokens = estimator.estimate_tokens_for_file(relative_path, content, 'deepseek')
                
                total_tokens += file_tokens
                file_count += 1
                total_size_bytes += len(content)
                
                # 按文件类型分类统计
                if ext == '.py':
                    file_type = 'Python代码'
                elif ext in ['.md', '.rst']:
                    file_type = '文档'
                elif ext in ['.yml', '.yaml', '.toml', '.ini', '.cfg']:
                    file_type = '配置文件'
                elif ext in ['.json', '.xml']:
                    file_type = '数据文件'
                elif ext in ['.html', '.htm', '.css', '.scss', '.sass']:
                    file_type = 'Web文件'
                elif ext in ['.txt']:
                    file_type = '文本文件'
                else:
                    file_type = '其他代码'
                
                if file_type not in file_details:
                    file_details[file_type] = {
                        'count': 0, 
                        'tokens': 0, 
                        'size_bytes': 0,
                        'files': []
                    }
                
                file_details[file_type]['count'] += 1
                file_details[file_type]['tokens'] += file_tokens
                file_details[file_type]['size_bytes'] += len(content)
                
                # 记录大文件
                if file_tokens > 1000:
                    file_details[file_type]['files'].append({
                        'path': relative_path,
                        'tokens': file_tokens,
                        'size_kb': len(content) / 1024
                    })
                
                # 显示进度（每50个文件）
                if file_count % 50 == 0:
                    print(f'已处理 {file_count} 个文件...')
                    
            except Exception as e:
                print(f'❌ 读取文件失败 {relative_path}: {e}')
                skipped_files += 1
                continue
    
    # 显示基础统计
    print(f'\n=== 基础统计 ===')
    print(f'总文件数: {file_count:,}')
    print(f'跳过文件数: {skipped_files:,}')
    print(f'总大小: {total_size_bytes / 1024 / 1024:.2f} MB')
    print(f'总Token数: {total_tokens:,}')
    
    # 计算基础费用
    base_cost_info = estimator._estimate_cost(total_tokens, 'deepseek')
    print(f'基础费用: ${base_cost_info["cost_usd"]:.4f} USD (¥{base_cost_info["cost_cny"]:.4f} CNY)')
    
    # 按类型显示详细统计
    print(f'\n=== 文件类型统计 ===')
    for file_type, details in sorted(file_details.items(), key=lambda x: x[1]['tokens'], reverse=True):
        count = details['count']
        tokens = details['tokens']
        size_mb = details['size_bytes'] / 1024 / 1024
        avg_tokens = tokens // count if count > 0 else 0
        
        print(f'{file_type}:')
        print(f'  文件数: {count}')
        print(f'  总Token: {tokens:,} (平均: {avg_tokens:,}/文件)')
        print(f'  总大小: {size_mb:.2f} MB')
        
        # 显示大文件
        if details['files']:
            print(f'  大文件 (>1000 tokens):')
            for file_info in details['files'][:3]:  # 只显示前3个
                print(f'    {file_info["path"]}: {file_info["tokens"]:,} tokens ({file_info["size_kb"]:.1f} KB)')
            if len(details['files']) > 3:
                print(f'    ... 还有 {len(details["files"]) - 3} 个大文件')
        print()
    
    # 计算完整的分析成本（包括开销和缓冲）
    print(f'=== 完整分析成本估算 ===')
    
    # 基础开销
    overhead = sum(estimator.analysis_overheads.values())
    
    # 根据仓库大小调整开销
    repo_size_mb = total_size_bytes / 1024 / 1024
    if repo_size_mb > 50:
        overhead_multiplier = 1.5
    elif repo_size_mb > 10:
        overhead_multiplier = 1.2
    else:
        overhead_multiplier = 1.0
    
    adjusted_overhead = int(overhead * overhead_multiplier)
    
    # 缓冲token
    buffer_tokens = int(total_tokens * 0.15)
    
    # 最终总计
    final_total = total_tokens + adjusted_overhead + buffer_tokens
    
    print(f'文件内容Token: {total_tokens:,}')
    print(f'分析过程开销: {adjusted_overhead:,} (基础:{overhead:,} × {overhead_multiplier})')
    print(f'缓冲Token (15%): {buffer_tokens:,}')
    print(f'最终总计: {final_total:,}')
    
    # 最终费用
    final_cost_info = estimator._estimate_cost(final_total, 'deepseek')
    print(f'\n=== 最终费用估算 ===')
    print(f'总费用: ${final_cost_info["cost_usd"]:.4f} USD (¥{final_cost_info["cost_cny"]:.4f} CNY)')
    print(f'  Input tokens: {final_cost_info["input_tokens"]:,} (${final_cost_info["input_cost_usd"]:.4f})')
    print(f'  Output tokens: {final_cost_info["output_tokens"]:,} (${final_cost_info["output_cost_usd"]:.4f})')
    
    # 与API估算对比（如果可用）
    print(f'\n=== 估算方法对比 ===')
    print(f'实际扫描方法: {final_total:,} tokens (${final_cost_info["cost_usd"]:.4f})')
    
    # 快速API估算对比
    try:
        simple_mb = repo_size_mb
        simple_tokens = int(simple_mb * 1000)  # 简单的每MB 1000 tokens估算
        simple_cost = estimator._estimate_cost(simple_tokens, 'deepseek')
        print(f'简单API估算: {simple_tokens:,} tokens (${simple_cost["cost_usd"]:.4f})')
        
        diff = abs(final_total - simple_tokens)
        diff_percent = (diff / final_total * 100) if final_total > 0 else 0
        print(f'差异: {diff:,} tokens ({diff_percent:.1f}%)')
        
        if diff_percent < 20:
            print('✅ API估算与实际扫描结果接近')
        else:
            print('⚠️  API估算与实际扫描差异较大，建议使用实际扫描结果')
            
    except Exception as e:
        print(f'API估算对比失败: {e}')
    
    return {
        'total_tokens': final_total,
        'total_files': file_count,
        'repo_size_mb': repo_size_mb,
        'cost_usd': final_cost_info['cost_usd'],
        'cost_cny': final_cost_info['cost_cny'],
        'file_details': file_details
    }


if __name__ == "__main__":
    result = test_local_repo()
    if result:
        print(f'\n=== 测试完成 ===')
        print(f'这是一个{result["repo_size_mb"]:.1f}MB的仓库，包含{result["total_files"]}个文件')
        print(f'完整的代码分析大约需要{result["total_tokens"]:,}个tokens')
        print(f'预计费用为${result["cost_usd"]:.4f} USD (¥{result["cost_cny"]:.4f} CNY)')