# Greenhouse Job Embedding Workflow

This directory contains optimized scripts for generating vector embeddings for job postings in the `Job_postings_greenhouse` collection.

## Overview

The greenhouse job embedding workflow processes job postings where `jd_extraction=True` and generates vector embeddings for semantic search and matching capabilities. The new implementation includes significant performance optimizations through parallel processing.

## Files

- `greenhouse_job_embedding.py` - Main embedding script with parallel processing
- `test_greenhouse_performance.py` - Performance testing script
- `batch_job_embedding.py` - Original sequential embedding script (for comparison)
- `GREENHOUSE_EMBEDDING_README.md` - This documentation

## Performance Improvements

### Key Optimizations

1. **Concurrent Processing**: Uses `asyncio` and `aiohttp` for parallel API calls
2. **Connection Pooling**: Reuses HTTP connections for better performance
3. **Retry Logic**: Implements exponential backoff for failed requests
4. **Rate Limiting**: Smart handling of API rate limits
5. **Error Recovery**: Robust error handling and recovery mechanisms

### Expected Performance Gains

- **3-5x faster** processing compared to sequential approach
- **Better resource utilization** through concurrent processing
- **Improved reliability** with retry logic and error handling
- **Scalable** to handle large datasets efficiently

## Usage

### Basic Usage

```bash
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Run with default parallel processing
python greenhouse_job_embedding.py

# Run with custom concurrency level
python greenhouse_job_embedding.py --concurrent 10
```

### Command Line Options

- `--concurrent N`: Number of concurrent requests (default: 5)

### Performance Testing

```bash
# Run performance test
python test_greenhouse_performance.py
```

## Collection Structure

The script processes documents from `Job_postings_greenhouse` collection with the following structure:

```json
{
  "_id": ObjectId,
  "title": "Job Title",
  "company": "Company Name", 
  "location": "Job Location",
  "job_description": "Full job description text",
  "jd_extraction": true,
  "jd_embedding": [vector_embedding],  // Added by script
  "embedding_generated_at": datetime,  // Added by script
  "embedding_model": "embedding-001",  // Added by script
  "embedding_task_type": "RETRIEVAL_QUERY"  // Added by script
}
```

## Content Extraction

The script extracts key content from job postings for embedding generation:

1. **Job Title**: Primary job title
2. **Key Sections**: Requirements, qualifications, skills, responsibilities from job description
3. **Full Description**: Complete job description (truncated to 8000 chars)

## Error Handling

### Retry Logic
- **Max Retries**: 3 attempts per request
- **Exponential Backoff**: 1s, 2s, 4s delays
- **Rate Limit Handling**: Automatic retry on 429 responses

### Error Recovery
- **Individual Job Failures**: Continue processing other jobs
- **Batch Failures**: Log errors and continue with next batch
- **Connection Issues**: Automatic reconnection and retry

## Monitoring and Logging

### Progress Tracking
- Real-time progress updates
- Processing rate monitoring
- Success/failure statistics
- Performance metrics

### Log Levels
- **INFO**: General progress and statistics
- **WARNING**: Non-critical issues (rate limits, retries)
- **ERROR**: Critical failures and exceptions

## Configuration

### Environment Variables
- `GEMINI_API_KEY`: Required for embedding generation
- `MONGODB_URI`: MongoDB connection string

### Processing Parameters
- **Max Concurrent**: 5 (adjustable via command line)
- **Batch Size**: 10 jobs per batch
- **Timeout**: 60 seconds per request
- **Rate Limiting**: 1 second between batches

## Troubleshooting

### Common Issues

1. **Rate Limiting**
   - Solution: Reduce `--concurrent` parameter
   - Monitor: Check logs for 429 errors

2. **Memory Issues**
   - Solution: Process smaller batches
   - Monitor: System memory usage

3. **Connection Timeouts**
   - Solution: Check network connectivity
   - Monitor: API response times

4. **MongoDB Connection**
   - Solution: Verify `MONGODB_URI` environment variable
   - Monitor: Connection logs

### Debug Mode

Enable detailed logging by setting log level to DEBUG in your logging configuration.

## Performance Benchmarks

### Test Results (5 jobs sample)
- **Parallel Processing (3 concurrent)**: ~0.7 seconds
- **Processing rate**: ~7 jobs/second
- **Success rate**: 100%

### Scaling Expectations
- **10 jobs**: ~1-2 seconds
- **100 jobs**: ~15-20 seconds  
- **1000 jobs**: ~2-3 minutes
- **227 jobs (full dataset)**: ~30-45 seconds

## Best Practices

1. **Start Small**: Test with a small batch first
2. **Monitor Resources**: Watch CPU and memory usage
3. **Adjust Concurrency**: Find optimal concurrent request level
4. **Regular Backups**: Backup MongoDB before large operations
5. **Error Monitoring**: Check logs for any persistent issues

## Future Enhancements

1. **True Batch API**: Implement native batch embedding API calls
2. **Progress Persistence**: Save progress for resumable processing
3. **Dynamic Scaling**: Auto-adjust concurrency based on performance
4. **Caching Layer**: Implement Redis caching for better performance
5. **Metrics Dashboard**: Real-time processing metrics and monitoring

## Support

For issues or questions:
1. Check the logs for error details
2. Verify environment variables are set correctly
3. Test with a small batch first
4. Review the troubleshooting section above
