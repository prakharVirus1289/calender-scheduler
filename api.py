"""
Flask REST API for Task Scheduler
Provides endpoints to schedule tasks via HTTP requests
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
from task_scheduler import (
    TaskScheduler, Task, TimeBlock, Priority,
    DaySchedule, ScheduledTask
)
from typing import List, Dict, Any

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend communication


def serialize_scheduled_task(task: ScheduledTask) -> Dict[str, Any]:
    """Convert ScheduledTask to JSON-serializable dict"""
    return {
        'task_name': task.task_name,
        'start_time': task.start_time,
        'end_time': task.end_time,
        'duration_hours': task.duration_hours,
        'priority': task.priority.value,
        'day_progress': task.day_progress,
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
    return jsonify({'status': 'healthy', 'message': 'Task Scheduler API is running'})


@app.route('/api/schedule', methods=['POST'])
def generate_schedule():
    """
    Generate a schedule from provided tasks and configuration
    
    Expected JSON payload:
    {
        "time_blocks": [
            {"start_hour": 9, "start_minute": 0, "end_hour": 12, "end_minute": 0},
            ...
        ],
        "tasks": [
            {
                "id": 1,
                "name": "Task Name",
                "days_needed": 5,
                "hours_per_day": 2.0,
                "priority": 1,  // 1=High, 2=Medium, 3=Low
                "deadline_day": 10
            },
            ...
        ],
        "buffer_minutes": 15,
        "max_tasks_per_day": 2,
        "start_date": "2024-02-15"  // Optional, defaults to today
    }
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        if 'time_blocks' not in data or 'tasks' not in data:
            return jsonify({
                'error': 'Missing required fields: time_blocks and tasks are required'
            }), 400
        
        # Parse time blocks
        time_blocks = []
        for block_data in data['time_blocks']:
            try:
                block = TimeBlock(
                    start_hour=block_data['start_hour'],
                    start_minute=block_data['start_minute'],
                    end_hour=block_data['end_hour'],
                    end_minute=block_data['end_minute']
                )
                time_blocks.append(block)
            except (KeyError, ValueError) as e:
                return jsonify({
                    'error': f'Invalid time block format: {str(e)}'
                }), 400
        
        if not time_blocks:
            return jsonify({'error': 'At least one time block is required'}), 400
        
        # Parse tasks
        tasks = []
        for task_data in data['tasks']:
            try:
                task = Task(
                    id=task_data['id'],
                    name=task_data['name'],
                    days_needed=task_data['days_needed'],
                    hours_per_day=task_data['hours_per_day'],
                    priority=Priority(task_data['priority']),
                    deadline_day=task_data['deadline_day']
                )
                tasks.append(task)
            except (KeyError, ValueError) as e:
                return jsonify({
                    'error': f'Invalid task format: {str(e)}'
                }), 400
        
        if not tasks:
            return jsonify({'error': 'At least one task is required'}), 400
        
        # Parse optional parameters
        buffer_minutes = data.get('buffer_minutes', 15)
        max_tasks_per_day = data.get('max_tasks_per_day', 2)
        
        # Parse start date
        start_date = None
        if 'start_date' in data:
            try:
                start_date = datetime.strptime(data['start_date'], '%Y-%m-%d')
            except ValueError:
                return jsonify({
                    'error': 'Invalid start_date format. Use YYYY-MM-DD'
                }), 400
        
        # Create scheduler
        scheduler = TaskScheduler(
            available_blocks=time_blocks,
            buffer_minutes=buffer_minutes,
            max_tasks_per_day=max_tasks_per_day,
            start_date=start_date
        )
        
        # Generate schedule
        schedule, warnings = scheduler.schedule_tasks(tasks)
        
        # Serialize response
        response = {
            'success': True,
            'schedule': [serialize_day_schedule(day) for day in schedule],
            'validation_warnings': warnings,
            'total_days': len(schedule)
        }
        
        return jsonify(response)
    
    except Exception as e:
        return jsonify({
            'error': f'Internal server error: {str(e)}'
        }), 500


@app.route('/api/validate', methods=['POST'])
def validate_tasks():
    """
    Validate tasks against available time blocks
    
    Expected JSON payload:
    {
        "time_blocks": [...],
        "tasks": [...]
    }
    """
    try:
        data = request.get_json()
        
        # Parse time blocks
        time_blocks = []
        for block_data in data['time_blocks']:
            block = TimeBlock(
                start_hour=block_data['start_hour'],
                start_minute=block_data['start_minute'],
                end_hour=block_data['end_hour'],
                end_minute=block_data['end_minute']
            )
            time_blocks.append(block)
        
        # Parse tasks
        tasks = []
        for task_data in data['tasks']:
            task = Task(
                id=task_data['id'],
                name=task_data['name'],
                days_needed=task_data['days_needed'],
                hours_per_day=task_data['hours_per_day'],
                priority=Priority(task_data['priority']),
                deadline_day=task_data['deadline_day']
            )
            tasks.append(task)
        
        # Create scheduler and validate
        scheduler = TaskScheduler(available_blocks=time_blocks)
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
    """Return an example request payload"""
    example = {
        "time_blocks": [
            {"start_hour": 9, "start_minute": 0, "end_hour": 12, "end_minute": 0},
            {"start_hour": 13, "start_minute": 0, "end_hour": 18, "end_minute": 0},
            {"start_hour": 19, "start_minute": 0, "end_hour": 20, "end_minute": 0}
        ],
        "tasks": [
            {
                "id": 1,
                "name": "Complete Project Report",
                "days_needed": 5,
                "hours_per_day": 2.0,
                "priority": 1,
                "deadline_day": 10
            },
            {
                "id": 2,
                "name": "Study for Exam",
                "days_needed": 3,
                "hours_per_day": 3.0,
                "priority": 1,
                "deadline_day": 7
            },
            {
                "id": 3,
                "name": "Code Review Tasks",
                "days_needed": 4,
                "hours_per_day": 1.5,
                "priority": 2,
                "deadline_day": 12
            }
        ],
        "buffer_minutes": 15,
        "max_tasks_per_day": 2,
        "start_date": "2024-02-15"
    }
    
    return jsonify(example)


if __name__ == '__main__':
    print("=" * 80)
    print("Task Scheduler API Server")
    print("=" * 80)
    print("\nAvailable endpoints:")
    print("  GET  /api/health    - Health check")
    print("  POST /api/schedule  - Generate schedule")
    print("  POST /api/validate  - Validate tasks")
    print("  GET  /api/example   - Get example payload")
    print("\nServer running on http://localhost:5000")
    print("=" * 80)
    print()
    
    app.run(debug=True, host='0.0.0.0', port=5000)
