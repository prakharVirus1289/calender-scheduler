# Smart Task Scheduler - Python Backend

A sophisticated task scheduling system that optimizes your daily schedule based on priorities, deadlines, and available time blocks.

## Features

✅ **Priority-Based Scheduling**: High, Medium, Low priority levels  
✅ **Deadline-Aware**: Won't start tasks that can't meet their deadlines  
✅ **Time Block Management**: Define when you're available each day  
✅ **Task Continuity**: Ensures tasks are completed without interruption  
✅ **Configurable Buffers**: Set break time between tasks  
✅ **Daily Task Limits**: Control cognitive load by limiting concurrent tasks  
✅ **REST API**: Easy integration with any frontend

## Architecture

The system consists of three main components:

1. **`task_scheduler.py`** - Core scheduling logic and algorithms
2. **`api.py`** - Flask REST API for HTTP access
3. **`task-scheduler.html`** - Standalone frontend (optional)

## Installation

```bash
# Install dependencies
pip install -r requirements.txt
```

## Usage

### Option 1: Python Module (Direct Usage)

```python
from task_scheduler import TaskScheduler, Task, TimeBlock, Priority
from datetime import datetime

# Define your available time blocks
time_blocks = [
    TimeBlock(9, 0, 12, 0),   # 9 AM - 12 PM
    TimeBlock(13, 0, 18, 0),  # 1 PM - 6 PM
    TimeBlock(19, 0, 20, 0),  # 7 PM - 8 PM
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
```

### Option 2: REST API Server

```bash
# Start the Flask server
python api.py
```

The API will be available at `http://localhost:5000`

#### API Endpoints

**1. Health Check**
```bash
GET /api/health
```

**2. Generate Schedule**
```bash
POST /api/schedule
Content-Type: application/json

{
  "time_blocks": [
    {"start_hour": 9, "start_minute": 0, "end_hour": 12, "end_minute": 0},
    {"start_hour": 13, "start_minute": 0, "end_hour": 18, "end_minute": 0}
  ],
  "tasks": [
    {
      "id": 1,
      "name": "Complete Project Report",
      "days_needed": 5,
      "hours_per_day": 2.0,
      "priority": 1,
      "deadline_day": 10
    }
  ],
  "buffer_minutes": 15,
  "max_tasks_per_day": 2,
  "start_date": "2024-02-15"
}
```

**3. Validate Tasks**
```bash
POST /api/validate
Content-Type: application/json

{
  "time_blocks": [...],
  "tasks": [...]
}
```

**4. Get Example Payload**
```bash
GET /api/example
```

### Option 3: Standalone HTML Frontend

Simply open `task-scheduler.html` in your browser for a complete UI.

## Scheduling Algorithm

The scheduler implements a sophisticated multi-criteria algorithm:

### 1. **Task Validation**
- Checks if each task's daily duration fits within available time blocks
- Warns about tasks that cannot be scheduled

### 2. **Priority Sorting**
Tasks are sorted each day by:
1. **In-Progress Status** (continuing tasks have highest priority)
2. **Urgency Score** (deadline pressure: `deadline - days_remaining - current_day`)
3. **Priority Level** (High > Medium > Low)

### 3. **Daily Scheduling Loop**
For each day:
1. Create fresh time blocks
2. Sort incomplete tasks by urgency
3. For each task:
   - Check if it can meet its deadline if started today
   - Find first suitable time block
   - Allocate time with buffer
   - Update task progress
4. Limit new task starts per day

### 4. **Time Block Allocation**
- Assigns tasks to earliest available block that fits
- Adds configurable buffer after each task
- Tracks remaining availability in each block

## Data Models

### TimeBlock
Represents an available time slot:
```python
TimeBlock(
    start_hour: int,      # 0-23
    start_minute: int,    # 0-59
    end_hour: int,        # 0-23
    end_minute: int       # 0-59
)
```

### Task
Represents work to be scheduled:
```python
Task(
    id: int,
    name: str,
    days_needed: int,           # Total days to complete
    hours_per_day: float,       # Hours needed each day
    priority: Priority,         # HIGH(1), MEDIUM(2), LOW(3)
    deadline_day: int,          # Days from start date
    days_completed: int = 0,    # Progress tracking
    in_progress: bool = False   # Currently being worked on
)
```

### ScheduledTask
A task assigned to a specific time:
```python
ScheduledTask(
    task_name: str,
    start_time: str,        # "HH:MM" format
    end_time: str,          # "HH:MM" format
    duration_hours: float,
    priority: Priority,
    day_progress: str,      # e.g., "3/5"
    task_id: int
)
```

### DaySchedule
Complete schedule for one day:
```python
DaySchedule(
    day_number: int,
    date: datetime,
    scheduled_tasks: List[ScheduledTask],
    warnings: List[str]
)
```

## Configuration Options

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `buffer_minutes` | int | 15 | Break time between tasks |
| `max_tasks_per_day` | int | 2 | Maximum new tasks to start daily |
| `start_date` | datetime | Today | Schedule start date |

## Example Output

```
================================================================================
SMART TASK SCHEDULER - GENERATED SCHEDULE
================================================================================

📅 DAY 1 - Thursday, February 15, 2024
--------------------------------------------------------------------------------
   09:00 - 12:00 (3.0h)
   📋 Study for Exam
   🔴 High | Progress: 1/3

   13:00 - 15:00 (2.0h)
   📋 Complete Project Report
   🔴 High | Progress: 1/5

📅 DAY 2 - Friday, February 16, 2024
--------------------------------------------------------------------------------
   09:00 - 12:00 (3.0h)
   📋 Study for Exam
   🔴 High | Progress: 2/3

   13:00 - 15:00 (2.0h)
   📋 Complete Project Report
   🔴 High | Progress: 2/5
```

## Testing

Run the example to see the scheduler in action:
```bash
python task_scheduler.py
```

## Advanced Usage

### Custom Validation
```python
# Validate before scheduling
warnings = scheduler.validate_tasks(tasks)
if warnings:
    print("Warnings:", warnings)
```

### Progress Tracking
```python
# Track task completion
for day in schedule:
    for task in day.scheduled_tasks:
        print(f"{task.task_name}: {task.day_progress}")
```

### Export to Calendar Format
```python
# Convert to calendar events
for day in schedule:
    for task in day.scheduled_tasks:
        event = {
            'date': day.date,
            'start': task.start_time,
            'end': task.end_time,
            'title': task.task_name
        }
        # Export to iCal, Google Calendar, etc.
```

## API Response Format

```json
{
  "success": true,
  "schedule": [
    {
      "day_number": 1,
      "date": "2024-02-15",
      "date_formatted": "Thursday, February 15, 2024",
      "scheduled_tasks": [
        {
          "task_name": "Study for Exam",
          "start_time": "09:00",
          "end_time": "12:00",
          "duration_hours": 3.0,
          "priority": 1,
          "day_progress": "1/3",
          "task_id": 2
        }
      ],
      "warnings": []
    }
  ],
  "validation_warnings": [],
  "total_days": 7
}
```

## Error Handling

The API returns appropriate HTTP status codes:
- `200 OK` - Success
- `400 Bad Request` - Invalid input
- `500 Internal Server Error` - Server error

## Contributing

This is a modular system. You can extend it by:
- Adding new priority algorithms
- Implementing task dependencies
- Adding recurring tasks support
- Integrating with calendar systems
- Adding machine learning for time estimation

## License

MIT License - feel free to use and modify as needed.

## Support

For questions or issues, please refer to the code comments or create an issue in the repository.
