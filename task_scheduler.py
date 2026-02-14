"""
Smart Task Scheduler - Backend Logic
Implements intelligent task scheduling based on priority, deadlines, and time constraints
"""

from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from enum import IntEnum


class Priority(IntEnum):
    """Task priority levels"""
    HIGH = 1
    MEDIUM = 2
    LOW = 3


@dataclass
class TimeBlock:
    """Represents an available time block in a day"""
    start_hour: int
    start_minute: int
    end_hour: int
    end_minute: int
    
    @property
    def start_minutes(self) -> int:
        """Total minutes from midnight for start time"""
        return self.start_hour * 60 + self.start_minute
    
    @property
    def end_minutes(self) -> int:
        """Total minutes from midnight for end time"""
        return self.end_hour * 60 + self.end_minute
    
    @property
    def duration_hours(self) -> float:
        """Duration of the block in hours"""
        return (self.end_minutes - self.start_minutes) / 60
    
    def can_fit_task(self, hours_needed: float) -> bool:
        """Check if this block can fit a task of given duration"""
        return self.duration_hours >= hours_needed
    
    def __repr__(self) -> str:
        return f"{self.start_hour:02d}:{self.start_minute:02d}-{self.end_hour:02d}:{self.end_minute:02d}"


@dataclass
class Task:
    """Represents a task to be scheduled"""
    id: int
    name: str
    days_needed: int
    hours_per_day: float
    priority: Priority
    deadline_day: int  # Deadline in days from start
    days_completed: int = 0
    in_progress: bool = False
    
    @property
    def days_remaining(self) -> int:
        """Days still needed to complete the task"""
        return self.days_needed - self.days_completed
    
    @property
    def is_complete(self) -> bool:
        """Check if task is fully completed"""
        return self.days_completed >= self.days_needed
    
    def can_meet_deadline(self, current_day: int) -> bool:
        """Check if task can still meet its deadline if started today"""
        days_until_deadline = self.deadline_day - current_day
        return days_until_deadline >= self.days_remaining
    
    def urgency_score(self, current_day: int) -> float:
        """Calculate urgency score (lower is more urgent)"""
        # Deadline pressure - days until deadline minus days remaining
        return self.deadline_day - self.days_remaining - current_day
    
    def __lt__(self, other: 'Task') -> bool:
        """Comparison for sorting - more urgent/higher priority first"""
        if self.in_progress != other.in_progress:
            return self.in_progress  # In-progress tasks first
        
        # Then by urgency
        self_urgency = self.urgency_score(0)  # Will be set properly in context
        other_urgency = other.urgency_score(0)
        
        if self_urgency != other_urgency:
            return self_urgency < other_urgency
        
        # Finally by priority
        return self.priority < other.priority


@dataclass
class ScheduledTask:
    """A task scheduled for a specific time slot"""
    task_name: str
    start_time: str
    end_time: str
    duration_hours: float
    priority: Priority
    day_progress: str  # e.g., "3/5"
    task_id: int


@dataclass
class DaySchedule:
    """Schedule for a single day"""
    day_number: int
    date: datetime
    scheduled_tasks: List[ScheduledTask] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def add_task(self, task: ScheduledTask):
        """Add a scheduled task to this day"""
        self.scheduled_tasks.append(task)
    
    def add_warning(self, warning: str):
        """Add a warning message"""
        self.warnings.append(warning)
    
    @property
    def has_content(self) -> bool:
        """Check if this day has any tasks or warnings"""
        return len(self.scheduled_tasks) > 0 or len(self.warnings) > 0


@dataclass
class AvailableBlock:
    """Represents remaining availability in a time block for a specific day"""
    original_block: TimeBlock
    remaining_start_minutes: int
    remaining_duration_hours: float
    
    def can_fit_task(self, hours_needed: float) -> bool:
        """Check if remaining space can fit the task"""
        return self.remaining_duration_hours >= hours_needed
    
    def allocate_time(self, hours_needed: float, buffer_minutes: int) -> Tuple[int, int]:
        """
        Allocate time for a task and return (start_minutes, end_minutes)
        Updates remaining availability
        """
        start_minutes = self.remaining_start_minutes
        end_minutes = start_minutes + int(hours_needed * 60)
        
        # Update remaining availability (including buffer)
        self.remaining_start_minutes = end_minutes + buffer_minutes
        self.remaining_duration_hours -= (hours_needed + buffer_minutes / 60)
        
        return start_minutes, end_minutes


class TaskScheduler:
    """Main scheduler class that implements the scheduling algorithm"""
    
    def __init__(
        self,
        available_blocks: List[TimeBlock],
        buffer_minutes: int = 15,
        max_tasks_per_day: int = 2,
        start_date: Optional[datetime] = None
    ):
        """
        Initialize the scheduler
        
        Args:
            available_blocks: List of daily available time blocks
            buffer_minutes: Buffer time between tasks
            max_tasks_per_day: Maximum new tasks to start per day
            start_date: Start date for scheduling (default: today)
        """
        self.available_blocks = sorted(available_blocks, key=lambda b: b.start_minutes)
        self.buffer_minutes = buffer_minutes
        self.max_tasks_per_day = max_tasks_per_day
        self.start_date = start_date or datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    def validate_tasks(self, tasks: List[Task]) -> List[str]:
        """
        Validate that all tasks can fit in available time blocks
        
        Returns:
            List of warning messages for tasks that don't fit
        """
        warnings = []
        max_block_duration = max(block.duration_hours for block in self.available_blocks)
        
        for task in tasks:
            if task.hours_per_day > max_block_duration:
                warnings.append(
                    f"Task '{task.name}' requires {task.hours_per_day}h per day, "
                    f"but longest available block is {max_block_duration}h"
                )
        
        return warnings
    
    def _create_daily_blocks(self) -> List[AvailableBlock]:
        """Create fresh availability blocks for a new day"""
        return [
            AvailableBlock(
                original_block=block,
                remaining_start_minutes=block.start_minutes,
                remaining_duration_hours=block.duration_hours
            )
            for block in self.available_blocks
        ]
    
    def _sort_tasks_by_urgency(self, tasks: List[Task], current_day: int) -> List[Task]:
        """
        Sort tasks by urgency and priority
        
        Priority order:
        1. In-progress tasks (must continue)
        2. Tasks by urgency score (deadline pressure)
        3. Tasks by priority level
        """
        def sort_key(task: Task) -> Tuple[bool, float, int]:
            return (
                not task.in_progress,  # False (in-progress) comes first
                task.urgency_score(current_day),  # Lower urgency score = more urgent
                task.priority.value  # Lower priority value = higher priority
            )
        
        return sorted(tasks, key=sort_key)
    
    def _minutes_to_time_string(self, minutes: int) -> str:
        """Convert minutes from midnight to HH:MM format"""
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours:02d}:{mins:02d}"
    
    def schedule_tasks(self, tasks: List[Task], max_days: Optional[int] = None) -> Tuple[List[DaySchedule], List[str]]:
        """
        Generate the complete schedule for all tasks
        
        Args:
            tasks: List of tasks to schedule
            max_days: Maximum days to schedule (default: max deadline + 10)
        
        Returns:
            Tuple of (list of day schedules, list of validation warnings)
        """
        # Validate tasks first
        validation_warnings = self.validate_tasks(tasks)
        
        if not tasks:
            return [], validation_warnings
        
        # Determine scheduling horizon
        if max_days is None:
            max_days = max(task.deadline_day for task in tasks) + 10
        
        # Create working copy of tasks
        working_tasks = [
            Task(
                id=task.id,
                name=task.name,
                days_needed=task.days_needed,
                hours_per_day=task.hours_per_day,
                priority=task.priority,
                deadline_day=task.deadline_day,
                days_completed=0,
                in_progress=False
            )
            for task in tasks
        ]
        
        schedule = []
        current_day = 0
        
        # Main scheduling loop
        while any(not task.is_complete for task in working_tasks) and current_day < max_days:
            current_day += 1
            
            # Create day schedule
            day_date = self.start_date + timedelta(days=current_day - 1)
            day_schedule = DaySchedule(day_number=current_day, date=day_date)
            
            # Get incomplete tasks sorted by urgency
            incomplete_tasks = [t for t in working_tasks if not t.is_complete]
            sorted_tasks = self._sort_tasks_by_urgency(incomplete_tasks, current_day)
            
            # Create fresh blocks for this day
            daily_blocks = self._create_daily_blocks()
            
            # Track tasks scheduled today
            new_tasks_started_today = 0
            
            # Schedule tasks
            for task in sorted_tasks:
                # Check task limit (don't count continuing tasks)
                if not task.in_progress and new_tasks_started_today >= self.max_tasks_per_day:
                    break
                
                # Check if task can meet deadline
                if not task.in_progress and not task.can_meet_deadline(current_day):
                    day_schedule.add_warning(
                        f"Cannot start '{task.name}' - needs {task.days_remaining} days "
                        f"but deadline is in {task.deadline_day - current_day} days"
                    )
                    continue
                
                # Find suitable block
                suitable_block = next(
                    (block for block in daily_blocks if block.can_fit_task(task.hours_per_day)),
                    None
                )
                
                if suitable_block:
                    # Allocate time
                    start_minutes, end_minutes = suitable_block.allocate_time(
                        task.hours_per_day,
                        self.buffer_minutes
                    )
                    
                    # Create scheduled task
                    scheduled_task = ScheduledTask(
                        task_name=task.name,
                        start_time=self._minutes_to_time_string(start_minutes),
                        end_time=self._minutes_to_time_string(end_minutes),
                        duration_hours=task.hours_per_day,
                        priority=task.priority,
                        day_progress=f"{task.days_completed + 1}/{task.days_needed}",
                        task_id=task.id
                    )
                    
                    day_schedule.add_task(scheduled_task)
                    
                    # Update task progress
                    was_in_progress = task.in_progress
                    task.days_completed += 1
                    task.in_progress = True
                    
                    if task.is_complete:
                        task.in_progress = False
                    
                    # Count new task starts
                    if not was_in_progress:
                        new_tasks_started_today += 1
                
                else:
                    # No suitable block found
                    if task.in_progress:
                        day_schedule.add_warning(
                            f"Cannot continue '{task.name}' - no available {task.hours_per_day}h block"
                        )
            
            # Add day to schedule if it has content
            if day_schedule.has_content:
                schedule.append(day_schedule)
        
        return schedule, validation_warnings
    
    def print_schedule(self, schedule: List[DaySchedule], warnings: List[str] = None):
        """Print the schedule in a readable format"""
        priority_symbols = {
            Priority.HIGH: "🔴 High",
            Priority.MEDIUM: "🟡 Medium",
            Priority.LOW: "🟢 Low"
        }
        
        print("=" * 80)
        print("SMART TASK SCHEDULER - GENERATED SCHEDULE")
        print("=" * 80)
        print()
        
        if warnings:
            print("⚠️  VALIDATION WARNINGS:")
            for warning in warnings:
                print(f"   - {warning}")
            print()
        
        for day in schedule:
            date_str = day.date.strftime("%A, %B %d, %Y")
            print(f"📅 DAY {day.day_number} - {date_str}")
            print("-" * 80)
            
            if day.warnings:
                for warning in day.warnings:
                    print(f"   ⚠️  {warning}")
            
            if day.scheduled_tasks:
                for task in day.scheduled_tasks:
                    priority_label = priority_symbols.get(task.priority, "Unknown")
                    print(f"   {task.start_time} - {task.end_time} ({task.duration_hours}h)")
                    print(f"   📋 {task.task_name}")
                    print(f"   {priority_label} | Progress: {task.day_progress}")
                    print()
            
            if not day.scheduled_tasks and not day.warnings:
                print("   (No tasks scheduled)")
                print()
            
            print()


def example_usage():
    """Example demonstrating how to use the scheduler"""
    
    # Define available time blocks (9-12, 1-6, 7-8)
    time_blocks = [
        TimeBlock(9, 0, 12, 0),   # 9 AM - 12 PM (3 hours)
        TimeBlock(13, 0, 18, 0),  # 1 PM - 6 PM (5 hours)
        TimeBlock(19, 0, 20, 0),  # 7 PM - 8 PM (1 hour)
    ]
    
    # Create tasks
    tasks = [
        Task(
            id=1,
            name="Complete Project Report",
            days_needed=5,
            hours_per_day=2.0,
            priority=Priority.HIGH,
            deadline_day=10
        ),
        Task(
            id=2,
            name="Study for Exam",
            days_needed=3,
            hours_per_day=3.0,
            priority=Priority.HIGH,
            deadline_day=7
        ),
        Task(
            id=3,
            name="Code Review Tasks",
            days_needed=4,
            hours_per_day=1.5,
            priority=Priority.MEDIUM,
            deadline_day=12
        ),
        Task(
            id=4,
            name="Read Research Papers",
            days_needed=6,
            hours_per_day=1.0,
            priority=Priority.LOW,
            deadline_day=15
        ),
    ]
    
    # Create scheduler
    scheduler = TaskScheduler(
        available_blocks=time_blocks,
        buffer_minutes=15,
        max_tasks_per_day=2,
        start_date=datetime(2024, 2, 15)
    )
    
    # Generate schedule
    schedule, warnings = scheduler.schedule_tasks(tasks)
    
    # Print the schedule
    scheduler.print_schedule(schedule, warnings)
    
    # Return for potential further processing
    return schedule, warnings


if __name__ == "__main__":
    # Run example
    schedule, warnings = example_usage()
    
    print("\n" + "=" * 80)
    print(f"✅ Schedule generated with {len(schedule)} days")
    print("=" * 80)
