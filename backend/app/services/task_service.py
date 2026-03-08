import uuid as uuid_lib
from typing import Optional, List
from sqlalchemy.orm import Session

from ..models.task import Task, TaskType, TaskStatus
from ..models.file import File


class TaskService:
    def __init__(self, db: Session):
        self.db = db
    
    def create(
        self,
        session_uuid: str,
        task_type: TaskType,
        options: dict = None,
        name: str = None
    ) -> Task:
        """Create a new task."""
        task_id = str(uuid_lib.uuid4())
        
        task = Task(
            id=task_id,
            session_uuid=session_uuid,
            type=task_type,
            status=TaskStatus.PENDING,
            name=name
        )
        
        if options:
            task.set_options(options)
        
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        
        return task
    
    def get(self, task_id: str) -> Optional[Task]:
        """Get task by ID."""
        return self.db.query(Task).filter(Task.id == task_id).first()
    
    def get_by_session(self, session_uuid: str) -> List[Task]:
        """Get all tasks for a session."""
        return self.db.query(Task).filter(
            Task.session_uuid == session_uuid
        ).order_by(Task.created_at.desc()).all()
    
    def get_by_status(self, status: TaskStatus) -> List[Task]:
        """Get all tasks with specific status."""
        return self.db.query(Task).filter(Task.status == status).all()
    
    def count_by_status(self, status: TaskStatus) -> int:
        """Count tasks with specific status."""
        return self.db.query(Task).filter(Task.status == status).count()
    
    def get_queue_info(self, task_id: str, session_uuid: str) -> dict:
        """
        Get queue position info for a task.
        Returns user-level and global queue positions for pending/processing tasks.
        """
        task = self.get(task_id)
        if not task:
            return None
        
        # Only calculate queue info for pending or processing tasks
        if task.status not in [TaskStatus.PENDING, TaskStatus.PROCESSING]:
            return {
                "user_position": None,
                "user_queue_length": 0,
                "global_position": None,
                "global_queue_length": 0
            }
        
        # Get all pending and processing tasks, ordered by creation time
        queued_tasks = self.db.query(Task).filter(
            Task.status.in_([TaskStatus.PENDING, TaskStatus.PROCESSING])
        ).order_by(Task.created_at.asc()).all()
        
        # Calculate global queue position
        global_position = None
        for i, t in enumerate(queued_tasks, 1):
            if t.id == task_id:
                global_position = i
                break
        
        # Calculate user-level queue position (tasks for this session)
        user_queued_tasks = [t for t in queued_tasks if t.session_uuid == session_uuid]
        user_position = None
        for i, t in enumerate(user_queued_tasks, 1):
            if t.id == task_id:
                user_position = i
                break
        
        return {
            "user_position": user_position,
            "user_queue_length": len(user_queued_tasks),
            "global_position": global_position,
            "global_queue_length": len(queued_tasks)
        }
    
    def update_status(
        self,
        task_id: str,
        status: TaskStatus,
        error_message: Optional[str] = None,
        cli_log: Optional[str] = None
    ) -> Optional[Task]:
        """Update task status."""
        task = self.get(task_id)
        if task:
            task.status = status
            if status == TaskStatus.PROCESSING:
                task.mark_processing()
            elif status == TaskStatus.COMPLETED:
                task.mark_completed(cli_log=cli_log)
            elif status == TaskStatus.FAILED:
                task.mark_failed(error_message or "Unknown error", cli_log=cli_log)
            
            self.db.commit()
            self.db.refresh(task)
        return task
    
    def update_cli_log(self, task_id: str, cli_log: str) -> Optional[Task]:
        """Update CLI log for a task."""
        task = self.get(task_id)
        if task:
            task.cli_log = cli_log
            self.db.commit()
            self.db.refresh(task)
        return task
    
    def add_output_file(self, task_id: str, file: File):
        """Associate output file with task."""
        file.task_id = task_id
        self.db.commit()
    
    def delete(self, task_id: str) -> bool:
        """Delete task."""
        task = self.get(task_id)
        if task:
            self.db.delete(task)
            self.db.commit()
            return True
        return False