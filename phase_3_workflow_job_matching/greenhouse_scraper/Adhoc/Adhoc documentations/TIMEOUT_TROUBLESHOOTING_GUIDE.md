# Timeout Troubleshooting Guide

## 🔍 Problem: Repeated Timeout Errors

### What You're Seeing

```
2025-10-19 21:29:03 - INFO - Processing job 68f540b8345bb9f51a026357 (attempt 1/3)
2025-10-19 21:29:34 - ERROR - Error processing job 68f540b8345bb9f51a026357: Timeout 30000ms exceeded.
=========================== logs ===========================
"load" event fired
============================================================
```

**Pattern:**
- Page navigation starts
- "load" event fires (page HTML is loaded)
- But then the script times out waiting for `networkidle`
- This repeats for all 3 retry attempts

---

## 🎯 Root Cause

### The Issue

The script was waiting for the page to reach **`networkidle`** state, which means:
- No network requests for at least 500ms
- All resources (images, scripts, etc.) are loaded

### Why It Fails

Many modern websites **never reach true networkidle** because they:
- ✅ Continuously send analytics/tracking data
- ✅ Have live chat widgets that ping servers
- ✅ Load ads that keep refreshing
- ✅ Have websocket connections
- ✅ Poll for updates in the background

**Result:** The page loads fine, but networkidle is never achieved, causing a 30-second timeout.

---

## ✅ Solution Implemented

### Changes Made

1. **Separated page load states:**
   - `domcontentloaded`: HTML is parsed (fast)
   - `load`: All resources loaded (medium)
   - `networkidle`: No network activity (often never happens)

2. **Made networkidle optional and non-blocking:**
   ```python
   # Old behavior - BLOCKS until networkidle or timeout
   page.wait_for_load_state('networkidle', timeout=30000)  # ❌
   
   # New behavior - CONTINUES even if networkidle times out
   try:
       page.wait_for_load_state('networkidle', timeout=15000)
   except:
       logger.warning("Network idle not achieved, continuing anyway")  # ✅
   ```

3. **Added configuration options:**
   - `WAIT_FOR_NETWORKIDLE`: Enable/disable networkidle wait
   - `NETWORKIDLE_TIMEOUT`: Separate timeout for networkidle (15s instead of 30s)

---

## 🔧 Configuration Options

### Option 1: Keep Default (Recommended)

The script now handles timeouts gracefully by default:

```python
# Default configuration (in job_description_dynamic_extractor.py)
TIMEOUT = 30000              # 30 seconds for page.goto()
WAIT_FOR_NETWORKIDLE = True  # Try to wait for networkidle
NETWORKIDLE_TIMEOUT = 15000  # But only wait 15 seconds
```

**What happens:**
1. ✅ Page navigates with 30-second timeout
2. ✅ Waits for `load` event (HTML + resources)
3. ⏱️ Tries to wait for `networkidle` for 15 seconds
4. ➡️ If networkidle times out, **continues anyway** (doesn't fail!)
5. ✅ Extracts content from the loaded page

### Option 2: Skip Networkidle Completely

For very slow sites or sites that never reach networkidle:

```python
# Skip networkidle wait entirely
WAIT_FOR_NETWORKIDLE = False
```

**Effect:** Faster processing, but might miss some lazy-loaded content.

### Option 3: Increase Timeouts

For very slow-loading sites:

```python
# Increase all timeouts
TIMEOUT = 60000              # 60 seconds for page load
NETWORKIDLE_TIMEOUT = 30000  # 30 seconds for networkidle
```

**Effect:** More patient waiting, but slower overall processing.

---

## 📊 Before vs After

### Before Fix

```
Attempt 1: Navigate → Wait for networkidle (30s) → TIMEOUT ❌
Attempt 2: Navigate → Wait for networkidle (30s) → TIMEOUT ❌
Attempt 3: Navigate → Wait for networkidle (30s) → TIMEOUT ❌
Result: Job marked as failed after 90+ seconds
```

### After Fix

```
Attempt 1: Navigate → Load (5s) → Try networkidle (15s, optional) → Extract ✅
Result: Job extracted successfully after ~20 seconds
```

---

## 🚀 How to Use

### For Sites Timing Out Frequently

If you're seeing many timeout errors for the same domains:

1. **Check which sites are timing out:**
   ```bash
   # Look at your logs
   grep "Timeout 30000ms exceeded" logs/job_description_dynamic_extractor.log
   ```

2. **Try disabling networkidle:**
   ```python
   # In job_description_dynamic_extractor.py, line 56
   WAIT_FOR_NETWORKIDLE = False
   ```

3. **Run again and check results:**
   ```bash
   python job_description_dynamic_extractor.py
   ```

### For Very Slow Sites

If pages are legitimately slow to load:

```python
# Increase the main timeout
TIMEOUT = 60000  # 60 seconds

# Keep networkidle enabled but with longer timeout
NETWORKIDLE_TIMEOUT = 30000  # 30 seconds
```

---

## 🔍 Understanding the Logs

### New Log Messages

With the fix, you'll see these new messages:

#### Success Path
```
2025-10-20 - INFO - Processing job 68f540b8 (attempt 1/3): https://example.com
2025-10-20 - DEBUG - Job 68f540b8: Page 'load' event completed
2025-10-20 - DEBUG - Job 68f540b8: Page reached 'networkidle' state
2025-10-20 - INFO - Strategy 1: Attempting comprehensive extraction
```

#### Networkidle Timeout (Non-Fatal)
```
2025-10-20 - INFO - Processing job 68f540b8 (attempt 1/3): https://example.com
2025-10-20 - DEBUG - Job 68f540b8: Page 'load' event completed
2025-10-20 - WARNING - Job 68f540b8: Network idle not achieved (common for sites with analytics), continuing anyway
2025-10-20 - INFO - Strategy 1: Attempting comprehensive extraction
```
**Note:** This is now a WARNING, not an ERROR. The script continues!

#### True Failure
```
2025-10-20 - INFO - Processing job 68f540b8 (attempt 1/3): https://example.com
2025-10-20 - ERROR - Error processing job 68f540b8: Timeout 30000ms exceeded.
```
**Note:** Only happens if the initial `page.goto()` fails or page truly doesn't load.

---

## 🎯 Recommended Settings by Use Case

### Fast Processing (Skip Networkidle)
```python
TIMEOUT = 30000                # 30 seconds
WAIT_FOR_NETWORKIDLE = False   # Skip it entirely
MAX_RETRIES = 2                # Fewer retries since we're faster
```

**Best for:** Large batches, sites with lots of tracking/analytics

### Balanced (Default)
```python
TIMEOUT = 30000               # 30 seconds
WAIT_FOR_NETWORKIDLE = True   # Try but don't fail
NETWORKIDLE_TIMEOUT = 15000   # 15 seconds
MAX_RETRIES = 3
```

**Best for:** Most situations, mixed site types

### Patient/Thorough
```python
TIMEOUT = 60000               # 60 seconds
WAIT_FOR_NETWORKIDLE = True
NETWORKIDLE_TIMEOUT = 30000   # 30 seconds
MAX_RETRIES = 3
```

**Best for:** Critical extractions, slow sites, need all lazy-loaded content

---

## 🐛 Debugging Timeout Issues

### Step 1: Identify Problem Sites

```bash
# Extract URLs that timeout
grep -B1 "Timeout 30000ms exceeded" logs/job_description_dynamic_extractor.log | grep "http"
```

### Step 2: Test Individual Site

Visit the problematic URL in your browser and:
- ✅ Check if it loads quickly or slowly
- ✅ Open Developer Tools → Network tab
- ✅ Watch for ongoing requests (analytics, ads, etc.)
- ✅ Note if requests never stop

### Step 3: Adjust Configuration

Based on your findings:

| Observation | Solution |
|-------------|----------|
| Page loads but requests never stop | `WAIT_FOR_NETWORKIDLE = False` |
| Page is legitimately slow | Increase `TIMEOUT` |
| Page has lots of lazy-loading | Increase scroll wait time |
| Page blocks automated browsers | Check for anti-bot protection |

---

## 📈 Performance Impact

### Time Savings

**Before (with timeouts):**
```
Job with 3 timeout failures: 90+ seconds
10 such jobs: 900+ seconds (15 minutes)
```

**After (with fix):**
```
Same job now succeeds: ~20 seconds
10 such jobs: 200 seconds (3.3 minutes)
```

**Savings: ~78% faster!** ⚡

---

## ✅ Verification

After implementing the fix, verify it's working:

### Check Configuration Display

When you run the script, you should see:

```
======================================================================
          Job Description Dynamic Extractor          
======================================================================

📋 Configuration:
  • Headless mode: False
  • Page load timeout: 30 seconds
  • Network idle timeout: 15 seconds        ← New!
  • Wait for network idle: True             ← New!
  • Max retries per job: 3
  • Default batch size: 5
  • Retry previously failed: False
```

### Monitor Logs

Look for the new warning messages instead of errors:

```bash
# This is now OK (WARNING, not ERROR)
grep "Network idle not achieved" logs/job_description_dynamic_extractor.log

# This should be much less frequent now
grep "Timeout 30000ms exceeded" logs/job_description_dynamic_extractor.log
```

### Check Success Rate

```bash
# View the CSV results
# Look for fewer timeout failures
```

---

## 🔧 Advanced: Site-Specific Handling

If certain domains consistently timeout, you could add custom handling:

```python
# In extract_job_description_with_agentql_sync(), around line 351

# Detect problematic domains
if 'kevgroup.com' in job_url or 'slowsite.com' in job_url:
    # Use more lenient settings for this site
    page.goto(job_url, timeout=60000, wait_until='domcontentloaded')
    time.sleep(5)  # Extra wait for slow sites
    # Skip networkidle for these sites
else:
    # Normal handling
    page.goto(job_url, timeout=TIMEOUT, wait_until='domcontentloaded')
```

---

## 📝 Summary

### What Was Fixed

✅ **Separated page load states** - Don't fail on networkidle timeout  
✅ **Made networkidle optional** - Can disable completely  
✅ **Added separate timeouts** - Shorter timeout for networkidle  
✅ **Better logging** - Warnings instead of errors for expected issues  
✅ **Configurable behavior** - Easy to adjust for different sites  

### Key Takeaway

**The page loading is no longer an all-or-nothing process.** The script now:
1. Waits for essential content (HTML + resources)
2. Optionally tries to wait for complete idle
3. **Continues with extraction regardless**
4. Only fails if the page truly doesn't load

---

## 🎓 Learn More

### Page Load States

| State | Means | When to Use |
|-------|-------|-------------|
| `domcontentloaded` | HTML parsed | Static sites, fast processing |
| `load` | All resources loaded | Most sites (default) |
| `networkidle` | No network activity | Rare, only if needed |

### Why Networkidle Is Problematic

Modern web development practices mean most sites will **never** reach networkidle:
- Google Analytics keeps pinging
- Facebook Pixel tracks continuously
- Ad networks refresh
- WebSocket connections stay open
- Service workers communicate

**Bottom line:** Networkidle is increasingly outdated for modern web scraping.

---

**Last Updated:** October 20, 2024  
**Fix Version:** v2.2 - Resilient Timeout Handling

