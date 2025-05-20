import json
import os
from datetime import datetime
import glob
import email.utils

def parse_date(date_str):
    """Parse date string in either RFC 2822 or ISO format"""
    if not date_str:
        return None  # Return None for empty dates instead of raising error
    
    try:
        # Try RFC 2822 format first
        parsed_date = email.utils.parsedate_to_datetime(date_str)
        return parsed_date
    except (TypeError, ValueError):
        try:
            # Try ISO format
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            return None  # Return None for invalid dates instead of raising error

def check_json_file(file_path):
    """Check if a JSON file is valid and properly formatted"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Special handling for contacts.json
        if os.path.basename(file_path) == 'contacts.json':
            required_fields = ['emails', 'names', 'first_names', 'last_names', 'organizations']
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                print(f"❌ Error: Missing required fields: {', '.join(missing_fields)}")
                return False
            return True
        
        # For email files, check for required structure
        if not isinstance(data, dict):
            print("❌ Error: Root object must be a dictionary")
            return False
        
        if 'emails' not in data:
            print("❌ Error: Missing 'emails' array")
            return False
        
        if not isinstance(data['emails'], list):
            print("❌ Error: 'emails' must be an array")
            return False
        
        # Check each email object
        emails_count = len(data['emails'])
        print(f"Found {emails_count} emails")
        
        # Track issues
        issues = []
        
        for i, email in enumerate(data['emails'], 1):
            # Required fields
            required_fields = ['subject', 'from', 'date', 'message_id', 'importance_score']
            missing_fields = [field for field in required_fields if field not in email]
            if missing_fields:
                issues.append(f"Email {i}: Missing required fields: {', '.join(missing_fields)}")
                continue
            
            # Check date format
            date = parse_date(email['date'])
            if date is None:
                issues.append(f"Email {i}: Invalid date format: {email['date']}")
        
        # Check date range if summary exists
        if 'summary' in data and 'date_range' in data['summary']:
            date_range = data['summary']['date_range']
            if 'oldest' in date_range and 'newest' in date_range:
                oldest = parse_date(date_range['oldest'])
                newest = parse_date(date_range['newest'])
                if oldest is None or newest is None:
                    issues.append("Invalid date range format in summary")
                else:
                    print(f"Date range: {oldest.isoformat()} to {newest.isoformat()}")
        
        # Print any issues found
        if issues:
            for issue in issues:
                print(f"❌ Error: {issue}")
            return False
        
        return True
        
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON format: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

def main():
    # Get all JSON files in the output directory
    output_dir = 'output'
    json_files = glob.glob(os.path.join(output_dir, '*.json'))
    
    # Sort files to process contacts.json first
    json_files.sort(key=lambda x: os.path.basename(x) != 'contacts.json')
    
    all_valid = True
    for file_path in json_files:
        print(f"\nChecking {file_path}...")
        if not check_json_file(file_path):
            all_valid = False
            continue
        print(f"✅ {file_path} is valid and properly formatted")
    
    if not all_valid:
        print("\n❌ Some files have issues that need to be fixed")
    else:
        print("\n✅ All files are valid and properly formatted")

if __name__ == "__main__":
    main() 