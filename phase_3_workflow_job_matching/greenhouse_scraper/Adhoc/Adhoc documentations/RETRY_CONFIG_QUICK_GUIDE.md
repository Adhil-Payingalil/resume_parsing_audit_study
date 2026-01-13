# Quick Guide: RETRY_PREVIOUSLY_FAILED Configuration

## 🎯 TL;DR

Set this flag in `job_description_dynamic_extractor.py` (line 49):

```python
RETRY_PREVIOUSLY_FAILED = False  # Default - Only retry fresh failures
RETRY_PREVIOUSLY_FAILED = True   # Retry ALL failures, including old ones
```

---

## 🔍 What Does This Control?

This flag controls whether the script processes jobs that have already been attempted with the retry mechanism.

---

## ⚙️ Configuration Options

### Option 1: `RETRY_PREVIOUSLY_FAILED = False` (DEFAULT)

**What it does:**
- ✅ Processes jobs where `jd_extraction = False`
- ✅ AND `retry_attempted_at` does NOT exist
- ❌ SKIPS jobs that have `retry_attempted_at` field

**Database Query:**
```python
{
    'job_link': {'$exists': True, '$ne': ''},
    'jd_extraction': False,
    'retry_attempted_at': {'$exists': False}  # <-- This line is added
}
```

**Use when:**
- You want to focus on jobs that have **never been retried** before
- You want to avoid wasting time on jobs that already failed a retry attempt
- You're running the script for the first time after a bulk extraction failure

**Example:**
```
Total jobs in database: 1000
- jd_extraction = True: 700 jobs ✅
- jd_extraction = False, retry_attempted_at exists: 200 jobs ⏭️ (SKIPPED)
- jd_extraction = False, no retry_attempted_at: 100 jobs ✅ (PROCESSED)

Result: Script will process 100 jobs
```

---

### Option 2: `RETRY_PREVIOUSLY_FAILED = True`

**What it does:**
- ✅ Processes ALL jobs where `jd_extraction = False`
- ✅ Includes jobs with `retry_attempted_at` field
- ✅ Gives previously failed jobs another chance

**Database Query:**
```python
{
    'job_link': {'$exists': True, '$ne': ''},
    'jd_extraction': False
    # No retry_attempted_at filter
}
```

**Use when:**
- You've improved the extraction logic and want to retry previously failed jobs
- You suspect the previous failures were due to temporary issues (timeouts, network, etc.)
- You want to give all failed jobs another chance

**Example:**
```
Total jobs in database: 1000
- jd_extraction = True: 700 jobs ✅
- jd_extraction = False, retry_attempted_at exists: 200 jobs ✅ (PROCESSED)
- jd_extraction = False, no retry_attempted_at: 100 jobs ✅ (PROCESSED)

Result: Script will process 300 jobs
```

---

## 📋 Comparison Table

| Aspect | `False` (Default) | `True` |
|--------|------------------|--------|
| **Fresh failures** | ✅ Processed | ✅ Processed |
| **Previously retried** | ❌ Skipped | ✅ Processed |
| **Use case** | First retry attempt | Second+ retry attempt |
| **Typical count** | Lower | Higher |
| **Risk of wasted effort** | Low | Medium |
| **Chance of new successes** | High | Medium |

---

## 🎬 Real-World Workflow

### Workflow 1: Initial Retry (Recommended)

```python
# Step 1: First retry attempt
RETRY_PREVIOUSLY_FAILED = False
# Run script -> Some jobs succeed, some fail

# Step 2: Check results
# If many jobs still failed, consider improving the script or timeouts

# Step 3: Second retry attempt (if needed)
RETRY_PREVIOUSLY_FAILED = True
# Run script -> Retry everything including previous failures
```

### Workflow 2: After Script Improvements

```python
# You've improved extraction logic or increased timeouts
RETRY_PREVIOUSLY_FAILED = True  # Give all failed jobs another chance
```

### Workflow 3: Periodic Maintenance

```python
# Check for new failures every week
RETRY_PREVIOUSLY_FAILED = False  # Only process new failures
```

---

## 🔍 How to Check Which Jobs Will Be Processed

Use this MongoDB query to see what the script will process:

### With `RETRY_PREVIOUSLY_FAILED = False`
```javascript
db.Job_postings_greenhouse.count({
    job_link: { $exists: true, $ne: '' },
    jd_extraction: false,
    retry_attempted_at: { $exists: false }
})
```

### With `RETRY_PREVIOUSLY_FAILED = True`
```javascript
db.Job_postings_greenhouse.count({
    job_link: { $exists: true, $ne: '' },
    jd_extraction: false
})
```

---

## 💡 Pro Tips

1. **Start with `False`**: Always run with `RETRY_PREVIOUSLY_FAILED = False` first to avoid processing jobs that have already failed
2. **Check the preview**: The script shows a preview of jobs - look for the "⚠️ Previously retried" indicator
3. **Monitor success rate**: If success rate is low, improve the script before running with `True`
4. **Check CSV results**: Review the generated CSV to understand why jobs are failing
5. **Use limit parameter**: Test with a small limit first: `Enter number of jobs to process: 10`

---

## 🚨 Common Pitfalls

### ❌ Wrong: Setting to True immediately
```python
RETRY_PREVIOUSLY_FAILED = True  # Don't do this on first run!
# This will waste time retrying jobs that already failed once
```

### ✅ Right: Start with False
```python
RETRY_PREVIOUSLY_FAILED = False  # Start with this
# Process fresh failures first, then decide if retry is needed
```

---

## 📊 Understanding the Output

When running the script, you'll see:

```
📋 Configuration:
  • Retry previously failed: False
    (Will only process jobs that have never been retried)
```

or

```
📋 Configuration:
  • Retry previously failed: True
    (Will process all failed jobs, including previously retried ones)
```

This confirms which mode you're running in.

---

## ❓ FAQ

**Q: What happens if a job fails with `RETRY_PREVIOUSLY_FAILED = False`?**  
A: The job gets `retry_attempted_at` timestamp set, so next time you run with `False`, it will be skipped.

**Q: Can I reset the retry attempts?**  
A: Yes, remove the `retry_attempted_at` field from the MongoDB documents:
```javascript
db.Job_postings_greenhouse.updateMany(
    { jd_extraction: false },
    { $unset: { retry_attempted_at: "", retry_error: "" } }
)
```

**Q: What if I want to retry only specific jobs?**  
A: You can manually unset `retry_attempted_at` for specific jobs, or modify the script to accept a list of job IDs.

**Q: Does this affect successful extractions?**  
A: No, jobs with `jd_extraction = True` are never processed regardless of this setting.

---

**Quick Start:** Keep `RETRY_PREVIOUSLY_FAILED = False` for normal operation!

