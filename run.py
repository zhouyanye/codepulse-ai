import argparse
import subprocess
import sys
import os
import logging
from dotenv import load_dotenv

# 设置日志
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 配置 uvicorn 日志格式
def setup_uvicorn_logging():
    import sys
    import logging
    from uvicorn.logging import AccessFormatter
    
    # 为 uvicorn 配置统一的日志格式
    for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error"]:
        lg = logging.getLogger(logger_name)
        if lg.handlers:
            lg.handlers.clear()
        
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        lg.addHandler(handler)
        lg.setLevel(logging.INFO)
        lg.propagate = False  

try:
    load_dotenv()
    logger.info("环境变量加载成功")
except Exception as e:
    logger.warning(f"加载环境变量失败: {e}")

# 启用Clash代理（默认7890端口）
# os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"
# os.environ["HTTP_PROXY"] = "http://127.0.0.1:7890"


def run_fastapi():
    """启动FastAPI后端"""
    setup_uvicorn_logging()  # 配置 uvicorn 日志格式
    logger.info("启动FastAPI后端服务...")
    print("API文档: http://localhost:8000/docs")
    try:
        subprocess.run([
            sys.executable, "-m", "uvicorn",
            "app.main:app",
            "--host", "0.0.0.0",
            "--port", "8000",
            "--log-level", "info"
        ], check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"启动FastAPI服务失败: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("FastAPI服务已停止")


def run_streamlit():
    """启动Streamlit前端"""
    logger.info("启动Streamlit前端...")
    print("前端界面: http://localhost:8501")
    try:
        subprocess.run([
            sys.executable, "-m", "streamlit",
            "run", "web/main.py",
            "--server.port", "8501",
            "--server.address", "0.0.0.0"
        ], check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"启动Streamlit前端失败: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Streamlit前端已停止")


def run_celery():
    """启动Celery worker"""
    logger.info("启动Celery worker...")
    try:
        from app.core.config import settings
        logger.info(f"Broker: {settings.CELERY_BROKER_URL}")
        subprocess.run([
            sys.executable, "-m", "celery",
            "-A", "app.celery",
            "worker",
            "--loglevel=info",
            "--pool=solo",
        ], check=True)
    except ImportError as e:
        logger.error(f"导入配置失败: {e}")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        logger.error(f"启动Celery worker失败: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Celery worker已停止")


def run_celery_beat():
    """启动Celery beat（定时任务）"""
    logger.info("启动Celery beat...")
    try:
        subprocess.run([
            sys.executable, "-m", "celery",
            "-A", "app.celery",
            "beat",
            "--loglevel=info"
        ], check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"启动Celery beat失败: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Celery beat已停止")


def run_all():
    """同时启动所有服务"""
    logger.info("同时启动所有服务...")
    
    # 创建子进程运行各项服务
    processes = []
    
    try:
        # 启动FastAPI
        fastapi_process = subprocess.Popen([
            sys.executable, "-m", "uvicorn",
            "app.main:app",
            "--host", "0.0.0.0",
            "--port", "8000",
        ])
        processes.append(fastapi_process)
        logger.info("FastAPI后端已启动 PID: %d", fastapi_process.pid)
        
        # 启动Celery
        celery_process = subprocess.Popen([
            sys.executable, "-m", "celery",
            "-A", "app.celery",
            "worker",
            "--loglevel=info",
            "--pool=solo",
        ])
        processes.append(celery_process)
        logger.info("Celery worker已启动 PID: %d", celery_process.pid)
        
        # 启动Streamlit
        streamlit_process = subprocess.Popen([
            sys.executable, "-m", "streamlit",
            "run", "web/main.py",
            "--server.port", "8501",
            "--server.address", "0.0.0.0"
        ])
        processes.append(streamlit_process)
        logger.info("Streamlit前端已启动 PID: %d", streamlit_process.pid)
        
        # 等待所有进程
        for process in processes:
            process.wait()
            
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在停止所有服务...")
        for process in processes:
            if process.poll() is None:  # 检查进程是否仍在运行
                process.terminate()
                try:
                    process.wait(timeout=5)  # 等待进程终止
                except subprocess.TimeoutExpired:
                    logger.warning("进程未能在规定时间内终止，发送强制终止信号")
                    process.kill()
        logger.info("所有服务已停止")


def check_git_availability():
    """检查Git是否可用"""
    try:
        result = subprocess.run(["git", "--version"], capture_output=True, text=True, check=False)
        if result.returncode == 0:
            logger.info(f"Git可用: {result.stdout.strip()}")
            return True
        else:
            logger.warning("Git不可用或未安装。某些功能（如仓库克隆）将不可用。")
            logger.warning("请安装Git并确保其在系统PATH中。")
            print("警告: Git不可用或未安装。某些功能（如仓库克隆）将不可用。")
            print("请安装Git并确保其在系统PATH中。")
            return False
    except FileNotFoundError:
        logger.warning("Git命令未找到。某些功能（如仓库克隆）将不可用。")
        logger.warning("请安装Git并确保其在系统PATH中。")
        print("警告: Git命令未找到。某些功能（如仓库克隆）将不可用。")
        print("请安装Git并确保其在系统PATH中。")
        return False
    except Exception as e:
        logger.warning(f"检查Git可用性时出错: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="CodePulse AI 启动器")
    parser.add_argument(
        "--component",
        choices=["fastapi", "streamlit", "celery", "celery-beat", "all"],
        help="选择要启动的组件"
    )
    
    args = parser.parse_args()
    
    # 检查Git可用性
    git_available = check_git_availability()
    if not git_available:
        logger.warning("Git不可用，某些功能（如仓库克隆）将不可用。")
    
    # 检查必要环境变量
    github_token = os.getenv("GITHUB_TOKEN")
    gitee_token = os.getenv("GITEE_TOKEN")
    if not github_token and not gitee_token:
        logger.warning("未设置 GITHUB_TOKEN 或 GITEE_TOKEN 环境变量，GitHub 和 Gitee API调用将受限")
    
    if args.component == "fastapi":
        run_fastapi()
    elif args.component == "streamlit":
        run_streamlit()
    elif args.component == "celery":
        run_celery()
    elif args.component == "celery-beat":
        run_celery_beat()
    elif args.component == "all":
        run_all()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
