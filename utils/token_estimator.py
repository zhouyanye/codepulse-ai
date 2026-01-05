"""
Token消耗估算工具
用于估算分析仓库所需的AI token数量
"""
import os
import logging
from typing import Dict, Any

# 尝试导入tiktoken，如果不存在则设置为None
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    tiktoken = None
    TIKTOKEN_AVAILABLE = False

logger = logging.getLogger(__name__)


class TokenEstimator:
    """Token消耗估算器"""

    def __init__(self):
        # 初始化不同模型的编码器
        self.encoders = {}
        if TIKTOKEN_AVAILABLE:
            self.encoders = {
                "deepseek": tiktoken.get_encoding("cl100k_base"),  # DeepSeek使用与GPT-3.5相同的编码
                "openai": tiktoken.get_encoding("cl100k_base"),  # OpenAI GPT-3.5/4
                "kimi": tiktoken.get_encoding("cl100k_base"),  # Kimi也使用类似编码
            }

        # 不同类型内容的token估算系数
        self.token_coefficients = {
            "code_file": 1.2,  # 代码文件
            "markdown_file": 1.0,  # Markdown文档
            "text_file": 0.8,  # 纯文本文件
            "other_file": 0.5,  # 其他类型文件
        }

        # 不同分析阶段的额外token开销
        self.analysis_overheads = {
            "initial_prompt": 500,  # 初始提示词基础开销
            "repo_structure": 300,  # 仓库结构分析
            "code_quality": 800,  # 代码质量分析
            "security_analysis": 1000,  # 安全分析
            "recommendations": 600,  # 优化建议
            "final_summary": 400,  # 最终总结
        }

    def estimate_tokens_for_file(self, file_path: str, file_content: str, provider: str = "deepseek") -> int:
        """
        估算单个文件的token消耗

        Args:
            file_path: 文件路径
            file_content: 文件内容
            provider: AI提供商

        Returns:
            估算的token数量
        """
        try:
            if TIKTOKEN_AVAILABLE:
                encoder = self.encoders.get(provider, self.encoders["deepseek"])

                # 基础token计算
                tokens = len(encoder.encode(file_content))

                # 根据文件类型调整系数
                file_extension = os.path.splitext(file_path)[1].lower()
                coefficient = self._get_file_coefficient(file_extension)

                return int(tokens * coefficient)
            else:
                # 如果tiktoken不可用，使用简单估算
                return self._simple_token_estimate(file_content, file_path)
        except Exception as e:
            logger.warning(f"估算文件 {file_path} 的token数量时出错: {e}")
            # 出错时返回保守估计
            return self._simple_token_estimate(file_content, file_path)

    def _simple_token_estimate(self, file_content: str, file_path: str) -> int:
        """
        改进的简单token估算方法（当tiktoken不可用时使用）
        基于实际token统计规律的更准确估算

        Args:
            file_content: 文件内容
            file_path: 文件路径

        Returns:
            估算的token数量
        """
        # 基于实际token统计规律的估算：
        # - 英文字符：平均1个字符 ≈ 0.3个token
        # - 中文字符：平均1个字符 ≈ 0.6个token
        # - 代码：包含大量符号和空格，token密度更低

        # 分离中文字符
        chinese_chars = len([c for c in file_content if '\u4e00' <= c <= '\u9fff'])
        non_chinese_content = ''.join([c for c in file_content if not ('\u4e00' <= c <= '\u9fff')])

        # 根据文件类型调整估算方法
        file_extension = os.path.splitext(file_path)[1].lower()
        coefficient = self._get_file_coefficient(file_extension)

        if coefficient == self.token_coefficients["code_file"]:
            # 代码文件：考虑代码的token特性
            # 移除注释和空行的影响
            lines = file_content.split('\n')
            code_lines = [line for line in lines if line.strip() and not line.strip().startswith('#')]
            code_content = '\n'.join(code_lines)

            # 代码token估算：英文字符token密度为0.3，符号和空格密度为0.2
            english_in_code = len([c for c in code_content if c.isalpha()])
            symbols_in_code = len([c for c in code_content if not c.isalpha() and not c.isspace()])

            code_tokens = int(english_in_code * 0.3 + symbols_in_code * 0.2)
            comment_tokens = int((len(file_content) - len(code_content)) * 0.4)

            base_estimate = code_tokens + comment_tokens
        else:
            # 非代码文件：分别估算英文和其他字符
            # 英文字符数量
            english_chars = len([c for c in non_chinese_content if c.isalpha()])
            # 其他字符（符号、数字、空格等）
            other_chars = len(non_chinese_content) - english_chars

            # 英文token估算：1个字符 ≈ 0.3个token
            english_tokens = int(english_chars * 0.3)
            # 其他字符token估算：符号和空格密度为0.2
            other_tokens = int(other_chars * 0.2)

            base_estimate = english_tokens + other_tokens

        # 中文字符token估算：1个字符 ≈ 0.6个token
        chinese_tokens = int(chinese_chars * 0.6)

        # 总估算
        total_estimate = base_estimate + chinese_tokens

        return int(total_estimate * coefficient)

    def _get_file_coefficient(self, extension: str) -> float:
        """根据文件扩展名获取token系数"""
        code_extensions = {'.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.h', '.hpp', '.cs', '.go', '.rs', '.php', '.rb', '.swift', '.kt', '.kts', '.scala', '.sc', '.sql', '.pl', '.pm', '.sh', '.bash', '.zsh', '.lua', '.r', '.dart', '.vue', '.svelte', '.html', '.htm', '.css', '.scss', '.sass', '.less', '.json', '.yaml', '.yml', '.xml', '.toml', '.ini', '.cfg', '.conf', '.env', '.gitignore', '.dockerfile', '.Dockerfile', '.makefile', '.cmake', '.gradle', '.bat', '.ps1', '.vbs', '.R', '.jl', '.ex', '.exs', '.erl', '.hrl', '.hs', '.lhs', '.ml', '.mli', '.clj', '.cljs', '.edn', '.f', '.for', '.f90', '.f95', '.cob', '.cbl', '.cobol', '.asm', '.s', '.cl', '.lisp', '.el', '.scm', '.ss', '.rkt', '.fs', '.fsi', '.fsx', '.v', '.sv', '.svh', '.tcl', '.tk', '.pro', '.pri', '.qml', '.jsfl', '.coffee', '.litcoffee', '.elm', '.purs', '.ls', '.hx', '.hxsl', '.idr', '.lidr', '.lean', '.hlean', '.agda', '.lagda', '.pi', '.pi0', '.pi1', '.d', '.di', '.nim', '.vbs', '.bas', '.ahk', '.au3', '.groovy', '.gvy', '.gy', '.gsh', '.cls', '.trigger', '.page', '.component', '.s', '.asm', '.s8', '.s64', '.mod', '.bmx', '.c', '.cpp', '.cc', '.cxx', '.h', '.hpp', '.hxx', '.ipp', '.inl', '.rc', '.def', '.odl', '.idl', '.ddl', '.mof', '.asm', '.a51', '.inc', '.nsp', '.sbl', '.prg', '.ch', '.prw', '.pqr', '.plx', '.plb', '.plc', '.plt', '.pli', '.pls', '.plsql', '.pck', '.pks', '.pkb', '.spc', '.bod', '.fnc', '.prc', '.trg', '.vw', '.idx', '.pkg', '.au3', '.ahk', '.mrc', '.dic', '.fky', '.chm', '.hlp', '.ctl', '.frm', '.bas', '.cls', '.dbr', '.frx', '.vbp', '.ctl', '.pag', '.ddr', '.ddk', '.ddc', '.ddp', '.ddt', '.ddm', '.ddx', '.ddy', '.ddz', '.ddf', '.dds', '.ddv', '.ddw'}
        markdown_extensions = {'.md', '.markdown', '.rst', '.mkd', '.mkdn', '.mdwn', '.mdown', '.markdown', '.mdx', '.rmd', '.pmd', '.dmd', '.adoc', '.asciidoc', '.textile', '.creole', '.mediawiki', '.wiki', '.pod', '.pod6'}
        text_extensions = {'.txt', '.csv', '.log', '.text', '.conf', '.config', '.cfg', '.cnf', '.prefs', '.properties', '.prop', '.settings', '.option', '.env', '.env.local', '.env.prod', '.env.production', '.env.dev', '.env.development', '.editorconfig', '.gitconfig', '.hgrc', '.inputrc', '.screenrc', '.tmux.conf', '.vimrc', '.nvimrc', '.zshrc', '.bashrc', '.profile', '.cshrc', '.login', '.logout', '.history', '.hist', '.journal', '.diary', '.readme', '.changelog', '.changes', '.todo', '.notes', '.plan', '.spec', '.specs', '.feature', '.features', '.story', '.stories', '.asc', '.usx', '.utxt', '.ans', '.ansi', '.no', '.nfo', '.diz', '.ly', '.lrc', '.srt', '.vtt', '.sub', '.idx', '.ssa', '.ass', '.apt', '.etx', '.fountain'}

        if extension in code_extensions:
            return self.token_coefficients["code_file"]
        elif extension in markdown_extensions:
            return self.token_coefficients["markdown_file"]
        elif extension in text_extensions:
            return self.token_coefficients["text_file"]
        else:
            return self.token_coefficients["other_file"]

    def estimate_total_tokens(self, repo_size_mb: float, file_stats: Dict[str, int],
                              provider: str = "deepseek", cache_hit_rate: float = 0.6) -> Dict[str, Any]:
        """
        改进的仓库总token估算方法

        Args:
            repo_size_mb: 仓库大小(MB)
            file_stats: 文件统计信息 {文件类型: 数量}
            provider: AI提供商
            cache_hit_rate: 上下文缓存命中率 (0.0 to 1.0)

        Returns:
            包含详细估算信息的字典
        """
        # 改进的基于仓库大小的估算（降低密度）
        # 基于实际观察：不同类型仓库的token密度不同
        if repo_size_mb < 1:  # 小仓库
            size_factor = 800  # token每MB（降低）
        elif repo_size_mb < 10:  # 中等仓库
            size_factor = 600
        elif repo_size_mb < 50:  # 大仓库
            size_factor = 400
        else:  # 超大仓库
            size_factor = 300  # 更保守

        size_based_estimate = repo_size_mb * size_factor

        # 改进的基于文件类型的详细估算（使用代码行数）
        file_based_estimate = 0
        file_details = {}

        # 获取代码行数（如果有）
        code_lines = file_stats.get("code_lines", 0)
        code_files_count = file_stats.get("code", 0)

        # 基于代码行数计算平均每行token数（代码约0.3-0.5 tokens/行）
        avg_tokens_per_line = 0.4  # 保守估计

        for file_type, count in file_stats.items():
            # 根据文件类型动态调整平均token数
            if "code" in file_type.lower():
                # 使用代码行数精确计算
                if code_lines > 0 and code_files_count > 0:
                    avg_tokens_per_file = int(code_lines / code_files_count * avg_tokens_per_line)
                    # 限制每个文件的预估范围
                    avg_tokens_per_file = max(50, min(avg_tokens_per_file, 2000))
                else:
                    # 降级：基于仓库大小估算
                    if repo_size_mb < 1:
                        avg_tokens_per_file = 100  # 小仓库文件更小
                    elif repo_size_mb < 10:
                        avg_tokens_per_file = 200
                    elif repo_size_mb < 50:
                        avg_tokens_per_file = 400
                    else:
                        avg_tokens_per_file = 600
            elif "document" in file_type.lower() or "markdown" in file_type.lower():
                # 文档文件
                avg_tokens_per_file = min(400, max(100, repo_size_mb * 50))
            elif "config" in file_type.lower():
                # 配置文件通常较小
                avg_tokens_per_file = 80
            elif "test" in file_type.lower():
                # 测试文件
                avg_tokens_per_file = 150
            else:
                # 其他文件
                avg_tokens_per_file = 100

            type_tokens = count * avg_tokens_per_file
            file_based_estimate += type_tokens
            file_details[file_type] = {
                "count": count,
                "avg_tokens_per_file": avg_tokens_per_file,
                "total_tokens": type_tokens
            }

        # 计算分析过程的额外开销（根据仓库大小动态调整）
        base_overhead = sum(self.analysis_overheads.values())
        if repo_size_mb > 10:
            # 大仓库需要更多的上下文处理开销
            size_multiplier = min(2.0, 1.0 + (repo_size_mb - 10) / 50)
            overhead_tokens = int(base_overhead * size_multiplier)
        else:
            overhead_tokens = base_overhead

        # 智能选择基础估算：优先使用基于文件的估算，但考虑大小因素
        if file_based_estimate > 0:
            # 有文件统计数据时，以文件估算为主，大小估算为参考
            base_estimate = file_based_estimate
            # 如果大小估算明显偏高，可能包含大量二进制文件，使用大小估算
            if size_based_estimate > file_based_estimate * 1.5:
                base_estimate = size_based_estimate
        else:
            # 没有文件统计时，使用大小估算
            base_estimate = size_based_estimate

        # 最终估算：基础估算 + 分析开销 + 缓冲token（15%）
        buffer_tokens = int(base_estimate * 0.15)
        total_estimate = base_estimate + overhead_tokens + buffer_tokens

        return {
            "repository_size_mb": repo_size_mb,
            "file_statistics": file_stats,
            "file_details": file_details,
            "size_based_estimate": int(size_based_estimate),
            "file_based_estimate": int(file_based_estimate),
            "analysis_overhead": overhead_tokens,
            "buffer_tokens": buffer_tokens,
            "total_estimated_tokens": int(total_estimate),
            "estimated_cost": self._estimate_cost(total_estimate, provider, cache_hit_rate),
            "estimation_method": "file_based" if file_based_estimate > 0 else "size_based"
        }

    def _estimate_cost(self, tokens: int, provider: str, cache_hit_rate: float = 0.6) -> Dict[str, float]:
        """
        API调用费用估算，已加入缓存命中率计算。

        Args:
            tokens: token数量
            provider: AI提供商
            cache_hit_rate: 上下文缓存命中率 (0.0 to 1.0)

        Returns:
            费用估算字典
        """
        # 更新各提供商的实际定价 (每100万 tokens的价格，单位: RMB)
        # 价格基于用户提供的最新数据

        pricing_rmb = {
            "deepseek": {
                # DeepSeek-V3.2
                # 输入：缓存命中 0.2元/M，未命中 2元/M。取未命中作为保守估计
                "input": 2.0,
                "input_cache_hit": 0.2,
                "output": 3.0,
                "name": "DeepSeek V3",
                "cache_hit_supported": True
            },
            "openai": {
                # GPT-3.5 Turbo (参考价)
                "input": 10.0,
                "output": 15.0,
                "name": "GPT-3.5 Turbo"
            },
            "kimi": {
                # Kimi k2 系列（基于官方定价）
                "kimi-k2-0905-preview": {  # 推荐
                    # 上下文长度 256k
                    "input": 4.00,  # 缓存未命中价格
                    "input_cache_hit": 1.00,  # 缓存命中价格
                    "output": 16.00,
                    "context_length": 262144,
                    "name": "Kimi k2-0905-preview (推荐)"
                },
                "kimi-k2-0711-preview": {  # 基础版
                    # 上下文长度 128k
                    "input": 4.00,
                    "input_cache_hit": 1.00,
                    "output": 16.00,
                    "context_length": 131072,
                    "name": "Kimi k2-0711-preview"
                },
                "kimi-k2-turbo-preview": {
                    # 上下文长度 256k
                    "input": 8.00,
                    "input_cache_hit": 1.00,
                    "output": 58.00,
                    "context_length": 262144,
                    "name": "Kimi k2-turbo-preview"
                },
                "kimi-k2-thinking": {  # 思考模式
                    # 上下文长度 256k
                    "input": 4.00,
                    "input_cache_hit": 1.00,
                    "output": 16.00,
                    "name": "Kimi k2-thinking"
                },
                "kimi-k2-thinking-turbo": {  # 思考模式高速
                    # 上下文长度 256k
                    "input": 8.00,
                    "input_cache_hit": 1.00,
                    "output": 58.00,
                    "name": "Kimi k2-thinking-turbo"
                },
                # 默认配置
                "input": 4.00,
                "input_cache_hit": 1.00,
                "output": 16.00,
                "name": "Kimi k2 models",
                "default_model": "kimi-k2-0905-preview"
            },
            "doubao": {
                # 豆包 doubao-seed-1.6 (推理模型)
                # 推理输入：0.80元/M，推理输出：1.00元/M
                # 缓存命中：推理输入0.08元/M，推理输入0.20元/M（批量），推理输出0.50元/M（批量）
                # 批量推理：输入0.20元/M（根据上下文长度），输出0.50元/M
                "input": 0.80,  # 推理输入价格
                "input_cache_hit": 0.08,  # 缓存命中价格
                "input_bulk": 0.20,  # 批量推理输入价格
                "output": 1.00,  # 输出价格
                "output_bulk": 0.50,  # 批量推理输出价格
                "name": "豆包 doubao-seed-1.6",
                "cache_hit_supported": True
            },
            "costrict": {
                # CoStrict 不使用AI API，只基于GitHub/Gitee API数据评分
                # 因此成本为0
                "input": 0.0,
                "output": 0.0,
                "name": "CoStrict (API-based, no AI cost)"
            }
        }

        provider_config = pricing_rmb.get(provider, pricing_rmb["deepseek"])

        # 假设input/output比例为7:3
        input_ratio = 0.7
        output_ratio = 0.3

        total_input_tokens = tokens * input_ratio
        total_output_tokens = tokens * output_ratio

        # --- 核心改动：引入缓存命中率计算 ---
        if "input_cache_hit" in provider_config:
            hit_input_tokens = total_input_tokens * cache_hit_rate
            miss_input_tokens = total_input_tokens * (1 - cache_hit_rate)

            input_cost_rmb = (hit_input_tokens / 1000000) * provider_config["input_cache_hit"] + \
                             (miss_input_tokens / 1000000) * provider_config["input"]
        else:
            # 如果模型不支持缓存，则按原价计算
            input_cost_rmb = (total_input_tokens / 1000000) * provider_config["input"]
        # --- 改动结束 ---

        output_cost_rmb = (total_output_tokens / 1000000) * provider_config["output"]
        total_cost_rmb = input_cost_rmb + output_cost_rmb

        logger.info(f"成本估算 - Provider: {provider}, Tokens: {tokens}, "
                    f"Cache Hit Rate: {cache_hit_rate:.0%}, "
                    f"Input Cost: ¥{input_cost_rmb:.4f}, "
                    f"Output Cost: ¥{output_cost_rmb:.4f}, "
                    f"Total: ¥{total_cost_rmb:.4f}")

        return {
            "cost_usd": total_cost_rmb / 7.2,  # 近似换算
            "cost_rmb": total_cost_rmb,
            "input_cost_rmb": input_cost_rmb,
            "output_cost_rmb": output_cost_rmb,
            "input_tokens": int(total_input_tokens),
            "output_tokens": int(total_output_tokens),
            "details": f"{provider_config['name']} Pricing (Cache Hit Rate: {cache_hit_rate:.0%})"
        }

    def get_example_estimates(self) -> Dict[str, Any]:
        """
        获取典型仓库大小的token消耗示例

        Returns:
            示例估算信息
        """
        examples = [
            {"size_mb": 1, "files": {"code": 5, "document": 3}},
            {"size_mb": 5, "files": {"code": 20, "document": 10, "other": 15}},
            {"size_mb": 10, "files": {"code": 50, "document": 20, "other": 30}},
            {"size_mb": 50, "files": {"code": 200, "document": 50, "other": 100}},
        ]

        results = {}
        for example in examples:
            size = example["size_mb"]
            stats = example["files"]
            # 使用默认的60%缓存命中率
            estimate = self.estimate_total_tokens(size, stats)
            results[f"{size}MB"] = {
                "file_stats": stats,
                "estimated_tokens": estimate["total_estimated_tokens"],
                "estimated_cost_usd": estimate["estimated_cost"]["cost_usd"],
                "estimated_cost_cny": estimate["estimated_cost"]["cost_rmb"]
            }

        return results


def format_token_estimate(estimate: Dict[str, Any]) -> str:
    """
    改进的格式化token估算结果为易读的字符串

    Args:
        estimate: 估算结果字典

    Returns:
        格式化的字符串
    """
    result = "=== Token消耗预估 ===\n"
    result += f"仓库大小: {estimate['repository_size_mb']} MB\n"
    result += f"文件统计: {estimate['file_statistics']}\n"
    result += f"估算方法: {estimate.get('estimation_method', '未知')}\n"
    result += f"预计费用: ${estimate['estimated_cost']['cost_usd']:.4f} USD "
    result += f"(¥{estimate['estimated_cost']['cost_rmb']:.4f} CNY)\n"
    result += f"估算Token总数: {estimate['total_estimated_tokens']:,}\n\n"

    result += "详细分解:\n"
    if 'size_based_estimate' in estimate:
        result += f"  基于大小估算: {estimate['size_based_estimate']:,} tokens\n"
    if 'file_based_estimate' in estimate:
        result += f"  基于文件估算: {estimate['file_based_estimate']:,} tokens\n"
    if 'analysis_overhead' in estimate:
        result += f"  分析过程开销: {estimate['analysis_overhead']:,} tokens\n"
    if 'buffer_tokens' in estimate:
        result += f"  缓冲Token (15%): {estimate['buffer_tokens']:,} tokens\n"

    # 显示文件类型的详细分析
    if 'file_details' in estimate and estimate['file_details']:
        result += "\n文件类型分析:\n"
        for file_type, details in estimate['file_details'].items():
            result += f"  {file_type}: {details['count']} 个文件 "
            result += f"× {details['avg_tokens_per_file']:,} tokens/文件 "
            result += f"= {details['total_tokens']:,} tokens\n"

    # 添加费用说明
    cost = estimate['estimated_cost']
    result += "\n费用说明:\n"
    result += f"   {cost.get('details', 'Pricing Details')}\n"
    result += f"   Input tokens: {cost.get('input_tokens', 0):,} (¥{cost.get('input_cost_rmb', 0):.4f})\n"
    result += f"   Output tokens: {cost.get('output_tokens', 0):,} (¥{cost.get('output_cost_rmb', 0):.4f})\n"
    result += f"  建议预留额外20%预算以防实际消耗超出预期\n"

    return result


def get_simple_estimate(repo_size_mb: float, provider: str = "deepseek", cache_hit_rate: float = 0.6) -> str:
    """
    获取简单的token估算

    Args:
        repo_size_mb: 仓库大小(MB)
        provider: AI提供商
        cache_hit_rate: 上下文缓存命中率

    Returns:
        格式化的估算字符串
    """
    estimator = TokenEstimator()
    # 文件统计
    file_stats = {
        "code": max(1, int(repo_size_mb * 2)),  # 估计的代码文件数
        "document": max(1, int(repo_size_mb * 0.5)),  # 估计的文档文件数
        "other": max(0, int(repo_size_mb * 0.3))  # 其他文件数
    }

    estimate = estimator.estimate_total_tokens(repo_size_mb, file_stats, provider, cache_hit_rate)
    return format_token_estimate(estimate)
