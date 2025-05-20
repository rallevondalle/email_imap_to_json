import json
import os
from datetime import datetime, timezone
import email.utils
import re

def make_timezone_aware(dt):
    """Convert naive datetime to timezone-aware using UTC"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt

def parse_date(date_str):
    """Parse date string in various formats"""
    if not date_str or date_str == 'None' or date_str == 'null':
        return None
        
    # Clean up the date string
    date_str = date_str.strip()
    
    # Try to extract date from common email header formats
    date_patterns = [
        r'Date:\s*(.*?)(?:\r?\n|$)',  # Standard email Date header
        r'Received:\s*.*?;\s*(.*?)(?:\r?\n|$)',  # Received header
        r'Delivery-Date:\s*(.*?)(?:\r?\n|$)',  # Delivery-Date header
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, date_str, re.IGNORECASE)
        if match:
            date_str = match.group(1).strip()
            break
    
    try:
        # Try RFC 2822 format first
        dt = email.utils.parsedate_to_datetime(date_str)
        return make_timezone_aware(dt)
    except (TypeError, ValueError):
        try:
            # Try ISO format
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return make_timezone_aware(dt)
        except (ValueError, AttributeError):
            try:
                # Try common email date formats
                formats = [
                    '%a, %d %b %Y %H:%M:%S %z',
                    '%a, %d %b %Y %H:%M:%S %Z',
                    '%a, %d %b %Y %H:%M:%S %z (%Z)',
                    '%a, %d %b %Y %H:%M:%S %z %Z',
                    '%a, %d %b %Y %H:%M:%S %z%Z',
                    '%a, %d %b %Y %H:%M:%S',
                    '%Y-%m-%d %H:%M:%S %z',
                    '%Y-%m-%d %H:%M:%S',
                    '%d %b %Y %H:%M:%S %z',
                    '%d %b %Y %H:%M:%S',
                    '%Y-%m-%dT%H:%M:%S.%f%z',
                    '%Y-%m-%dT%H:%M:%S%z',
                    '%Y-%m-%dT%H:%M:%S.%f',
                    '%Y-%m-%dT%H:%M:%S',
                    '%d %b %Y %H:%M:%S %z (%Z)',
                    '%d %b %Y %H:%M:%S %Z',
                    '%d %b %Y %H:%M:%S %z',
                    '%d %b %Y %H:%M:%S'
                ]
                
                # Try to extract timezone if present
                tz_match = re.search(r'([+-]\d{4}|[A-Z]{3,4}|[A-Z]{3,4}\s*\([A-Z]{3,4}\))', date_str)
                if tz_match:
                    tz = tz_match.group(1)
                    # Remove timezone for initial parsing
                    date_str_no_tz = date_str.replace(tz, '').strip()
                    for fmt in formats:
                        try:
                            dt = datetime.strptime(date_str_no_tz, fmt.replace(' %z', '').replace(' %Z', ''))
                            # Add timezone back
                            if tz.startswith('+') or tz.startswith('-'):
                                dt = dt.replace(tzinfo=datetime.strptime(tz, '%z').tzinfo)
                            return make_timezone_aware(dt)
                        except ValueError:
                            continue
                else:
                    # Try without timezone
                    for fmt in formats:
                        try:
                            dt = datetime.strptime(date_str, fmt.replace(' %z', '').replace(' %Z', ''))
                            return make_timezone_aware(dt)
                        except ValueError:
                            continue
            except Exception:
                pass
    return None

def fix_json_file(file_path):
    """Fix line terminators and date formatting in a JSON file"""
    print(f"\nProcessing {file_path}...")
    
    try:
        # Read the existing file
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Special handling for contacts.json
        if os.path.basename(file_path) == 'contacts.json':
            # Ensure all required fields exist
            required_fields = ['emails', 'names', 'first_names', 'last_names', 'organizations']
            for field in required_fields:
                if field not in data:
                    data[field] = []
            
            # Save with fixed structure
            with open(file_path, 'w', encoding='utf-8', newline='\n') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print(f"Successfully fixed {file_path}")
            return
        
        # Fix line terminators in email bodies
        for email in data.get('emails', []):
            if 'body' in email:
                email['body'] = email['body'].replace('\r\n', '\n').replace('\r', '\n')
        
        # Fix date range in summary
        summary = data.get('summary', {})
        date_range = summary.get('date_range', {})
        
        # Recalculate date range
        valid_dates = []
        invalid_dates = []
        
        for email in data.get('emails', []):
            date_str = email.get('date', '')
            if date_str:
                date_obj = parse_date(date_str)
                if date_obj:
                    valid_dates.append(date_obj)
                    # Update the email's date to ISO format
                    email['date'] = date_obj.isoformat()
                else:
                    # Try to get date from headers if available
                    headers = email.get('headers', {})
                    for header in ['date', 'received', 'delivery-date']:
                        if header in headers:
                            date_obj = parse_date(headers[header])
                            if date_obj:
                                valid_dates.append(date_obj)
                                email['date'] = date_obj.isoformat()
                                break
                    else:
                        invalid_dates.append((email.get('message_id', 'unknown'), date_str))
        
        if valid_dates:
            # Ensure all dates are timezone-aware before comparison
            valid_dates = [make_timezone_aware(dt) for dt in valid_dates]
            date_range = {
                'oldest': min(valid_dates).isoformat(),
                'newest': max(valid_dates).isoformat()
            }
            summary['date_range'] = date_range
            data['summary'] = summary
            
            # Report invalid dates
            if invalid_dates:
                print(f"Warning: Found {len(invalid_dates)} invalid dates in {file_path}")
                for msg_id, date in invalid_dates[:5]:  # Show first 5 invalid dates
                    print(f"  - Message {msg_id}: {date}")
                if len(invalid_dates) > 5:
                    print(f"  ... and {len(invalid_dates) - 5} more")
        else:
            print(f"Warning: No valid dates found in {file_path}")
        
        # Save with fixed line endings
        with open(file_path, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"Successfully fixed {file_path}")
        if valid_dates:
            print(f"Date range: {date_range['oldest']} to {date_range['newest']}")
        
    except Exception as e:
        print(f"Error processing {file_path}: {str(e)}")

def main():
    # Get the output directory
    output_dir = os.path.join(os.path.dirname(__file__), 'output')
    
    # Process all JSON files in the output directory
    for filename in os.listdir(output_dir):
        if filename.endswith('.json'):
            file_path = os.path.join(output_dir, filename)
            fix_json_file(file_path)

if __name__ == "__main__":
    main() 