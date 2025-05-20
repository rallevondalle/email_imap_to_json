import json
import os
from email_processor import EmailProcessor
from collections import defaultdict

def get_available_files():
    """Get list of available email JSON files"""
    output_dir = 'output'
    json_files = [f for f in os.listdir(output_dir) if f.endswith('_raw_emails.json')]
    return sorted(json_files)

def process_file(processor, file_path):
    """Process a single file and return statistics about score changes"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            emails = data.get('emails', [])
        
        if not emails:
            return None
            
        # Store original scores
        original_scores = {email['message_id']: email.get('importance_score', 0) for email in emails}
        
        # Update scores
        updated_emails = processor.score_emails(emails)
        
        # Calculate statistics
        stats = {
            'total_emails': len(emails),
            'score_changes': defaultdict(int),  # Count of emails by score change
            'high_importance': 0,  # Count of high importance emails (score >= 3)
            'medium_importance': 0,  # Count of medium importance emails (1 <= score < 3)
            'low_importance': 0,  # Count of low importance emails (score < 1)
            'max_increase': 0,
            'max_decrease': 0,
            'total_change': 0
        }
        
        for email in updated_emails:
            old_score = original_scores[email['message_id']]
            new_score = email['importance_score']
            score_change = new_score - old_score
            
            # Track score changes
            stats['score_changes'][score_change] += 1
            stats['total_change'] += score_change
            
            # Track max changes
            stats['max_increase'] = max(stats['max_increase'], score_change)
            stats['max_decrease'] = min(stats['max_decrease'], score_change)
            
            # Track importance levels
            if new_score >= 3:
                stats['high_importance'] += 1
            elif new_score >= 1:
                stats['medium_importance'] += 1
            else:
                stats['low_importance'] += 1
        
        # Save updated file
        data['emails'] = updated_emails
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return stats
        
    except Exception as e:
        print(f"Error processing {file_path}: {str(e)}")
        return None

def main():
    # Initialize processor
    processor = EmailProcessor(verbose=True)
    
    # Get available files
    json_files = get_available_files()
    
    if not json_files:
        print("No email files found in output directory!")
        return
    
    # Display available files
    print("\nAvailable files:")
    for i, file_name in enumerate(json_files, 1):
        print(f"{i}. {file_name}")
    print(f"{len(json_files) + 1}. Process all files")
    
    # Get user selection
    while True:
        try:
            choice = input("\nSelect file number to process (or 'q' to quit): ")
            if choice.lower() == 'q':
                return
            
            choice = int(choice)
            if choice == len(json_files) + 1:
                selected_files = json_files
                break
            elif 1 <= choice <= len(json_files):
                selected_files = [json_files[choice - 1]]
                break
            else:
                print("Invalid selection. Please try again.")
        except ValueError:
            print("Please enter a valid number.")
    
    # Process selected files and collect statistics
    all_stats = {}
    total_stats = {
        'total_emails': 0,
        'score_changes': defaultdict(int),
        'high_importance': 0,
        'medium_importance': 0,
        'low_importance': 0,
        'max_increase': 0,
        'max_decrease': 0,
        'total_change': 0
    }
    
    print("\nProcessing files...")
    for file_name in selected_files:
        file_path = os.path.join('output', file_name)
        print(f"\nProcessing {file_name}...")
        
        stats = process_file(processor, file_path)
        if stats:
            all_stats[file_name] = stats
            
            # Update total statistics
            total_stats['total_emails'] += stats['total_emails']
            total_stats['high_importance'] += stats['high_importance']
            total_stats['medium_importance'] += stats['medium_importance']
            total_stats['low_importance'] += stats['low_importance']
            total_stats['max_increase'] = max(total_stats['max_increase'], stats['max_increase'])
            total_stats['max_decrease'] = min(total_stats['max_decrease'], stats['max_decrease'])
            total_stats['total_change'] += stats['total_change']
            
            # Merge score changes
            for change, count in stats['score_changes'].items():
                total_stats['score_changes'][change] += count
    
    # Print detailed summary
    print("\n" + "="*80)
    print("SCORE UPDATE SUMMARY")
    print("="*80)
    
    print(f"\nTotal Emails Processed: {total_stats['total_emails']}")
    print(f"Total Score Change: {total_stats['total_change']}")
    print(f"Maximum Score Increase: {total_stats['max_increase']}")
    print(f"Maximum Score Decrease: {total_stats['max_decrease']}")
    
    print("\nImportance Distribution:")
    print(f"High Importance (score >= 3): {total_stats['high_importance']} emails")
    print(f"Medium Importance (1 <= score < 3): {total_stats['medium_importance']} emails")
    print(f"Low Importance (score < 1): {total_stats['low_importance']} emails")
    
    print("\nScore Changes Distribution:")
    for change in sorted(total_stats['score_changes'].keys()):
        count = total_stats['score_changes'][change]
        print(f"Score {change:+d}: {count} emails")
    
    print("\nPer-File Statistics:")
    for file_name, stats in all_stats.items():
        print(f"\n{file_name}:")
        print(f"  Total Emails: {stats['total_emails']}")
        print(f"  Score Change: {stats['total_change']}")
        print(f"  High Importance: {stats['high_importance']}")
        print(f"  Medium Importance: {stats['medium_importance']}")
        print(f"  Low Importance: {stats['low_importance']}")

if __name__ == "__main__":
    main() 