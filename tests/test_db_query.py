"""
数据库查询工具
用于查看和管理 CodePulse AI 的任务记录数据库
"""
import os
import sys
import json
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from models.task_manager import TaskRecord, TaskManager
from app.core.config import settings


def connect_db():
    """连接到数据库"""
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine, SessionLocal


def list_all_tasks():
    """列出所有任务记录"""
    engine, SessionLocal = connect_db()
    db = SessionLocal()

    try:
        tasks = db.query(TaskRecord).order_by(TaskRecord.created_at.desc()).all()

        if not tasks:
            print("没有找到任务记录")
            return

        print(f"找到 {len(tasks)} 个任务记录:")
        print("-" * 120)

        for i, task in enumerate(tasks, 1):
            print(f"任务 {i}:")
            print(f"  任务ID: {task.task_id}")
            print(f"  状态: {task.status}")
            print(f"  进度: {task.progress}%")
            print(f"  消息: {task.message}")
            print(f"  AI提供商: {task.ai_provider}")
            print(f"  仓库URL: {task.repo_url}")
            print(f"  包含静态扫描: {'是' if task.include_static_scan else '否'}")
            print(f"  用户已确认: {'是' if task.user_confirmed else '否'}")
            print(f"  已取消: {'是' if task.cancelled else '否'}")
            print(f"  创建时间: {task.created_at}")
            print(f"  更新时间: {task.updated_at}")

            if task.cost_estimate:
                try:
                    cost_data = json.loads(task.cost_estimate)
                    print(f"  成本估算: {cost_data}")
                except:
                    print(f"  成本估算: {task.cost_estimate}")

            print("-" * 120)

    finally:
        db.close()


def get_task_by_id(task_id):
    """根据任务ID获取任务详情"""
    engine, SessionLocal = connect_db()
    db = SessionLocal()

    try:
        task = db.query(TaskRecord).filter(TaskRecord.task_id == task_id).first()

        if not task:
            print(f"未找到任务ID为 '{task_id}' 的记录")
            return

        print(f"任务详情:")
        print(f"  任务ID: {task.task_id}")
        print(f"  状态: {task.status}")
        print(f"  进度: {task.progress}%")
        print(f"  消息: {task.message}")
        print(f"  AI提供商: {task.ai_provider}")
        print(f"  仓库URL: {task.repo_url}")
        print(f"  包含静态扫描: {'是' if task.include_static_scan else '否'}")
        print(f"  用户已确认: {'是' if task.user_confirmed else '否'}")
        print(f"  已取消: {'是' if task.cancelled else '否'}")
        print(f"  错误: {task.error}")
        print(f"  创建时间: {task.created_at}")
        print(f"  更新时间: {task.updated_at}")

        if task.cost_estimate:
            print(f"  成本估算: {task.cost_estimate}")
        if task.result:
            print(f"  结果: {task.result[:200]}...")  # 只显示前200个字符

    finally:
        db.close()


def delete_task_by_id(task_id):
    """根据任务ID删除任务"""
    task_manager = TaskManager()
    success = task_manager.delete_task(task_id)

    if success:
        print(f"任务 '{task_id}' 已成功删除")
    else:
        print(f"删除任务 '{task_id}' 失败，可能该任务不存在")


def cleanup_expired_tasks(hours=24):
    """清理过期任务"""
    task_manager = TaskManager()
    count = task_manager.cleanup_expired_tasks(hours)
    print(f"已清理 {count} 个过期任务（超过 {hours} 小时未更新）")


def main():
    """主函数"""
    print("CodePulse AI 数据库查询工具")
    print("=" * 50)

    if len(sys.argv) < 2:
        print("用法:")
        print("  python test_db_query.py list                    # 列出所有任务")
        print("  python test_db_query.py get <task_id>          # 获取指定任务详情")
        print("  python test_db_query.py delete <task_id>       # 删除指定任务")
        print("  python test_db_query.py cleanup [hours]        # 清理过期任务（默认24小时）")
        return

    command = sys.argv[1].lower()

    if command == "list":
        list_all_tasks()
    elif command == "get" and len(sys.argv) > 2:
        task_id = sys.argv[2]
        get_task_by_id(task_id)
    elif command == "delete" and len(sys.argv) > 2:
        task_id = sys.argv[2]
        delete_task_by_id(task_id)
    elif command == "cleanup":
        hours = int(sys.argv[2]) if len(sys.argv) > 2 else 24
        cleanup_expired_tasks(hours)
    else:
        print("无效的命令或参数")
        print("用法:")
        print("  python test_db_query.py list                    # 列出所有任务")
        print("  python test_db_query.py get <task_id>          # 获取指定任务详情")
        print("  python test_db_query.py delete <task_id>       # 删除指定任务")
        print("  python test_db_query.py cleanup [hours]        # 清理过期任务（默认24小时）")


if __name__ == "__main__":
    main()
