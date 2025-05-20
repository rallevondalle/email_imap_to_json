import csv
import json
import os
from datetime import datetime
from email_validator import validate_email, EmailNotValidError

def update_contacts():
    # Load existing contacts
    contacts_file = os.path.join(os.path.dirname(__file__), 'output', 'contacts.json')
    if not os.path.exists(contacts_file):
        print("No existing contacts.json found. Please run parse_contacts.py first.")
        return
    
    try:
        with open(contacts_file, 'r', encoding='utf-8') as f:
            existing_contacts = json.load(f)
    except Exception as e:
        print(f"Error loading existing contacts: {str(e)}")
        return
    
    # Convert lists back to sets for easier comparison
    existing_contacts = {
        'emails': set(existing_contacts['emails']),
        'names': set(existing_contacts['names']),
        'first_names': set(existing_contacts['first_names']),
        'last_names': set(existing_contacts['last_names']),
        'organizations': set(existing_contacts['organizations'])
    }
    
    # Define possible locations for contacts.csv
    possible_locations = [
        os.path.join(os.path.dirname(__file__), 'contacts.csv'),  # Project directory
        os.path.expanduser('~/Downloads/contacts.csv'),           # Downloads folder
        os.path.expanduser('~/Desktop/contacts.csv')             # Desktop
    ]
    
    # Try each location until we find the file
    csv_file = None
    for location in possible_locations:
        if os.path.exists(location):
            csv_file = location
            break
    
    if not csv_file:
        print("No contacts.csv file found. Please place it in the project directory, Downloads, or Desktop.")
        return
    
    print(f"Found contacts file at: {csv_file}")
    
    # Initialize new contacts data structure
    new_contacts = {
        'emails': set(),
        'names': set(),
        'first_names': set(),
        'last_names': set(),
        'organizations': set()
    }
    
    try:
        print("Parsing new contacts...")
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            row_count = 0
            for row in reader:
                row_count += 1
                if row_count % 100 == 0:
                    print(f"Processed {row_count} contacts...")
                
                # Process email addresses
                email_fields = ['E-mail 1 - Value', 'E-mail 2 - Value', 'E-mail 3 - Value']
                for field in email_fields:
                    if field in row and row[field]:
                        try:
                            email = validate_email(row[field].strip()).email
                            new_contacts['emails'].add(email)
                        except EmailNotValidError:
                            continue
                
                # Process names and organization
                if 'First Name' in row and row['First Name']:
                    first_name = row['First Name'].strip().lower()
                    new_contacts['first_names'].add(first_name)
                    new_contacts['names'].add(first_name)
                
                if 'Last Name' in row and row['Last Name']:
                    last_name = row['Last Name'].strip().lower()
                    new_contacts['last_names'].add(last_name)
                    new_contacts['names'].add(last_name)
                    
                    # Add full name if both first and last names exist
                    if 'First Name' in row and row['First Name']:
                        full_name = f"{row['First Name'].strip().lower()} {last_name}"
                        new_contacts['names'].add(full_name)
                
                if 'Organization Name' in row and row['Organization Name']:
                    org = row['Organization Name'].strip().lower()
                    new_contacts['organizations'].add(org)
        
        # Calculate changes
        changes = {
            'emails': {
                'added': len(new_contacts['emails'] - existing_contacts['emails']),
                'removed': len(existing_contacts['emails'] - new_contacts['emails'])
            },
            'names': {
                'added': len(new_contacts['names'] - existing_contacts['names']),
                'removed': len(existing_contacts['names'] - new_contacts['names'])
            },
            'first_names': {
                'added': len(new_contacts['first_names'] - existing_contacts['first_names']),
                'removed': len(existing_contacts['first_names'] - new_contacts['first_names'])
            },
            'last_names': {
                'added': len(new_contacts['last_names'] - existing_contacts['last_names']),
                'removed': len(existing_contacts['last_names'] - new_contacts['last_names'])
            },
            'organizations': {
                'added': len(new_contacts['organizations'] - existing_contacts['organizations']),
                'removed': len(existing_contacts['organizations'] - new_contacts['organizations'])
            }
        }
        
        # Save updated contacts
        contacts_json = {
            'emails': sorted(list(new_contacts['emails'])),
            'names': sorted(list(new_contacts['names'])),
            'first_names': sorted(list(new_contacts['first_names'])),
            'last_names': sorted(list(new_contacts['last_names'])),
            'organizations': sorted(list(new_contacts['organizations'])),
            'last_updated': datetime.now().isoformat()
        }
        
        with open(contacts_file, 'w', encoding='utf-8') as f:
            json.dump(contacts_json, f, ensure_ascii=False, indent=2)
        
        # Print summary of changes
        print("\nContact Update Summary:")
        print(f"Emails: {changes['emails']['added']} added, {changes['emails']['removed']} removed")
        print(f"Names: {changes['names']['added']} added, {changes['names']['removed']} removed")
        print(f"First Names: {changes['first_names']['added']} added, {changes['first_names']['removed']} removed")
        print(f"Last Names: {changes['last_names']['added']} added, {changes['last_names']['removed']} removed")
        print(f"Organizations: {changes['organizations']['added']} added, {changes['organizations']['removed']} removed")
        print(f"\nTotal counts:")
        print(f"- {len(new_contacts['emails'])} email addresses")
        print(f"- {len(new_contacts['first_names'])} first names")
        print(f"- {len(new_contacts['last_names'])} last names")
        print(f"- {len(new_contacts['names'])} total names (including full names)")
        print(f"- {len(new_contacts['organizations'])} organizations")
        print(f"\nUpdated: {contacts_file}")
        
    except Exception as e:
        print(f"Error updating contacts: {str(e)}")

if __name__ == "__main__":
    update_contacts() 