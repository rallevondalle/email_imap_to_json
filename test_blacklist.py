import os
from email_processor import EmailProcessor

def test_blacklist():
    # Initialize processor with verbose mode
    processor = EmailProcessor(verbose=True)
    
    # Print blacklist contents
    print("\nLoaded blacklist terms:")
    if processor.blacklist:
        for term in sorted(processor.blacklist):
            print(f"- {term}")
    else:
        print("No blacklist terms found!")
    
    # Test some example emails
    test_emails = [
        {
            'subject': 'Your weekly newsletter is here!',
            'from': 'newsletter@example.com',
            'body': 'This is your weekly newsletter with updates and news.',
            'to': 'user@example.com',
            'is_from_contact': False,
            'is_reply': False,
            'attachments': [],
            'importance_score': 0
        },
        {
            'subject': 'Special offer - 50% off!',
            'from': 'marketing@example.com',
            'body': 'Limited time offer with special discount code.',
            'to': 'user@example.com',
            'is_from_contact': False,
            'is_reply': False,
            'attachments': [],
            'importance_score': 0
        },
        {
            'subject': 'Important meeting tomorrow',
            'from': 'colleague@company.com',
            'body': 'Please join the meeting at 2 PM to discuss the project.',
            'to': 'user@example.com',
            'is_from_contact': True,
            'is_reply': True,
            'attachments': [],
            'importance_score': 0
        }
    ]
    
    print("\nTesting blacklist scoring:")
    for email in test_emails:
        score = processor._calculate_importance_score(email)
        print(f"\nEmail: {email['subject']}")
        print(f"From: {email['from']}")
        print(f"Score: {score}")
        print(f"Content: {email['body']}")
        
        # Check if any blacklisted terms are present
        text_to_check = f"{email['subject']} {email['from']} {email['body']}".lower()
        found_terms = [term for term in processor.blacklist if term in text_to_check]
        if found_terms:
            print("Found blacklisted terms:")
            for term in found_terms:
                print(f"- {term}")
        else:
            print("No blacklisted terms found")

if __name__ == "__main__":
    test_blacklist() 