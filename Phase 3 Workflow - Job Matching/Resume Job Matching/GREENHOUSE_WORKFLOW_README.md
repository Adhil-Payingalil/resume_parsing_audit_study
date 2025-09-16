# Greenhouse Resume-Job Matching Workflow

This module provides a specialized workflow for matching resumes with job postings from the Greenhouse collection (`Job_postings_greenhouse`) in MongoDB. It's designed as a separate process from the main resume-job matching workflow to maintain data separation and allow independent processing.

## Overview

The Greenhouse workflow follows the same architecture as the main workflow but with key differences:

- **Source Collection**: Uses `Job_postings_greenhouse` instead of `job_postings`
- **Filtering**: Only processes jobs with `jd_extraction=True` and valid `jd_embedding`
- **Output Collections**: Uses separate collections for results:
  - `greenhouse_resume_job_matches` - for successful matches
  - `greenhouse_unmatched_job_postings` - for jobs with no valid matches

## Files

### Core Files
- `greenhouse_resume_job_matching_workflow.py` - Main workflow implementation
- `greenhouse_config.py` - Configuration specific to Greenhouse workflow
- `test_greenhouse_workflow.py` - Test script for the workflow

## Features

### Job Filtering
- Only processes jobs where `jd_extraction=True`
- Requires valid `jd_embedding` field
- Supports industry prefix filtering
- Handles duplicate processing prevention

### Two-Stage Filtering
1. **Industry Filtering**: Fast pre-filtering by industry prefix
2. **Vector Search**: Semantic similarity search on filtered resumes

### LLM Validation
- Validates and ranks multiple resume candidates
- Uses Gemini 2.5 Flash model
- Configurable validation threshold
- Detailed reasoning for each candidate

### Performance Optimizations
- Resume caching to avoid repeated database queries
- Batch processing with parallel execution
- Memory management for large-scale processing
- Checkpointing for resumability

## Configuration

### Basic Usage
```python
from greenhouse_resume_job_matching_workflow import GreenhouseResumeJobMatchingWorkflow
from greenhouse_config import default_greenhouse_config

# Use default configuration
with GreenhouseResumeJobMatchingWorkflow() as workflow:
    results = workflow.run_workflow(max_jobs=100)
```

### Custom Configuration
```python
from greenhouse_config import GreenhouseConfig

# Custom configuration
config = GreenhouseConfig(
    industry_prefixes=["ITC", "CCC"],
    max_jobs=50,
    batch_size=10,
    similarity_threshold=0.35,
    validation_threshold=75
)

with GreenhouseResumeJobMatchingWorkflow(config=config) as workflow:
    results = workflow.run_workflow()
```

## Configuration Options

### Database Settings
- `db_name`: Database name (default: "Resume_study")
- `collections`: Collection names for jobs, resumes, matches, and unmatched

### Filtering Options
- `industry_prefixes`: List of industry prefixes to filter resumes
- `search_terms`: List of search terms (may not apply to Greenhouse jobs)
- `max_jobs`: Maximum number of jobs to process (None = all)

### Matching Parameters
- `top_k`: Number of top resumes to return from vector search
- `similarity_threshold`: Minimum similarity score (0-1)
- `validation_threshold`: Minimum LLM validation score (0-100)

### Performance Settings
- `batch_size`: Number of jobs to process in parallel
- `max_workers`: Maximum number of worker threads
- `cache_ttl`: Resume cache time-to-live in seconds
- `checkpoint_interval`: Save checkpoint every N jobs
- `memory_limit_mb`: Memory limit for processing

### Processing Options
- `skip_processed_jobs`: Skip jobs already processed in previous runs
- `force_reprocess`: Force reprocessing of all jobs

## Usage Examples

### Basic Workflow Execution
```python
# Simple execution with default settings
with GreenhouseResumeJobMatchingWorkflow() as workflow:
    results = workflow.run_workflow()
    print(f"Processed {results['jobs_processed']} jobs")
    print(f"Found {results['total_valid_matches']} valid matches")
```

### Processing Statistics
```python
with GreenhouseResumeJobMatchingWorkflow() as workflow:
    stats = workflow.get_processing_statistics()
    print(f"Total jobs: {stats['total_jobs']}")
    print(f"Jobs with embeddings: {stats['jobs_with_embeddings']}")
    print(f"Processing progress: {stats['processing_progress']['percentage']:.1f}%")
```

### Single Job Processing
```python
with GreenhouseResumeJobMatchingWorkflow() as workflow:
    jobs = workflow.get_filtered_jobs(limit=1)
    if jobs:
        result = workflow.process_job(jobs[0])
        print(f"Job processing result: {result}")
```

## Testing

Run the test script to verify the workflow:

```bash
cd "Phase 3 Workflow - Job Matching/Resume Job Matching"
python test_greenhouse_workflow.py
```

The test script will:
1. Test single job processing
2. Run a small batch workflow
3. Display processing statistics
4. Show results summary

## Data Flow

1. **Job Retrieval**: Get jobs from `Job_postings_greenhouse` with `jd_extraction=True` and valid embeddings
2. **Industry Filtering**: Filter resumes by industry prefix for performance
3. **Vector Search**: Find semantically similar resumes using MongoDB vector search
4. **LLM Validation**: Validate and rank candidates using Gemini
5. **Result Storage**: Store matches in `greenhouse_resume_job_matches` or unmatched jobs in `greenhouse_unmatched_job_postings`

## Error Handling

- Comprehensive error logging at each stage
- Graceful handling of individual job failures
- Automatic retry logic for LLM calls
- Memory management for large-scale processing
- Checkpoint recovery for interrupted workflows

## Performance Considerations

- **Caching**: Resume data is cached to avoid repeated database queries
- **Batch Processing**: Jobs are processed in configurable batches
- **Parallel Processing**: Multiple jobs can be processed simultaneously
- **Memory Management**: Automatic cache clearing when memory usage is high
- **Vector Search Optimization**: Two-stage filtering reduces vector search scope

## Monitoring and Logging

The workflow provides detailed logging for:
- Processing progress and statistics
- Performance metrics (search times, validation times)
- Error conditions and recovery
- Cache hit/miss ratios
- Memory usage monitoring

## Differences from Main Workflow

| Aspect | Main Workflow | Greenhouse Workflow |
|--------|---------------|-------------------|
| Job Collection | `job_postings` | `Job_postings_greenhouse` |
| Job Filter | Standard fields | `jd_extraction=True` + `jd_embedding` |
| Matches Collection | `resume_job_matches` | `greenhouse_resume_job_matches` |
| Unmatched Collection | `unmatched_job_postings` | `greenhouse_unmatched_job_postings` |
| Job Description Field | `description` | `job_description` |
| Checkpoint Type | Standard | `workflow_type: "greenhouse"` |

## Troubleshooting

### Common Issues

1. **No Jobs Found**
   - Verify `jd_extraction=True` jobs exist in `Job_postings_greenhouse`
   - Check that jobs have valid `jd_embedding` fields
   - Ensure proper MongoDB connection

2. **No Resume Matches**
   - Verify industry prefix filtering
   - Check vector search index exists
   - Adjust similarity threshold if too high

3. **LLM Validation Errors**
   - Check Gemini API key configuration
   - Verify model availability
   - Review validation threshold settings

4. **Memory Issues**
   - Reduce batch size
   - Lower cache TTL
   - Increase memory limit

### Debug Mode

Enable detailed logging by setting the log level:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Future Enhancements

- Support for additional job posting platforms
- Enhanced filtering options
- Real-time processing capabilities
- Advanced performance metrics
- Integration with job scraping workflows
