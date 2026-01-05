import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.celery_utils import get_task_status

task_id = "2d1285bb-c64d-48b9-81bf-79adf6f717b5"
status = get_task_status(task_id)
print("Task status:", status)
