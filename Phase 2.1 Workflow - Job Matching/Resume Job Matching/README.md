# Resume-to-Job Matching Workflow

This module provides a comprehensive workflow for matching resumes to job postings using a two-stage approach: vector search followed by LLM validation.

## Overview

The workflow consists of three main components:

1. **Vector Search**: Uses embeddings to find semantically similar resumes for each job posting
2. **LLM Validation**: Uses Gemini Pro to validate the quality of matches and assign scores
3. **Data Storage**: Stores validated matches and unmatched jobs in separate collections

## Architecture

### Collections

#### `resume_job_matches`
Stores validated matches between resumes and job postings:

```json
{
  "_id": ObjectId,
  "job_posting_id": ObjectId,           // Reference to job_postings
  "resume_id": ObjectId,                // Reference to Standardized_resume_data
  "job_url_direct": string,             // Direct application URL
  "job_title": string,                  // Job title
  "company_name": string,               // Company name
  "job_description_raw": string,        // Full job description
  "file_id": string,                    // Original resume file ID
  "resume_data": object,                // Full resume_data JSON
  "key_metrics": object,                // Full key_metrics JSON
  "semantic_similarity": float,         // Vector similarity score (0-1)
  "match_score": float,                 // LLM-generated score (0-100)
  "match_reasoning": string,            // LLM explanation
  "match_status": string,               // "PENDING", "VALIDATED", "REJECTED"
  "created_at": DateTime,               // When match was created
  "validated_at": DateTime              // When LLM validation completed
}
```

#### `unmatched_job_postings`
Stores jobs that couldn't be matched with any resume:

```json
{
  "_id": ObjectId,
  "job_posting_id": ObjectId,           // Reference to original job_postings
  "job_url_direct": string,             // Direct application URL
  "job_title": string,                  // Job title
  "company_name": string,               // Company name
  "job_description_raw": string,        // Full job description
  "rejection_reason": string,           // Primary reason for no match
  "top_similarity_score": float,        // Best similarity score found
  "created_at": DateTime,               // When moved to unmatched collection
  "scraped_at": DateTime                // When originally scraped
}
```

## Components

### 1. ResumeJobMatcher (`resume_job_matcher.py`)

Main class that handles the core matching logic:

- **Vector Search**: Finds top 3-4 semantically similar resumes for each job
- **LLM Validation**: Uses Gemini Pro to validate match quality
- **Data Storage**: Stores results in MongoDB collections
- **Statistics**: Provides workflow statistics and monitoring

### 2. Test Suite (`test_resume_job_matching.py`)

Comprehensive test suite for validating the workflow:

- Database connection testing
- Vector search functionality
- LLM validation testing
- Single and batch job processing
- Error handling validation

### 3. Workflow Runner (`run_matching_workflow.py`)

Main execution script with multiple modes:

- **Batch Mode**: Process multiple jobs in batches
- **Single Mode**: Process a specific job by ID
- **Status Mode**: Check current workflow status

## Usage

### Prerequisites

1. **Environment Setup**: Ensure your virtual environment is activated
2. **MongoDB**: Database must be running and accessible
3. **Gemini API**: API key must be configured in environment variables
4. **Data**: Both `job_postings` and `Standardized_resume_data` collections must have embeddings

### Running Tests

```bash
# Activate virtual environment
cd "Phase 2.1 Workflow - Job Matching/Resume Job Matching"
python test_resume_job_matching.py
```

### Running the Workflow

#### Batch Processing (Default)
```bash
# Process all pending jobs in batches of 10
python run_matching_workflow.py

# Process with custom parameters
python run_matching_workflow.py --batch-size 5 --max-jobs 50 --delay 2.0
```

#### Single Job Processing
```bash
# Process a specific job by ID
python run_matching_workflow.py --mode single --job-id "507f1f77bcf86cd799439011"
```

#### Status Check
```bash
# Check current workflow status
python run_matching_workflow.py --mode status
```

### Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--mode` | Mode: batch, single, or status | batch |
| `--batch-size` | Jobs per batch | 10 |
| `--max-jobs` | Maximum total jobs to process | None (all) |
| `--delay` | Delay between jobs (seconds) | 1.0 |
| `--job-id` | Specific job ID (single mode) | None |
| `--db-name` | MongoDB database name | Resume_study |

## Workflow Process

### 1. Job Discovery
- Queries `job_postings` collection for jobs without existing matches
- Filters for jobs with embeddings
- Returns jobs in batches for processing

### 2. Vector Search
- For each job, calculates cosine similarity with all resumes
- Returns top 3-4 most similar resumes
- Applies similarity threshold (default: 0.3)

### 3. LLM Validation
- Uses Gemini Pro to evaluate each potential match
- Generates match score (0-100) and reasoning
- Validates match quality (score ≥ 70 considered valid)

### 4. Data Storage
- **Valid Matches**: Stored in `resume_job_matches` collection
- **Unmatched Jobs**: Stored in `unmatched_job_postings` collection
- **Statistics**: Updated for monitoring and analysis

## Configuration

### Similarity Threshold
Adjust the similarity threshold in `resume_job_matcher.py`:

```python
# Only validate if similarity is above threshold
if similarity_score >= 0.3:  # Adjustable threshold
```

### LLM Validation Threshold
Adjust the validation threshold in the prompt:

```python
"is_valid": <true if score >= 70, false otherwise>
```

### Batch Processing
Configure batch processing parameters:

```python
# In run_matching_workflow.py
batch_size: int = 10
delay_between_jobs: float = 1.0
```

## Monitoring and Statistics

### Get Statistics
```python
from resume_job_matcher import ResumeJobMatcher

matcher = ResumeJobMatcher()
stats = matcher.get_matching_statistics()
print(stats)
```

### Statistics Output
```json
{
  "jobs": {
    "total": 150,
    "with_embeddings": 145,
    "without_embeddings": 5
  },
  "resumes": {
    "total": 200,
    "with_embeddings": 195,
    "without_embeddings": 5
  },
  "matches": {
    "total": 45,
    "validated": 42,
    "unmatched_jobs": 23
  }
}
```

## Error Handling

The workflow includes comprehensive error handling:

- **Database Connection**: Graceful handling of connection failures
- **API Rate Limiting**: Built-in delays between API calls
- **Invalid Data**: Skips jobs/resumes without embeddings
- **LLM Failures**: Continues processing even if validation fails
- **Logging**: Detailed logging for debugging and monitoring

## Performance Considerations

### Optimization Tips

1. **Batch Size**: Adjust based on your system's capacity
2. **API Delays**: Increase delays if hitting rate limits
3. **Similarity Threshold**: Higher thresholds reduce LLM calls
4. **Indexing**: Ensure proper MongoDB indexes are created

### Expected Performance

- **Vector Search**: ~1-2 seconds per job
- **LLM Validation**: ~3-5 seconds per match
- **Overall**: ~10-20 jobs per minute (depending on configuration)

## Integration

### With Job Scraping
The workflow integrates with your existing job scraping pipeline:

1. Jobs are scraped and stored in `job_postings`
2. Embeddings are generated for new jobs
3. Matching workflow processes pending jobs
4. Results are stored for application generation

### With Resume Processing
The workflow uses your existing resume data:

1. Resumes are processed and stored in `Standardized_resume_data`
2. Embeddings are generated for resumes
3. Matching workflow finds relevant jobs
4. Matches are stored for experimental design

## Troubleshooting

### Common Issues

1. **No Pending Jobs**: Check if jobs have embeddings
2. **No Valid Matches**: Adjust similarity or validation thresholds
3. **API Errors**: Check Gemini API key and rate limits
4. **Database Errors**: Verify MongoDB connection and permissions

### Debug Mode
Enable detailed logging by modifying the logger configuration in `utils.py`.

## Future Enhancements

1. **Async Processing**: Implement async/await for better performance
2. **Advanced Filtering**: Add industry/skill-based filtering
3. **Batch API**: Use Gemini Batch API for cost optimization
4. **Caching**: Implement embedding and validation result caching
5. **Monitoring Dashboard**: Web-based monitoring interface 