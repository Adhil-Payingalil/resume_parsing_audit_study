# AgentQL Error Handling Guide

## Overview

The Job Description Dynamic Extractor now includes comprehensive error handling for AgentQL-specific errors, including API limits and authentication issues. When these critical errors occur, the script will **automatically stop processing** to prevent wasted API calls and provide clear error messages.

---

## 🚨 Critical Errors Detected

The script automatically detects and handles the following AgentQL errors:

### 1. **API Limit Errors** (`AgentQLLimitError`)

Triggered when:
- Rate limit reached
- Quota exceeded
- Monthly/credit limit reached
- API usage limit hit
- HTTP 429 (Too Many Requests)

**What happens:**
- ⛔ Script stops immediately
- 💾 Partial results are saved to CSV
- 📝 Clear error message displayed
- 🚫 No more API calls are made

**Example error message:**
```
======================================================================
🚨 CRITICAL ERROR: AgentQL API Limit Reached
======================================================================
Error: AgentQL API limit reached: rate limit exceeded

The script has stopped because the AgentQL API limit has been reached.
Please check your AgentQL usage limits and try again later.

Partial results (if any) have been saved to CSV.
======================================================================
```

### 2. **Authentication Errors** (`AgentQLCriticalError`)

Triggered when:
- Invalid API key
- Unauthorized access
- Authentication failed
- HTTP 401 (Unauthorized)
- HTTP 403 (Forbidden)

**What happens:**
- ⛔ Script stops immediately
- 💾 Partial results are saved to CSV
- 📝 Clear error message displayed
- 🔑 User prompted to check API key

**Example error message:**
```
======================================================================
🚨 CRITICAL ERROR: AgentQL Error
======================================================================
Error: AgentQL authentication error: invalid api key

The script has stopped due to a critical AgentQL error.
This could be due to authentication issues or service problems.

Partial results (if any) have been saved to CSV.
======================================================================
```

### 3. **Service Errors** (Non-Critical)

Triggered when:
- Service unavailable
- Server error
- Internal server error
- HTTP 500/502/503

**What happens:**
- ⚠️ Warning logged
- ➡️ Script continues with next job
- 🔄 Will retry according to MAX_RETRIES setting

---

## 🔧 How It Works

### Error Detection Flow

```
Job Processing
    ↓
AgentQL Query Executed
    ↓
Error Occurs?
    ↓
    ├─ YES → Check Error Type
    │         ↓
    │         ├─ API Limit → Stop Script ⛔
    │         ├─ Auth Error → Stop Script ⛔
    │         └─ Service Error → Log & Continue ⚠️
    │
    └─ NO → Continue Processing ✅
```

### Stop Mechanism

1. **Error Detected**: AgentQL error is detected in `extract_job_description_with_agentql_sync()`
2. **Error Checked**: `check_agentql_error()` method analyzes the error message
3. **Exception Raised**: `AgentQLLimitError` or `AgentQLCriticalError` is raised
4. **Flag Set**: `self.should_stop = True` is set
5. **Processing Stops**: Current batch completes, then script stops
6. **Results Saved**: All partial results are saved to CSV
7. **Summary Displayed**: Final summary shows early stop warning

---

## 📋 Code Examples

### Custom Exception Classes

```python
class AgentQLLimitError(Exception):
    """Raised when AgentQL API limit is reached"""
    pass

class AgentQLCriticalError(Exception):
    """Raised when a critical AgentQL error occurs"""
    pass
```

### Error Detection Method

```python
def check_agentql_error(self, error_message: str) -> None:
    """
    Check if error is an AgentQL critical error
    Raises appropriate exception if detected
    """
    error_lower = str(error_message).lower()
    
    # Check for API limit
    if any(indicator in error_lower for indicator in 
           ['rate limit', 'quota exceeded', 'limit reached', ...]):
        raise AgentQLLimitError(f"AgentQL API limit reached: {error_message}")
    
    # Check for authentication
    if any(indicator in error_lower for indicator in 
           ['unauthorized', 'invalid api key', '401', '403', ...]):
        raise AgentQLCriticalError(f"AgentQL authentication error: {error_message}")
```

### Usage in Extraction

```python
try:
    result = page.query_data(comprehensive_query)
except Exception as e:
    logger.error(f"AgentQL query failed: {e}")
    # Check for critical errors
    try:
        self.check_agentql_error(str(e))
    except (AgentQLLimitError, AgentQLCriticalError):
        # Re-raise to stop processing
        raise
```

---

## 🎯 Error Indicators

### API Limit Indicators
- `rate limit`
- `quota exceeded`
- `limit reached`
- `api limit`
- `too many requests`
- `usage limit`
- `monthly limit`
- `credit limit`
- `429` (HTTP status)

### Authentication Indicators
- `unauthorized`
- `invalid api key`
- `authentication failed`
- `api key`
- `401` (HTTP status)
- `403` (HTTP status)

### Service Error Indicators
- `service unavailable`
- `server error`
- `internal server error`
- `500` (HTTP status)
- `502` (HTTP status)
- `503` (HTTP status)

---

## 🔍 Debugging AgentQL Errors

### Check Logs

All AgentQL errors are logged with specific prefixes:

```bash
# Critical errors
🚨 AgentQL API limit reached: ...
🚨 AgentQL authentication error: ...
🚨 Critical AgentQL error occurred: ...

# Warnings
⚠️ AgentQL service error (may be temporary): ...
⚠️ Stopping extraction due to critical error
⚠️ Extraction stopped early due to critical error!
```

### View Full Log File

```bash
# Windows
type logs\job_description_dynamic_extractor.log | findstr "AgentQL"

# Linux/Mac
grep "AgentQL" logs/job_description_dynamic_extractor.log
```

---

## 💡 Best Practices

### 1. Monitor API Usage

Before running large batches:
```python
# Start with a small limit to test
limit = 10  # Test with 10 jobs first
```

### 2. Check API Key

Verify your API key is valid:
```bash
# Check .env file
cat .env | grep AGENTQL_API_KEY
```

### 3. Review Error Patterns

If you see repeated errors:
```python
# Review the CSV output
import pandas as pd
df = pd.read_csv('data/job_description_dynamic_results_YYYYMMDD_HHMMSS.csv')
print(df[df['status'] == 'failed']['error'].value_counts())
```

### 4. Implement Backoff Strategy

For service errors, the script already includes delays:
```python
MAX_RETRIES = 3  # Retry up to 3 times
time.sleep(2)    # 2-second delay between retries
```

---

## 🛠️ Configuration

### Adjust Retry Behavior

```python
# In job_description_dynamic_extractor.py

MAX_RETRIES = 3          # Number of retries per job
BATCH_SIZE = 5           # Jobs per batch
TIMEOUT = 30000          # 30 seconds per page
```

### Modify Error Detection

You can customize which errors are critical by editing the `check_agentql_error()` method:

```python
def check_agentql_error(self, error_message: str) -> None:
    error_lower = str(error_message).lower()
    
    # Add custom error indicators
    custom_indicators = ['your_custom_error', 'another_error']
    if any(indicator in error_lower for indicator in custom_indicators):
        raise AgentQLCriticalError(f"Custom error: {error_message}")
```

---

## 📊 Error Statistics

After processing, the summary will show:

```
======================================================================
                        Extraction Summary                          
======================================================================
⚠️ Extraction stopped early due to critical error!
⚠️ Partial results have been saved
📊 Total processed successfully: 15
❌ Total failed: 5
📝 Total jobs attempted: 20
⏱️  Total time: 245.32 seconds
🚀 Average rate: 0.08 jobs/sec
✅ Success rate: 75.0%
📁 Results saved to: data\job_description_dynamic_results_20251020_143045.csv
======================================================================
```

---

## 🔄 Recovery After Errors

### After API Limit Error

1. **Wait**: Wait for your API limit to reset (check AgentQL dashboard)
2. **Check Remaining**: Verify remaining jobs:
   ```python
   RETRY_PREVIOUSLY_FAILED = False  # Don't retry jobs that were attempted
   ```
3. **Resume**: Run the script again with the same configuration

### After Authentication Error

1. **Verify API Key**: Check your `.env` file
2. **Update Key**: If expired, get a new key from AgentQL
3. **Test**: Run with a small limit first:
   ```
   Enter number of jobs to process: 5
   ```

### After Service Error

Service errors are temporary - the script will automatically retry. If you see many service errors:
1. Wait 5-10 minutes
2. Try again
3. If persistent, check AgentQL status page

---

## 🧪 Testing Error Handling

### Simulate API Limit Error

```python
# In your test environment
def test_api_limit():
    extractor = JobDescriptionDynamicExtractor()
    try:
        extractor.check_agentql_error("rate limit exceeded")
    except AgentQLLimitError as e:
        print(f"✅ API limit error caught: {e}")
```

### Simulate Auth Error

```python
def test_auth_error():
    extractor = JobDescriptionDynamicExtractor()
    try:
        extractor.check_agentql_error("invalid api key")
    except AgentQLCriticalError as e:
        print(f"✅ Auth error caught: {e}")
```

---

## 📞 Troubleshooting

| Problem | Solution |
|---------|----------|
| Script stops after 1 job | Check for API limit error in logs |
| "Invalid API key" error | Verify AGENTQL_API_KEY in .env file |
| Frequent 429 errors | Reduce BATCH_SIZE or add delays |
| Service unavailable | Wait 5-10 minutes and retry |
| No error but script stops | Check for `should_stop = True` in logs |

---

## 📝 Summary

The AgentQL error handling system:

✅ **Automatically detects** critical AgentQL errors  
✅ **Stops processing** to prevent wasted API calls  
✅ **Saves partial results** before exiting  
✅ **Provides clear messages** for debugging  
✅ **Distinguishes** between critical and temporary errors  
✅ **Logs everything** for post-analysis  

---

**Last Updated:** October 20, 2024  
**Feature Version:** v2.1 - AgentQL Error Handling

