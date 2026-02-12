# Phase 5: Gmail Response Tracking

This phase focuses on tracking and analyzing the responses received from job applications submitted in Phase 4. It involves two main steps: scraping emails from the study's Gmail accounts and identifying relevant job application updates (e.g., interview invitations, rejections).

## Workflow Overview

1.  **Step 1: Data Collection (`gmail_email_scraper.py`)**
    *   Connects to multiple Gmail accounts using IMAP.
    *   Scrapes emails and stores them in a centralized MongoDB collection.
    *   Tags emails with the associated PII, treatment type, and geographic cluster.

2.  **Step 2: Data Classification (`classify_emails.py`)**
    *   Analyzes the scraped emails to categorize them.
    *   Identifies key "application updates" vs. other types of emails (spam, auto-replies, security alerts).
    *   Uses keyword matching and LLM validation for accuracy.

---

## Step 1: Gmail Email Scraper

**Script:** `gmail_email_scraper.py`

This script programmatically logs into the study's Gmail accounts, fetches emails, and saves them to MongoDB.

### Key Features
*   **Batch Processing**: Reads credentials from a CSV file to process multiple accounts in one run.
*   **Smart Sync**: Skips accounts or emails that have already been scraped to avoid duplication.
*   **Metadata Enrichment**: Adds PII identifier, cluster, and treatment info to every email record.
*   **Security**: Uses Gmail App Passwords for secure IMAP access.

### Usage
Run the script to start the scraping process:
```bash
python "Phase 5 Workflow - Gmail response tracking/gmail_email_scraper.py"
```

### Configuration
*   **Input**: Expects `Gmail passkey mapping.csv` in the same directory.
    *   Columns: `PII_Identifier_ID`, `Geographic_Cluster`, `Associated_Countries`, `Last_Name`, `Email`, `Passkey`.
*   **Output**: Stores data in MongoDB collection `email_scrapping_test` (default).

---

## Step 2: Email Classification

**Script:** `classify_emails.py`

This script processes the raw emails in MongoDB to determine their nature. The primary goal is to count how many "callbacks" (interviews/next steps) each treatment received.

### Classification Categories
The script tags each email with `email_category`:
1.  **`application_update`** (Target): Real responses from employers.
    *   *Subcategories*: `rejection`, `interview_invitation`, `next_steps`, `status_update`.
2.  **`application_submission`**: Auto-confirmations ("We received your application").
3.  **`security_code` / `google_notification`**: Account alerts (filtered out from analysis).
4.  **`other`**: Everything else.

### Key Features
*   **Keyword Analysis**: Checks subject and body for terms like "interview", "unfortunately", "schedule", etc.
*   **Gemini Validation**: Can optionally use Google's Gemini LLM to double-check complex or ambiguous emails for higher accuracy.
*   **Review Flags**: Adds flags like `manual_validation` for positive outcomes (interviews) to ensure human verification.

### Usage
Run the classifier to process all unclassified emails in the database:
```bash
python "Phase 5 Workflow - Gmail response tracking/classify_emails.py"
```

### Output
*   Updates existing MongoDB documents with:
    *   `email_category`: The determined category.
    *   `email_subcategory`: Specific type of update (if applicable).
    *   `is_application_update`: boolean flag for easy querying.
    *   `confidence`: Score indicating certainty of classification.

---

## Prerequisities

1.  **Environment Variables**: Ensure `.env` is set up with:
    *   `MONGODB_URI`: Connection string for the database.
    *   `GEMINI_API_KEY`: (Optional) Required if using LLM validation for classification.
2.  **Dependencies**:
    *   `pymongo`, `python-dotenv`
    *   `google-generativeai` (for Gemini classification)
