# Email to JSON Processor

This program fetches emails from an IMAP server and converts them into a structured JSON format, including metadata about replies, contacts, and attachments. It also provides tools for analyzing, fixing, and managing the email data.

## Features

- Fetches emails from IMAP server
- Converts emails to structured JSON format
- Identifies if an email is a reply
- Checks if sender is in your contacts list
- Handles email attachments
- Supports VCF contact files
- Properly decodes email headers and content
- Calculates email importance scores
- Maintains contact information
- Validates and fixes JSON data
- Analyzes email patterns and statistics

## Setup

1. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Create a `.env` file in the project root with your IMAP settings:
   ```
   IMAP_SERVER=imap.example.com
   IMAP_PORT=993
   EMAIL_ADDRESS=your.email@example.com
   EMAIL_PASSWORD=your_password
   CONTACTS_FILE=contacts.vcf  # Optional: path to your VCF contacts file
   ```

3. (Optional) Add your contacts file in VCF format if you want to identify emails from your contacts.

## Available Scripts

### Main Scripts
- `email_processor.py`: Main script for fetching and processing emails
- `parse_contacts.py`: Processes VCF contact files into a structured format
- `update_contacts.py`: Updates contact information from various sources
- `check_json.py`: Validates JSON files and checks for common issues
- `fix_json.py`: Fixes issues in JSON files (date formats, line terminators, etc.)
- `analyze_emails.py`: Analyzes email patterns and generates statistics
- `update_scores.py`: Updates importance scores for emails
- `test_blacklist.py`: Tests blacklist functionality

### Configuration Files
- `scoring_config.json`: Configuration for email importance scoring
- `blacklist.txt`: List of terms to reduce email importance scores
- `contacts.csv`: Contact information in CSV format

## Usage

### Fetching and Processing Emails
```bash
python email_processor.py [options]
```
Options:
- `--limit N`: Process only the N most recent emails
- `--since DATE`: Process emails since DATE (YYYY-MM-DD)
- `--folder FOLDER`: Process specific folder
- `--list-folders`: List available folders
- `--verbose`: Enable detailed logging
- `--no-contacts`: Skip loading contacts
- `--no-scoring`: Skip scoring emails

### Validating and Fixing Data
```bash
python check_json.py  # Check all JSON files
python fix_json.py    # Fix issues in JSON files
```

### Managing Contacts
```bash
python parse_contacts.py  # Process VCF contact files
python update_contacts.py # Update contact information
```

### Analyzing Emails
```bash
python analyze_emails.py  # Generate email statistics
python update_scores.py   # Update email importance scores
```

## Output Format

The JSON output includes:
- Summary statistics
  - Total emails
  - Emails from contacts
  - Reply counts
  - Attachment counts
  - Importance score distribution
  - Sender statistics
  - Date ranges
- Email details
  - Subject
  - From/To
  - Date (with timezone)
  - Message ID
  - Reply references
  - Contact status
  - Body content
  - Attachments
  - Importance score

## Security Notes

- Never commit your `.env` file to version control
- Consider using an app-specific password for your email account
- The program uses SSL/TLS for secure IMAP connection
- Contact information is stored locally and not shared
- Email content is processed locally and not sent to external services 