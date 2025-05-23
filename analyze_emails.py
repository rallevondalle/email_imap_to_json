import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta
import re
from email_processor import EmailProcessor
from urllib.parse import urlparse

def analyze_emails(json_file):
    print(f"\nAnalyzing {json_file}...")
    
    # Initialize processor with verbose mode to load contacts
    processor = EmailProcessor(verbose=True)
    
    # Load the JSON file
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        emails = data.get('emails', [])
    
    if not emails:
        print("No emails found in the file.")
        return
    
    # Initialize counters
    sender_counter = Counter()
    subject_counter = Counter()
    newsletter_counter = Counter()
    importance_distribution = Counter()
    time_distribution = Counter()
    attachment_stats = Counter()
    reply_stats = Counter()
    contact_stats = Counter()
    domain_counter = Counter()
    word_counter = Counter()
    blacklist_terms = Counter()
    
    # For reply time analysis
    thread_times = []
    thread_emails = defaultdict(list)
    thread_sizes = Counter()  # Track how many emails are in each thread
    thread_reply_counts = Counter()  # Track how many times you replied in each thread
    
    # Common newsletter indicators
    newsletter_indicators = [
        'newsletter', 'digest', 'weekly', 'monthly', 'daily', 'subscription',
        'subscribe', 'unsubscribe', 'opt-out', 'opt out'
    ]
    
    # Load blacklist terms
    blacklist = processor.blacklist
    
    # First pass: organize emails into threads
    for email in emails:
        message_id = email.get('message_id', '')
        in_reply_to = email.get('in_reply_to', '')
        references = email.get('references', '')
        references_list = references.split() if references else []
        
        # Determine thread root
        thread_root = None
        if in_reply_to:
            thread_root = in_reply_to
        elif references_list:
            thread_root = references_list[0]
        else:
            thread_root = message_id
            
        thread_emails[thread_root].append(email)
        thread_sizes[thread_root] += 1
        
        # If this is a reply, increment the reply count for this thread
        if in_reply_to or references_list:
            thread_reply_counts[thread_root] += 1
    
    # Process each email
    for email in emails:
        # Count senders and domains
        sender = email.get('from', '')
        if sender:
            sender_counter[sender] += 1
            # Extract domain from email
            match = re.search(r'@([\w.-]+)', sender)
            if match:
                domain_counter[match.group(1)] += 1
        
        # Count subjects and words
        subject = email.get('subject', '')
        if subject:
            subject_counter[subject] += 1
            # Count words in subject
            words = re.findall(r'\b\w+\b', subject.lower())
            word_counter.update(words)
            
            # Check for newsletter indicators in subject
            subject_lower = subject.lower()
            if any(indicator in subject_lower for indicator in newsletter_indicators):
                newsletter_counter[subject] += 1
        
        # Count importance scores
        importance = email.get('importance_score', 0)
        importance_distribution[importance] += 1
        
        # Count time distribution (by hour)
        try:
            date_str = email.get('date', '')
            if date_str:
                date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                time_distribution[date_obj.hour] += 1
        except (ValueError, TypeError):
            pass
        
        # Count attachments
        attachments = email.get('attachments', [])
        attachment_stats[len(attachments)] += 1
        
        # Count replies and analyze reply times
        is_reply = email.get('is_reply', False)
        in_reply_to = email.get('in_reply_to', '')
        references = email.get('references', '')
        references_list = references.split() if references else []
        
        # Consider an email a reply if it has in_reply_to or references
        if in_reply_to or references_list:
            reply_stats['replies'] += 1
            
            # Try to find the original email in the thread
            original_message_id = in_reply_to if in_reply_to else references_list[0]
            try:
                # Find the original email in the thread
                original_email = next((e for e in emails if e.get('message_id') == original_message_id), None)
                if original_email:
                    try:
                        original_date = datetime.fromisoformat(original_email['date'].replace('Z', '+00:00'))
                        reply_date = datetime.fromisoformat(email['date'].replace('Z', '+00:00'))
                        reply_time = reply_date - original_date
                        if reply_time > timedelta(0):  # Only count positive reply times
                            thread_times.append(reply_time)
                    except (ValueError, TypeError):
                        pass
            except Exception:
                pass
        else:
            # Check if this email was replied to
            message_id = email.get('message_id', '')
            was_replied_to = any(
                e.get('in_reply_to') == message_id or 
                (e.get('references', '') and message_id in e.get('references', '').split())
                for e in emails
            )
            if was_replied_to:
                reply_stats['replied_to'] += 1
            else:
                reply_stats['not_replied_to'] += 1
        
        # Check if sender is in contacts
        is_from_contact = False
        if processor.contacts:
            try:
                from_parts = sender.split('<')
                if len(from_parts) > 1:
                    sender_email = from_parts[-1].strip('>')
                else:
                    sender_email = sender.strip()
                is_from_contact = sender_email in processor.contacts['emails']
            except Exception:
                pass
        
        if is_from_contact:
            contact_stats['from_contacts'] += 1
        else:
            contact_stats['from_non_contacts'] += 1
            
        # Check for blacklist terms
        text_to_check = f"{subject} {email.get('body', '')}".lower()
        for term in blacklist:
            if term in text_to_check:
                blacklist_terms[term] += 1
    
    # Print statistics
    print(f"\nTotal Emails: {len(emails)}")
    
    print("\nTop 10 Senders:")
    for sender, count in sender_counter.most_common(10):
        print(f"- {sender}: {count} emails")
    
    print("\nTop 10 Email Domains:")
    for domain, count in domain_counter.most_common(10):
        print(f"- {domain}: {count} emails")
    
    print("\nTop 10 Subjects:")
    for subject, count in subject_counter.most_common(10):
        print(f"- {subject}: {count} emails")
    
    print("\nTop 10 Most Common Words in Subjects:")
    for word, count in word_counter.most_common(10):
        print(f"- {word}: {count} occurrences")
    
    print("\nTop 10 Newsletters:")
    for subject, count in newsletter_counter.most_common(10):
        print(f"- {subject}: {count} emails")
    
    print("\nImportance Score Distribution:")
    for score, count in sorted(importance_distribution.items()):
        percentage = (count / len(emails)) * 100
        print(f"- Score {score}: {count} emails ({percentage:.1f}%)")
    
    if time_distribution:
        print("\nTime Distribution (by hour):")
        for hour in range(24):
            count = time_distribution[hour]
            percentage = (count / len(emails)) * 100
            print(f"- {hour:02d}:00: {count} emails ({percentage:.1f}%)")
        
        # Busiest hour
        busiest_hour = max(time_distribution.items(), key=lambda x: x[1])
        print(f"\nBusiest Hour: {busiest_hour[0]:02d}:00 with {busiest_hour[1]} emails")
    
    print("\nAttachment Statistics:")
    for count, emails_count in sorted(attachment_stats.items()):
        percentage = (emails_count / len(emails)) * 100
        print(f"- {count} attachments: {emails_count} emails ({percentage:.1f}%)")
    
    print("\nReply Statistics:")
    for type_, count in reply_stats.items():
        percentage = (count / len(emails)) * 100
        print(f"- {type_}: {count} emails ({percentage:.1f}%)")
    
    # Add detailed thread statistics
    print("\nThread Statistics:")
    total_threads = len(thread_sizes)
    print(f"- Total number of threads: {total_threads}")
    
    # Thread size distribution
    print("\nThread Size Distribution:")
    size_distribution = Counter()
    for thread_root, size in thread_sizes.items():
        size_distribution[size] += 1
    
    for size, count in sorted(size_distribution.items()):
        percentage = (count / total_threads) * 100
        print(f"- {size} emails in thread: {count} threads ({percentage:.1f}%)")
    
    # Your reply frequency in threads
    print("\nYour Reply Frequency in Threads:")
    reply_frequency = Counter()
    for thread_root, reply_count in thread_reply_counts.items():
        thread_size = thread_sizes[thread_root]
        if thread_size > 1:  # Only count threads with multiple emails
            reply_frequency[reply_count] += 1
    
    for reply_count, thread_count in sorted(reply_frequency.items()):
        percentage = (thread_count / total_threads) * 100
        print(f"- {reply_count} replies in thread: {thread_count} threads ({percentage:.1f}%)")
    
    # Calculate and display reply time statistics
    if thread_times:
        avg_reply_time = sum(thread_times, timedelta(0)) / len(thread_times)
        print("\nReply Time Statistics:")
        print(f"- Average Reply Time: {avg_reply_time}")
        print(f"- Fastest Reply: {min(thread_times)}")
        print(f"- Slowest Reply: {max(thread_times)}")
        print(f"- Total Threads Analyzed: {len(thread_times)}")
    
    print("\nContact Statistics:")
    for type_, count in contact_stats.items():
        percentage = (count / len(emails)) * 100
        print(f"- {type_}: {count} emails ({percentage:.1f}%)")
    
    if blacklist_terms:
        print("\nTop 10 Blacklisted Terms Found:")
        for term, count in blacklist_terms.most_common(10):
            print(f"- {term}: {count} occurrences")
    
    # Additional analysis
    print("\nAdditional Statistics:")
    
    # Average importance score
    avg_importance = sum(score * count for score, count in importance_distribution.items()) / len(emails)
    print(f"- Average Importance Score: {avg_importance:.2f}")
    
    # Most common attachment count
    most_common_attachments = max(attachment_stats.items(), key=lambda x: x[1])
    print(f"- Most Common Attachment Count: {most_common_attachments[0]} ({most_common_attachments[1]} emails)")
    
    # Calculate percentages for importance categories
    high_importance = sum(count for score, count in importance_distribution.items() if score >= 5)
    medium_importance = sum(count for score, count in importance_distribution.items() if 0 <= score < 5)
    low_importance = sum(count for score, count in importance_distribution.items() if score < 0)
    
    print("\nImportance Categories:")
    print(f"- High Importance (score >= 5): {high_importance} emails ({(high_importance/len(emails))*100:.1f}%)")
    print(f"- Medium Importance (0 <= score < 5): {medium_importance} emails ({(medium_importance/len(emails))*100:.1f}%)")
    print(f"- Low Importance (score < 0): {low_importance} emails ({(low_importance/len(emails))*100:.1f}%)")

def main():
    # Get all JSON files in the output directory
    output_dir = os.path.join(os.path.dirname(__file__), 'output')
    json_files = [f for f in os.listdir(output_dir) if f.endswith('_raw_emails.json')]
    
    if not json_files:
        print("No JSON files found in the output directory.")
        return
    
    print("Available files:")
    for i, file in enumerate(json_files, 1):
        print(f"{i}. {file}")
    
    # Ask user which file to analyze
    while True:
        try:
            choice = int(input("\nEnter the number of the file to analyze (or 0 to exit): "))
            if choice == 0:
                return
            if 1 <= choice <= len(json_files):
                break
            print("Invalid choice. Please try again.")
        except ValueError:
            print("Please enter a number.")
    
    selected_file = os.path.join(output_dir, json_files[choice - 1])
    analyze_emails(selected_file)

if __name__ == "__main__":
    main() 