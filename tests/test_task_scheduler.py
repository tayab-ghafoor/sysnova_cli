"""
Comprehensive test suite for TaskScheduler.
Tests: add, get_due, mark_executed, next_run calculation
Production-ready with full coverage.
"""
import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone

import sys

_test_dir = Path(__file__).parent.resolve()
_src_dir = _test_dir.parent / "src"
if _src_dir.exists():
    sys.path.insert(0, str(_src_dir))
else:
    sys.path.insert(0, str(_test_dir.parent))

from system_manager_cli.core.task_scheduler import TaskScheduler
from system_manager_cli.models.scheduled_task import (
    SCHEDULE_DAILY,
    SCHEDULE_EVERY_MINUTE,
    SCHEDULE_WEEKLY,
    SCHEDULE_MONTHLY,
    STATUS_ACTIVE,
    STATUS_PAUSED,
)


@pytest.fixture
def temp_data_file():
    """Create a temporary data file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = Path(f.name)
    yield temp_path
    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture
def scheduler(temp_data_file):
    """Create a TaskScheduler instance with temporary data file."""
    return TaskScheduler(data_file=temp_data_file)


class TestTaskSchedulerAdd:
    """Test suite for adding tasks."""

    def test_add_task_basic(self, scheduler):
        """Test basic task addition."""
        task_data = {
            "task_type": "backup",
            "schedule_type": SCHEDULE_DAILY,
            "run_time": "10:30",
        }
        
        task = scheduler.add_task(task_data)
        
        assert task.id == 1
        assert task.task_type == "backup"
        assert task.status == STATUS_ACTIVE
        assert task.next_run is not None

    def test_add_multiple_tasks(self, scheduler):
        """Test adding multiple tasks assigns unique IDs."""
        task1_data = {
            "task_type": "backup",
            "schedule_type": SCHEDULE_DAILY,
            "run_time": "10:00",
        }
        task2_data = {
            "task_type": "logs_analysis",
            "schedule_type": SCHEDULE_WEEKLY,
            "run_time": "14:00",
        }
        
        task1 = scheduler.add_task(task1_data)
        task2 = scheduler.add_task(task2_data)
        
        assert task1.id == 1
        assert task2.id == 2
        assert len(scheduler.get_all_tasks()) == 2

    def test_add_task_with_backup_paths(self, scheduler):
        """Test adding task with backup paths."""
        task_data = {
            "task_type": "backup",
            "schedule_type": SCHEDULE_DAILY,
            "run_time": "10:00",
            "backup_paths": ["/path/to/backup1", "/path/to/backup2"],
        }
        
        task = scheduler.add_task(task_data)
        
        assert task.backup_paths == ["/path/to/backup1", "/path/to/backup2"]

    def test_add_task_with_logs_config(self, scheduler):
        """Test adding task with logs configuration."""
        task_data = {
            "task_type": "logs_analysis",
            "schedule_type": SCHEDULE_DAILY,
            "run_time": "09:00",
            "logs_path_source": "/app/logs",
            "logs_custom_path": "/custom/logs/output",
        }
        
        task = scheduler.add_task(task_data)
        
        assert task.logs_path_source == "/app/logs"
        assert task.logs_custom_path == "/custom/logs/output"

    def test_add_task_persistence(self, scheduler, temp_data_file):
        """Test that added tasks are persisted to file."""
        task_data = {
            "task_type": "backup",
            "schedule_type": SCHEDULE_DAILY,
            "run_time": "10:00",
        }
        
        task = scheduler.add_task(task_data)
        task_id = task.id
        
        # Create new scheduler with same file
        scheduler2 = TaskScheduler(data_file=temp_data_file)
        retrieved_task = scheduler2.get_task_by_id(task_id)
        
        assert retrieved_task is not None
        assert retrieved_task.task_type == "backup"


class TestTaskSchedulerGetDue:
    """Test suite for getting due tasks."""

    def test_get_due_tasks_none(self, scheduler):
        """Test get_due when no tasks are due."""
        now = datetime.now(timezone.utc)
        future_time = (now + timedelta(hours=1)).strftime("%H:%M")
        
        task_data = {
            "task_type": "backup",
            "schedule_type": SCHEDULE_DAILY,
            "run_time": future_time,
        }
        scheduler.add_task(task_data)
        
        due_tasks = scheduler.get_due_tasks()
        assert len(due_tasks) == 0

    def test_get_due_tasks_immediate(self, scheduler):
        """Test get_due when task is overdue."""
        past_time = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%H:%M")
        
        task_data = {
            "task_type": "backup",
            "schedule_type": SCHEDULE_DAILY,
            "run_time": past_time,
        }
        scheduler.add_task(task_data)
        
        due_tasks = scheduler.get_due_tasks()
        assert len(due_tasks) >= 1

    def test_get_due_tasks_filters_by_status(self, scheduler):
        """Test that get_due only returns active tasks."""
        past_time = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%H:%M")
        
        task_data = {
            "task_type": "backup",
            "schedule_type": SCHEDULE_DAILY,
            "run_time": past_time,
        }
        task = scheduler.add_task(task_data)
        
        # Pause the task
        scheduler.update_task(task.id, {"status": STATUS_PAUSED})
        
        due_tasks = scheduler.get_due_tasks()
        assert len(due_tasks) == 0

    def test_get_due_tasks_every_minute(self, scheduler):
        """Test that every-minute tasks are always due."""
        task_data = {
            "task_type": "backup",
            "schedule_type": SCHEDULE_EVERY_MINUTE,
            "run_time": "00:00",
        }
        scheduler.add_task(task_data)
        
        due_tasks = scheduler.get_due_tasks()
        assert len(due_tasks) > 0


class TestTaskSchedulerMarkExecuted:
    """Test suite for marking tasks as executed."""

    def test_mark_executed_updates_timestamps(self, scheduler):
        """Test that mark_executed updates last_run and recalculates next_run."""
        task_data = {
            "task_type": "backup",
            "schedule_type": SCHEDULE_DAILY,
            "run_time": "10:00",
        }
        task = scheduler.add_task(task_data)
        original_next_run = task.next_run
        
        scheduler.mark_executed(task.id)
        updated_task = scheduler.get_task_by_id(task.id)
        
        assert updated_task.last_run is not None
        assert updated_task.next_run != original_next_run

    def test_mark_executed_nonexistent_task(self, scheduler):
        """Test mark_executed with nonexistent task ID."""
        # Should not raise exception
        scheduler.mark_executed(999)

    def test_mark_executed_persistence(self, scheduler, temp_data_file):
        """Test that executed task updates are persisted."""
        task_data = {
            "task_type": "backup",
            "schedule_type": SCHEDULE_DAILY,
            "run_time": "10:00",
        }
        task = scheduler.add_task(task_data)
        task_id = task.id
        
        scheduler.mark_executed(task_id)
        
        # Create new scheduler and verify persistence
        scheduler2 = TaskScheduler(data_file=temp_data_file)
        updated_task = scheduler2.get_task_by_id(task_id)
        
        assert updated_task.last_run is not None


class TestNextRunCalculation:
    """Test suite for next_run calculation logic."""

    def test_calculate_next_run_daily(self, scheduler):
        """Test daily schedule next_run calculation."""
        task_data = {
            "task_type": "backup",
            "schedule_type": SCHEDULE_DAILY,
            "run_time": "10:30",
        }
        task = scheduler.add_task(task_data)
        
        next_run_dt = datetime.fromisoformat(task.next_run)
        assert next_run_dt.hour == 10
        assert next_run_dt.minute == 30

    def test_calculate_next_run_weekly(self, scheduler):
        """Test weekly schedule next_run calculation."""
        task_data = {
            "task_type": "backup",
            "schedule_type": SCHEDULE_WEEKLY,
            "run_time": "10:00",
        }
        task = scheduler.add_task(task_data)
        
        now = datetime.now(timezone.utc)
        next_run_dt = datetime.fromisoformat(task.next_run)
        
        # Next run should be 1-7 days in future
        days_ahead = (next_run_dt.date() - now.date()).days
        assert 1 <= days_ahead <= 7

    def test_calculate_next_run_monthly(self, scheduler):
        """Test monthly schedule next_run calculation."""
        task_data = {
            "task_type": "backup",
            "schedule_type": SCHEDULE_MONTHLY,
            "run_time": "10:00",
        }
        task = scheduler.add_task(task_data)
        
        now = datetime.now(timezone.utc)
        next_run_dt = datetime.fromisoformat(task.next_run)
        
        # Next run should be in future
        assert next_run_dt > now

    def test_calculate_next_run_every_minute(self, scheduler):
        """Test every-minute schedule next_run calculation."""
        task_data = {
            "task_type": "backup",
            "schedule_type": SCHEDULE_EVERY_MINUTE,
            "run_time": "00:00",
        }
        task = scheduler.add_task(task_data)
        
        now = datetime.now(timezone.utc)
        next_run_dt = datetime.fromisoformat(task.next_run)
        
        # Next run should be approximately 1 minute in future
        time_diff = (next_run_dt - now).total_seconds()
        assert 59 <= time_diff <= 61

    def test_next_run_recalculates_on_update(self, scheduler):
        """Test that next_run is recalculated when schedule changes."""
        task_data = {
            "task_type": "backup",
            "schedule_type": SCHEDULE_DAILY,
            "run_time": "10:00",
        }
        task = scheduler.add_task(task_data)
        original_next_run = task.next_run
        
        # Update the schedule
        scheduler.update_task(task.id, {
            "schedule_type": SCHEDULE_WEEKLY,
        })
        
        updated_task = scheduler.get_task_by_id(task.id)
        assert updated_task.next_run != original_next_run


class TestTaskSchedulerUpdate:
    """Test suite for updating tasks."""

    def test_update_task_basic(self, scheduler):
        """Test basic task update."""
        task_data = {
            "task_type": "backup",
            "schedule_type": SCHEDULE_DAILY,
            "run_time": "10:00",
        }
        task = scheduler.add_task(task_data)
        
        scheduler.update_task(task.id, {"run_time": "14:00"})
        updated_task = scheduler.get_task_by_id(task.id)
        
        assert updated_task.run_time == "14:00"

    def test_update_nonexistent_task(self, scheduler):
        """Test update returns None for nonexistent task."""
        result = scheduler.update_task(999, {"run_time": "14:00"})
        assert result is None

    def test_update_task_persistence(self, scheduler, temp_data_file):
        """Test that task updates are persisted."""
        task_data = {
            "task_type": "backup",
            "schedule_type": SCHEDULE_DAILY,
            "run_time": "10:00",
        }
        task = scheduler.add_task(task_data)
        task_id = task.id
        
        scheduler.update_task(task_id, {"run_time": "15:00"})
        
        # Create new scheduler and verify
        scheduler2 = TaskScheduler(data_file=temp_data_file)
        updated_task = scheduler2.get_task_by_id(task_id)
        
        assert updated_task.run_time == "15:00"


class TestTaskSchedulerRemove:
    """Test suite for removing tasks."""

    def test_remove_task_success(self, scheduler):
        """Test successful task removal."""
        task_data = {
            "task_type": "backup",
            "schedule_type": SCHEDULE_DAILY,
            "run_time": "10:00",
        }
        task = scheduler.add_task(task_data)
        assert len(scheduler.get_all_tasks()) == 1
        
        result = scheduler.remove_task(task.id)
        assert result is True
        assert len(scheduler.get_all_tasks()) == 0

    def test_remove_nonexistent_task(self, scheduler):
        """Test remove returns False for nonexistent task."""
        result = scheduler.remove_task(999)
        assert result is False

    def test_remove_task_persistence(self, scheduler, temp_data_file):
        """Test that task removal is persisted."""
        task_data = {
            "task_type": "backup",
            "schedule_type": SCHEDULE_DAILY,
            "run_time": "10:00",
        }
        task = scheduler.add_task(task_data)
        task_id = task.id
        
        scheduler.remove_task(task_id)
        
        # Create new scheduler and verify
        scheduler2 = TaskScheduler(data_file=temp_data_file)
        retrieved_task = scheduler2.get_task_by_id(task_id)
        
        assert retrieved_task is None


class TestTaskSchedulerGetters:
    """Test suite for getter methods."""

    def test_get_all_tasks(self, scheduler):
        """Test retrieving all tasks."""
        for i in range(3):
            task_data = {
                "task_type": f"task_{i}",
                "schedule_type": SCHEDULE_DAILY,
                "run_time": "10:00",
            }
            scheduler.add_task(task_data)
        
        all_tasks = scheduler.get_all_tasks()
        assert len(all_tasks) == 3

    def test_get_task_by_id(self, scheduler):
        """Test retrieving specific task by ID."""
        task_data = {
            "task_type": "backup",
            "schedule_type": SCHEDULE_DAILY,
            "run_time": "10:00",
        }
        task = scheduler.add_task(task_data)
        
        retrieved = scheduler.get_task_by_id(task.id)
        assert retrieved is not None
        assert retrieved.id == task.id

    def test_get_task_by_id_not_found(self, scheduler):
        """Test get_task_by_id returns None for missing ID."""
        result = scheduler.get_task_by_id(999)
        assert result is None

    def test_get_all_tasks_returns_copy(self, scheduler):
        """Test that get_all_tasks returns a list copy."""
        task_data = {
            "task_type": "backup",
            "schedule_type": SCHEDULE_DAILY,
            "run_time": "10:00",
        }
        scheduler.add_task(task_data)
        
        tasks1 = scheduler.get_all_tasks()
        tasks2 = scheduler.get_all_tasks()
        
        # Should be separate list instances
        assert tasks1 is not tasks2
        assert len(tasks1) == len(tasks2)
