# Gmail Email Scraper

A Python script to programmatically log into Gmail accounts and scrape emails using IMAP. The scraped emails are stored in MongoDB for later analysis and classification.

## Overview

This script is part of Phase 5 of the resume parsing audit study workflow. It reads Gmail credentials from a CSV file, connects to each account using IMAP, fetches emails from the inbox, and stores them in MongoDB. The end goal is to classify how many job applications received callbacks based on applications generated in Phase 4.

## Features

- **Batch Processing**: Processes multiple Gmail accounts from a CSV file
- **IMAP Integration**: Uses `imaplib` for secure Gmail access
- **Email Parsing**: Extracts headers, body (text and HTML), and metadata
- **MongoDB Storage**: Stores emails with full metadata in MongoDB
- **Error Handling**: Robust error handling with detailed logging
- **Skip Existing**: Option to skip accounts that already have emails in MongoDB
- **Progress Tracking**: Real-time progress updates and summary statistics

## Prerequisites

1. **Python 3.7+**
2. **Gmail App Passwords**: Each Gmail account must have an app password (passkey) enabled
   - Go to Google Account → Security → 2-Step Verification → App passwords
   - Generate an app password for "Mail"
3. **MongoDB**: MongoDB instance accessible via `MONGODB_URI` environment variable
4. **Required Python Packages**:
   - `pymongo` (already in project requirements)
   - `python-dotenv` (already in project requirements)

## Setup

1. **Environment Variables**: Ensure `.env` file contains:
   ```
   MONGODB_URI=your_mongodb_connection_string
   ```

2. **CSV File Format**: The script expects a CSV file named `Gmail passkey mapping.csv` in the same directory with the following columns:
   - `PII_Identifier_ID`: Unique identifier
   - `Geographic_Cluster`: Geographic cluster name
   - `Treatment Type`: Treatment type (control, Type_I, Type_II, Type_III)
   - `Associated_Countries`: Associated countries
   - `Last_Name`: Last name
   - `Email`: Gmail email address
   - `Password`: Account password (not used for IMAP)
   - `Passkey`: Gmail app password (16-character passkey)

3. **CSV File Location**: Place `Gmail passkey mapping.csv` in the same directory as the script.

## Usage

### Basic Usage

Run the script from the project root:

```bash
python "Phase 5 Workflow - Gmail response tracking/gmail_email_scraper.py"
```

Or from within the directory:

```bash
cd "Phase 5 Workflow - Gmail response tracking"
python gmail_email_scraper.py
```

### Configuration Options

Edit the `main()` function in the script to customize:

```python
def main():
    # Path to CSV file (default: same directory as script)
    csv_path = os.path.join(script_dir, "Gmail passkey mapping.csv")
    
    # MongoDB collection name
    collection_name = "email_scrapping_test"
    
    # Limit number of emails per account (None for all emails)
    emails_per_account = None  # or set to a number like 100
    
    # Skip accounts that already have emails in MongoDB
    skip_existing = True
```

### Programmatic Usage

You can also import and use the functions programmatically:

```python
from gmail_email_scraper import scrape_gmail_accounts

stats = scrape_gmail_accounts(
    csv_path="path/to/Gmail passkey mapping.csv",
    collection_name="email_scrapping_test",
    emails_per_account=100,  # Limit to 100 most recent emails
    skip_existing=True
)

print(f"Scraped {stats['total_emails_scraped']} emails from {stats['successful_connections']} accounts")
```

## Output

### MongoDB Collection Structure

Emails are stored in the `email_scrapping_test` collection (or your specified collection) with the following structure:

```json
{
  "_id": ObjectId("..."),
  "email_id": "12345",  // IMAP UID
  "gmail_account": "example@gmail.com",
  "subject": "Email Subject",
  "from": "sender@example.com",
  "to": "recipient@example.com",
  "cc": null,
  "bcc": null,
  "reply_to": null,
  "date": ISODate("2025-01-15T10:30:00Z"),
  "date_str": "Mon, 15 Jan 2025 10:30:00 +0000",
  "message_id": "<message-id@example.com>",
  "in_reply_to": null,
  "references": null,
  "body_text": "Plain text email body",
  "body_html": "<html>...</html>",
  "scraped_at": ISODate("2025-01-15T12:00:00Z"),
  "PII_Identifier_ID": "SA-01",
  "Geographic_Cluster": "South Asia",
  "Treatment_Type": "control",
  "Associated_Countries": "India, Pakistan, Bangladesh, Sri Lanka, Nepal",
  "Last_Name": "Patel"
}
```

### Statistics Output

The script prints a summary after completion:

```
============================================================
SCRAPING SUMMARY
============================================================
Total accounts: 28
Successful connections: 28
Failed connections: 0
Total emails scraped: 1,234
============================================================
```

## Function Reference

### Main Functions

- `read_gmail_credentials(csv_path)`: Reads Gmail credentials from CSV file
- `connect_to_gmail(email_addr, passkey)`: Connects to Gmail using IMAP
- `fetch_emails(mail, email_addr, limit)`: Fetches emails from inbox
- `parse_email(msg_bytes, email_id)`: Parses email message into structured format
- `save_emails_to_mongodb(emails, collection_name)`: Saves emails to MongoDB
- `scrape_gmail_accounts(...)`: Main orchestration function

### Helper Functions

- `clean_passkey(passkey)`: Removes spaces from Gmail app password
- `decode_mime_words(s)`: Decodes MIME encoded words in headers
- `get_email_body(msg)`: Extracts email body (text and HTML)

## Troubleshooting

### Connection Issues

**Error: "IMAP error connecting"**
- Verify the Gmail app password (passkey) is correct
- Ensure 2-Step Verification is enabled on the Google account
- Check that IMAP is enabled in Gmail settings
- Verify the passkey has no extra spaces (script handles this automatically)

**Error: "Failed to connect to MongoDB"**
- Check `MONGODB_URI` environment variable is set correctly
- Verify MongoDB instance is accessible
- Check network connectivity

### Email Fetching Issues

**Error: "Failed to select INBOX"**
- Account may have restricted IMAP access
- Check Gmail account settings for IMAP restrictions

**No emails found**
- Verify the account has emails in the inbox
- Check if emails are in other folders (script only checks INBOX)

### Parsing Issues

**Encoding errors**
- The script handles encoding errors gracefully
- Some emails with unusual encodings may have partial content

## Logging

The script uses the project's logging utilities. Logs are written to:
- Console output (INFO level)
- `data/logs/resume_parser{timestamp}.log` (INFO level)
- `data/logs/Errors/error_resume_parser{timestamp}.log` (ERROR level)

## Limitations

1. **INBOX Only**: Currently only scrapes emails from the INBOX folder
2. **No Attachments**: Email attachments are skipped (only body content is stored)
3. **Rate Limiting**: Gmail may rate limit if processing too many accounts quickly
4. **Storage**: Large numbers of emails will consume MongoDB storage

## Future Enhancements

- [ ] Support for multiple folders (Sent, Spam, etc.)
- [ ] Attachment handling
- [ ] Email classification logic for job application callbacks
- [ ] Incremental updates (only fetch new emails)
- [ ] Rate limiting and retry logic
- [ ] Email filtering (by date, sender, subject, etc.)

## Related Workflows

- **Phase 4**: PDF generation workflow (generates job applications)
- **Phase 5**: Gmail response tracking (this script - scrapes emails)
- **Next Steps**: Email classification to identify job application callbacks

## Notes

- Gmail app passwords are 16 characters and should be entered with or without spaces (script handles both)
- The script automatically skips accounts that already have emails in MongoDB (when `skip_existing=True`)
- All timestamps are stored in UTC
- Email dates are parsed from email headers and may vary in format

## Support

For issues or questions, check the logs in `data/logs/` for detailed error messages.








