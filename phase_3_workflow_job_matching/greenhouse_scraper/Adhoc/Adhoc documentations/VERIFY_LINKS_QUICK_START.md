# Job Link Verification - Quick Start

## 🚀 Quick Commands

### Verify Job Links
```bash
python verify_job_links.py
```

### Analyze Results
```bash
python analyze_verified_links.py
```

## 📋 What Each Script Does

### 1. `verify_job_links.py`
- Opens each job link in a browser
- Checks if the job is still accepting applications
- Detects redirects and "job closed" messages
- Updates MongoDB with verification status
- Creates CSV report in `data/` folder

### 2. `analyze_verified_links.py`
- Shows statistics on active vs inactive jobs
- Lists reasons why jobs were marked inactive
- Displays company breakdown
- Can export results to CSV

## 🎯 Common Workflows

### First Time: Verify All Jobs
```bash
python verify_job_links.py
# Press Enter to verify all jobs
# Choose 'y' for headless mode (faster)
```

### Check Results
```bash
python analyze_verified_links.py
# Choose option 2 to export inactive jobs to CSV
```

### Verify Only New Jobs (Skip Already Verified)
```bash
python verify_job_links.py
# Enter a number or press Enter
# Already verified jobs are automatically skipped
```

### Re-verify Everything
```bash
python verify_job_links.py
# When prompted, choose 'y' to re-verify all jobs
```

## 📊 What Gets Added to MongoDB

Each job gets these new fields:

```javascript
{
  "link_status": "active",              // or "inactive" or "error"
  "link_verified_at": "2025-10-09...",  // timestamp
  "link_final_url": "https://...",      // URL after redirects
  "link_status_reason": "..."           // why inactive/error (if any)
}
```

## 💡 Tips

- **Test first**: Verify 5-10 jobs first to ensure it works
- **Headless mode**: Use `y` for faster verification (no browser window)
- **Check logs**: View `logs/verify_job_links.log` if issues occur
- **Review results**: Always review inactive jobs before deleting them

## ⚙️ Configuration

Edit `verify_job_links.py` to adjust:

```python
HEADLESS = True      # False to see browser
TIMEOUT = 15000      # milliseconds (increase if many errors)
MAX_RETRIES = 2      # retries per job
```

## 🔍 Job Status Meanings

- **active** ✅ - Job is still accepting applications
- **inactive** ❌ - Job closed, filled, or redirects to homepage
- **error** ⚠️ - Could not verify (timeout, network issue, etc.)

## 📝 Output Files

### Verification CSV
`data/job_link_verification_YYYYMMDD_HHMMSS.csv`

Columns: job_id, job_title, company, original_url, final_url, status, reason, verified_at

### Export CSVs (from analyze script)
- `data/jobs_inactive_YYYYMMDD_HHMMSS.csv` - All inactive jobs
- `data/jobs_active_YYYYMMDD_HHMMSS.csv` - All active jobs

## 🛠️ Troubleshooting

### Many errors?
- Increase `TIMEOUT = 30000` in verify_job_links.py
- Check your internet connection
- Try with fewer jobs first

### Jobs incorrectly marked inactive?
- Add site-specific phrases to `JOB_CLOSED_INDICATORS`
- Check `link_status_reason` field to see what was detected

### Too slow?
- Use headless mode: `HEADLESS = True`
- Reduce timeout: `TIMEOUT = 10000`
- Verify in smaller batches

## 📚 Need More Info?

See full guide: `JOB_LINK_VERIFICATION_GUIDE.md`


