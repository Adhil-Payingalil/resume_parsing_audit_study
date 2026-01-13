# Job Link Verification Guide

This guide explains how to verify if job postings in your database are still active.

## Overview

The verification system consists of two main scripts:

1. **`verify_job_links.py`** - Verifies if job links are still active
2. **`analyze_verified_links.py`** - Analyzes and reports verification results

## How It Works

The verification process:

1. **Opens each job link** in a browser
2. **Detects redirects** - Compares the original URL with the final URL after redirects
3. **Looks for closure indicators** - Searches for common phrases like:
   - "no longer accepting applications"
   - "position has been filled"
   - "job is no longer available"
   - "404" or "page not found"
4. **Checks for apply buttons** - Active jobs typically have an "Apply" button
5. **Updates MongoDB** with the verification status

## Job Link Status

Each job link is classified as:

- **`active`** - Job posting is still accepting applications
- **`inactive`** - Job posting is closed, filled, or redirects to a generic page
- **`error`** - Could not verify (timeout, network error, etc.)

## Usage

### Step 1: Verify Job Links

Run the verification script:

```bash
python verify_job_links.py
```

**Interactive Options:**

- **Number of jobs to verify**: Enter a number or press Enter to verify all
- **Headless mode**: `y` to run without showing browser (faster), `n` to see the browser
- **Re-verify**: If all jobs are already verified, you can choose to re-verify them

**What happens:**

- Each job link is opened in a browser
- The script checks if the job is still active
- Results are saved to MongoDB with these new fields:
  - `link_status`: 'active', 'inactive', or 'error'
  - `link_verified_at`: Timestamp of verification
  - `link_final_url`: Final URL after redirects
  - `link_status_reason`: Reason for inactive/error status
- A CSV report is saved to `data/job_link_verification_YYYYMMDD_HHMMSS.csv`

**Example Output:**

```
📊 Total verified: 150
✅ Active jobs: 95 (63.3%)
❌ Inactive jobs: 48 (32.0%)
⚠️ Errors: 7 (4.7%)
⏱️ Total time: 245.32 seconds
🚀 Average rate: 0.61 jobs/sec
```

### Step 2: Analyze Results

After verification, analyze the results:

```bash
python analyze_verified_links.py
```

**What you'll see:**

1. **Overall Statistics** - Total jobs, verified vs unverified
2. **Status Breakdown** - Active, inactive, and error counts with percentages
3. **Inactive Reasons** - Why jobs were marked as inactive
4. **Error Reasons** - What errors occurred during verification
5. **Recent Verifications** - Last 10 verified jobs
6. **Company Breakdown** - Active vs inactive jobs by company

**Additional Options:**

1. View detailed list of inactive jobs
2. Export inactive jobs to CSV
3. Export active jobs to CSV

## MongoDB Fields

The verification process adds these fields to each job document:

```javascript
{
  // ... existing fields ...
  "link_status": "active",              // 'active', 'inactive', or 'error'
  "link_verified_at": ISODate("2025-10-09T12:30:45Z"),
  "link_final_url": "https://...",      // Final URL after redirects
  "link_status_reason": null            // Reason for inactive/error (if applicable)
}
```

## Use Cases

### 1. Clean Up Old Job Postings

Export inactive jobs and decide which to remove:

```bash
python analyze_verified_links.py
# Choose option 2 to export inactive jobs
```

Review the CSV and delete jobs that are permanently closed.

### 2. Re-verify Old Jobs

If you verified jobs months ago, re-verify them:

```bash
python verify_job_links.py
# When prompted, choose 'y' to re-verify all jobs
```

### 3. Verify Only New Jobs

By default, the script skips already verified jobs, so you can run it periodically to verify only new additions.

### 4. Focus on Specific Companies

You can modify the MongoDB query in `verify_job_links.py` to verify specific companies:

```python
query = {
    'job_link': {'$exists': True, '$ne': ''},
    'company': 'Google'  # Add company filter
}
```

## Configuration

Edit these settings in `verify_job_links.py`:

```python
HEADLESS = True          # Run browser in background (faster)
TIMEOUT = 15000          # Timeout for page loads (milliseconds)
MAX_RETRIES = 2          # Retries per job if verification fails
```

## Tips

1. **Start Small**: Test with a small number first (e.g., 10 jobs) to ensure everything works
2. **Headless Mode**: Use headless mode for faster verification
3. **Network**: Ensure stable internet connection for accurate results
4. **Errors**: If many errors occur, try increasing `TIMEOUT` or `MAX_RETRIES`
5. **Rate Limiting**: The script includes 1-2 second delays between requests to be respectful to servers

## Troubleshooting

### Problem: Many jobs marked as errors

**Solution**: Increase timeout or check your internet connection:

```python
TIMEOUT = 30000  # Increase to 30 seconds
MAX_RETRIES = 3  # Try more retries
```

### Problem: Jobs incorrectly marked as inactive

**Solution**: Some job sites may have unique closure messages. Add them to `JOB_CLOSED_INDICATORS` in `verify_job_links.py`:

```python
JOB_CLOSED_INDICATORS = [
    # ... existing indicators ...
    "your specific phrase here",
]
```

### Problem: Verification is too slow

**Solution**:
1. Enable headless mode: `HEADLESS = True`
2. Reduce timeout: `TIMEOUT = 10000`
3. Verify in batches (e.g., 50 at a time)

## CSV Output

The verification CSV includes:

| Column | Description |
|--------|-------------|
| `job_id` | MongoDB document ID |
| `job_title` | Job title |
| `company` | Company name |
| `original_url` | Original job link |
| `final_url` | URL after redirects |
| `status` | 'active', 'inactive', or 'error' |
| `reason` | Why inactive/error (if applicable) |
| `verified_at` | Timestamp of verification |

## Best Practices

1. **Regular Verification**: Run monthly to keep data fresh
2. **Review Before Deleting**: Always review inactive jobs before removing from database
3. **Keep Logs**: The script logs everything to `logs/verify_job_links.log`
4. **Backup First**: Backup your database before bulk deletions
5. **Spot Check**: Manually verify a few "inactive" jobs to ensure accuracy

## Next Steps

After verification:

1. **Review inactive jobs** - Are they really closed?
2. **Export inactive jobs** - Save them for records
3. **Delete if needed** - Remove permanently closed positions
4. **Update your scraping** - Focus on active companies/sources

## Support

For issues or questions:
- Check logs in `logs/verify_job_links.log`
- Review CSV output for patterns
- Adjust configuration settings as needed


