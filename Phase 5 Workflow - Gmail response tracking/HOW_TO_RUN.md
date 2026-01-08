# How to Run the Gmail Email Scraping and Classification Scripts

## Prerequisites

1. **Virtual Environment**: Make sure your `.venv` is activated
2. **Environment Variables**: Ensure `.env` file contains `MONGODB_URI`
3. **CSV File**: `Gmail passkey mapping.csv` should be in the same directory

## Scripts Overview

1. **`gmail_email_scraper.py`** - Scrapes emails from Gmail accounts
2. **`classify_emails.py`** - Classifies scraped emails into categories
3. **`analyze_email_data.py`** - Analyzes email patterns (optional)

---

## Step 1: Scrape Emails from Gmail

### Basic Usage

```bash
# Activate virtual environment (if not already activated)
.venv\Scripts\activate

# Run the scraper
python "Phase 5 Workflow - Gmail response tracking/gmail_email_scraper.py"
```

### What it does:
- Reads Gmail credentials from `Gmail passkey mapping.csv`
- Connects to each Gmail account using IMAP
- Fetches emails from inbox
- Saves emails to MongoDB collection `email_scrapping_test`
- Skips accounts that already have emails (if counts match)

### Configuration Options

Edit the `main()` function in `gmail_email_scraper.py` to customize:

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

### Expected Output:
```
2025-12-12 20:19:52,524 - __main__ - INFO - Starting Gmail email scraping...
2025-12-12 20:19:52,524 - __main__ - INFO - CSV file: ...
2025-12-12 20:19:52,524 - __main__ - INFO - MongoDB collection: email_scrapping_test
2025-12-12 20:19:52,530 - __main__ - INFO - Read 28 Gmail credentials from CSV
...
============================================================
SCRAPING SUMMARY
============================================================
Total accounts: 28
Successful connections: 6
Failed connections: 22
Total emails scraped: 1213
============================================================
```

---

## Step 2: Classify Emails

### Basic Usage

```bash
# Make sure virtual environment is activated
.venv\Scripts\activate

# Run the classifier
python "Phase 5 Workflow - Gmail response tracking/classify_emails.py"
```

### What it does:
- Reads all emails from `email_scrapping_test` collection
- Classifies each email into categories
- Adds `email_category` field to all emails
- Adds `email_subcategory` field to `application_update` emails
- Updates emails directly in MongoDB

### Expected Output:
```
2025-12-12 20:45:09,366 - __main__ - INFO - Classifying 3160 emails...
2025-12-12 20:45:09,369 - __main__ - INFO - Classified 100/3160 emails...
...
============================================================
CLASSIFICATION SUMMARY
============================================================
Total emails: 3160
Successfully classified: 3160
Updated in MongoDB: 3160
Errors: 0

Application-related emails: 2500
Application updates: 469

Categories:
  application_submission: 1200
  security_code: 1000
  application_update: 469
  google_notification: 50
  other: 441

Subcategories (application updates):
  rejection: 172
  status_update: 119
  next_steps: 113
  interview_invitation: 53
  offer: 12
============================================================
```

---

## Step 3: Query Classified Emails in MongoDB

After classification, you can query emails using MongoDB:

### Using MongoDB Compass or MongoDB Shell

```javascript
// Get all application updates
db.email_scrapping_test.find({ "email_category": "application_update" })

// Get only rejections
db.email_scrapping_test.find({ 
  "email_category": "application_update",
  "email_subcategory": "rejection"
})

// Get interview invitations
db.email_scrapping_test.find({ 
  "email_category": "application_update",
  "email_subcategory": "interview_invitation"
})

// Get all application submissions
db.email_scrapping_test.find({ "email_category": "application_submission" })

// Count emails by category
db.email_scrapping_test.aggregate([
  { $group: { _id: "$email_category", count: { $sum: 1 } } },
  { $sort: { count: -1 } }
])

// Count application updates by subcategory
db.email_scrapping_test.aggregate([
  { $match: { "email_category": "application_update" } },
  { $group: { _id: "$email_subcategory", count: { $sum: 1 } } },
  { $sort: { count: -1 } }
])
```

### Using Python

```python
from classify_emails import get_application_updates

# Get all application updates
all_updates = get_application_updates()

# Get only rejections
rejections = get_application_updates(subcategory="rejection")

# Get interview invitations
interviews = get_application_updates(subcategory="interview_invitation")
```

---

## Optional: Analyze Email Data

### Run Analysis Script

```bash
python "Phase 5 Workflow - Gmail response tracking/analyze_email_data.py"
```

This script provides insights into:
- Top senders by domain
- Keyword frequency
- Sample email subjects and bodies
- Email distribution by account

---

## Complete Workflow

### First Time Setup

1. **Scrape emails** (Step 1)
   ```bash
   python "Phase 5 Workflow - Gmail response tracking/gmail_email_scraper.py"
   ```

2. **Classify emails** (Step 2)
   ```bash
   python "Phase 5 Workflow - Gmail response tracking/classify_emails.py"
   ```

3. **Query results** in MongoDB or using Python functions

### Subsequent Runs

- **Scrape new emails**: Run Step 1 again - it will only fetch new emails
- **Re-classify**: Run Step 2 again - it will update all emails with classification

---

## Troubleshooting

### Connection Errors

If you see `'ascii' codec can't encode character '\xa0'`:
- This is fixed in the current version - the script handles non-breaking spaces automatically

### MongoDB Connection Issues

- Check that `MONGODB_URI` is set in `.env` file
- Verify MongoDB connection string is correct

### No Emails Found

- Check that emails exist in Gmail inbox
- Verify passkeys are correct in CSV file
- Check IMAP is enabled in Gmail settings

### Classification Not Working

- Ensure emails have been scraped first
- Check MongoDB collection name matches
- Verify emails exist in the collection

---

## Quick Reference

### File Locations
- **Scraper**: `Phase 5 Workflow - Gmail response tracking/gmail_email_scraper.py`
- **Classifier**: `Phase 5 Workflow - Gmail response tracking/classify_emails.py`
- **Analyzer**: `Phase 5 Workflow - Gmail response tracking/analyze_email_data.py`
- **CSV**: `Phase 5 Workflow - Gmail response tracking/Gmail passkey mapping.csv`

### MongoDB Collections
- **Source**: `email_scrapping_test` (scraped emails)
- **Fields Added**: 
  - `email_category` (all emails)
  - `email_subcategory` (only for `application_update` emails)

### Categories
- `application_update` - Updates on application status
- `application_submission` - Application submission confirmations
- `security_code` - Security code notifications
- `google_notification` - Google account notifications
- `other` - Other emails

### Subcategories (for `application_update` only)
- `rejection` - Application rejected
- `interview_invitation` - Interview invitation
- `next_steps` - Next steps in process
- `offer` - Job offer
- `status_update` - General status update








