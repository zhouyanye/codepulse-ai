import asyncio
import logging
import threading
import json
import uuid
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, DateTime, Boolean, create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base, SessionLocal
from app.core.config import settings

logger = logging.getLogger(__name__)


class TaskRecord(Base):
    """任务记录模型（使用共享的数据库连接）"""
    __tablename__ = "task_records"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String, unique=True, index=True)
    status = Column(String, default="initializing")
    progress = Column(Integer, default=0)
    message = Column(Text)
    cost_estimate = Column(Text)  # JSON字符串
    result = Column(Text)  # JSON字符串
    error = Column(Text)
    cancelled = Column(Boolean, default=False)
    ai_provider = Column(String)
    repo_url = Column(String)
    include_static_scan = Column(Boolean, default=True)
    github_token = Column(String)
    gitee_token = Column(String)
    user_confirmed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class TaskManager:
    """任务管理器 - 使用共享的数据库连接持久化存储任务状态"""
    
    def __init__(self):
        # 使用共享的 SessionLocal，不重复创建引擎
        self.SessionLocal = SessionLocal
        self.lock = threading.Lock()
        
        # 确保表已创建
        from app.core.database import engine
        Base.metadata.create_all(bind=engine, checkfirst=True)
        
    def _serialize_to_json(self, data: Any) -> Optional[str]:
        """将数据序列化为JSON字符串"""
        if data is None:
            return None
        if isinstance(data, str):
            return data
        try:
            return json.dumps(data, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"JSON序列化失败: {e}")
            return json.dumps({"error": f"序列化失败: {str(e)}"})
    
    def _deserialize_from_json(self, data: Optional[str]) -> Any:
        """将JSON字符串反序列化为Python对象"""
        if data is None:
            return None
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return data
    
    def create_task(self, task_data: Dict[str, Any]) -> str:
        """创建新任务"""
        task_id = str(uuid.uuid4())
        db = self.SessionLocal()
        try:
            task_record = TaskRecord(
                task_id=task_id,
                status=task_data.get("status", "initializing"),
                progress=task_data.get("progress", 0),
                message=task_data.get("message", "任务初始化中"),
                cost_estimate=self._serialize_to_json(task_data.get("cost_estimate")),
                result=self._serialize_to_json(task_data.get("result")),
                error=task_data.get("error"),
                cancelled=task_data.get("cancelled", False),
                ai_provider=task_data.get("ai_provider"),
                repo_url=task_data.get("repo_url"),
                include_static_scan=task_data.get("include_static_scan", True),
                github_token=task_data.get("github_token"),
                gitee_token=task_data.get("gitee_token"),
                user_confirmed=task_data.get("user_confirmed", False)
            )
            db.add(task_record)
            db.commit()
            logger.info(f"任务创建成功: {task_id}")
        except Exception as e:
            logger.error(f"创建任务失败: {e}", exc_info=True)
            db.rollback()
        finally:
            db.close()
        return task_id
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        db = self.SessionLocal()
        try:
            task_record = db.query(TaskRecord).filter(TaskRecord.task_id == task_id).first()
            if task_record:
                return {
                    "status": task_record.status,
                    "progress": task_record.progress,
                    "message": task_record.message,
                    "cost_estimate": self._deserialize_from_json(task_record.cost_estimate),
                    "result": self._deserialize_from_json(task_record.result),
                    "error": task_record.error,
                    "cancelled": task_record.cancelled,
                    "ai_provider": task_record.ai_provider,
                    "repo_url": task_record.repo_url,
                    "include_static_scan": task_record.include_static_scan,
                    "github_token": task_record.github_token,
                    "gitee_token": task_record.gitee_token,
                    "user_confirmed": task_record.user_confirmed
                }
            return None
        except Exception as e:
            logger.error(f"获取任务失败: {e}", exc_info=True)
            return None
        finally:
            db.close()
    
    def update_task(self, task_id: str, **kwargs) -> bool:
        """更新任务状态"""
        db = self.SessionLocal()
        try:
            task_record = db.query(TaskRecord).filter(TaskRecord.task_id == task_id).first()
            if not task_record:
                return False
            
            # 处理需要序列化的字段
            serialize_fields = {"cost_estimate", "result"}
            for key, value in kwargs.items():
                if hasattr(task_record, key):
                    if key in serialize_fields:
                        setattr(task_record, key, self._serialize_to_json(value))
                    else:
                        setattr(task_record, key, value)
            
            task_record.updated_at = datetime.now(timezone.utc)
            db.commit()
            return True
        except Exception as e:
            logger.error(f"更新任务失败: {e}", exc_info=True)
            db.rollback()
            return False
        finally:
            db.close()
    
    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        db = self.SessionLocal()
        try:
            task_record = db.query(TaskRecord).filter(TaskRecord.task_id == task_id).first()
            if task_record:
                db.delete(task_record)
                db.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"删除任务失败: {e}", exc_info=True)
            db.rollback()
            return False
        finally:
            db.close()
    
    def cleanup_expired_tasks(self, hours: int = 24) -> int:
        """清理过期任务"""
        from datetime import timedelta
        db = self.SessionLocal()
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            expired_tasks = db.query(TaskRecord).filter(TaskRecord.updated_at < cutoff_time).all()
            count = len(expired_tasks)
            
            for task in expired_tasks:
                db.delete(task)
            
            db.commit()
            logger.info(f"清理了 {count} 个过期任务")
            return count
        except Exception as e:
            logger.error(f"清理过期任务失败: {e}", exc_info=True)
            db.rollback()
            return 0
        finally:
            db.close()


# 全局任务管理器实例
task_manager = TaskManager()