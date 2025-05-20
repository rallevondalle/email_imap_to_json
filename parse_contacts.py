import csv
import json
import os
from email_validator import validate_email, EmailNotValidError

def parse_contacts():
    # Define possible locations for contacts.csv
    possible_locations = [
        os.path.join(os.path.dirname(__file__), 'contacts.csv'),  # Project directory
        os.path.expanduser('~/Downloads/contacts.csv'),           # Downloads folder
        os.path.expanduser('~/Desktop/contacts.csv')             # Desktop
    ]
    
    # Try each location until we find the file
    contacts_file = None
    for location in possible_locations:
        if os.path.exists(location):
            contacts_file = location
            break
    
    if not contacts_file:
        print("No contacts.csv file found. Please place it in the project directory, Downloads, or Desktop.")
        return
    
    print(f"Found contacts file at: {contacts_file}")
    
    # Initialize contacts data structure
    contacts = {
        'emails': set(),
        'names': set(),
        'first_names': set(),
        'last_names': set(),
        'organizations': set()
    }
    
    try:
        print("Parsing contacts...")
        with open(contacts_file, 'r', encoding='utf-8') as f:
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
                            contacts['emails'].add(email)
                        except EmailNotValidError:
                            continue
                
                # Process names and organization
                if 'First Name' in row and row['First Name']:
                    first_name = row['First Name'].strip().lower()
                    contacts['first_names'].add(first_name)
                    contacts['names'].add(first_name)
                
                if 'Last Name' in row and row['Last Name']:
                    last_name = row['Last Name'].strip().lower()
                    contacts['last_names'].add(last_name)
                    contacts['names'].add(last_name)
                    
                    # Add full name if both first and last names exist
                    if 'First Name' in row and row['First Name']:
                        full_name = f"{row['First Name'].strip().lower()} {last_name}"
                        contacts['names'].add(full_name)
                
                if 'Organization Name' in row and row['Organization Name']:
                    org = row['Organization Name'].strip().lower()
                    contacts['organizations'].add(org)
        
        # Convert sets to lists for JSON serialization
        contacts_json = {
            'emails': sorted(list(contacts['emails'])),
            'names': sorted(list(contacts['names'])),
            'first_names': sorted(list(contacts['first_names'])),
            'last_names': sorted(list(contacts['last_names'])),
            'organizations': sorted(list(contacts['organizations'])),
            'last_updated': None  # Will be set by update_contacts.py
        }
        
        # Save to JSON file
        output_file = os.path.join(os.path.dirname(__file__), 'output', 'contacts.json')
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(contacts_json, f, ensure_ascii=False, indent=2)
        
        print("\nContact parsing complete:")
        print(f"- {len(contacts['emails'])} email addresses")
        print(f"- {len(contacts['first_names'])} first names")
        print(f"- {len(contacts['last_names'])} last names")
        print(f"- {len(contacts['names'])} total names (including full names)")
        print(f"- {len(contacts['organizations'])} organizations")
        print(f"\nSaved to: {output_file}")
        
    except Exception as e:
        print(f"Error parsing contacts: {str(e)}")

if __name__ == "__main__":
    parse_contacts() 