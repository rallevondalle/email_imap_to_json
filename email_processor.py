import imaplib
import email
import json
import os
import csv
import argparse
import re
from email.header import decode_header
from datetime import datetime, timezone
from dotenv import load_dotenv
from email_validator import validate_email, EmailNotValidError
import html2text
import quopri
import base64
from email.utils import parsedate_to_datetime

class EmailProcessor:
    def __init__(self, verbose=False, load_contacts=True):
        load_dotenv()
        self.imap_server = os.getenv('IMAP_SERVER')
        self.imap_port = int(os.getenv('IMAP_PORT', 993))
        self.email_address = os.getenv('EMAIL_ADDRESS')
        self.email_password = os.getenv('EMAIL_PASSWORD')
        self.verbose = verbose
        self.contacts = None
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = False
        self.html_converter.ignore_images = True
        
        # Load blacklist
        try:
            with open('blacklist.txt', 'r', encoding='utf-8') as f:
                self.blacklist = [line.strip().lower() for line in f if line.strip()]
        except FileNotFoundError:
            self.blacklist = []
            if self.verbose:
                print("No blacklist.txt file found. Using empty blacklist.")
        
        # Load scoring configuration
        try:
            with open('scoring_config.json', 'r', encoding='utf-8') as f:
                self.scoring_config = json.load(f)
        except FileNotFoundError:
            self.scoring_config = {}
            if self.verbose:
                print("No scoring_config.json file found. Using default scoring.")
        
        if load_contacts:
            self._load_contacts()
        
        # Create output directory if it doesn't exist
        self.output_dir = os.path.join(os.path.dirname(__file__), 'output')
        os.makedirs(self.output_dir, exist_ok=True)
        
    def _log(self, message, end='\n'):
        """Print message only if verbose mode is enabled"""
        if self.verbose:
            print(message, end=end)

    def _get_current_time(self):
        """Get current time in ISO format with UTC timezone"""
        return datetime.now(timezone.utc).isoformat()

    def _load_contacts(self):
        """Load contacts from JSON file"""
        if not self.verbose:
            return None
            
        contacts = {
            'emails': set(),
            'names': set(),
            'first_names': set(),
            'last_names': set(),
            'organizations': set()
        }
        
        # Try to load from JSON file
        contacts_file = os.path.join(os.path.dirname(__file__), 'output', 'contacts.json')
        if os.path.exists(contacts_file):
            try:
                self._log(f"\nLoading contacts from {contacts_file}...")
                with open(contacts_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    contacts['emails'] = set(data.get('emails', []))
                    contacts['names'] = set(data.get('names', []))
                    contacts['first_names'] = set(data.get('first_names', []))
                    contacts['last_names'] = set(data.get('last_names', []))
                    contacts['organizations'] = set(data.get('organizations', []))
                
                self._log(f"\nContact loading complete:")
                self._log(f"- {len(contacts['emails'])} email addresses")
                self._log(f"- {len(contacts['first_names'])} first names")
                self._log(f"- {len(contacts['last_names'])} last names")
                self._log(f"- {len(contacts['names'])} total names (including full names)")
                self._log(f"- {len(contacts['organizations'])} organizations")
                if data.get('last_updated'):
                    self._log(f"- Last updated: {data['last_updated']}")
            except Exception as e:
                print(f"Error loading contacts: {str(e)}")
        else:
            print("No contacts.json found. Please run parse_contacts.py first.")
        
        self.contacts = contacts
        return contacts

    def _decode_email_header(self, header):
        """Decode email header properly"""
        if not header:
            return ""
        try:
            decoded_header = decode_header(header)
            header_parts = []
            for content, charset in decoded_header:
                if isinstance(content, bytes):
                    if charset:
                        header_parts.append(content.decode(charset))
                    else:
                        header_parts.append(content.decode('utf-8', errors='replace'))
                else:
                    header_parts.append(content)
            return ' '.join(header_parts)
        except Exception as e:
            print(f"Error decoding header: {str(e)}")
            return str(header)

    def _calculate_importance_score(self, email_data):
        """Calculate importance score for an email using configuration"""
        score = 0
        text_to_check = f"{email_data['subject']} {email_data['from']} {email_data['body']}".lower()
        
        # Check billing addresses
        if 'billing_addresses' in self.scoring_config:
            to_addresses = email_data.get('to', '').lower()
            if any(addr in to_addresses for addr in self.scoring_config['billing_addresses']['addresses']):
                return self.scoring_config['billing_addresses']['score']
        
        # Check financial documents that need attention
        if 'financial_documents' in self.scoring_config:
            if any(term in text_to_check for term in self.scoring_config['financial_documents']['terms']):
                score += self.scoring_config['financial_documents']['score']
        
        # Check receipts (negative score)
        if 'receipts' in self.scoring_config:
            if any(term in text_to_check for term in self.scoring_config['receipts']['terms']):
                score += self.scoring_config['receipts']['score']
        
        # Check important keywords
        if 'important_keywords' in self.scoring_config:
            if any(term in email_data['subject'].lower() for term in self.scoring_config['important_keywords']['terms']):
                score += self.scoring_config['important_keywords']['score']
        
        # Check blacklist terms
        for term in self.blacklist:
            if term in text_to_check:
                score -= 2  # Keep blacklist penalty consistent
        
        # Check contact bonuses
        if self.contacts and 'contact_bonus' in self.scoring_config:
            if email_data['is_from_contact']:
                score += self.scoring_config['contact_bonus']['from_contact']
            
            # Check name matches
            sender_name = email_data['from'].split('<')[0].strip().lower()
            if sender_name in self.contacts['names']:
                score += self.scoring_config['contact_bonus']['full_name_match']
            else:
                # Check first and last names
                name_parts = sender_name.split()
                if any(part in self.contacts['first_names'] for part in name_parts):
                    score += self.scoring_config['contact_bonus']['first_name_match']
                if any(part in self.contacts['last_names'] for part in name_parts):
                    score += self.scoring_config['contact_bonus']['last_name_match']
            
            # Check organization matches
            if any(org in text_to_check for org in self.contacts['organizations']):
                score += self.scoring_config['contact_bonus']['organization_match']
        
        # Check reply bonus
        if 'reply_bonus' in self.scoring_config and email_data['is_reply']:
            score += self.scoring_config['reply_bonus']['is_reply']
        
        return score

    def _decode_body(self, part):
        """Decode email body with proper encoding handling"""
        try:
            # Get the content transfer encoding and charset
            encoding = part.get('Content-Transfer-Encoding', '').lower()
            charset = part.get_content_charset() or 'utf-8'
            
            # Get the raw payload
            payload = part.get_payload(decode=True)
            if payload is None:
                return ""

            # Try to get the decoded content using email library's built-in functions
            try:
                # First try to get the decoded content directly
                if part.is_multipart():
                    return ""
                
                # Get the content type
                content_type = part.get_content_type()
                
                # Handle different content types
                if content_type == 'text/plain':
                    # Try to get the content using get_payload
                    content = part.get_payload(decode=True)
                    if content:
                        # Try different charsets
                        for test_charset in [charset, 'utf-8', 'latin-1', 'iso-8859-1']:
                            try:
                                return content.decode(test_charset, errors='replace')
                            except Exception:
                                continue
                
                elif content_type == 'text/html':
                    # For HTML content, try the same approach
                    content = part.get_payload(decode=True)
                    if content:
                        for test_charset in [charset, 'utf-8', 'latin-1', 'iso-8859-1']:
                            try:
                                return content.decode(test_charset, errors='replace')
                            except Exception:
                                continue
                
                # If we get here, try one last time with the original payload
                return payload.decode(charset, errors='replace')
                
            except Exception as e:
                if self.verbose:
                    print(f"Error in content decoding: {str(e)}")
                
                # Fallback to direct decoding
                try:
                    return payload.decode(charset, errors='replace')
                except Exception:
                    try:
                        return payload.decode('utf-8', errors='replace')
                    except Exception:
                        try:
                            return payload.decode('latin-1', errors='replace')
                        except Exception:
                            return "Error decoding email body"

        except Exception as e:
            if self.verbose:
                print(f"Error in _decode_body: {str(e)}")
            return "Error decoding email body"

    def _clean_text(self, text):
        """Clean and format text content"""
        if not text:
            return ""
            
        # Replace multiple spaces with a single one
        text = re.sub(r' {2,}', ' ', text)
        
        # Remove markdown image syntax
        text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
        
        # Remove markdown links but keep the text
        text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)
        
        # Remove horizontal rules
        text = re.sub(r'-{3,}', '', text)
        
        # Remove multiple dashes
        text = re.sub(r'-{2,}', '-', text)
        
        # Clean up any remaining markdown
        text = re.sub(r'[*_]{1,2}(.*?)[*_]{1,2}', r'\1', text)
        
        # Remove any remaining HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        return text

    def _parse_email(self, email_message):
        """Parse email message into structured data"""
        try:
            # Parse date first
            date_str = email_message['date']
            parsed_date = None
            
            # Try to parse the date from the header
            if date_str:
                try:
                    parsed_date = parsedate_to_datetime(date_str)
                    if parsed_date:
                        # Ensure timezone awareness
                        if parsed_date.tzinfo is None:
                            parsed_date = parsed_date.replace(tzinfo=timezone.utc)
                        date_str = parsed_date.isoformat()
                except Exception as e:
                    if self.verbose:
                        print(f"Error parsing date '{date_str}': {str(e)}")
                    date_str = None
            
            # If date parsing failed, try to extract from message_id
            if not date_str and email_message['message-id']:
                try:
                    # Extract timestamp from message_id (format: <number.number.timestamp.JavaMail.domain>)
                    msg_id_parts = email_message['message-id'].split('.')
                    if len(msg_id_parts) >= 3:
                        timestamp = int(msg_id_parts[2])
                        # Convert milliseconds to seconds if needed
                        if timestamp > 1000000000000:  # If timestamp is in milliseconds
                            timestamp = timestamp // 1000
                        parsed_date = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                        date_str = parsed_date.isoformat()
                        if self.verbose:
                            print(f"Recovered date from message_id: {date_str}")
                except Exception as e:
                    if self.verbose:
                        print(f"Error extracting date from message_id: {str(e)}")

            email_data = {
                'subject': self._decode_email_header(email_message['subject']),
                'from': self._decode_email_header(email_message['from']),
                'to': self._decode_email_header(email_message['to']),
                'date': date_str,
                'message_id': email_message['message-id'],
                'in_reply_to': email_message['in-reply-to'],
                'references': email_message['references'],
                'is_reply': bool(email_message['in-reply-to']),
                'is_from_contact': False,
                'body': '',  # Single body field instead of separate plain/html
                'attachments': [],
                'importance_score': 0
            }

            # Check if sender is in contacts
            try:
                from_parts = email_data['from'].split('<')
                if len(from_parts) > 1:
                    sender_email = validate_email(from_parts[-1].strip('>')).email
                else:
                    sender_email = validate_email(email_data['from'].strip()).email
                email_data['is_from_contact'] = sender_email in self.contacts['emails'] if self.contacts else False
            except (EmailNotValidError, IndexError):
                pass

            # Process email body and attachments
            if email_message.is_multipart():
                for part in email_message.walk():
                    content_type = part.get_content_type()
                    if content_type == "text/plain":
                        # Get plain text content
                        text_content = self._decode_body(part)
                        if text_content:
                            email_data['body'] = self._clean_text(text_content)
                    elif content_type == "text/html":
                        # Only use HTML content if we don't have plain text
                        if not email_data['body']:
                            html_content = self._decode_body(part)
                            if html_content:
                                try:
                                    # Convert HTML to plain text
                                    text_content = self.html_converter.handle(html_content)
                                    email_data['body'] = self._clean_text(text_content)
                                except Exception as e:
                                    if self.verbose:
                                        print(f"Error converting HTML to plain text: {str(e)}")
                    elif part.get_content_maintype() == 'application':
                        filename = part.get_filename()
                        if filename:
                            email_data['attachments'].append({
                                'filename': self._decode_email_header(filename),
                                'content_type': content_type,
                                'size': len(part.get_payload(decode=True) or b'')
                            })
            else:
                content_type = email_message.get_content_type()
                if content_type == "text/plain":
                    text_content = self._decode_body(email_message)
                    email_data['body'] = self._clean_text(text_content)
                elif content_type == "text/html":
                    html_content = self._decode_body(email_message)
                    if html_content:
                        try:
                            text_content = self.html_converter.handle(html_content)
                            email_data['body'] = self._clean_text(text_content)
                        except Exception as e:
                            if self.verbose:
                                print(f"Error converting HTML to plain text: {str(e)}")

            # Calculate importance score
            email_data['importance_score'] = self._calculate_importance_score(email_data)

            return email_data
        except Exception as e:
            if self.verbose:
                print(f"Error parsing email: {str(e)}")
            return None

    def _format_imap_date(self, date_str):
        """Convert YYYY-MM-DD to DD-MMM-YYYY format for IMAP"""
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            return date_obj.strftime('%d-%b-%Y').upper()  # Convert month to uppercase
        except ValueError:
            raise ValueError("Date must be in YYYY-MM-DD format")

    def list_folders(self):
        """List all available folders on the IMAP server"""
        try:
            self._log(f"\nConnecting to IMAP server {self.imap_server}...")
            mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            mail.login(self.email_address, self.email_password)
            
            # List all folders
            status, folders = mail.list()
            if status != 'OK':
                self._log(f"Error listing folders: {folders}")
                return []
            
            # Process folder names
            folder_list = []
            self._log("\nAvailable folders:")
            for folder in folders:
                # Decode folder name from bytes and normalize case
                folder_name = folder.decode('utf-8').split('"')[-1]
                
                # Skip empty folder names
                if not folder_name:
                    continue
                
                # Normalize INBOX to lowercase for consistency
                if folder_name.upper() == 'INBOX':
                    folder_name = 'inbox'
                
                # Include INBOX, Archive folders, and custom folders
                # Exclude only system folders like Spam, Trash, etc.
                if (folder_name.lower() == 'inbox' or 
                    folder_name.lower().startswith('archive') or 
                    not any(x in folder_name.upper() for x in ['SPAM', 'TRASH', 'JUNK', 'DELETED', 'SENT', 'DRAFTS'])):
                    folder_list.append(folder_name)
                    self._log(f"Including folder: {folder_name}")
                else:
                    self._log(f"Excluding folder: {folder_name}")
            
            mail.logout()
            return folder_list
        except Exception as e:
            print(f"Error listing folders: {str(e)}")
            return []

    def fetch_emails(self, folder='INBOX', limit=None, since_date=None):
        """Fetch emails from specified folder"""
        try:
            self._log(f"\nConnecting to IMAP server {self.imap_server}...")
            # Connect to IMAP server
            mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            mail.login(self.email_address, self.email_password)
            
            # Select folder in read-only mode
            self._log(f"Selecting folder: {folder}")
            mail.select(folder, readonly=True)

            # Search for all emails
            self._log("Searching for all emails...")
            status, messages = mail.search(None, 'ALL')
            self._log(f"IMAP Search Status: {status}")
            
            if status != 'OK':
                self._log(f"IMAP Search Error: {messages}")
                return []
                
            email_ids = messages[0].split()
            total_emails = len(email_ids)
            self._log(f"Found {total_emails} total emails")
            
            # Process emails
            emails = []
            # If no limit is set, process all emails
            if limit:
                email_ids = email_ids[-limit:]  # Get the most recent emails
                self._log(f"Processing {limit} most recent emails")
            
            for i, email_id in enumerate(email_ids, 1):
                try:
                    # Fetch email data
                    status, msg_data = mail.fetch(email_id, '(RFC822)')
                    if status != 'OK':
                        self._log(f"Error fetching email {i}: {msg_data}")
                        continue
                    
                    # Parse email message
                    email_message = email.message_from_bytes(msg_data[0][1])
                    email_data = self._parse_email(email_message)
                    
                    if email_data:
                        emails.append(email_data)
                        self._log(f"Processed email {i}/{len(email_ids)}: {email_data['subject']}")
                    
                except Exception as e:
                    self._log(f"Error processing email {i}: {str(e)}")
                    continue
            
            mail.close()
            mail.logout()
            return emails
            
        except Exception as e:
            print(f"Error fetching emails: {str(e)}")
            return []

    def score_emails(self, emails):
        """Score emails based on importance"""
        for email in emails:
            email['importance_score'] = self._calculate_importance_score(email)
        return emails

    def generate_summary(self, emails):
        """Generate summary statistics for emails"""
        summary = {
            'total_emails': len(emails),
            'from_contacts': sum(1 for e in emails if e.get('is_from_contact', False)),
            'replies': sum(1 for e in emails if e.get('is_reply', False)),
            'with_attachments': sum(1 for e in emails if e.get('attachments')),
            'total_attachments': sum(len(e.get('attachments', [])) for e in emails),
            'importance_scores': {
                'high': sum(1 for e in emails if e.get('importance_score', 0) > 5),
                'medium': sum(1 for e in emails if 0 <= e.get('importance_score', 0) <= 5),
                'low': sum(1 for e in emails if e.get('importance_score', 0) < 0)
            },
            'senders': {},
            'subjects': []
        }
        
        # Count senders
        for email in emails:
            sender = email.get('from', '')
            if sender:
                summary['senders'][sender] = summary['senders'].get(sender, 0) + 1
        
        # Get recent subjects
        recent_emails = sorted(emails, key=lambda x: x.get('date', ''), reverse=True)[:10]
        summary['subjects'] = [e.get('subject', '') for e in recent_emails]
        
        return summary

    def _merge_emails(self, existing_emails, new_emails):
        """Merge new emails with existing ones, avoiding duplicates"""
        # Create a set of existing message IDs
        existing_ids = {email.get('message_id') for email in existing_emails}
        
        # Add only new emails
        for email in new_emails:
            if email.get('message_id') not in existing_ids:
                existing_emails.append(email)
                existing_ids.add(email.get('message_id'))
        
        # Sort by date
        def get_date(email):
            try:
                date_str = email.get('date', '')
                if not date_str:
                    return datetime.min
                try:
                    return parsedate_to_datetime(date_str)
                except (TypeError, ValueError):
                    try:
                        return datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %z')
                    except ValueError:
                        try:
                            return datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %Z')
                        except ValueError:
                            return datetime.min
            except Exception:
                return datetime.min
        
        return sorted(existing_emails, key=get_date, reverse=True)

    def save_to_json(self, emails, output_file='emails.json'):
        """Save processed emails to JSON file, handling incremental updates"""
        try:
            # Ensure output file is in the output directory
            output_file = os.path.join(self.output_dir, os.path.basename(output_file))
            
            # Load existing emails if file exists
            existing_emails = []
            if os.path.exists(output_file):
                try:
                    with open(output_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        existing_emails = data.get('emails', [])
                        self._log(f"Loaded {len(existing_emails)} existing emails from {output_file}")
                except Exception as e:
                    self._log(f"Error loading existing file: {str(e)}")
            
            # Merge new emails with existing ones
            merged_emails = self._merge_emails(existing_emails, emails)
            new_count = len(merged_emails) - len(existing_emails)
            
            # Generate summary
            summary = self.generate_summary(merged_emails)
            
            # Ensure date range is properly set
            date_range = summary.get('date_range', {})
            valid_dates = []
            for email in merged_emails:
                date_str = email.get('date', '')
                if date_str:
                    try:
                        try:
                            date_obj = parsedate_to_datetime(date_str)
                        except (TypeError, ValueError):
                            try:
                                date_obj = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %z')
                            except ValueError:
                                try:
                                    date_obj = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %Z')
                                except ValueError:
                                    continue
                        # Ensure timezone awareness
                        if date_obj.tzinfo is None:
                            date_obj = date_obj.replace(tzinfo=timezone.utc)
                        valid_dates.append(date_obj)
                    except (TypeError, ValueError, AttributeError):
                        continue
            
            if valid_dates:
                date_range = {
                    'oldest': min(valid_dates).isoformat(),
                    'newest': max(valid_dates).isoformat()
                }
            else:
                date_range = {
                    'oldest': datetime.min.replace(tzinfo=timezone.utc).isoformat(),
                    'newest': datetime.now(timezone.utc).isoformat()
                }
            summary['date_range'] = date_range
            
            # Save both emails and summary
            output_data = {
                'summary': summary,
                'emails': merged_emails,
                'last_updated': datetime.now().isoformat()
            }
            
            # Write to file
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            
            # Print summary with focus on new emails
            if new_count > 0:
                print(f"\nNew Emails Added to {os.path.basename(output_file)}: {new_count}")
                print(f"Total Emails in Database: {len(merged_emails)}")
                print(f"From Contacts: {summary['from_contacts']}")
                print(f"Replies: {summary['replies']}")
                print(f"Emails with Attachments: {summary['with_attachments']}")
                print(f"Total Attachments: {summary['total_attachments']}")
                print(f"\nImportance Distribution:")
                print(f"High Importance: {summary['importance_scores']['high']}")
                print(f"Medium Importance: {summary['importance_scores']['medium']}")
                print(f"Low Importance: {summary['importance_scores']['low']}")
                print(f"\nDate Range:")
                print(f"Oldest: {date_range['oldest']}")
                print(f"Newest: {date_range['newest']}")
                print("\nTop Senders:")
                for sender, count in sorted(summary['senders'].items(), key=lambda x: x[1], reverse=True)[:5]:
                    print(f"- {sender}: {count} emails")
                print("\nRecent Subjects:")
                for subject in summary['subjects']:
                    print(f"- {subject}")
            else:
                print(f"\nNo new emails added to {os.path.basename(output_file)}")
            
        except Exception as e:
            print(f"Error saving to JSON: {str(e)}")
            # Print the full traceback for debugging
            import traceback
            traceback.print_exc()

    def count_emails(self, folder='INBOX', since_date=None):
        """Count emails in specified folder without fetching them"""
        try:
            self._log(f"\nConnecting to IMAP server {self.imap_server}...")
            # Connect to IMAP server
            mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            mail.login(self.email_address, self.email_password)
            
            # Select folder in read-only mode
            self._log(f"Selecting folder: {folder}")
            mail.select(folder, readonly=True)

            # Build search criteria
            search_criteria = 'ALL'
            if since_date:
                imap_date = self._format_imap_date(since_date)
                search_criteria = f'(SINCE "{imap_date}")'
                self._log(f"Searching for emails since {imap_date}...")
            else:
                self._log("Searching for all emails...")

            # Search for emails
            _, messages = mail.search(None, search_criteria)
            email_ids = messages[0].split()
            total_emails = len(email_ids)
            
            mail.close()
            mail.logout()
            return total_emails

        except Exception as e:
            print(f"Error counting emails: {str(e)}")
            return 0

    def generate_unified_stats(self):
        """Generate statistics across all JSON files in the output directory"""
        all_emails = []
        total_emails = 0
        total_from_contacts = 0
        total_replies = 0
        total_attachments = 0
        importance_scores = []
        sender_counts = {}
        date_ranges = {
            'oldest': None,
            'newest': None
        }
        
        # Get all JSON files in the output directory
        json_files = [f for f in os.listdir(self.output_dir) if f.endswith('_emails.json')]
        
        if not json_files:
            print("No email JSON files found in the output directory.")
            return
        
        print(f"\nProcessing {len(json_files)} JSON files...")
        
        for json_file in json_files:
            try:
                with open(os.path.join(self.output_dir, json_file), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    emails = data.get('emails', [])
                    total_emails += len(emails)
                    
                    # Process each email
                    for email in emails:
                        # Count contacts and replies
                        if email.get('is_from_contact'):
                            total_from_contacts += 1
                        if email.get('is_reply'):
                            total_replies += 1
                        
                        # Count attachments
                        total_attachments += len(email.get('attachments', []))
                        
                        # Track importance scores
                        if 'importance_score' in email:
                            importance_scores.append(email['importance_score'])
                        
                        # Track senders
                        sender = email.get('from', '').split('<')[0].strip()
                        if sender:
                            sender_counts[sender] = sender_counts.get(sender, 0) + 1
                        
                        # Track date ranges
                        email_date = email.get('date')
                        if email_date:
                            try:
                                email_date = datetime.fromisoformat(email_date.replace('Z', '+00:00'))
                                if date_ranges['oldest'] is None or email_date < date_ranges['oldest']:
                                    date_ranges['oldest'] = email_date
                                if date_ranges['newest'] is None or email_date > date_ranges['newest']:
                                    date_ranges['newest'] = email_date
                            except (ValueError, TypeError):
                                continue
                
                print(f"Processed {json_file}: {len(emails)} emails")
            except Exception as e:
                print(f"Error processing {json_file}: {str(e)}")
        
        # Calculate statistics
        avg_importance = sum(importance_scores) / len(importance_scores) if importance_scores else 0
        top_senders = sorted(sender_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # Print unified statistics
        print("\n=== Unified Email Statistics ===")
        print(f"Total Emails: {total_emails}")
        print(f"Emails from Contacts: {total_from_contacts} ({total_from_contacts/total_emails*100:.1f}%)")
        print(f"Reply Emails: {total_replies} ({total_replies/total_emails*100:.1f}%)")
        print(f"Total Attachments: {total_attachments}")
        print(f"Average Importance Score: {avg_importance:.2f}")
        
        if date_ranges['oldest'] and date_ranges['newest']:
            print(f"\nDate Range:")
            print(f"Oldest: {date_ranges['oldest'].isoformat()}")
            print(f"Newest: {date_ranges['newest'].isoformat()}")
        
        print("\nTop 10 Senders:")
        for sender, count in top_senders:
            print(f"- {sender}: {count} emails")
        
        # Save unified statistics to a JSON file
        stats = {
            'total_emails': total_emails,
            'emails_from_contacts': total_from_contacts,
            'reply_emails': total_replies,
            'total_attachments': total_attachments,
            'average_importance_score': avg_importance,
            'date_range': {
                'oldest': date_ranges['oldest'].isoformat() if date_ranges['oldest'] else None,
                'newest': date_ranges['newest'].isoformat() if date_ranges['newest'] else None
            },
            'top_senders': {sender: count for sender, count in top_senders},
            'processed_files': json_files,
            'generated_at': self._get_current_time()
        }
        
        stats_file = os.path.join(self.output_dir, 'unified_stats.json')
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2)
        
        print(f"\nUnified statistics saved to {stats_file}")

def main():
    parser = argparse.ArgumentParser(description='Process emails from IMAP server')
    parser.add_argument('--limit', type=int, help='Limit the number of emails to process')
    parser.add_argument('--since', type=str, help='Process emails since date (YYYY-MM-DD)')
    parser.add_argument('--folder', type=str, help='Process specific folder')
    parser.add_argument('--list-folders', action='store_true', help='List available folders')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
    parser.add_argument('--no-contacts', action='store_true', help='Skip loading contacts')
    parser.add_argument('--no-scoring', action='store_true', help='Skip scoring emails')
    parser.add_argument('--unified-stats', action='store_true', help='Generate unified statistics across all JSON files')
    args = parser.parse_args()
    
    processor = EmailProcessor(verbose=args.verbose, load_contacts=not args.no_contacts)
    
    if args.unified_stats:
        processor.generate_unified_stats()
        return
    
    if args.list_folders:
        processor.list_folders()
        return
    
    # Get list of available folders
    available_folders = processor.list_folders()
    if not available_folders:
        print("No folders available. Check your IMAP connection and permissions.")
        return
    
    # If folder is specified via command line, use it
    if args.folder:
        folders = [args.folder]
    else:
        # Sort folders alphabetically, but keep INBOX second to last
        sorted_folders = []
        inbox_folder = None
        
        # First, collect all folders except INBOX
        for folder in available_folders:
            if folder == 'INBOX':
                inbox_folder = folder
            else:
                sorted_folders.append(folder)
        
        # Sort the non-INBOX folders alphabetically
        sorted_folders.sort()
        
        # Add INBOX second to last
        if inbox_folder:
            sorted_folders.append(inbox_folder)
        
        # Show folder selection menu
        print("\nAvailable folders:")
        for i, folder in enumerate(sorted_folders, 1):
            print(f"{i}. {folder}")
        print(f"{len(sorted_folders) + 1}. Process all folders")
        
        while True:
            try:
                choice = input("\nSelect folder number (or 'q' to quit): ")
                if choice.lower() == 'q':
                    return
                
                choice = int(choice)
                if choice == len(sorted_folders) + 1:
                    folders = sorted_folders
                    break
                elif 1 <= choice <= len(sorted_folders):
                    folders = [sorted_folders[choice - 1]]
                    break
                else:
                    print("Invalid selection. Please try again.")
            except ValueError:
                print("Please enter a valid number.")
    
    for folder in folders:
        print(f"\nProcessing folder: {folder}")
        # Fetch new emails
        emails = processor.fetch_emails(folder=folder, limit=args.limit, since_date=args.since)
        
        if emails:
            # Score the emails only if not disabled
            if not args.no_scoring:
                emails = processor.score_emails(emails)
            # Save to folder-specific file, ensuring consistent case and no extra spaces
            output_file = f"{folder.lower().strip()}_raw_emails.json"
            processor.save_to_json(emails, output_file)
        else:
            print(f"No emails were processed from {folder}. Check your IMAP settings and connection.")

if __name__ == "__main__":
    main() 