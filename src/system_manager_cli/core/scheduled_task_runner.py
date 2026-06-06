"""
Scheduled Task Runner — Background daemon for auto-executing due tasks.

This module provides a daemon thread that:
1. Runs in the background without blocking the CLI
2. Periodically checks for due scheduled tasks
3. Automatically executes them via the app
4. Logs execution results

The runner is started once during app initialization and runs for the
lifetime of the CLI session.

Architecture:
- Non-blocking: uses threading.Thread with daemon=True
- No external dependencies: uses standard threading module
- Graceful shutdown: respects thread daemon status
- Error handling: catches and logs all exceptions
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Optional

from system_manager_cli.ulits.logger import get_logger

logger = get_logger(__name__)


class ScheduledTaskRunner:
    """
    Daemon thread manager for auto-executing due scheduled tasks.
    
    Usage:
        runner = ScheduledTaskRunner(
            scheduler=app.task_scheduler,
            executor=app.execute_scheduled_task,
            check_interval=60  # Check every 60 seconds
        )
        runner.start()
    """

    def __init__(
        self,
        scheduler: Any,
        executor: Callable[[Any], dict[str, Any]],
        check_interval: int = 60,
    ):
        """
        Initialize the task runner.
        
        Args:
            scheduler: TaskScheduler instance with get_due_tasks() method
            executor: Callable to execute a task, returns dict with status
            check_interval: Seconds between checks for due tasks (default 60)
        """
        self.scheduler = scheduler
        self.executor = executor
        self.check_interval = max(10, check_interval)  # Minimum 10 seconds
        
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._executed_count = 0

    def start(self) -> None:
        """Start the background task runner thread."""
        if self._thread is not None and self._thread.is_alive():
            logger.warning("Task runner is already running")
            return
        
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name="ScheduledTaskRunner",
        )
        self._thread.start()
        logger.info(
            "Scheduled task runner started (check interval: %d seconds)",
            self.check_interval,
        )

    def stop(self) -> None:
        """Stop the background task runner thread."""
        if self._thread is None:
            return
        
        self._running = False
        if self._thread.is_alive():
            # Wait up to 5 seconds for graceful shutdown
            self._thread.join(timeout=5)
            if self._thread.is_alive():
                logger.warning("Task runner thread did not stop cleanly")
        
        logger.info(
            "Scheduled task runner stopped (executed %d tasks)",
            self._executed_count,
        )

    def get_execution_count(self) -> int:
        """Return the number of tasks executed since startup."""
        return self._executed_count

    def _run_loop(self) -> None:
        """Main loop: periodically check and execute due tasks."""
        logger.debug("Task runner loop started")
        
        while self._running:
            try:
                self._check_and_execute_due_tasks()
            except Exception as exc:
                logger.error(
                    "Unhandled exception in task runner loop: %s",
                    exc,
                    exc_info=True,
                )
            
            # Sleep in small intervals to allow quick shutdown
            for _ in range(self.check_interval):
                if not self._running:
                    break
                time.sleep(1)
        
        logger.debug("Task runner loop exited")

    def _check_and_execute_due_tasks(self) -> None:
        """Check for due tasks and execute them."""
        try:
            due_tasks = self.scheduler.get_due_tasks()
            
            if not due_tasks:
                return
            
            logger.info("Found %d due task(s) to execute", len(due_tasks))
            
            for task in due_tasks:
                try:
                    task_id = getattr(task, "id", "?")
                    task_type = getattr(task, "task_type", "unknown")
                    
                    logger.info("Executing scheduled task #%s (%s)", task_id, task_type)
                    
                    # Execute the task
                    result = self.executor(task)
                    
                    # Log result
                    status = result.get("status", "unknown")
                    error = result.get("error", "")
                    
                    if status == "completed":
                        logger.info(
                            "Task #%s completed successfully",
                            task_id,
                        )
                        self._executed_count += 1
                    else:
                        logger.warning(
                            "Task #%s failed: %s",
                            task_id,
                            error or status,
                        )
                    
                    # Update task's last_run timestamp
                    self.scheduler.mark_executed(task_id)
                    
                except Exception as exc:
                    logger.error(
                        "Error executing task #%s: %s",
                        getattr(task, "id", "?"),
                        exc,
                        exc_info=True,
                    )
        
        except Exception as exc:
            logger.error(
                "Error checking due tasks: %s",
                exc,
                exc_info=True,
            )
