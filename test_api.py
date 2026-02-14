"""
Test script for Task Scheduler API
Demonstrates how to use the REST API
"""

import requests
import json
from datetime import datetime


def test_api():
    """Test the Task Scheduler API"""
    
    base_url = "http://localhost:5000/api"
    
    print("=" * 80)
    print("TASK SCHEDULER API TEST")
    print("=" * 80)
    print()
    
    # Test 1: Health Check
    print("Test 1: Health Check")
    print("-" * 80)
    try:
        response = requests.get(f"{base_url}/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        print("✅ Health check passed\n")
    except Exception as e:
        print(f"❌ Health check failed: {e}\n")
        return
    
    # Test 2: Get Example
    print("Test 2: Get Example Payload")
    print("-" * 80)
    try:
        response = requests.get(f"{base_url}/example")
        example_data = response.json()
        print(f"Status: {response.status_code}")
        print(json.dumps(example_data, indent=2))
        print("✅ Example retrieved\n")
    except Exception as e:
        print(f"❌ Failed to get example: {e}\n")
        return
    
    # Test 3: Validate Tasks
    print("Test 3: Validate Tasks")
    print("-" * 80)
    validation_payload = {
        "time_blocks": example_data["time_blocks"],
        "tasks": example_data["tasks"]
    }
    
    try:
        response = requests.post(
            f"{base_url}/validate",
            json=validation_payload,
            headers={"Content-Type": "application/json"}
        )
        result = response.json()
        print(f"Status: {response.status_code}")
        print(f"Valid: {result.get('is_valid')}")
        print(f"Warnings: {result.get('warnings', [])}")
        print("✅ Validation passed\n")
    except Exception as e:
        print(f"❌ Validation failed: {e}\n")
    
    # Test 4: Generate Schedule
    print("Test 4: Generate Schedule")
    print("-" * 80)
    
    schedule_payload = {
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
        "start_date": datetime.now().strftime("%Y-%m-%d")
    }
    
    try:
        response = requests.post(
            f"{base_url}/schedule",
            json=schedule_payload,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"Status: {response.status_code}")
            print(f"Total Days: {result['total_days']}")
            print(f"Validation Warnings: {result['validation_warnings']}")
            print()
            
            # Print first 3 days of schedule
            for day in result['schedule'][:3]:
                print(f"📅 Day {day['day_number']} - {day['date_formatted']}")
                for task in day['scheduled_tasks']:
                    print(f"   {task['start_time']} - {task['end_time']}: {task['task_name']}")
                    print(f"   Progress: {task['day_progress']}")
                if day['warnings']:
                    for warning in day['warnings']:
                        print(f"   ⚠️ {warning}")
                print()
            
            if result['total_days'] > 3:
                print(f"   ... and {result['total_days'] - 3} more days")
            
            print("✅ Schedule generated successfully\n")
        else:
            print(f"❌ Failed with status {response.status_code}")
            print(f"Error: {response.json()}\n")
    
    except Exception as e:
        print(f"❌ Schedule generation failed: {e}\n")
    
    print("=" * 80)
    print("ALL TESTS COMPLETED")
    print("=" * 80)


if __name__ == "__main__":
    print("Make sure the API server is running (python api.py)")
    print("Press Enter to continue or Ctrl+C to cancel...")
    try:
        input()
        test_api()
    except KeyboardInterrupt:
        print("\nTest cancelled")
