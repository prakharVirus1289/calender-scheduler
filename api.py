"""
Flask REST API for Task Scheduler
Features: Closed time slots, hours-based tracking, JSON persistence
"""

from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from datetime import datetime
from task_scheduler import (
    TaskScheduler, Task, ClosedTimeSlot, Priority,
    DaySchedule, ScheduledTask
)
from typing import List, Dict, Any
import json
from pathlib import Path
import os

app = Flask(__name__)
CORS(app)

# Storage directory for user data
# STORAGE_DIR = Path("scheduler_storage")
# STORAGE_DIR.mkdir(exist_ok=True)

STORAGE_DIR = "./scheduler_storage"

# Static files directory (for serving HTML)
STATIC_DIR = Path(__file__).parent


def serialize_scheduled_task(task: ScheduledTask) -> Dict[str, Any]:
    """Convert ScheduledTask to JSON-serializable dict"""
    return {
        'task_name': task.task_name,    
        'start_time': task.start_time,
        'end_time': task.end_time,
        'duration_hours': task.duration_hours,
        'priority': task.priority.value,
        'progress': task.progress,
        'task_id': task.task_id
    }


def serialize_day_schedule(day: DaySchedule) -> Dict[str, Any]:
    """Convert DaySchedule to JSON-serializable dict"""
    return {
        'day_number': day.day_number,
        'date': day.date.strftime('%Y-%m-%d'),
        'date_formatted': day.date.strftime('%A, %B %d, %Y'),
        'scheduled_tasks': [serialize_scheduled_task(task) for task in day.scheduled_tasks],
        'warnings': day.warnings
    }


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""

    print("checking ewefwef" , flush=True)

    return jsonify({'status': 'healthy', 'message': 'Task Scheduler API is running'})


@app.route('/page', methods=['GET'])
@app.route('/', methods=['GET'])
def serve_page():
    """Serve the task scheduler HTML interface"""
    try:
        html_file = STATIC_DIR / "task-scheduler.html"
        if html_file.exists():
            return send_file(html_file)
        else:
            return jsonify({
                'error': 'HTML interface not found',
                'message': 'Please ensure task-scheduler.html is in the same directory as api.py'
            }), 404
    except Exception as e:
        return jsonify({
            'error': f'Failed to serve page: {str(e)}'
        }), 500


@app.route('/api/schedule', methods=['POST'])
def generate_schedule():
    """
    Generate schedule with closed time slots and hours-based tracking
    
    Expected JSON payload:
    {
        "closed_slots": [
            {
                "start_hour": 0, "start_minute": 0,
                "end_hour": 8, "end_minute": 0,
                "applies_to": "all_days"  // or "specific_date" or "weekdays"
                "specific_date": "2024-02-20"  // optional, for specific_date
                "weekdays": [0, 1, 2]  // optional, for weekdays (0=Mon, 6=Sun)
            }
        ],
        "tasks": [
            {
                "id": 1,
                "name": "Task Name",
                "total_hours": 10.0,
                "hours_per_session": 2.0,
                "priority": 1,
                "deadline_day": 10
            }
        ],
        "buffer_minutes": 15,
        "max_tasks_per_day": 2,
        "start_date": "now" or "2024-02-15"
    }
    """
    try:
        data = request.get_json()
        
        if 'closed_slots' not in data or 'tasks' not in data:
            return jsonify({
                'error': 'Missing required fields: closed_slots and tasks are required'
            }), 400
        
        # Parse closed time slots
        closed_slots = []
        for slot_data in data['closed_slots']:
            try:
                slot = ClosedTimeSlot(
                    start_hour=slot_data['start_hour'],
                    start_minute=slot_data['start_minute'],
                    end_hour=slot_data['end_hour'],
                    end_minute=slot_data['end_minute'],
                    applies_to=slot_data['applies_to'],
                    specific_date=slot_data.get('specific_date'),
                    weekdays=slot_data.get('weekdays')
                )
                closed_slots.append(slot)
            except (KeyError, ValueError) as e:
                return jsonify({
                    'error': f'Invalid closed slot format: {str(e)}'
                }), 400
        
        # Parse tasks
        tasks = []
        for task_data in data['tasks']:
            try:
                task = Task(
                    id=task_data['id'],
                    name=task_data['name'],
                    total_hours=task_data['total_hours'],
                    hours_per_session=task_data['hours_per_session'],
                    priority=Priority(task_data['priority']),
                    deadline_day=task_data['deadline_day'],
                    hours_completed=task_data.get('hours_completed', 0.0),
                    in_progress=task_data.get('in_progress', False)
                )
                tasks.append(task)
            except (KeyError, ValueError) as e:
                return jsonify({
                    'error': f'Invalid task format: {str(e)}'
                }), 400
        
        if not tasks:
            return jsonify({'error': 'At least one task is required'}), 400
        
        # Parse configuration
        buffer_minutes = data.get('buffer_minutes', 15)
        max_tasks_per_day = data.get('max_tasks_per_day', 2)
        
        # Parse start date
        start_date_str = data.get('start_date', 'now')
        if start_date_str == 'now':
            start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            except ValueError:
                return jsonify({
                    'error': 'Invalid start_date format. Use "now" or YYYY-MM-DD'
                }), 400
        
        # Create scheduler
        scheduler = TaskScheduler(
            closed_slots=closed_slots,
            buffer_minutes=buffer_minutes,
            max_tasks_per_day=max_tasks_per_day,
            start_date=start_date,
            storage_file=str(STORAGE_DIR / "last_schedule.json")
        )
        
        # Generate schedule
        schedule, warnings = scheduler.schedule_tasks(tasks)
        
        # Save to file
        scheduler.save_data(tasks, schedule)
        
        # Serialize response
        response = {
            'success': True,
            'schedule': [serialize_day_schedule(day) for day in schedule],
            'validation_warnings': warnings,
            'total_days': len(schedule),
            'saved_to': str(STORAGE_DIR / "last_schedule.json")
        }
        
        return jsonify(response)
    
    except Exception as e:
        return jsonify({
            'error': f'Internal server error: {str(e)}'
        }), 500


@app.route('/api/save', methods=['POST'])
def save_tasks():
    """
    Save tasks, closed slots, and all configuration (without generating schedule)
    """
    try:
        data = request.get_json()
        
        # Validate that we have the required data
        if 'tasks' not in data or 'closed_slots' not in data:
            return jsonify({
                'error': 'Missing required fields: tasks and closed_slots are required'
            }), 400
        
        # Add timestamp
        data['saved_at'] = datetime.now().isoformat()
        
        # Save to file
        save_file = STORAGE_DIR / "tasks.json"
        with open(save_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        return jsonify({
            'success': True,
            'message': 'All data saved successfully',
            'saved_to': str(save_file),
            'saved_data': {
                'tasks': len(data['tasks']),
                'closed_slots': len(data['closed_slots']),
                'has_config': 'config' in data
            }
        })
    
    except Exception as e:
        return jsonify({
            'error': f'Save error: {str(e)}'
        }), 500


@app.route('/api/load', methods=['GET'])
def load_tasks():
    """
    Load saved tasks and configuration
    """
    try:
        # save_file = STORAGE_DIR / "tasks.json"
        save_file = 'C:/Users/ASUS/Documents/GitHub/calender-scheduler/scheduler_storage/tasks.json'
        
        if not save_file.exists():
            return jsonify({
                'success': False,
                'message': 'No saved tasks found'
            }), 404
        
        with open(save_file, 'r') as f:
            data = json.load(f)
        
        return jsonify({
            'success': True,
            'data': data,
            'message': 'Tasks loaded successfully'
        })
    
    except Exception as e:
        return jsonify({
            'error': f'Load error: {str(e)}'
        }), 500


@app.route('/api/load_schedule', methods=['GET'])
def load_schedule():
    """
    Load the last generated schedule
    """
    try:
        schedule_file = STORAGE_DIR / "last_schedule.json"
        
        if not schedule_file.exists():
            return jsonify({
                'success': False,
                'message': 'No saved schedule found'
            }), 404
        
        with open(schedule_file, 'r') as f:
            data = json.load(f)
        
        return jsonify({
            'success': True,
            'data': data,
            'message': 'Schedule loaded successfully'
        })
    
    except Exception as e:
        return jsonify({
            'error': f'Load error: {str(e)}'
        }), 500


@app.route('/api/validate', methods=['POST'])
def validate_tasks():
    """
    Validate tasks against available time (considering closed slots)
    """
    try:
        data = request.get_json()
        
        # Parse closed slots
        closed_slots = []
        for slot_data in data['closed_slots']:
            slot = ClosedTimeSlot(
                start_hour=slot_data['start_hour'],
                start_minute=slot_data['start_minute'],
                end_hour=slot_data['end_hour'],
                end_minute=slot_data['end_minute'],
                applies_to=slot_data['applies_to'],
                specific_date=slot_data.get('specific_date'),
                weekdays=slot_data.get('weekdays')
            )
            closed_slots.append(slot)
        
        # Parse tasks
        tasks = []
        for task_data in data['tasks']:
            task = Task(
                id=task_data['id'],
                name=task_data['name'],
                total_hours=task_data['total_hours'],
                hours_per_session=task_data['hours_per_session'],
                priority=Priority(task_data['priority']),
                deadline_day=task_data['deadline_day']
            )
            tasks.append(task)
        
        # Create scheduler and validate
        scheduler = TaskScheduler(closed_slots=closed_slots)
        warnings = scheduler.validate_tasks(tasks)
        
        return jsonify({
            'success': True,
            'warnings': warnings,
            'is_valid': len(warnings) == 0
        })
    
    except Exception as e:
        return jsonify({
            'error': f'Validation error: {str(e)}'
        }), 400


@app.route('/api/example', methods=['GET'])
def get_example():
    """Return an example request payload with closed slots"""
    example = {
        "closed_slots": [
            # Sleep
            {"start_hour": 0, "start_minute": 0, "end_hour": 8, "end_minute": 0, "applies_to": "all_days"},
            {"start_hour": 22, "start_minute": 0, "end_hour": 24, "end_minute": 0, "applies_to": "all_days"},
            # Lunch
            {"start_hour": 12, "start_minute": 0, "end_hour": 13, "end_minute": 0, "applies_to": "all_days"},
            # Dinner
            {"start_hour": 20, "start_minute": 0, "end_hour": 21, "end_minute": 0, "applies_to": "all_days"},
            # Weekend sleep-in
            {"start_hour": 8, "start_minute": 0, "end_hour": 10, "end_minute": 0, "applies_to": "weekdays", "weekdays": [5, 6]}
        ],
        "tasks": [
            {
                "id": 1,
                "name": "Complete Project Report",
                "total_hours": 10.0,
                "hours_per_session": 2.0,
                "priority": 1,
                "deadline_day": 10
            },
            {
                "id": 2,
                "name": "Study for Exam",
                "total_hours": 9.0,
                "hours_per_session": 3.0,
                "priority": 1,
                "deadline_day": 7
            }
        ],
        "buffer_minutes": 15,
        "max_tasks_per_day": 2,
        "start_date": "now"
    }
    
    return jsonify(example)


if __name__ == '__main__':
    print("=" * 80)
    print("Task Scheduler API Server")
    print("=" * 80)
    print("\nNew Features:")
    print("  - Closed time slots (blocked times)")
    print("  - Hours-based progress tracking")
    print("  - JSON persistence for tasks and schedules")
    print("\nWeb Interface:")
    print("  http://localhost:5000/         - Main page")
    print("  http://localhost:5000/page     - Main page (alternative)")
    print("\nAPI endpoints:")
    print("  GET  /api/health         - Health check")
    print("  POST /api/schedule       - Generate schedule")
    print("  POST /api/save          - Save tasks")
    print("  GET  /api/load          - Load tasks")
    print("  GET  /api/load_schedule - Load last schedule")
    print("  POST /api/validate      - Validate tasks")
    print("  GET  /api/example       - Get example payload")
    # print(f"\nStorage directory: {STORAGE_DIR.absolute()}")
    print("\nServer running on http://localhost:5000")
    print("=" * 80)
    print()
    
    app.run(debug=True, host='0.0.0.0', port=5000)