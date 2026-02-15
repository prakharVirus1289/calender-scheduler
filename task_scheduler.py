"""
Smart Task Scheduler - Updated Backend Logic
Features: Closed time slots, hours-based tracking, JSON persistence
"""

from datetime import datetime, timedelta, time
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass, field, asdict
from enum import IntEnum
import json
from pathlib import Path


class Priority(IntEnum):
    """Task priority levels"""
    HIGH = 1
    MEDIUM = 2
    LOW = 3


@dataclass
class ClosedTimeSlot:
    """Represents a blocked/unavailable time slot"""
    start_hour: int
    start_minute: int
    end_hour: int
    end_minute: int
    applies_to: str  # "all_days", "specific_date", "weekdays"
    specific_date: Optional[str] = None  # Format: "YYYY-MM-DD"
    weekdays: Optional[List[int]] = None  # [0=Mon, 1=Tue, ..., 6=Sun]
    
    @property
    def start_minutes(self) -> int:
        """Total minutes from midnight for start time"""
        return self.start_hour * 60 + self.start_minute
    
    @property
    def end_minutes(self) -> int:
        """Total minutes from midnight for end time"""
        return self.end_hour * 60 + self.end_minute
    
    def applies_to_date(self, date: datetime) -> bool:
        """Check if this closed slot applies to the given date"""
        if self.applies_to == "all_days":
            return True
        elif self.applies_to == "specific_date":
            return date.strftime("%Y-%m-%d") == self.specific_date
        elif self.applies_to == "weekdays" and self.weekdays:
            return date.weekday() in self.weekdays
        return False


@dataclass
class TimeBlock:
    """Represents an available time block"""
    start_hour: int
    start_minute: int
    end_hour: int
    end_minute: int
    
    @property
    def start_minutes(self) -> int:
        return self.start_hour * 60 + self.start_minute
    
    @property
    def end_minutes(self) -> int:
        return self.end_hour * 60 + self.end_minute
    
    @property
    def duration_hours(self) -> float:
        return (self.end_minutes - self.start_minutes) / 60
    
    def can_fit_hours(self, hours_needed: float) -> bool:
        return self.duration_hours >= hours_needed


@dataclass
class Task:
    """Represents a task to be scheduled"""
    id: int
    name: str
    total_hours: float  # Total hours needed to complete
    hours_per_session: float  # Hours to work per session
    priority: Priority
    deadline_day: int
    hours_completed: float = 0.0
    in_progress: bool = False
    
    @property
    def hours_remaining(self) -> float:
        return max(0, self.total_hours - self.hours_completed)
    
    @property
    def is_complete(self) -> bool:
        return self.hours_completed >= self.total_hours
    
    @property
    def sessions_needed(self) -> int:
        """Number of sessions still needed"""
        if self.hours_per_session <= 0:
            return 0
        return int(self.hours_remaining / self.hours_per_session) + \
               (1 if self.hours_remaining % self.hours_per_session > 0 else 0)
    
    def can_meet_deadline(self, current_day: int) -> bool:
        days_until_deadline = self.deadline_day - current_day
        return days_until_deadline >= self.sessions_needed
    
    def urgency_score(self, current_day: int) -> float:
        return self.deadline_day - self.sessions_needed - current_day
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'name': self.name,
            'total_hours': self.total_hours,
            'hours_per_session': self.hours_per_session,
            'priority': self.priority.value,
            'deadline_day': self.deadline_day,
            'hours_completed': self.hours_completed,
            'in_progress': self.in_progress
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'Task':
        """Create Task from dictionary"""
        return Task(
            id=data['id'],
            name=data['name'],
            total_hours=data['total_hours'],
            hours_per_session=data['hours_per_session'],
            priority=Priority(data['priority']),
            deadline_day=data['deadline_day'],
            hours_completed=data.get('hours_completed', 0.0),
            in_progress=data.get('in_progress', False)
        )


@dataclass
class ScheduledTask:
    """A task scheduled for a specific time slot"""
    task_name: str
    start_time: str
    end_time: str
    duration_hours: float
    priority: Priority
    progress: str  # e.g., "5.5h / 10h"
    task_id: int


@dataclass
class DaySchedule:
    """Schedule for a single day"""
    day_number: int
    date: datetime
    scheduled_tasks: List[ScheduledTask] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def add_task(self, task: ScheduledTask):
        self.scheduled_tasks.append(task)
    
    def add_warning(self, warning: str):
        self.warnings.append(warning)
    
    @property
    def has_content(self) -> bool:
        return len(self.scheduled_tasks) > 0 or len(self.warnings) > 0
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'day_number': self.day_number,
            'date': self.date.strftime('%Y-%m-%d'),
            'scheduled_tasks': [
                {
                    'task_name': t.task_name,
                    'start_time': t.start_time,
                    'end_time': t.end_time,
                    'duration_hours': t.duration_hours,
                    'priority': t.priority.value,
                    'progress': t.progress,
                    'task_id': t.task_id
                }
                for t in self.scheduled_tasks
            ],
            'warnings': self.warnings
        }


@dataclass
class AvailableBlock:
    """Represents remaining availability in a time block"""
    original_block: TimeBlock
    remaining_start_minutes: int
    remaining_duration_hours: float
    
    def can_fit_hours(self, hours_needed: float) -> bool:
        return self.remaining_duration_hours >= hours_needed
    
    def allocate_time(self, hours_needed: float, buffer_minutes: int) -> Tuple[int, int]:
        start_minutes = self.remaining_start_minutes
        end_minutes = start_minutes + int(hours_needed * 60)
        
        self.remaining_start_minutes = end_minutes + buffer_minutes
        self.remaining_duration_hours -= (hours_needed + buffer_minutes / 60)
        
        return start_minutes, end_minutes


class TaskScheduler:
    """Main scheduler class with closed time slots and hours-based tracking"""
    
    def __init__(
        self,
        closed_slots: List[ClosedTimeSlot],
        buffer_minutes: int = 15,
        max_tasks_per_day: int = 2,
        start_date: Optional[datetime] = None,
        storage_file: str = "scheduler_data.json"
    ):
        self.closed_slots = closed_slots
        self.buffer_minutes = buffer_minutes
        self.max_tasks_per_day = max_tasks_per_day
        self.start_date = start_date or datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        self.storage_file = storage_file
    
    def _get_available_blocks_for_date(self, date: datetime) -> List[TimeBlock]:
        """Calculate available time blocks for a specific date by subtracting closed slots"""
        # Start with full day (00:00 to 24:00)
        available_ranges = [(0, 24 * 60)]  # List of (start_minutes, end_minutes) tuples
        
        # Get all closed slots that apply to this date
        applicable_closed_slots = [
            slot for slot in self.closed_slots
            if slot.applies_to_date(date)
        ]
        
        # Sort closed slots by start time
        applicable_closed_slots.sort(key=lambda s: s.start_minutes)
        
        # Subtract each closed slot from available ranges
        for closed_slot in applicable_closed_slots:
            new_ranges = []
            for start, end in available_ranges:
                # If closed slot doesn't overlap with this range, keep the range
                if closed_slot.end_minutes <= start or closed_slot.start_minutes >= end:
                    new_ranges.append((start, end))
                else:
                    # Split the range around the closed slot
                    if start < closed_slot.start_minutes:
                        new_ranges.append((start, closed_slot.start_minutes))
                    if closed_slot.end_minutes < end:
                        new_ranges.append((closed_slot.end_minutes, end))
            available_ranges = new_ranges
        
        # Convert ranges to TimeBlock objects (filter out blocks < 30 minutes)
        blocks = []
        for start_mins, end_mins in available_ranges:
            if end_mins - start_mins >= 30:  # Minimum 30 minutes
                blocks.append(TimeBlock(
                    start_hour=start_mins // 60,
                    start_minute=start_mins % 60,
                    end_hour=end_mins // 60,
                    end_minute=end_mins % 60
                ))
        
        return blocks
    
    def validate_tasks(self, tasks: List[Task], max_days: int = 100) -> List[str]:
        """Validate that tasks can potentially be scheduled"""
        warnings = []
        
        # Find maximum available block across all days
        max_block_hours = 0
        for day_offset in range(min(max_days, 30)):  # Check first 30 days
            date = self.start_date + timedelta(days=day_offset)
            blocks = self._get_available_blocks_for_date(date)
            if blocks:
                max_block_hours = max(max_block_hours, max(b.duration_hours for b in blocks))
        
        for task in tasks:
            if task.hours_per_session > max_block_hours:
                warnings.append(
                    f"Task '{task.name}' requires {task.hours_per_session}h per session, "
                    f"but longest available block is {max_block_hours:.1f}h"
                )
        
        return warnings
    
    def _create_daily_blocks(self, date: datetime) -> List[AvailableBlock]:
        """Create available blocks for a specific date"""
        blocks = self._get_available_blocks_for_date(date)
        return [
            AvailableBlock(
                original_block=block,
                remaining_start_minutes=block.start_minutes,
                remaining_duration_hours=block.duration_hours
            )
            for block in blocks
        ]
    
    def _sort_tasks_by_urgency(self, tasks: List[Task], current_day: int) -> List[Task]:
        """Sort tasks by: in_progress > urgency > priority"""
        def sort_key(task: Task) -> Tuple[bool, bool, float, int]:
            return (
                task.is_complete,  # Completed tasks last
                not task.in_progress,  # In-progress tasks first
                task.urgency_score(current_day),
                task.priority.value
            )
        return sorted(tasks, key=sort_key)
    
    def _minutes_to_time_string(self, minutes: int) -> str:
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours:02d}:{mins:02d}"
    
    def schedule_tasks(self, tasks: List[Task], max_days: Optional[int] = None) -> Tuple[List[DaySchedule], List[str]]:
        """Generate schedule using hours-based tracking"""
        validation_warnings = self.validate_tasks(tasks)
        
        if not tasks:
            return [], validation_warnings
        
        if max_days is None:
            max_days = max(task.deadline_day for task in tasks) + 10
        
        # Create working copy
        working_tasks = [
            Task(
                id=task.id,
                name=task.name,
                total_hours=task.total_hours,
                hours_per_session=task.hours_per_session,
                priority=task.priority,
                deadline_day=task.deadline_day,
                hours_completed=task.hours_completed,
                in_progress=task.in_progress
            )
            for task in tasks
        ]
        
        schedule = []
        current_day = 0
        
        while any(not task.is_complete for task in working_tasks) and current_day < max_days:
            current_day += 1
            day_date = self.start_date + timedelta(days=current_day - 1)
            day_schedule = DaySchedule(day_number=current_day, date=day_date)
            
            incomplete_tasks = [t for t in working_tasks if not t.is_complete]
            sorted_tasks = self._sort_tasks_by_urgency(incomplete_tasks, current_day)
            
            daily_blocks = self._create_daily_blocks(day_date)
            
            if not daily_blocks:
                # No available time on this day
                continue
            
            new_tasks_started_today = 0
            
            for task in sorted_tasks:
                if not task.in_progress and new_tasks_started_today >= self.max_tasks_per_day:
                    break
                
                if not task.in_progress and not task.can_meet_deadline(current_day):
                    day_schedule.add_warning(
                        f"Cannot start '{task.name}' - needs {task.sessions_needed} more sessions "
                        f"but deadline is in {task.deadline_day - current_day} days"
                    )
                    continue
                
                # Find suitable block
                suitable_block = next(
                    (block for block in daily_blocks if block.can_fit_hours(task.hours_per_session)),
                    None
                )
                
                if suitable_block:
                    start_minutes, end_minutes = suitable_block.allocate_time(
                        task.hours_per_session,
                        self.buffer_minutes
                    )
                    
                    # Update task progress
                    was_in_progress = task.in_progress
                    task.hours_completed += task.hours_per_session
                    task.hours_completed = min(task.hours_completed, task.total_hours)  # Cap at total
                    task.in_progress = True
                    
                    scheduled_task = ScheduledTask(
                        task_name=task.name,
                        start_time=self._minutes_to_time_string(start_minutes),
                        end_time=self._minutes_to_time_string(end_minutes),
                        duration_hours=task.hours_per_session,
                        priority=task.priority,
                        progress=f"{task.hours_completed:.1f}h / {task.total_hours:.1f}h",
                        task_id=task.id
                    )
                    
                    day_schedule.add_task(scheduled_task)
                    
                    if task.is_complete:
                        task.in_progress = False
                    
                    if not was_in_progress:
                        new_tasks_started_today += 1
                else:
                    if task.in_progress:
                        day_schedule.add_warning(
                            f"Cannot continue '{task.name}' - no available {task.hours_per_session}h block"
                        )
            
            if day_schedule.has_content:
                schedule.append(day_schedule)
        
        return schedule, validation_warnings
    
    def save_data(self, tasks: List[Task], schedule: List[DaySchedule]):
        """Save tasks and schedule to JSON file"""
        data = {
            'tasks': [task.to_dict() for task in tasks],
            'schedule': [day.to_dict() for day in schedule],
            'config': {
                'buffer_minutes': self.buffer_minutes,
                'max_tasks_per_day': self.max_tasks_per_day,
                'start_date': self.start_date.strftime('%Y-%m-%d')
            },
            'saved_at': datetime.now().isoformat()
        }
        
        with open(self.storage_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load_data(self) -> Optional[Dict]:
        """Load tasks and schedule from JSON file"""
        try:
            if Path(self.storage_file).exists():
                with open(self.storage_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading data: {e}")
        return None
    
    def print_schedule(self, schedule: List[DaySchedule], warnings: List[str] = None):
        """Print schedule in readable format"""
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
                    print(f"   {priority_label} | Progress: {task.progress}")
                    print()
            
            print()


def example_usage():
    """Example with closed time slots and hours-based tracking"""
    
    # Define CLOSED time slots (blocked/unavailable times)
    closed_slots = [
        # Sleep - applies to all days
        ClosedTimeSlot(0, 0, 8, 0, "all_days"),  # 12 AM - 8 AM
        ClosedTimeSlot(22, 0, 24, 0, "all_days"),  # 10 PM - 12 AM
        
        # Meals - all days
        ClosedTimeSlot(12, 0, 13, 0, "all_days"),  # Lunch
        ClosedTimeSlot(20, 0, 21, 0, "all_days"),  # Dinner
        
        # Weekend mornings - sleep in
        ClosedTimeSlot(8, 0, 10, 0, "weekdays", weekdays=[5, 6]),  # Sat, Sun
    ]
    
    # Create tasks with hours-based tracking
    tasks = [
        Task(
            id=1,
            name="Complete Project Report",
            total_hours=10.0,  # 10 hours total
            hours_per_session=2.0,  # 2 hours per day
            priority=Priority.HIGH,
            deadline_day=10
        ),
        Task(
            id=2,
            name="Study for Exam",
            total_hours=9.0,  # 9 hours total
            hours_per_session=3.0,  # 3 hours per day
            priority=Priority.HIGH,
            deadline_day=7
        ),
        Task(
            id=3,
            name="Code Review Tasks",
            total_hours=6.0,  # 6 hours total
            hours_per_session=1.5,  # 1.5 hours per day
            priority=Priority.MEDIUM,
            deadline_day=12
        ),
    ]
    
    # Create scheduler
    scheduler = TaskScheduler(
        closed_slots=closed_slots,
        buffer_minutes=15,
        max_tasks_per_day=2,
        start_date=datetime(2024, 2, 15)
    )
    
    # Generate schedule
    schedule, warnings = scheduler.schedule_tasks(tasks)
    
    # Print the schedule
    scheduler.print_schedule(schedule, warnings)
    
    # Save to file
    scheduler.save_data(tasks, schedule)
    print(f"\n✅ Schedule saved to {scheduler.storage_file}")
    
    return schedule, warnings


if __name__ == "__main__":
    schedule, warnings = example_usage()
    print("\n" + "=" * 80)
    print(f"✅ Schedule generated with {len(schedule)} days")
    print("=" * 80)