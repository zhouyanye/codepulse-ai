import streamlit as st
import requests

from datetime import datetime
from web.i18n import t, switch_language
import base64
from pyecharts import options as opts
from pyecharts.charts import Radar, Gauge, Bar, Pie
from streamlit_echarts import st_pyecharts
import markdown2
import pdfkit

# 页面配置
st.set_page_config(
    page_title=t("app_title"),
    page_icon="random",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS
st.markdown("""
<style>
    .main-header {
        font-size: 4.2rem; font-weight: 800;
        background: linear-gradient(90deg, #1890ff, #13c2c2, #52c41a);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        text-align: center; margin: 2rem 0;
    }
    .subtitle {text-align: center; color: #666; font-size: 1.4rem; margin-bottom: 3rem;}
    .repo-title {font-size: 2.4rem; font-weight: bold; color: #1f77b4; text-align: center; margin: 2rem 0 1rem;}
    .limited-badge {
        background: #722ed1; color: white; padding: 6px 16px; border-radius: 30px;
        font-size: 0.9rem; display: inline-block; margin: 10px 0;
    }
    .recommendation {
        background: #f6ffed; border-left: 5px solid #52c41a;
        padding: 1.2rem; border-radius: 12px; margin: 12px 0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }
</style>
""", unsafe_allow_html=True)


# 辅助函数
def get_language_from_recommendation(rec: dict, default: str = "text") -> str:
    # 语言映射表 - 更全面的扩展名映射
    lang_map = {
        # Python
        'py': 'python',
        'pyw': 'python',
        'pyi': 'python',
        # Web
        'html': 'html',
        'htm': 'html',
        'css': 'css',
        'js': 'javascript',
        'jsx': 'javascript',
        'ts': 'typescript',
        'tsx': 'typescript',
        # Java
        'java': 'java',
        # C-family
        'c': 'c',
        'cpp': 'cpp',
        'cxx': 'cpp',
        'cc': 'cpp',
        'h': 'c',
        'hpp': 'cpp',
        'hxx': 'cpp',
        'cs': 'csharp',
        # Go
        'go': 'go',
        # PHP
        'php': 'php',
        'php3': 'php',
        'php4': 'php',
        'php5': 'php',
        'phtml': 'php',
        # Ruby
        'rb': 'ruby',
        # Rust
        'rs': 'rust',
        # Swift
        'swift': 'swift',
        # Kotlin
        'kt': 'kotlin',
        'kts': 'kotlin',
        # Scala
        'scala': 'scala',
        'sc': 'scala',
        # Shell/Script
        'sh': 'bash',
        'bash': 'bash',
        'zsh': 'bash',
        'fish': 'bash',
        'ps1': 'powershell',
        'bat': 'batch',
        'cmd': 'batch',
        # Data/Config
        'json': 'json',
        'jsonc': 'jsonc',
        'yaml': 'yaml',
        'yml': 'yaml',
        'xml': 'xml',
        'csv': 'text',
        'txt': 'text',
        'log': 'text',
        # SQL
        'sql': 'sql',
        'mysql': 'sql',
        'pgsql': 'sql',
        # Markdown
        'md': '``',
        '``': '``',
        # Docker
        'dockerfile': 'dockerfile',
        'Dockerfile': 'dockerfile',
        # Make
        'makefile': 'makefile',
        'Makefile': 'makefile',
        # CMake
        'cmake': 'cmake',
        # Configuration
        'ini': 'ini',
        'cfg': 'ini',
        'conf': 'ini',
        'toml': 'toml',
        'properties': 'properties',
        # Other
        'lua': 'lua',
        'perl': 'perl',
        'pl': 'perl',
        'r': 'r',
        'dart': 'dart',
        'groovy': 'groovy',
        'vbs': 'vbscript',
        'vba': 'vba',
        'asm': 'assembly',
        's': 'assembly',
        'svg': 'xml',
        'svgz': 'xml',
        'plist': 'xml',
        'xsd': 'xml',
        'xsl': 'xml',
        'xhtml': 'html',
        'shtml': 'html',
        'tmpl': 'text',
        'tpl': 'text',
        'erb': 'erb',
        'haml': 'haml',
        'slim': 'slim',
        'jade': 'pug',
        'pug': 'pug',
        'styl': 'stylus',
        'sass': 'sass',
        'scss': 'scss',
        'less': 'less',
        'coffee': 'coffeescript',
        'litcoffee': 'coffeescript',
        'vue': 'vue',
        'svelte': 'svelte',
        'elm': 'elm',
        'erl': 'erlang',
        'hrl': 'erlang',
        'ex': 'elixir',
        'exs': 'elixir',
        'clj': 'clojure',
        'cljs': 'clojure',
        'cljc': 'clojure',
        'edn': 'edn',
        'fs': 'fsharp',
        'fsi': 'fsharp',
        'fsx': 'fsharp',
        'fsscript': 'fsharp',
        'hs': 'haskell',
        'lhs': 'haskell',
        'ml': 'ocaml',
        'mli': 'ocaml',
        'mll': 'ocaml',
        'mly': 'ocaml',
        'hx': 'haxe',
        'hxml': 'xml',
        'd': 'd',
        'di': 'd',
        'pde': 'processing',
        'wxs': 'xml',
        'wxl': 'xml',
        'xib': 'xml',
        'storyboard': 'xml',
        'pbxproj': 'json',
        'lock': 'text',  # 依赖锁文件
    }

    # 尝试从location字段提取
    location = rec.get('location', '')
    if location and ':' in location:
        # 格式可能是 "file.py:123-145"
        file_path = location.split(':')[0]
    else:
        file_path = location

    # 从文件路径提取扩展名
    import os
    file_ext = os.path.splitext(file_path)[1].lower().lstrip('.')

    # 返回对应语言或默认值
    return lang_map.get(file_ext, default)


# 自动修复功能函数
def generate_fix_patch(recommendation: dict, api_base_url: str, ai_provider: str, token: str):
    """生成自动修复代码补丁"""
    st.session_state.current_rec = recommendation

    with st.spinner(t("generating_fix")):
        try:
            payload = {
                "recommendation": recommendation,
                "ai_provider": ai_provider,
                "repo_url": st.session_state.get("repo_url", "")
            }

            # 如果有token，添加到payload中
            if token:
                repo_url = st.session_state.get("repo_url", "")
                if "gitee.com" in repo_url.lower():
                    payload["gitee_token"] = token
                else:
                    payload["github_token"] = token

            resp = requests.post(f"{api_base_url}/api/v1/generate-fix", json=payload, timeout=300)

            if resp.status_code == 200:
                result = resp.json()
                # 使用推荐的ID作为键存储修复结果，覆盖之前的修复结果
                if 'fix_results' not in st.session_state:
                    st.session_state.fix_results = {}
                rec_id = recommendation.get('id', 'unknown')

                # 覆盖之前的修复结果，只保留最新的
                st.session_state.fix_results[rec_id] = result

                st.success(t("success_auto_fix"))

                # 显示修复结果
                with st.expander(t("auto_fix_expander"), expanded=True):
                    if result.get("fixed_code"):
                        # 根据文件扩展名获取对应的语言名称
                        file_ext = result.get('file_extension', 'py')
                        # 使用统一的语言检测函数
                        language = get_language_from_recommendation({'location': f'file.{file_ext}'})
                        st.code(result["fixed_code"], language=language)

                    if result.get("diff"):
                        st.write(f"**{t('code_diff')}:**")
                        st.code(result["diff"], language="diff")

                    # 下载修复代码按钮
                    if result.get("fixed_code"):
                        st.download_button(
                            t("download_fix"),
                            result["fixed_code"],
                            f"fix_{rec_id}.{result.get('file_extension', 'py')}",
                            "text/plain",
                            key=f"download_fix_{rec_id}"
                        )
            else:
                st.error(t("error_auto_fix_failed", status=resp.status_code, text=resp.text))

        except Exception as e:
            st.error(t("error_auto_fix_error", error=str(e)))


def generate_diff_patch(recommendation: dict, api_base_url: str, ai_provider: str, token: str):
    """生成Diff格式补丁"""
    st.session_state.current_rec = recommendation

    with st.spinner(t("generating_diff")):
        try:
            payload = {
                "recommendation": recommendation,
                "ai_provider": ai_provider,
                "repo_url": st.session_state.get("repo_url", ""),
                "format": "diff"
            }

            # 如果有token，添加到payload中
            if token:
                repo_url = st.session_state.get("repo_url", "")
                if "gitee.com" in repo_url.lower():
                    payload["gitee_token"] = token
                else:
                    payload["github_token"] = token

            resp = requests.post(f"{api_base_url}/api/v1/generate-fix", json=payload, timeout=300)

            if resp.status_code == 200:
                result = resp.json()
                # 使用推荐的ID作为键存储diff结果，覆盖之前的diff结果
                if 'diff_results' not in st.session_state:
                    st.session_state.diff_results = {}
                rec_id = recommendation.get('id', 'unknown')

                # 覆盖之前的diff结果，只保留最新的
                st.session_state.diff_results[rec_id] = result

                st.success(t("success_diff"))

                # 显示Diff结果
                with st.expander(t("diff_patch_expander"), expanded=True):
                    if result.get("diff"):
                        st.code(result["diff"], language="diff")

                        # 下载Diff文件
                        st.download_button(
                            t("download_diff"),
                            result["diff"],
                            f"patch_{rec_id}.diff",
                            "text/plain",
                            key=f"download_diff_{rec_id}"
                        )

                    if result.get("apply_command"):
                        st.write(f"**{t('apply_command')}:**")
                        st.code(result["apply_command"], language="bash")

                    if result.get("files_affected"):
                        st.write(f"**{t('affected_files')}:**")
                        for file_info in result["files_affected"]:
                            st.markdown(f"- `{file_info['path']}` ({file_info.get('changes', 0)} {t('changes_count')})")

            else:
                st.error(t("error_diff_failed", status=resp.status_code, text=resp.text))

        except Exception as e:
            st.error(t("error_diff_error", error=str(e)))


st.markdown('<div class="main-header">CodePulse AI</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">开源项目全维度健康评估系统 · 专业 · 客观 · 全面</div>', unsafe_allow_html=True)

# 侧边栏
with st.sidebar:
    st.header(t("sidebar_config"))
    api_base_url = st.text_input(t("backend_url"), value="http://localhost:8000")
    token = st.text_input(t("token_section_title"), type="password")
    ai_provider = st.selectbox(t("ai_engine"), ["deepseek", "kimi", "doubao", "openai", "costrict"], index=0)
    include_static_scan = st.checkbox(t("enable_static_scan"), value=True)
    switch_language()
    # History Section
    with st.expander(t("history_recent"), expanded=False):
        try:
            hist_resp = requests.get(f"{api_base_url}/api/v1/analyze/history", timeout=15)
            if hist_resp.status_code == 200:
                history_items = hist_resp.json()
                if history_items:
                    for item in history_items:
                        score_color = "green" if item['overall_score'] >= 80 else "orange" if item[
                                                                                                  'overall_score'] >= 60 else "red"
                        col_hist1, col_hist2, col_hist3 = st.columns([3, 1, 1.2])
                        with col_hist1:
                            st.markdown(f"**{item['owner']}/{item['repo_name']}**")
                            st.caption(f"{item['created_at'][:10]} | {item['platform']}")
                        with col_hist2:
                            st.markdown(f":{score_color}[{item['overall_score']:.2f}]")
                        with col_hist3:
                            if st.button(t("view_button"), key=f"hist_btn_{item['id']}", use_container_width=True):
                                # Load history detail
                                with st.spinner(t("loading_history")):
                                    try:
                                        detail_resp = requests.get(
                                            f"{api_base_url}/api/v1/analyze/history/{item['id']}", timeout=10)
                                        if detail_resp.status_code == 200:
                                            st.session_state.result = detail_resp.json()
                                            st.session_state.repo_url = item['repo_url']
                                            st.success(t("success_history_loaded"))
                                            st.rerun()
                                        else:
                                            st.error(t("error_load_failed", error=detail_resp.status_code))
                                    except Exception as e:
                                        st.error(t("error_load_history", error=e))
                        st.markdown("---")
                else:
                    st.caption(t("info_no_history"))
            else:
                st.caption(t("info_no_history_data"))
        except Exception as e:
            st.caption(t("loading_failed"))

    st.info(t("info_support_platforms"))
    st.caption(t("footer_copyright"))


# 成本估算功能
def estimate_analysis_cost(repo_url: str, api_base_url: str, ai_provider: str, token: str):
    """估算分析成本并显示警告"""
    if not repo_url.strip():
        st.error(t("error_empty_url"))
        return

    with st.spinner(t("scanning_cost")):
        try:
            payload = {
                "repo_url": repo_url.strip(),
                "ai_provider": ai_provider
            }

            # 如果有token，添加到payload中
            if token:
                repo_url_lower = repo_url.lower()
                if "gitee.com" in repo_url_lower:
                    payload["gitee_token"] = token
                else:
                    payload["github_token"] = token

            resp = requests.post(f"{api_base_url}/api/v1/estimate-cost", json=payload, timeout=300)

            if resp.status_code == 200:
                result = resp.json()

                # 显示成本估算结果
                st.markdown("### " + t("cost_estimate_result"))

                col1, col2 = st.columns(2)
                with col1:
                    st.metric(t("estimated_tokens"), f"{result.get('estimated_tokens', 0):,}")
                    st.metric(t("file_count_label"), result.get('file_count', 0))
                    st.metric(t("code_lines_label"), f"{result.get('total_lines', 0):,}")

                with col2:
                    st.metric(t("estimated_cost_label"), f"¥{result.get('estimated_cost_rmb', 0):.4f}")
                    st.metric(t("estimated_time"), f"{result.get('estimated_time_minutes', 0)} 分钟")
                    st.metric(t("skipped_files_label"), result.get('skipped_files_count', 0))

                # 显示黑名单过滤信息
                if result.get('filtered_files'):
                    with st.expander(t("filtered_file_types")):
                        filtered_info = result['filtered_files']
                        st.write(
                            f"**{t('blacklist_rules')}**: {', '.join(filtered_info.get('blacklist_patterns', []))}")
                        st.write(f"**{t('skipped_large_files')}**: {len(filtered_info.get('large_files', []))} 个")
                        st.write(f"**{t('skipped_binary_files')}**: {len(filtered_info.get('binary_files', []))} 个")

                        if filtered_info.get('large_files'):
                            st.write(f"**{t('large_files_list')}:**")
                            for file_info in filtered_info['large_files']:
                                st.write(f"- `{file_info['path']}` ({file_info['size_kb']} KB)")

                # 成本警告
                estimated_cost = result.get('estimated_cost_rmb', 0)
                if estimated_cost > 1.0:
                    st.warning(t("cost_high", cost=estimated_cost))
                elif estimated_cost > 0.1:
                    st.info(t("cost_medium", cost=estimated_cost))
                else:
                    st.success(t("cost_low", cost=estimated_cost))

                # 确认按钮
                if st.button(t("confirm_continue"), type="primary"):
                    # 触发主分析流程
                    st.session_state.force_analyze = True
                    st.rerun()

            else:
                st.error(t("error_cost_estimate", status=resp.status_code, text=resp.text))

        except Exception as e:
            st.error(t("error_connect_backend", error=str(e)))


# 主界面
if "task_id" not in st.session_state:
    # 没有运行中的任务时显示输入框和开始分析按钮
    col1, col2 = st.columns([3.5, 1])
    with col1:
        repo_url = st.text_input(
            t("input_url_label"),
            placeholder=t("input_url_placeholder"),
            value=st.session_state.get("repo_url", "https://github.com/zhouyanye/codepulse-ai"),  # 使用会话状态中的URL作为默认值，如果没有则使用默认值
            help=t("help_text")
        )
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        analyze_btn = st.button(t("start_analysis_btn"), type="primary", use_container_width=True)
else:
    # 有运行中的任务时显示进度和取消按钮
    col1, col2 = st.columns([3.5, 1])
    with col1:
        repo_url = st.text_input(
            t("input_url_label"),
            placeholder=t("input_url_placeholder"),
            value=st.session_state.get("repo_url", ""),
            help=t("help_text"),
            disabled=True  # 在分析过程中禁用输入框
        )
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        if st.button(t("btn_cancel"), type="secondary", use_container_width=True, key="main_cancel_btn"):
            # 从会话状态获取任务ID
            task_id = st.session_state.task_id
            # 立即调用取消API
            try:
                cancel_resp = requests.post(f"{api_base_url}/api/v1/analyze/cancel/{task_id}", timeout=30)
                if cancel_resp.status_code == 200:
                    st.info(t("cancelling_analysis"))
                else:
                    st.warning(t("cancel_request_sent"))
            except requests.exceptions.RequestException as e:
                # 即使API调用失败也终止前端轮询
                st.warning(t("cancel_request_failed_polling"))

            # 设置取消确认标志
            st.session_state.cancel_confirmation = True
            st.rerun()

    # 在有任务运行时，不需要定义 analyze_btn，所以将其设为 False
    analyze_btn = False

# 执行分析（同步轮询模式）============
if analyze_btn or st.session_state.get("analyze_pending", False):
    # 清除之前仓库的AI修复和diff数据
    if 'fix_results' in st.session_state:
        del st.session_state.fix_results
    if 'diff_results' in st.session_state:
        del st.session_state.diff_results
    if 'current_rec' in st.session_state:
        del st.session_state.current_rec
    
    # 重置待分析标志
    if st.session_state.get("analyze_pending", False):
        st.session_state.analyze_pending = False

    # 检查是否已有分析任务在进行中
    if "task_id" in st.session_state:
        st.warning(t("warning_analysis_running"))
        st.stop()

    # URL验证逻辑，支持Gitee和GitHub URL
    repo_url_stripped = repo_url.strip()
    if not repo_url_stripped:
        st.error(t("error_empty_url"))
        st.stop()

    # 转换为小写以便检查
    repo_url_lower = repo_url_stripped.lower()

    # 检查是否以http或https开头
    if not repo_url_lower.startswith(("http://", "https://")):
        st.error(t("error_invalid_url_start"))
        st.stop()

    # 检查是否包含github.com或gitee.com域名
    if "github.com" not in repo_url_lower and "gitee.com" not in repo_url_lower:
        st.error(t("error_invalid_platform"))
        st.stop()

    # 检查域名后是否有路径（至少两个段：owner/repo）
    import re

    # 匹配类似 https://github.com/owner/repo 或 https://gitee.com/owner/repo，允许额外路径、查询参数或片段
    pattern = r'^https?://(?:www\.)?(github\.com|gitee\.com)/[^/]+/[^/]+'
    if not re.match(pattern, repo_url_lower):
        st.error(t("error_invalid_format"))
        st.stop()
    else:
        # 检测平台类型
        platform = "GitHub" if "github.com" in repo_url_stripped.lower() else "Gitee" if "gitee.com" in repo_url_stripped.lower() else "未知"
        if platform == "未知":
            st.warning(t("error_unknown_platform"))

        # 清除之前的分析结果和任务状态
        if "cost_confirmed" in st.session_state:
            del st.session_state.cost_confirmed
        if "cancel_confirmation" in st.session_state:
            del st.session_state.cancel_confirmation
        st.session_state.repo_url = repo_url_stripped

        # 启动分析任务
        try:
            payload = {
                "repo_url": repo_url_stripped,
                "ai_provider": ai_provider,
                "include_static_scan": include_static_scan
            }

            # 根据平台类型使用对应的token字段
            if token:
                token_stripped = token.strip()
                if platform == "Gitee":
                    payload["gitee_token"] = token_stripped
                else:
                    payload["github_token"] = token_stripped

            # 启动同步轮询分析任务
            resp = requests.post(f"{api_base_url}/api/v1/analyze/sync-polling", json=payload, timeout=60)
            if resp.status_code == 200:
                task_data = resp.json()
                task_id = task_data.get("task_id")
                st.session_state.task_id = task_id
                st.session_state.ai_provider = task_data.get("ai_provider", ai_provider)
                st.rerun()
            else:
                st.error(t("error_start_analysis", status=resp.status_code, text=resp.text))
        except requests.exceptions.ConnectionError:
            st.error(t("error_connection_backend"))
        except requests.exceptions.Timeout:
            st.error(t("error_timeout"))
        except Exception as e:
            st.error(t("error_connect_backend", error=str(e)))

# 轮询分析状态
if "task_id" in st.session_state:
    task_id = st.session_state.task_id

    try:
        # 获取任务状态
        status_resp = requests.get(f"{api_base_url}/api/v1/analyze/polling-status/{task_id}", timeout=30)
        if status_resp.status_code == 200:
            status_data = status_resp.json()
            status = status_data.get("status")
            progress = status_data.get("progress", 0)
            message = status_data.get("message", t("processing_label"))
            ai_provider = status_data.get("ai_provider", "unknown")

            # 显示进度容器
            progress_container = st.container()
            with progress_container:
                # 创建进度条
                progress_bar = st.progress(0)
                status_text = st.empty()
                status_text.write(f"**{message}** ({progress}%)")
                progress_bar.progress(progress / 100)

                # 显示更详细的进度信息
                if progress < 100:
                    col_progress_info1, col_progress_info2 = st.columns(2)
                    with col_progress_info1:
                        st.metric("当前进度", f"{progress}%")
                    with col_progress_info2:
                        estimated_time = "未知"
                        if "克隆" in message or "cloning" in message.lower():
                            estimated_time = "取决于仓库大小"
                        elif "AI" in message or "ai" in message.lower():
                            estimated_time = "取决于AI服务响应"
                        elif "分析" in message or "analyzing" in message.lower():
                            estimated_time = "取决于代码复杂度"
                        elif "结构" in message or "structure" in message.lower():
                            estimated_time = "分析仓库结构中"
                        elif "计算" in message or "calculating" in message.lower():
                            estimated_time = "正在计算结果"
                        st.metric("预估剩余时间", estimated_time)

            # 处理不同状态
            if status == "completed":
                # 分析完成
                st.session_state.result = status_data.get("result")
                if "task_id" in st.session_state:
                    del st.session_state.task_id
                st.success(t("success_analysis_complete"))
                progress_container.empty()
                # 短暂延迟，确保页面更新后再重新运行
                import time
                time.sleep(0.5)
                st.rerun()

            elif status == "failed":
                # 分析失败
                error_msg = status_data.get("error", t("error_occurred"))
                if "timeout" in error_msg.lower() or "超时" in error_msg:
                    st.error(t("error_analysis_timeout"))
                elif "git" in error_msg.lower() or "clone" in error_msg.lower():
                    st.error(t("error_clone_failed"))
                elif "api" in error_msg.lower() or "token" in error_msg.lower():
                    st.error(t("error_api_access"))
                elif "permission" in error_msg.lower():
                    st.error(t("error_permission"))
                elif "not found" in error_msg.lower() or "404" in str(error_msg):
                    st.error(t("error_repo_not_found"))
                elif "network" in error_msg.lower() or "connection" in error_msg.lower():
                    st.error(t("error_network"))
                elif "cancelled" in error_msg.lower() or "取消" in error_msg:
                    st.warning(t("warning_analysis_cancelled"))
                else:
                    st.error(f"分析失败：{error_msg}")

                if "task_id" in st.session_state:
                    del st.session_state.task_id
                progress_container.empty()

            elif status == "cancelled":
                # 分析被取消
                st.warning(t("warning_analysis_cancelled"))
                if "task_id" in st.session_state:
                    del st.session_state.task_id
                progress_container.empty()

            else:
                # 处理中，继续轮询
                # 使用 time.sleep 确保轮询间隔，避免过于频繁的请求
                import time
                time.sleep(1)  # 等待1秒后继续轮询

                # 检查是否有成本估算结果（非costrict模式）
                cost_estimate = status_data.get("cost_estimate")
                if cost_estimate and not st.session_state.get("cost_confirmed", False) and ai_provider != "costrict":
                    # 显示成本确认弹窗
                    progress_container.empty()
                    st.markdown("### " + t("estimated_cost_title"))
                    st.info(t("estimated_cost_notice"))

                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric(t("estimated_tokens"), f"{cost_estimate.get('estimated_tokens', 0):,}")
                        st.metric(t("file_count_label"), cost_estimate.get('file_count', 0))
                        st.metric(t("code_lines_label"), f"{cost_estimate.get('total_lines', 0):,}")
                    with col2:
                        st.metric(t("estimated_cost_label"), f"¥{cost_estimate.get('estimated_cost_rmb', 0):.4f}")
                        # 从估算结果中取时间范围字符串（estimated_analysis_time）
                        estimated_time = cost_estimate.get('estimated_analysis_time', f"3-5分钟")
                        st.metric(t("estimated_time"), estimated_time)
                        st.metric(t("skipped_files_label"), cost_estimate.get('skipped_files_count', 0))

                    st.caption("注：根据项目大小估算，实际时间可能因网络速度、AI服务响应时间而有所不同")

                    # 成本警告
                    estimated_cost = cost_estimate.get('estimated_cost_rmb', 0)
                    if estimated_cost > 1.0:
                        st.warning(t("cost_high", cost=estimated_cost))
                    elif estimated_cost > 0.1:
                        st.info(t("cost_medium", cost=estimated_cost))
                    else:
                        st.success(t("cost_low", cost=estimated_cost))

                    # 确认和取消按钮
                    col_confirm, col_cancel = st.columns([1, 1])
                    with col_confirm:
                        if st.button(t("confirm_continue"), type="primary", key="confirm_cost_btn"):
                            # 确认成本
                            confirm_resp = requests.post(f"{api_base_url}/api/v1/analyze/confirm-cost/{task_id}",
                                                         timeout=30)
                            st.session_state.cost_confirmed = True
                            st.rerun()
                    with col_cancel:
                        if st.button(t("btn_cancel"), type="secondary", key="cancel_analysis_btn"):
                            # 立即调用取消API，而不是只设置标志
                            try:
                                cancel_resp = requests.post(f"{api_base_url}/api/v1/analyze/cancel/{task_id}", timeout=30)
                                if cancel_resp.status_code == 200:
                                    st.info("正在取消分析...")
                                else:
                                    st.warning("取消请求已发送，可能需要几秒钟生效")
                            except requests.exceptions.RequestException as e:
                                st.warning(t("cancel_request_failed_analysis"))

                            # 清理会话状态
                            if "task_id" in st.session_state:
                                del st.session_state.task_id
                            if "cost_confirmed" in st.session_state:
                                del st.session_state.cost_confirmed
                            st.rerun()

                else:
                    # 检查是否需要显示取消确认对话框
                    if st.session_state.get("cancel_confirmation", False):
                        # 显示取消确认对话框
                        st.warning(t("confirm_cancel_analysis"))
                        col_confirm_cancel, col_cancel_no = st.columns([1, 1])
                        with col_confirm_cancel:
                            if st.button(t("btn_confirm_cancel"), type="primary", use_container_width=True, key="confirm_cancel_final_btn"):
                                # 立即调用取消API
                                try:
                                    cancel_resp = requests.post(f"{api_base_url}/api/v1/analyze/cancel/{task_id}", timeout=30)
                                    if cancel_resp.status_code == 200:
                                        st.info("正在取消分析...")
                                    else:
                                        st.warning("取消请求已发送，可能需要几秒钟生效")
                                except requests.exceptions.RequestException as e:
                                    # 即使API调用失败也终止前端轮询
                                    st.warning(t("cancel_request_failed_polling"))

                                # 清理会话状态以停止轮询
                                if "task_id" in st.session_state:
                                    del st.session_state.task_id
                                if "cancel_confirmation" in st.session_state:
                                    del st.session_state.cancel_confirmation
                                st.rerun()
                        with col_cancel_no:
                            if st.button(t("confirm_continue"), type="secondary", use_container_width=True, key="continue_analysis_after_cancel_btn"):
                                # 取消取消操作
                                if "cancel_confirmation" in st.session_state:
                                    del st.session_state.cancel_confirmation
                                st.rerun()

                    else:
                        # 显示取消按钮（只有在没有显示确认对话框时才显示）
                        col_action1, col_action2 = st.columns([4, 1])
                        with col_action2:
                            if st.button(t("btn_cancel"), type="secondary", use_container_width=True, key="show_cancel_dialog_main_btn"):
                                # 设置取消确认标志，显示确认对话框
                                st.session_state.cancel_confirmation = True
                                st.rerun()
                # 检查取消状态
                if status_data.get("cancelled", False):
                    # 任务已被取消，立即停止轮询并显示取消状态
                    if "task_id" in st.session_state:
                        del st.session_state.task_id
                    st.rerun()
                else:
                    # 只有在未取消时才重新运行轮询
                    time.sleep(0.5)  # 减少轮询频率，减少服务器压力
                    st.rerun()
    except requests.exceptions.ConnectionError:
        st.error(t("error_connection_backend"))
        # 清理会话状态以防止状态不一致
        if "task_id" in st.session_state:
            del st.session_state.task_id
        if "cancel_confirmation" in st.session_state:
            del st.session_state.cancel_confirmation
    except requests.exceptions.Timeout:
        st.error(t("error_timeout"))
        # 清理会话状态以防止状态不一致
        if "task_id" in st.session_state:
            del st.session_state.task_id
        if "cancel_confirmation" in st.session_state:
            del st.session_state.cancel_confirmation
    except Exception as e:
        st.error(t("error_polling", error=str(e)))
        # 清理会话状态以防止状态不一致
        if "task_id" in st.session_state:
            del st.session_state.task_id
        if "cancel_confirmation" in st.session_state:
            del st.session_state.cancel_confirmation

# 结果展示
if "result" in st.session_state:
    r = st.session_state.result
    info = r.get("repo_info", {})

    # 根据平台调整显示
    repo_url_display = st.session_state.repo_url
    platform = "GitHub" if "github.com" in repo_url_display.lower() else "Gitee" if "gitee.com" in repo_url_display.lower() else "GitHub"
    if platform == "GitHub":
        full_name = info.get("full_name") or repo_url_display.rstrip("/").replace("https://github.com/", "")
    else:
        full_name = info.get("full_name") or repo_url_display.rstrip("/").replace("https://gitee.com/", "")

    # XSS安全：使用安全的字符串函数而不是直接HTML
    st.subheader(full_name)

    is_limited = info.get("message") == "Not Found" or r.get("analysis_mode") == "limited_private" or r.get(
        "access_mode") == "limited"
    if is_limited:
        platform_name = "Gitee" if "gitee.com" in repo_url_display.lower() else "GitHub"
        # XSS安全：使用安全的字符串函数而不是直接HTML
        st.markdown(f"**{t('limited_analysis_mode', platform=platform_name)}**")

    if info.get("description"):
        st.caption(info["description"])

    # 作者信息
    owner = info.get("owner", {})
    # 处理owner是字符串而不是字典的情况
    if isinstance(owner, dict):
        platform = "GitHub" if "github.com" in repo_url_display.lower() else "Gitee"
        owner_login = owner.get("login", full_name.split("/")[0]) if full_name else ""
        if platform == "GitHub":
            owner_url = owner.get("html_url", f"https://github.com/{owner_login}")
            owner_avatar = owner.get("avatar_url", f"https://github.com/{owner_login}.png")
        else:
            owner_url = owner.get("html_url", f"https://gitee.com/{owner_login}")
            owner_avatar = owner.get("avatar_url", "https://foruda.gitee.com/images/logo/gitee-logo.png")
    else:
        owner_login = full_name.split("/")[0] if full_name else ""
        platform = "GitHub" if "github.com" in repo_url_display.lower() else "Gitee"
        owner_url = f"https://{platform.lower()}.com/{owner_login}"
        if platform == "GitHub":
            owner_avatar = f"https://github.com/{owner_login}.png"
        else:
            owner_avatar = "https://foruda.gitee.com/images/logo/gitee-logo.png"

    col_author1, col_author2 = st.columns([1, 5])
    with col_author1:
        st.image(owner_avatar, width=90)
    with col_author2:
        st.write(f"**{t('author_label')}：**[{owner_login}]({owner_url})")
        def safe_date_format(date_str):
            """安全处理日期字符串"""
            if not date_str or date_str == '未知':
                return t('unknown_date')
            try:
                return date_str[:10] if len(date_str) >= 10 else date_str
            except:
                return '未知'
        st.write(
            f"{t('created_at_label')}：{safe_date_format(info.get('created_at', t('unknown_date')))}　"
            f"{t('last_updated')}：{safe_date_format(info.get('pushed_at', t('unknown_date')))}　"
            f"{t('main_language_label')}：{info.get('language', t('unknown_date'))}"
        )

    # 仓库指标展示 (Stars, Forks, Watchers, Issues)
    st.markdown("---")
    col_metrics1, col_metrics2, col_metrics3, col_metrics4 = st.columns(4)
    with col_metrics1:
        st.metric("Stars", info.get("stars", 0))
    with col_metrics2:
        st.metric("Forks", info.get("forks", 0))
    with col_metrics3:
        st.metric("Issues", info.get("open_issues", 0))
    with col_metrics4:
        # 根据平台显示不同的watchers数据
        if platform == "GitHub":
            watchers = info.get("watchers", "N/A")
        else:
            # Gitee没有明确的watchers概念，使用订阅数代替
            watchers = info.get("subscribers_count", info.get("stars", "N/A"))
        st.metric("Watchers", watchers)

    # 最新提交 / Release / Branch 信息
    community_metrics = r.get("community_health", {})

    col_latest1, col_latest2, col_latest3 = st.columns(3)
    with col_latest1:
        st.markdown(f"**{t('latest_release_label')}**")
        if platform == "GitHub":
            release_info = community_metrics.get("release_info", {})
            latest_release = release_info.get("latest_release", t("no_release_data"))
            st.markdown(latest_release)
        else:
            gitee_metrics = r.get("gitee_metrics", {})
            total_score = gitee_metrics.get("total_score", "N/A")
            st.markdown(f"{total_score}/100" if total_score != "N/A" else t("no_data"))

    with col_latest2:
        st.markdown(f"**{t('default_branch_label')}**")
        st.markdown(info.get("default_branch", "main"))

    with col_latest3:
        st.markdown(f"**{t('contributors_label')}**")
        contributors_count = community_metrics.get("contributors_count", "N/A")
        st.markdown(f"{contributors_count} {t('people_unit')}" if contributors_count != "N/A" else t("no_data"))

    # CI/CD 状态、License、Topics
    col_extras1, col_extras2, col_extras3 = st.columns(3)
    with col_extras1:
        st.markdown(f"**{t('license_label')}**")
        license_info = info.get("license")
        if license_info:
            if isinstance(license_info, dict):
                st.markdown(license_info.get("name", license_info.get("key", t("unknown_date"))))
            else:
                st.markdown(str(license_info))
        else:
            st.markdown(t("not_specified_label"))

    with col_extras2:
        st.markdown(f"**{t('topics_label')}**")
        topics = info.get("topics", [])
        if topics:
            st.markdown(", ".join(topics[:5]))
        else:
            st.markdown(t("no_topics"))

    with col_extras3:
        st.markdown(f"**{t('cicd_status_label')}**")
        repo_structure = r.get("repo_structure", {})
        has_ci_cd = repo_structure.get("has_ci_cd", False)
        if has_ci_cd:
            st.markdown(t("enabled"))
        else:
            st.markdown(t("not_configured"))

    st.divider()
    # ======== 可视化区域========
    st.subheader(t("report_title"))

    col1, col2 = st.columns(2)
    col3, col4 = st.columns(2)

    # 图表1：总体评分仪表盘
    with col1:
        st.markdown(f"#### {t('overall_health_label')}")

        score = r["overall_score"]

        gauge = (
            Gauge(init_opts=opts.InitOpts(height="380px"))
            .add(
                series_name=t("health_label"),
                data_pair=[("", score)],
                min_=0,
                max_=100,
                radius="90%",
                # 全圆
                start_angle=225,
                end_angle=-45,
                # 指针（保留，让视觉更自然）
                pointer=opts.GaugePointerOpts(
                    length="70%",  # 指针长度
                    width=6,  # 指针宽度
                ),
                axisline_opts=opts.AxisLineOpts(
                    linestyle_opts=opts.LineStyleOpts(
                        width=22,
                        color=[
                            (0.6, "#ff4d4f"),  # 红
                            (0.8, "#fa8c16"),  # 橙
                            (1, "#52c41a"),  # 绿
                        ]
                    )
                ),

                # 数字不覆盖指针
                detail_label_opts=opts.GaugeDetailOpts(
                    formatter="{value}",
                    font_size=38,
                    color="#333",
                    offset_center=[0, "30%"],  # 调低数字位置
                ),
                # 下方标签
                title_label_opts=opts.GaugeTitleOpts(
                    offset_center=[0, "55%"],
                    font_size=18,
                    color="#666"
                ),
            )
            .set_global_opts(
                legend_opts=opts.LegendOpts(is_show=False),
                tooltip_opts=opts.TooltipOpts(is_show=False),
            )
        )

        st_pyecharts(gauge)

    with col2:
        st.markdown(f"#### {t('radar_chart_title')}")

        schema = [t("code_quality_label"), t("community_health_label"), t("documentation_label"),
                  t("maintenance_label")]
        values = [
            r['code_quality'].get('score', 0),
            r['community_health'].get('score', 0),
            r['documentation'].get('score', 0),
            r['maintenance'].get('score', 0)
        ]

        radar = Radar(init_opts=opts.InitOpts(height="430px"))

        radar.add_schema(
            schema=[
                opts.RadarIndicatorItem(name=s, max_=100) for s in schema
            ],
            splitline_opt=opts.SplitLineOpts(
                linestyle_opts=opts.LineStyleOpts(color="#dcdcdc", width=1)
            ),
            splitarea_opt=opts.SplitAreaOpts(
                areastyle_opts=opts.AreaStyleOpts(color=["#fafafa", "#ffffff"])
            ),
            axisline_opt=opts.AxisLineOpts(
                linestyle_opts=opts.LineStyleOpts(color="#bfbfbf")
            ),
            textstyle_opts=opts.TextStyleOpts(color="#333", font_size=16)
        )

        radar.add(
            series_name=t("score_label"),
            data=[values],
            color="#1890ff",
            areastyle_opts=opts.AreaStyleOpts(opacity=0.25),
            linestyle_opts=opts.LineStyleOpts(width=3, color="#1890ff"),
            symbol="circle",
        )

        radar.set_global_opts(
            legend_opts=opts.LegendOpts(is_show=False),
            title_opts=opts.TitleOpts(title="")
        )

        st_pyecharts(radar)

    # 图表3：条形图（左下）
    with col3:
        st.markdown(f"#### {t('health_trend_title')}")
        bar = Bar(init_opts=opts.InitOpts(height="380px"))
        bar.add_xaxis(schema)
        bar.add_yaxis(t("score_word"), values, color="#13c2c2")
        bar.set_global_opts(
            title_opts=opts.TitleOpts(title=""),
            yaxis_opts=opts.AxisOpts(max_=100),
            visualmap_opts=opts.VisualMapOpts(is_show=False,
                                              range_color=["#fca5a5", "#fdba74", "#fde047", "#bef264", "#86efac"])
        )
        st_pyecharts(bar)

    # 图表4：静态分析问题玫瑰图
    with col4:
        st.markdown(f"#### {t('static_issues_title')}")

        # 检查是否启用了静态扫描
        if not include_static_scan:
            st.info(t("info_no_scan"))
        else:
            scan_results = r['code_quality'].get('static_scan_results', {})
            severity_counts = {t("high_risk"): 0, t("medium_risk"): 0, t("low_risk_label"): 0, t("info_word"): 0}

            if isinstance(scan_results, dict):
                ai_scan_data = scan_results.get('ai_static_scan', {})
                if isinstance(ai_scan_data, dict):
                    result_list = ai_scan_data.get('results', [])
                    if isinstance(result_list, list):
                        for issue in result_list:
                            if isinstance(issue, dict):
                                # 处理AI静态扫描结果的严重程度
                                severity = issue.get("issue_severity", "").lower()
                                if not severity:
                                    # 如果没有issue_severity，尝试从原始severity字段获取
                                    severity = issue.get("severity", "").lower()

                                # 标准化严重程度分类
                                if severity in ["high", "critical", "high/critical", "严重", "high risk"]:
                                    severity_counts[t("high_risk")] += 1
                                elif severity in ["medium", "moderate", "中等", "medium risk"]:
                                    severity_counts[t("medium_risk")] += 1
                                elif severity in ["low", "info", "informational", "低风险", "提示", "low risk"]:
                                    severity_counts[t("low_risk_label")] += 1
                                else:
                                    # 默认归类为提示
                                    severity_counts[t("info_word")] += 1
                            elif isinstance(issue, str) and ("issue" in issue.lower() or "problem" in issue.lower()):
                                severity_counts[t("info_word")] += 1

            # 只显示有数据的类别
            filtered_severity_counts = {k: v for k, v in severity_counts.items() if v > 0}

            if filtered_severity_counts:
                pie = Pie(init_opts=opts.InitOpts(height="380px"))

                pie.add(
                    "",
                    [list(z) for z in filtered_severity_counts.items()],
                    radius=["20%", "80%"],
                    rosetype="radius"
                )

                # 为不同严重程度设置不同颜色
                colors = []
                for severity in filtered_severity_counts.keys():
                    if t("high_risk") in severity:
                        colors.append("#ff4d4f")  # 红色
                    elif t("medium_risk") in severity:
                        colors.append("#fa8c16")  # 橙色
                    elif t("low_risk_label") in severity:
                        colors.append("#fadb14")  # 黄色
                    else:
                        colors.append("#13c2c2")  # 蓝色

                pie.set_colors(colors)

                pie.set_global_opts(
                    title_opts=opts.TitleOpts(title=""),
                    legend_opts=opts.LegendOpts(
                        orient="vertical", pos_left="2%", pos_top="middle"
                    )
                )

                pie.set_series_opts(
                    label_opts=opts.LabelOpts(
                        formatter=f"{{b}}: {{c}}{t('issues_count_unit')}",
                        font_size=12,
                    )
                )

                st_pyecharts(pie)
            else:
                st.success(t("info_no_scan_issues"))

    st.divider()

    # ======== 报告区========
    tabs = st.tabs([t("tab_security"), t("tab_recommendations"), t("tab_static"), t("tab_export")])

    with tabs[0]:
        st.subheader(t("tab_security"))

        security_issues = []
        if 'code_quality' in r and isinstance(r['code_quality'], dict):
            security_issues = r['code_quality'].get('security_issues', [])
        if not security_issues or len(security_issues) == 0:
            st.success(t("info_no_issues"))
            st.caption(t("info_low_risk_note"))
        else:
            # 按严重性分组显示 - 支持多种严重性格式
            high_issues = []
            medium_issues = []
            low_issues = []

            for issue in security_issues:
                severity = str(issue.get('severity', '')).lower()
                if severity in ['高', 'high', 'high risk', 'critical', '严重']:
                    high_issues.append(issue)
                elif severity in ['中', 'medium', 'medium risk', 'moderate', '中等']:
                    medium_issues.append(issue)
                elif severity in ['低', 'low', 'low risk', 'info', 'informational', '低风险', '提示']:
                    low_issues.append(issue)
                # 如果都不匹配，可以根据内容判断是否为安全相关
                elif not severity or 'security' in str(issue.get('type', '')).lower() or '安全' in str(issue.get('type', '')):
                    # 默认归类为低风险，如果类型包含安全相关关键词但没有明确严重性
                    low_issues.append(issue)

            if high_issues:
                st.error(f" **{t('security_title')}{t('security_high', count=len(high_issues))}")
                for issue in high_issues:
                    with st.expander(
                            f"{issue.get('title', t('security_title'))} - `{issue.get('location', t('security_manual_check'))}`",
                            expanded=True):
                        st.write(f"**{t('security_type')}**: {issue.get('type', t('security_type'))}")
                        st.write(f"**{t('security_analysis')}**: {issue.get('analysis', t('further_analysis'))}")
                        st.write(f"**{t('security_impact')}**: {issue.get('impact', t('potential_risk'))}")

                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**{t('security_issue_code')}:**")
                            # 根据文件位置确定语言类型
                            location = issue.get('location', '')
                            lang = get_language_from_recommendation({'location': location})
                            st.code(issue.get('issue_code', t('security_no_code')), language=lang)
                        with col2:
                            st.write(f"**{t('security_fix_code')}:**")
                            # 根据文件位置确定语言类型
                            location = issue.get('location', '')
                            lang = get_language_from_recommendation({'location': location})
                            st.code(issue.get('fix_code', t('security_manual_check')), language=lang)

                        st.write(
                            f"**{t('security_recommendation')}**: {issue.get('recommendation', t('security_fix_soon'))}")

            if medium_issues:
                st.warning(f"**{t('security_medium', count=len(medium_issues))}")
                for issue in medium_issues:
                    with st.expander(
                            f"{issue.get('title', t('security_title'))} - `{issue.get('location', t('security_manual_check'))}`"):
                        st.write(f"**{t('security_type')}**: {issue.get('type', t('security_type'))}")
                        st.write(f"**{t('security_analysis')}**: {issue.get('analysis', t('further_analysis'))}")
                        st.write(f"**{t('security_impact')}**: {issue.get('impact', t('potential_risk'))}")

                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**{t('security_issue_code')}:**")
                            # 根据文件位置确定语言类型
                            location = issue.get('location', '')
                            lang = get_language_from_recommendation({'location': location})
                            st.code(issue.get('issue_code', t('security_no_code')), language=lang)
                        with col2:
                            st.write(f"**{t('security_fix_code')}:**")
                            # 根据文件位置确定语言类型
                            location = issue.get('location', '')
                            lang = get_language_from_recommendation({'location': location})
                            st.code(issue.get('fix_code', t('security_manual_check')), language=lang)

                        st.write(
                            f"**{t('security_recommendation')}**: {issue.get('recommendation', t('security_fix_soon'))}")

            if low_issues:
                st.info(f"**{t('security_low', count=len(low_issues))}")
                for issue in low_issues:
                    with st.expander(
                            f"{issue.get('title', t('security_title'))} - `{issue.get('location', t('security_manual_check'))}`"):
                        st.write(f"**{t('security_type')}**: {issue.get('type', t('security_type'))}")
                        st.write(f"**{t('security_analysis')}**: {issue.get('analysis', t('further_analysis'))}")
                        st.write(f"**{t('security_impact')}**: {issue.get('impact', t('potential_risk'))}")

                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**{t('security_issue_code')}:**")
                            # 根据文件位置确定语言类型
                            location = issue.get('location', '')
                            lang = get_language_from_recommendation({'location': location})
                            st.code(issue.get('issue_code', t('security_no_code')), language=lang)
                        with col2:
                            st.write(f"**{t('security_fix_code')}:**")
                            # 根据文件位置确定语言类型
                            location = issue.get('location', '')
                            lang = get_language_from_recommendation({'location': location})
                            st.code(issue.get('fix_code', t('security_manual_check')), language=lang)

                        st.write(
                            f"**{t('security_recommendation')}**: {issue.get('recommendation', t('security_fix_soon'))}")

    with tabs[1]:
        st.subheader(t("tab_recommendations"))

        recommendations = r.get('recommendations', [])
        structured_recs = [rec for rec in recommendations if isinstance(rec, dict)]
        string_recs = [rec for rec in recommendations if isinstance(rec, str)]

        # 高、中、低优先级建议显示
        high_priority = [rec for rec in structured_recs if rec.get('priority') == '高']
        medium_priority = [rec for rec in structured_recs if rec.get('priority') == '中']
        low_priority = [rec for rec in structured_recs if rec.get('priority') == '低']

        if high_priority:
            st.error(f"**{t('priority_high', count=len(high_priority))}")
            for i, rec in enumerate(high_priority):
                with st.expander(f"{rec.get('title')} - `{rec.get('location', t('global'))}`", expanded=True):
                    st.write(f"**{t('rec_category')}**: {rec.get('category')}")
                    st.write(f"**{t('rec_description')}**: {rec.get('description')}")
                    st.write(f"**{t('rec_reason')}**: {rec.get('reason')}")
                    st.write(f"**{t('rec_impact')}**: {rec.get('impact')}")

                    if rec.get('issue'):
                        c1, c2 = st.columns(2)
                        lang = get_language_from_recommendation(rec)
                        with c1:
                            st.write(f"**{t('rec_current_code')}:**")
                            st.code(rec.get('issue'), language=lang)
                        with c2:
                            st.write(f"**{t('rec_fix')}:**")
                            st.code(rec.get('fix'), language=lang)
                    st.write(f"**{t('rec_recommendation')}**: {rec.get('recommendation')}")

                    # 添加自动修复按钮
                    col_btn1, col_btn2 = st.columns([1, 1])
                    with col_btn1:
                        if st.button(t("btn_generate_fix"), key=f"fix_high_{i}"):
                            generate_fix_patch(rec, api_base_url, ai_provider, token)
                    with col_btn2:
                        if st.button(t("btn_generate_diff"), key=f"diff_high_{i}"):
                            generate_diff_patch(rec, api_base_url, ai_provider, token)

                    # 检查并显示修复和diff结果，使用左右并排方式展示
                    rec_id = rec.get('id', 'unknown')
                    fix_result_exists = 'fix_results' in st.session_state and rec_id in st.session_state.fix_results
                    diff_result_exists = 'diff_results' in st.session_state and rec_id in st.session_state.diff_results

                    if fix_result_exists or diff_result_exists:
                        # 使用列布局并排显示修复和diff结果
                        col_fix, col_diff = st.columns(2)

                        with col_fix:
                            if fix_result_exists:
                                fix_result = st.session_state.fix_results[rec_id]
                                if fix_result.get("fixed_code") or (fix_result.get("diff") and not diff_result_exists):
                                    with st.expander(t("auto_fix_expander"), expanded=True):
                                        if fix_result.get("fixed_code"):
                                            # 根据文件扩展名获取对应的语言名称
                                            file_ext = fix_result.get('file_extension', 'py')
                                            # 使用统一的语言检测函数
                                            language = get_language_from_recommendation({'location': f'file.{file_ext}'})
                                            st.code(fix_result["fixed_code"], language=language)

                                        # 只在没有单独的diff结果时显示diff（避免重复）
                                        if fix_result.get("diff") and not diff_result_exists:
                                            st.write(f"**{t('code_diff')}:**")
                                            st.code(fix_result["diff"], language="diff")

                                        # 下载修复代码按钮
                                        if fix_result.get("fixed_code"):
                                            st.download_button(
                                                t("download_fix"),
                                                fix_result["fixed_code"],
                                                f"fix_{rec_id}.{fix_result.get('file_extension', 'py')}",
                                                "text/plain",
                                                key=f"download_fix_btn_{rec_id}_high"
                                            )

                        with col_diff:
                            if diff_result_exists:
                                diff_results_list = st.session_state.diff_results[rec_id]
                                # 如果是列表，显示最新的diff结果
                                if isinstance(diff_results_list, list) and len(diff_results_list) > 0:
                                    # 提供选择框让用户选择查看哪次diff
                                    if len(diff_results_list) > 1:
                                        diff_selection = st.selectbox(
                                            f"选择Diff版本 (共{len(diff_results_list)}次)",
                                            options=range(len(diff_results_list)),
                                            format_func=lambda x: f"第{x+1}次Diff",
                                            key=f"diff_select_{rec_id}_high"
                                        )
                                        diff_result = diff_results_list[diff_selection]
                                    else:
                                        diff_result = diff_results_list[0]
                                else:
                                    # 兼容旧格式（如果仍为单个对象）
                                    diff_result = diff_results_list

                                with st.expander(t("diff_patch_expander"), expanded=True):
                                    if diff_result.get("diff"):
                                        st.code(diff_result["diff"], language="diff")

                                        # 下载Diff文件
                                        st.download_button(
                                            t("download_diff"),
                                            diff_result["diff"],
                                            f"patch_{rec_id}.diff",
                                            "text/plain",
                                            key=f"download_diff_btn_{rec_id}_high_{len(diff_results_list) if isinstance(diff_results_list, list) else 1}"
                                        )

                                    if diff_result.get("apply_command"):
                                        st.write(f"**{t('apply_command')}:**")
                                        st.code(diff_result["apply_command"], language="bash")

                                    if diff_result.get("files_affected"):
                                        st.write(f"**{t('affected_files')}:**")
                                        for file_info in diff_result["files_affected"]:
                                            st.markdown(f"- `{file_info['path']}` ({file_info.get('changes', 0)} {t('changes_count')})")

        if medium_priority:
            st.warning(f"**{t('priority_medium', count=len(medium_priority))}")
            for i, rec in enumerate(medium_priority):
                with st.expander(f"{rec.get('title')} - `{rec.get('location', t('global'))}`"):
                    st.write(f"**{t('rec_category')}**: {rec.get('category')}")
                    st.write(f"**{t('rec_description')}**: {rec.get('description')}")
                    st.write(f"**{t('rec_reason')}**: {rec.get('reason')}")
                    st.write(f"**{t('rec_impact')}**: {rec.get('impact')}")
                    if rec.get('issue'):
                        c1, c2 = st.columns(2)
                        lang = get_language_from_recommendation(rec)
                        with c1:
                            st.write(f"**{t('rec_current_code')}:**")
                            st.code(rec.get('issue'), language=lang)
                        with c2:
                            st.write(f"**{t('rec_fix')}:**")
                            st.code(rec.get('fix'), language=lang)
                    st.write(f"**{t('rec_recommendation')}**: {rec.get('recommendation')}")

                    # 添加自动修复按钮
                    col_btn1, col_btn2 = st.columns([1, 1])
                    with col_btn1:
                        if st.button(t("btn_generate_fix"), key=f"fix_medium_{i}"):
                            generate_fix_patch(rec, api_base_url, ai_provider, token)
                    with col_btn2:
                        if st.button(t("btn_generate_diff"), key=f"diff_medium_{i}"):
                            generate_diff_patch(rec, api_base_url, ai_provider, token)

                    # 检查并显示修复和diff结果，使用左右并排方式展示
                    rec_id = rec.get('id', 'unknown')
                    fix_result_exists = 'fix_results' in st.session_state and rec_id in st.session_state.fix_results
                    diff_result_exists = 'diff_results' in st.session_state and rec_id in st.session_state.diff_results

                    if fix_result_exists or diff_result_exists:
                        # 使用列布局并排显示修复和diff结果
                        col_fix, col_diff = st.columns(2)

                        with col_fix:
                            if fix_result_exists:
                                fix_results_list = st.session_state.fix_results[rec_id]
                                # 如果是列表，显示最新的修复结果
                                if isinstance(fix_results_list, list) and len(fix_results_list) > 0:
                                    # 提供选择框让用户选择查看哪次修复
                                    if len(fix_results_list) > 1:
                                        fix_selection = st.selectbox(
                                            f"选择修复版本 (共{len(fix_results_list)}次)",
                                            options=range(len(fix_results_list)),
                                            format_func=lambda x: f"第{x+1}次修复",
                                            key=f"fix_select_{rec_id}_medium"
                                        )
                                        fix_result = fix_results_list[fix_selection]
                                    else:
                                        fix_result = fix_results_list[0]
                                else:
                                    # 兼容旧格式（如果仍为单个对象）
                                    fix_result = fix_results_list

                                if fix_result.get("fixed_code") or (fix_result.get("diff") and not diff_result_exists):
                                    with st.expander(t("auto_fix_expander"), expanded=True):
                                        if fix_result.get("fixed_code"):
                                            # 根据文件扩展名获取对应的语言名称
                                            file_ext = fix_result.get('file_extension', 'py')
                                            # 使用统一的语言检测函数
                                            language = get_language_from_recommendation({'location': f'file.{file_ext}'})
                                            st.code(fix_result["fixed_code"], language=language)

                                        # 只在没有单独的diff结果时显示diff（避免重复）
                                        if fix_result.get("diff") and not diff_result_exists:
                                            st.write(f"**{t('code_diff')}:**")
                                            st.code(fix_result["diff"], language="diff")

                                        # 下载修复代码按钮
                                        if fix_result.get("fixed_code"):
                                            st.download_button(
                                                t("download_fix"),
                                                fix_result["fixed_code"],
                                                f"fix_{rec_id}.{fix_result.get('file_extension', 'py')}",
                                                "text/plain",
                                                key=f"download_fix_btn_{rec_id}_medium_{len(fix_results_list) if isinstance(fix_results_list, list) else 1}"
                                            )

                        with col_diff:
                            if diff_result_exists:
                                diff_results_list = st.session_state.diff_results[rec_id]
                                # 如果是列表，显示最新的diff结果
                                if isinstance(diff_results_list, list) and len(diff_results_list) > 0:
                                    # 提供选择框让用户选择查看哪次diff
                                    if len(diff_results_list) > 1:
                                        diff_selection = st.selectbox(
                                            f"选择Diff版本 (共{len(diff_results_list)}次)",
                                            options=range(len(diff_results_list)),
                                            format_func=lambda x: f"第{x+1}次Diff",
                                            key=f"diff_select_{rec_id}_medium"
                                        )
                                        diff_result = diff_results_list[diff_selection]
                                    else:
                                        diff_result = diff_results_list[0]
                                else:
                                    # 兼容旧格式（如果仍为单个对象）
                                    diff_result = diff_results_list

                                with st.expander(t("diff_patch_expander"), expanded=True):
                                    if diff_result.get("diff"):
                                        st.code(diff_result["diff"], language="diff")

                                        # 下载Diff文件
                                        st.download_button(
                                            t("download_diff"),
                                            diff_result["diff"],
                                            f"patch_{rec_id}.diff",
                                            "text/plain",
                                            key=f"download_diff_btn_{rec_id}_medium_{len(diff_results_list) if isinstance(diff_results_list, list) else 1}"
                                        )

                                    if diff_result.get("apply_command"):
                                        st.write(f"**{t('apply_command')}:**")
                                        st.code(diff_result["apply_command"], language="bash")

                                    if diff_result.get("files_affected"):
                                        st.write(f"**{t('affected_files')}:**")
                                        for file_info in diff_result["files_affected"]:
                                            st.markdown(f"- `{file_info['path']}` ({file_info.get('changes', 0)} {t('changes_count')})")

        if low_priority:
            st.info(f"**{t('priority_low', count=len(low_priority))}")
            for i, rec in enumerate(low_priority):
                with st.expander(f"{rec.get('title')} - `{rec.get('location', t('global'))}`"):
                    st.write(f"**{t('rec_category')}**: {rec.get('category')}")
                    st.write(f"**{t('rec_description')}**: {rec.get('description')}")
                    st.write(f"**{t('rec_reason')}**: {rec.get('reason')}")
                    st.write(f"**{t('rec_impact')}**: {rec.get('impact')}")
                    if rec.get('issue'):
                        c1, c2 = st.columns(2)
                        lang = get_language_from_recommendation(rec)
                        with c1:
                            st.write(f"**{t('rec_current_code')}:**")
                            st.code(rec.get('issue'), language=lang)
                        with c2:
                            st.write(f"**{t('rec_fix')}:**")
                            st.code(rec.get('fix'), language=lang)
                    st.write(f"**{t('rec_recommendation')}**: {rec.get('recommendation')}")

                    # 添加自动修复按钮
                    col_btn1, col_btn2 = st.columns([1, 1])
                    with col_btn1:
                        if st.button(t("btn_generate_fix"), key=f"fix_low_{i}"):
                            generate_fix_patch(rec, api_base_url, ai_provider, token)
                    with col_btn2:
                        if st.button(t("btn_generate_diff"), key=f"diff_low_{i}"):
                            generate_diff_patch(rec, api_base_url, ai_provider, token)

                    # 检查并显示修复和diff结果，使用左右并排方式展示
                    rec_id = rec.get('id', 'unknown')
                    fix_result_exists = 'fix_results' in st.session_state and rec_id in st.session_state.fix_results
                    diff_result_exists = 'diff_results' in st.session_state and rec_id in st.session_state.diff_results

                    if fix_result_exists or diff_result_exists:
                        # 使用列布局并排显示修复和diff结果
                        col_fix, col_diff = st.columns(2)

                        with col_fix:
                            if fix_result_exists:
                                fix_results_list = st.session_state.fix_results[rec_id]
                                # 如果是列表，显示最新的修复结果
                                if isinstance(fix_results_list, list) and len(fix_results_list) > 0:
                                    # 提供选择框让用户选择查看哪次修复
                                    if len(fix_results_list) > 1:
                                        fix_selection = st.selectbox(
                                            f"选择修复版本 (共{len(fix_results_list)}次)",
                                            options=range(len(fix_results_list)),
                                            format_func=lambda x: f"第{x+1}次修复",
                                            key=f"fix_select_{rec_id}_low"
                                        )
                                        fix_result = fix_results_list[fix_selection]
                                    else:
                                        fix_result = fix_results_list[0]
                                else:
                                    # 兼容旧格式（如果仍为单个对象）
                                    fix_result = fix_results_list

                                if fix_result.get("fixed_code") or (fix_result.get("diff") and not diff_result_exists):
                                    with st.expander(t("auto_fix_expander"), expanded=True):
                                        if fix_result.get("fixed_code"):
                                            # 根据文件扩展名获取对应的语言名称
                                            file_ext = fix_result.get('file_extension', 'py')
                                            # 使用统一的语言检测函数
                                            language = get_language_from_recommendation({'location': f'file.{file_ext}'})
                                            st.code(fix_result["fixed_code"], language=language)

                                        # 只在没有单独的diff结果时显示diff（避免重复）
                                        if fix_result.get("diff") and not diff_result_exists:
                                            st.write(f"**{t('code_diff')}:**")
                                            st.code(fix_result["diff"], language="diff")

                                        # 下载修复代码按钮
                                        if fix_result.get("fixed_code"):
                                            st.download_button(
                                                t("download_fix"),
                                                fix_result["fixed_code"],
                                                f"fix_{rec_id}.{fix_result.get('file_extension', 'py')}",
                                                "text/plain",
                                                key=f"download_fix_btn_{rec_id}_low_{len(fix_results_list) if isinstance(fix_results_list, list) else 1}"
                                            )

                        with col_diff:
                            if diff_result_exists:
                                diff_results_list = st.session_state.diff_results[rec_id]
                                # 如果是列表，显示最新的diff结果
                                if isinstance(diff_results_list, list) and len(diff_results_list) > 0:
                                    # 提供选择框让用户选择查看哪次diff
                                    if len(diff_results_list) > 1:
                                        diff_selection = st.selectbox(
                                            f"选择Diff版本 (共{len(diff_results_list)}次)",
                                            options=range(len(diff_results_list)),
                                            format_func=lambda x: f"第{x+1}次Diff",
                                            key=f"diff_select_{rec_id}_low"
                                        )
                                        diff_result = diff_results_list[diff_selection]
                                    else:
                                        diff_result = diff_results_list[0]
                                else:
                                    # 兼容旧格式（如果仍为单个对象）
                                    diff_result = diff_results_list

                                with st.expander(t("diff_patch_expander"), expanded=True):
                                    if diff_result.get("diff"):
                                        st.code(diff_result["diff"], language="diff")

                                        # 下载Diff文件
                                        st.download_button(
                                            t("download_diff"),
                                            diff_result["diff"],
                                            f"patch_{rec_id}.diff",
                                            "text/plain",
                                            key=f"download_diff_btn_{rec_id}_low_{len(diff_results_list) if isinstance(diff_results_list, list) else 1}"
                                        )

                                    if diff_result.get("apply_command"):
                                        st.write(f"**{t('apply_command')}:**")
                                        st.code(diff_result["apply_command"], language="bash")

                                    if diff_result.get("files_affected"):
                                        st.write(f"**{t('affected_files')}:**")
                                        for file_info in diff_result["files_affected"]:
                                            st.markdown(f"- `{file_info['path']}` ({file_info.get('changes', 0)} {t('changes_count')})")

        meaningful_strings = [
            s for s in string_recs
            if len(s.strip()) > 10 and  # 确保有实际内容
               not any(bad in s.lower() for bad in
                       ["静态扫描", "costrict", "未发现明显", "恭喜", "扫描未发现", "分析完成"])
        ]

    with tabs[2]:
        st.subheader(t("static_title"))

        scan_results = {}
        if 'static_scan_results' in r:
            scan_results = r['static_scan_results']
        elif 'code_quality' in r and isinstance(r['code_quality'], dict):
            scan_results = r['code_quality'].get('static_scan_results', {})

        if not scan_results or not isinstance(scan_results, dict):
            st.info(t("info_no_static_data"))
        else:
            # 不再过滤安全相关问题，显示所有静态扫描发现的问题
            filtered_scan_results = {}
            for tool, data in scan_results.items():
                # 跳过非 dict
                if not isinstance(data, dict):
                    filtered_scan_results[tool] = data
                    continue

                result_list = data.get('results', [])
                if not isinstance(result_list, list):
                    result_list = []

                # 保留所有问题，不再过滤安全相关问题
                filtered_result_list = []
                for issue in result_list:
                    if isinstance(issue, dict):
                        # 保留所有问题，包括安全问题
                        filtered_result_list.append(issue)
                    else:
                        filtered_result_list.append(issue)

                # 更新问题列表
                filtered_data = data.copy()
                filtered_data['results'] = filtered_result_list
                filtered_scan_results[tool] = filtered_data

            # 显示过滤后的结果
            for tool, data in filtered_scan_results.items():
                # 跳过非 dict
                if not isinstance(data, dict):
                    st.warning(f"{tool.upper()}：{data}")
                    continue

                result_list = data.get('results', [])
                if not isinstance(result_list, list):
                    result_list = []

                count = len(result_list)

                with st.expander(f"{tool.upper()}（{count} {t('records')}）", expanded=(count > 0)):
                    if count == 0:
                        st.info(t("static_no_issues"))
                        continue

                    for issue in result_list[:25]:
                        if not isinstance(issue, dict):
                            st.code(f"[RAW OUTPUT]\n{issue}")
                            continue

                        # 字段提取（专为AI静态扫描优化）
                        code = (
                                issue.get("test_id") or
                                issue.get("test_name") or
                                issue.get("symbol") or
                                issue.get("id") or
                                issue.get("vulnerability_id") or
                                issue.get("cwe", {}).get("id") or
                                issue.get("type") or  # 支持AI静态扫描的type字段
                                issue.get("code") or  # 支持AI静态扫描的专业代码标识
                                "UNKNOWN"
                        )

                        message = (
                                issue.get("issue_text") or
                                issue.get("message") or
                                issue.get("text") or
                                issue.get("advisory") or
                                issue.get("description") or
                                issue.get("more_info") or
                                "No message"
                        ).strip()

                        # 文件位置
                        file_path = issue.get("filename") or issue.get("path") or ""
                        line_num = issue.get("line_number") or issue.get("line") or ""
                        # 确保行号正确显示
                        if file_path and line_num:
                            location = f"{file_path}:**{line_num}**"
                        elif file_path:
                            location = f"{file_path}"
                        else:
                            location = ""

                        # 编程语言
                        language = issue.get("language", "")

                        # 颜色高亮逻辑
                        code_lower = str(code).lower()
                        severity = (
                                issue.get("issue_severity") or
                                issue.get("severity") or
                                "low"
                        ).lower()

                        # 检查是否为安全问题
                        issue_type = str(issue.get("type", "")).lower()
                        issue_text = str(issue.get("issue_text", "")).lower()
                        is_security_issue = (
                                "security" in issue_type or
                                "vulnerability" in issue_type or
                                "漏洞" in issue_text or
                                "安全" in issue_text or
                                "hardcoded" in issue_text or
                                "credential" in issue_text
                        )

                        # 构建显示文本
                        display_text = f"**{code}**: {message}"
                        if language:
                            display_text = f"[{language}] {display_text}"
                        if location:
                            display_text = f"{display_text}:{location}"

                        # 如果是安全问题，添加安全标签
                        if is_security_issue:
                            display_text = f"{display_text}"

                        # 标准化严重程度判断，用于所有类型问题显示
                        if severity in ["high", "critical", "high/critical", "严重", "high risk"]:
                            st.error(display_text)
                        elif severity in ["medium", "moderate", "中等", "medium risk"]:
                            st.warning(display_text)
                        elif severity in ["low", "info", "informational", "低风险", "提示", "low risk"]:
                            st.info(display_text)
                        else:
                            st.markdown(display_text)

    with tabs[3]:
        st.subheader(t("export_title"))

        # 生成更详细的报告内容
        security_issues = r['code_quality'].get('security_issues', [])
        recommendations = r.get('recommendations', [])

        # 确定平台类型
        if "gitee.com" in st.session_state.repo_url.lower():
            platform_name = "Gitee"
        elif "github.com" in st.session_state.repo_url.lower():
            platform_name = "GitHub"
        else:
            platform_name = "代码托管平台"

        md_report = f"""# CodePulse AI 开源项目健康评估报告

**仓库**：[{platform_name}仓库]({st.session_state.repo_url})
**作者**：[{owner_login}]({owner_url})
**分析时间**：{datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}
**分析模式**：{'本地有限分析模式' if is_limited else '完整分析模式'}
**AI生成标识**：本报告由人工智能（AI）生成，内容仅供参考。

## 总体评分：{round(r['overall_score'], 2)}/100

| 评估维度   | 得分                        | 说明                     |
|------------|-----------------------------|--------------------------|
| 总体评分   | {round(r['overall_score'], 2)}/100      | 项目综合健康度           |
| 代码质量   | {round(r['code_quality'].get('score', 0), 2)}/100      | 代码规范性与可维护性     |
| 社区健康   | {round(r['community_health'].get('score', 0), 2)}/100  | 社区活跃度与协作情况     |
| 文档完整   | {round(r['documentation'].get('score', 0), 2)}/100    | 文档质量与可读性         |
| 维护活跃   | {round(r['maintenance'].get('score', 0), 2)}/100      | 项目维护频率             |
| 安全评分   | {round(r['code_quality'].get('security_score', 0), 2)}/100 | 安全漏洞和风险评估   |

**评分占比说明：**
- 代码质量评分：占 **30%** 权重 - 核心功能代码的质量
- 安全漏洞评分：占 **20%** 权重 - 存在高危安全问题会大幅降低此分数
- 社区健康评分：占 **20%** 权重 - 基于stars、forks、issues
- 文档完整评分：占 **15%** 权重 - 文档质量与可读性
- 维护活跃评分：占 **15%** 权重 - 项目维护频率

**注意：** 如果安全漏洞评分为32/100，说明存在严重安全隐患，这是导致总体评分低的主要原因；如果社区健康评分为35/100，说明项目社区活跃度较低（stars和forks较少）；如果文档完整评分为55/100，说明文档质量一般，缺少详细的说明。

## 安全漏洞分析
"""

        if security_issues:
            # 支持中英文严重程度判断
            high_issues = [issue for issue in security_issues if str(issue.get('severity', '')).lower() in ['高', 'high', 'critical', '严重']]
            medium_issues = [issue for issue in security_issues if str(issue.get('severity', '')).lower() in ['中', 'medium', 'moderate', '中等']]
            low_issues = [issue for issue in security_issues if str(issue.get('severity', '')).lower() in ['低', 'low', 'info', 'informational', '低风险', '提示']]

            if high_issues:
                md_report += f"\n###  高危漏洞 ({len(high_issues)}个)\n"
                for issue in high_issues:
                    md_report += f"""
#### {issue.get('title', '未知安全问题')}
- **位置**: `{issue.get('location', '未知位置')}`
- **类型**: {issue.get('type', '安全漏洞')}
- **分析**: {issue.get('analysis', '需要进一步分析')}
- **影响**: {issue.get('impact', '潜在安全风险')}

**问题代码:**
```
{issue.get('issue_code', '# 未提供代码片段')}
```

**修复代码:**
```
{issue.get('fix_code', '# 请手动检查')}
```

**建议**: {issue.get('recommendation', '建议及时修复')}

"""

            if medium_issues:
                md_report += f"\n### 中等风险 ({len(medium_issues)}个)\n"
                for issue in medium_issues:
                    md_report += f"""
#### {issue.get('title', '未知安全问题')}
- **位置**: `{issue.get('location', '未知位置')}`
- **类型**: {issue.get('type', '安全漏洞')}
- **分析**: {issue.get('analysis', '需要进一步分析')}
- **影响**: {issue.get('impact', '潜在安全风险')}

**问题代码:**
```
{issue.get('issue_code', '# 未提供代码片段')}
```

**修复代码:**
```
{issue.get('fix_code', '# 请手动检查')}
```

**建议**: {issue.get('recommendation', '建议及时修复')}

"""

            if low_issues:
                md_report += f"\n### 低风险问题 ({len(low_issues)}个)\n"
                for issue in low_issues:
                    md_report += f"""
#### {issue.get('title', '未知安全问题')}
- **位置**: `{issue.get('location', '未知位置')}`
- **类型**: {issue.get('type', '安全漏洞')}
- **分析**: {issue.get('analysis', '需要进一步分析')}

**建议**: {issue.get('recommendation', '建议及时修复')}

"""
        else:
            md_report += "\n 未检测到明显的安全漏洞\n"

        md_report += f"\n##  静态扫描详细报告\n"

        scan_results = r['code_quality'].get('static_scan_results', {})
        if scan_results and isinstance(scan_results, dict):
            for tool, data in scan_results.items():
                if not isinstance(data, dict):
                    md_report += f"\n### {tool.upper()}\n"
                    md_report += f"{data}\n\n"
                    continue

                result_list = data.get('results', [])
                if not isinstance(result_list, list):
                    result_list = []

                md_report += f"\n### {tool.upper()} ({len(result_list)} 条记录)\n"

                if len(result_list) == 0:
                    md_report += "未发现任何问题，符合业界最佳安全实践\n\n"
                    continue

                for issue in result_list[:25]:  # 限制最多25条记录
                    if not isinstance(issue, dict):
                        md_report += f"```\n{issue}\n```\n\n"
                        continue

                    # 提取问题信息
                    code = (
                            issue.get("test_id") or
                            issue.get("test_name") or
                            issue.get("symbol") or
                            issue.get("id") or
                            issue.get("vulnerability_id") or
                            issue.get("cwe", {}).get("id") or
                            issue.get("type") or
                            issue.get("code") or
                            "UNKNOWN"
                    )

                    message = (
                            issue.get("issue_text") or
                            issue.get("message") or
                            issue.get("text") or
                            issue.get("advisory") or
                            issue.get("description") or
                            issue.get("more_info") or
                            "No message"
                    ).strip()

                    # 文件位置
                    file_path = issue.get("filename") or issue.get("path") or ""
                    line_num = issue.get("line_number") or issue.get("line") or ""
                    location = f"{file_path}:{line_num}".strip(":") if file_path else ""

                    # 编程语言
                    language = issue.get("language", "")

                    # 严重程度
                    severity = (
                            issue.get("issue_severity") or
                            issue.get("severity") or
                            "low"
                    ).lower()

                    # 格式化输出
                    if language:
                        md_report += f"- **[{language}] [{code}]** {message}\n"
                    else:
                        md_report += f"- **[{code}]** {message}\n"
                    if location:
                        md_report += f"  - **位置**: `{location}`\n"

                    # 根据严重程度添加标记
                    # 标准化严重程度判断
                    if severity in ["high", "critical", "high/critical", "严重", "high risk"]:
                        md_report += f"  - **严重程度**: 高危\n"
                    elif severity in ["medium", "moderate", "中等", "medium risk"]:
                        md_report += f"  - **严重程度**: 中等\n"
                    elif severity in ["low", "info", "informational", "低风险", "提示", "low risk"]:
                        md_report += f"  - **严重程度**: 低风险\n"
                    else:
                        md_report += f"  - **严重程度**: 一般\n"
                    md_report += "\n"
        else:
            md_report += "\n未进行静态扫描或扫描无结果\n"

        md_report += f"\n## 优化建议\n"

        # 分离结构化建议和字符串建议
        structured_recs = [rec for rec in recommendations if isinstance(rec, dict)]
        string_recs = [rec for rec in recommendations if isinstance(rec, str)]

        # 新的结构化建议格式
        if structured_recs:
            # 按优先级分组
            high_priority = [rec for rec in structured_recs if rec.get('priority') == '高']
            medium_priority = [rec for rec in structured_recs if rec.get('priority') == '中']
            low_priority = [rec for rec in structured_recs if rec.get('priority') == '低']

            if high_priority:
                md_report += f"\n### 高优先级 ({len(high_priority)}个)\n"
                for rec in high_priority:
                    md_report += f"""
#### {rec.get('title', '优化建议')}
- **位置**: `{rec.get('location', '未知位置')}`
- **类别**: {rec.get('category', '代码优化')}
- **描述**: {rec.get('description', '需要优化')}
- **原因**: {rec.get('reason', '提高代码质量')}
- **影响**: {rec.get('impact', '改善项目质量')}

"""
                    if rec.get('issue'):
                        lang = get_language_from_recommendation(rec)
                        md_report += f"""**当前代码:**
```{lang}
{rec.get('issue')}
```

**建议修复:**
```{lang}
{rec.get('fix')}
```
"""
                    md_report += f"**建议**: {rec.get('recommendation', '请按照上述方案修复')}\n\n"

            if medium_priority:
                md_report += f"\n### 中优先级 ({len(medium_priority)}个)\n"
                for rec in medium_priority:
                    md_report += f"""
#### {rec.get('title', '优化建议')}
- **位置**: `{rec.get('location', '未知位置')}`
- **类别**: {rec.get('category', '代码优化')}
- **描述**: {rec.get('description', '需要优化')}

"""
                    if rec.get('issue'):
                        lang = get_language_from_recommendation(rec)
                        md_report += f"""**建议修复:**
```{lang}
{rec.get('fix')}
```

"""
                    md_report += f"**建议**: {rec.get('recommendation', '请按照上述方案修复')}\n\n"

            if low_priority:
                md_report += f"\n### 低优先级 ({len(low_priority)}个)\n"
                for rec in low_priority:
                    md_report += f"\n#### {rec.get('title', '优化建议')}\n"
                    md_report += f"- **位置**: `{rec.get('location', '未知位置')}`\n"
                    md_report += f"- **类别**: {rec.get('category', '代码优化')}\n"
                    md_report += f"- **描述**: {rec.get('description', '需要优化')}\n"

                    if rec.get('issue'):
                        lang = get_language_from_recommendation(rec)
                        md_report += f"\n**当前代码:**\n```{lang}\n{rec.get('issue')}\n```\n"
                        md_report += f"\n**建议修复:**\n```{lang}\n{rec.get('fix')}\n```\n"

                    md_report += f"\n**建议**: {rec.get('recommendation', '请按照上述方案修复')}\n"
        else:
            # 优秀项目高端结语
            md_report += "\n### 专家结论\n"
            md_report += "- 此项目已达到业界顶尖水平，代码质量、安全性、架构设计均无可挑剔\n"
            md_report += "- 社区活跃、文档完善、测试覆盖全面，属于标杆级开源项目\n"
            md_report += "- 建议继续保持当前优秀实践与开发节奏\n"

    col_d1, col_d2 = st.columns(2)
    with col_d1:
        st.download_button(t("download_md"), md_report,
                           f"CodePulse_Report_{full_name.replace('/', '_')}.md", "text/markdown",
                           key="download_md_report")
    with col_d2:

        if st.button(t("generate_pdf_btn"), use_container_width=True):
            with st.spinner(t("generating_pdf")):
                try:
                    # 1. 将 Markdown 转换为 HTML
                    html_content = markdown2.markdown(
                        md_report,
                        extras=["tables", "fenced-code-blocks", "break-on-newline"]
                    )

                    # 2. 创建临时目录存放HTML文件
                    import tempfile

                    temp_dir = tempfile.mkdtemp()

                    # 3. 构建HTML内容
                    full_html = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <meta charset="utf-8">
                        <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
                        <meta name="ai-generated" content="true">
                        <meta name="generator" content="CodePulse AI">
                        <style>
                            * {{
                                margin: 0;
                                padding: 0;
                                box-sizing: border-box;
                            }}
                            body {{
                                font-family: 'SimSun', 'Microsoft YaHei', 'STSong-Light', 'MSung-Light', 'PingFang SC', sans-serif;
                                padding: 0.5cm;
                                line-height: 1.4;
                                font-size: 10px;
                            }}
                            p {{
                                margin: 0.3em 0;
                            }}
                            ul, ol {{
                                margin: 0.3em 0;
                                padding-left: 1.2em;
                            }}
                            li {{
                                margin: 0.15em 0;
                            }}
                            h1, h2, h3, h4, h5, h6 {{
                                font-family: 'SimSun', 'Microsoft YaHei', 'STSong-Light', 'MSung-Light', 'PingFang SC', sans-serif;
                                color: #2c3e50;
                                margin-top: 0.5em;
                                margin-bottom: 0.3em;
                            }}
                            pre, code {{
                                font-family: 'Consolas', 'Courier New', monospace;
                                background: #f8f8f8;
                                padding: 5px;
                                border-radius: 2px;
                                font-size: 9px;
                                overflow-x: auto;
                            }}
                            table {{
                                border-collapse: collapse;
                                width: 100%;
                                margin: 0.5em 0;
                            }}
                            th, td {{
                                border: 1px solid #ddd;
                                padding: 5px;
                                text-align: left;
                            }}
                            th {{
                                background-color: #f2f2f2;
                            }}
                            .markdown-table {{
                                font-family: 'SimSun', 'Microsoft YaHei', 'STSong-Light', 'MSung-Light', 'PingFang SC', sans-serif;
                            }}
                            .ai-disclaimer {{
                                margin-top: 2em;
                                padding: 0.5em;
                                border-top: 1px solid #ccc;
                                font-size: 9px;
                                color: #666;
                                text-align: center;
                            }}
                        </style>
                    </head>
                    <body>
                        {html_content}
                        <div class="ai-disclaimer">
                             本报告由人工智能（AI）生成，内容仅供参考。
                        </div>
                    </body>
                    </html>
                    """

                    # 5. 使用 pdfkit 生成 PDF
                    # 配置 wkhtmltopdf 路径（如果不在 PATH 中）
                    try:
                        config = pdfkit.configuration(wkhtmltopdf='C:/Program Files/wkhtmltopdf/bin/wkhtmltopdf.exe')
                    except:
                        config = None  # 使用自动检测

                    options = {
                        'encoding': 'UTF-8',
                        'page-size': 'A4',
                        'margin-top': '0.2cm',
                        'margin-right': '0.2cm',
                        'margin-bottom': '0.2cm',
                        'margin-left': '0.2cm',
                        'quiet': '',
                    }

                    pdf_data = pdfkit.from_string(full_html, False, options=options, configuration=config)

                    if len(pdf_data) == 0:
                        raise Exception(t("pdf_empty"))

                    # 清理临时文件
                    import shutil

                    shutil.rmtree(temp_dir)

                    # 4. 提供下载按钮
                    b64 = base64.b64encode(pdf_data).decode()
                    href = f'<a href="data:application/pdf;base64,{b64}" download="CodePulse_{full_name.replace("/", "_")}.pdf">{t("export_download", format="PDF")}</a>'
                    st.success(t("success_pdf"))
                    st.markdown(href, unsafe_allow_html=True)

                except Exception as e:
                    st.error(f"PDF生成失败：{str(e)}")
