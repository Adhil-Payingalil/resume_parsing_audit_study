# Job Description Extractor using Jina AI

This guide explains how to use the optimized job description extraction system that integrates with your existing Greenhouse job scraper.

## Overview

The system consists of two main components:
1. **`scraper.py`** - Your existing script that scrapes job postings and saves them to MongoDB
2. **`job_description_extractor.py`** - New script that extracts job descriptions using Jina AI API

## Features

### 🚀 Performance Optimizations
- **Concurrent Processing**: Processes multiple jobs simultaneously using asyncio
- **Rate Limiting**: Respects Jina AI API rate limits (10 requests/second)
- **Batch Processing**: Processes jobs in configurable batches
- **Connection Pooling**: Optimized HTTP connections with aiohttp
- **Bulk MongoDB Updates**: Updates multiple documents efficiently

### 🛡️ Reliability Features
- **Retry Logic**: Automatic retries with exponential backoff
- **Error Handling**: Comprehensive error handling and logging
- **Timeout Management**: Configurable timeouts for API calls
- **Progress Tracking**: Real-time progress updates and statistics

## Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Environment Variables
Make sure your `.env` file contains:
```env
JINAAI_API_KEY=your_jina_ai_api_key
MONGODB_URI=your_mongodb_connection_string
MONGODB_DATABASE=Resume_study
```

### 3. Test the Setup
```bash
python test_jina_extraction.py
```

## Usage

### Basic Usage
```bash
python job_description_extractor.py
```

The script will prompt you for:
- Number of jobs to process (or all jobs)
- Batch size (default: 20 concurrent jobs)

### Advanced Usage
You can modify the configuration in `job_description_extractor.py`:

```python
# Configuration
RATE_LIMIT_DELAY = 0.1  # 100ms between requests (10 requests per second)
BATCH_SIZE = 20  # Process 20 jobs concurrently
MAX_RETRIES = 3
TIMEOUT = 30  # 30 seconds timeout per request
```

## How It Works

### 1. Data Flow
```
MongoDB Jobs → Filter Jobs Without Descriptions → Extract Descriptions → Update MongoDB
```

### 2. Extraction Process
1. **Query MongoDB**: Finds jobs that don't have descriptions yet
2. **Concurrent Processing**: Processes multiple jobs simultaneously
3. **Jina AI API**: Uses `r.jina.ai` endpoint to extract content
4. **Content Parsing**: Extracts job description from markdown content
5. **Bulk Update**: Updates MongoDB with descriptions efficiently

### 3. Database Schema
The script adds this field to your existing job documents:
```json
{
  "job_description": "Full job description text..."
}
```

## Performance Metrics

### Expected Performance
- **Speed**: ~10-20 jobs per second (depending on API response times)
- **Concurrency**: 20 jobs processed simultaneously
- **Rate Limiting**: 10 requests per second to respect API limits
- **Memory**: Efficient memory usage with streaming responses

### Example Output
```
Processing batch 1/5 (20 jobs)
✅ Successfully extracted description for job 507f1f77bcf86cd799439011
✅ Successfully extracted description for job 507f1f77bcf86cd799439012
...
Progress: 20 processed, 0 failed, 15.2 jobs/sec
```

## Error Handling

### Common Issues
1. **Rate Limiting**: Automatic retry with exponential backoff
2. **Network Timeouts**: Configurable timeout settings
3. **Invalid URLs**: Skips jobs with invalid or missing URLs
4. **API Errors**: Comprehensive error logging

### Logging
All activities are logged to:
- Console output (real-time)
- `job_description_extractor.log` file

## Monitoring

### Progress Tracking
The script provides real-time updates:
- Jobs processed per batch
- Success/failure rates
- Processing speed (jobs per second)
- Estimated time remaining

### Statistics
At completion, you'll see:
```
✅ Extraction completed!
📊 Total processed: 150
❌ Total failed: 5
⏱️ Total time: 45.2 seconds
🚀 Average rate: 3.4 jobs/sec
```

## Troubleshooting

### Common Problems

1. **API Key Issues**
   ```
   ❌ JINAAI_API_KEY not found in environment variables
   ```
   Solution: Check your `.env` file

2. **MongoDB Connection Issues**
   ```
   ❌ Failed to connect to MongoDB
   ```
   Solution: Verify your `MONGODB_URI` in `.env`

3. **Rate Limiting**
   ```
   Rate limited for job 507f..., waiting 4s...
   ```
   Solution: This is normal - the script handles it automatically

### Debug Mode
For detailed debugging, check the log file:
```bash
tail -f job_description_extractor.log
```

## Integration with Existing Workflow

### Complete Workflow
1. **Run Job Scraper**: `python scraper.py`
2. **Extract Descriptions**: `python job_description_extractor.py`
3. **Analyze Data**: Query MongoDB for jobs with descriptions

### Database Queries
```python
# Find jobs with descriptions
jobs_with_descriptions = collection.find({
    "job_description": {"$exists": True, "$ne": ""}
})

# Find jobs with non-empty descriptions
non_empty_descriptions = collection.find({
    "job_description": {"$exists": True, "$ne": "", "$ne": None}
})
```

## Cost Optimization

### Jina AI API Usage
- Uses the `r.jina.ai` endpoint (Reader API)
- Rate limited to 10 requests per second
- Automatic retry logic to minimize failed requests
- Processes only jobs without existing descriptions

### MongoDB Efficiency
- Bulk operations for database updates
- Indexed queries for fast job retrieval
- Only updates necessary fields

## Next Steps

1. **Run the test script** to verify your setup
2. **Start with a small batch** (e.g., 50 jobs) to test
3. **Monitor the logs** for any issues
4. **Scale up** to process all jobs once you're confident

## Support

If you encounter issues:
1. Check the log file for detailed error messages
2. Verify your API key and MongoDB connection
3. Test with a single job using the test script
4. Adjust batch size and rate limiting if needed
