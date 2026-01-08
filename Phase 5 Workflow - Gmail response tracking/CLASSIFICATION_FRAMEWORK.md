# Email Classification Framework

## Overview

This document describes the classification framework used to categorize emails scraped from Gmail accounts, with a focus on identifying job application updates.

## Classification Categories

### 1. `application_update` ⭐ (Primary Focus)
**Description**: Emails containing updates on job application status (rejections, interview invitations, next steps, offers, etc.)

**Subcategories**:
- **`rejection`**: Application was rejected/not selected
- **`interview_invitation`**: Invitation to interview or phone screen
- **`next_steps`**: Instructions for next steps in the process
- **`offer`**: Job offer or congratulations on selection
- **`status_update`**: General status update without specific action

**Keywords Used**:
- Rejection: "unfortunately", "not moving forward", "not selected", "not a match", "not proceed", "we've decided"
- Interview: "interview", "phone screen", "schedule", "screening", "technical interview", "behavioral interview"
- Next Steps: "next step", "next steps", "move forward", "advance to", "next round"
- Offer: "offer", "congratulations", "excited to", "pleased to", "selected for"
- Status: "status update", "update on", "update regarding", "application status"

**Current Statistics** (from 3,160 emails):
- Total Application Updates: **469 emails**
  - Rejections: 172
  - Interview Invitations: 53
  - Next Steps: 113
  - Offers: 12
  - Status Updates: 119

### 2. `application_submission`
**Description**: Confirmation emails when an application is submitted

**Keywords**: "thank you for applying", "application received", "application submitted", "application confirmation"

**Current Statistics**: ~1,200+ emails

### 3. `security_code`
**Description**: Security code/verification code notifications from Greenhouse or other ATS systems

**Keywords**: "security code", "verification code", "access code"

**Current Statistics**: ~1,000+ emails

### 4. `google_notification`
**Description**: Google account security alerts, verification emails, account setup notifications

**Keywords**: "security alert", "2-step verification", "google account", "sign-in attempt"

**Current Statistics**: ~50+ emails

### 5. `other`
**Description**: All other emails not related to job applications

**Current Statistics**: ~400+ emails

## Classification Logic

The classification follows a priority-based approach:

1. **Google Notifications** (highest priority to exclude)
   - Check sender domain (accounts.google.com, google.com)
   - Check for Google notification keywords

2. **Security Code Notifications**
   - Check if from Greenhouse and contains "security code"
   - Check for security code keywords

3. **Application Submission Confirmations**
   - Check for "thank you for applying" patterns
   - Check sender domain (Greenhouse)

4. **Application Updates** (most important)
   - Scan subject and body for update keywords
   - Determine subcategory based on specific keywords
   - Calculate confidence score based on keyword matches

5. **Default Classification**
   - If from Greenhouse but no clear pattern → `application_submission`
   - Otherwise → `other`

## Confidence Scoring

Each classification includes a confidence score (0.0 to 1.0):
- **0.9-1.0**: High confidence (clear keywords, known sender)
- **0.7-0.9**: Medium-high confidence (some keywords match)
- **0.5-0.7**: Medium confidence (weak pattern match)
- **<0.5**: Low confidence (default classification)

## Data Structure

Classified emails are stored in MongoDB with the following additional fields:

```json
{
  "email_classification": {
    "category": "application_update",
    "subcategory": "rejection",
    "confidence": 0.95,
    "reasoning": ["Found update keywords: unfortunately, not selected"],
    "classified_at": ISODate("2025-12-12T20:46:00Z")
  },
  "is_application_related": true,
  "is_application_update": true
}
```

## Usage

### Classify All Emails
```python
from classify_emails import classify_all_emails

stats = classify_all_emails(
    collection_name="email_scrapping_test",
    update_mongodb=True,
    output_collection="email_classifications"
)
```

### Get Application Updates
```python
from classify_emails import get_application_updates

# Get all application updates
all_updates = get_application_updates()

# Get specific subcategory
rejections = get_application_updates(subcategory="rejection")
interviews = get_application_updates(subcategory="interview_invitation")
```

### View Sample Classifications
```python
from classify_emails import view_sample_classifications

# View sample application updates
view_sample_classifications(category="application_update", limit=20)
```

## Analysis Results

From the analysis of 3,160 emails:

### Top Senders (by domain)
1. **us.greenhouse-mail.io**: ~2,000+ emails (63%)
2. **accounts.google.com**: ~50 emails (2%)
3. Other ATS/company domains: ~1,100 emails (35%)

### Email Categories Distribution
- **Application-related**: ~2,500 emails (79%)
  - Application Updates: 469 (15%)
  - Application Submissions: ~1,200 (38%)
  - Security Codes: ~1,000 (32%)
- **Google Notifications**: ~50 emails (2%)
- **Other**: ~600 emails (19%)

### Application Update Breakdown
- **Rejections**: 172 (37% of updates)
- **Status Updates**: 119 (25% of updates)
- **Next Steps**: 113 (24% of updates)
- **Interview Invitations**: 53 (11% of updates)
- **Offers**: 12 (3% of updates)

## Key Insights

1. **Most emails are application-related** (79%), which is expected for job application tracking
2. **Application updates represent 15%** of all emails, indicating active communication from employers
3. **Rejection rate**: 37% of application updates are rejections (172 out of 469)
4. **Positive outcomes**: 11% interview invitations + 3% offers = 14% positive outcomes
5. **Greenhouse is the dominant ATS** used by companies in this study

## Future Enhancements

1. **Machine Learning Classification**: Train a model on labeled data for better accuracy
2. **Company Extraction**: Extract company names from emails
3. **Position Extraction**: Extract job titles/positions from emails
4. **Date Analysis**: Track response times and patterns
5. **Sentiment Analysis**: Analyze tone of rejections vs. positive updates
6. **Link Extraction**: Extract application links, interview scheduling links, etc.

## Files

- `classify_emails.py`: Main classification script
- `analyze_email_data.py`: Data analysis script for understanding patterns
- `gmail_email_scraper.py`: Email scraping script








